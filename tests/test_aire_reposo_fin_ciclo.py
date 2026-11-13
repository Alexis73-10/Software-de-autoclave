# 12-nov (Cristian): fin de ciclo con las puertas confirmadas cerradas, el aire
# atmosférico queda abierto en banda, en vacío y sin lectura; solo la
# sobrepresión (lectura vigente sobre atm + rango_presion_atm) lo cierra.
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.states import ciclo as ciclo_mod
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado
from autoclave.state_machine.states.control_banda import aire_reposo
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo

ATM, RANGO = 75.0, 5.0
_CONFIG = {"presion_admosferica": ATM, "rango_presion_atm": RANGO}


# ---------------------------------------------------------------- regla pura
@pytest.mark.parametrize("pres", [ATM, ATM + RANGO, ATM - RANGO, 40.0, None, float("nan")])
def test_regla_abierto_salvo_sobrepresion(pres):
    assert aire_reposo(pres, True, _CONFIG, True) is True


def test_regla_sobrepresion_cierra():
    assert aire_reposo(ATM + RANGO + 0.1, True, _CONFIG, True) is False


def test_regla_trama_ai_vencida_abierto_aunque_lea_sobrepresion():
    assert aire_reposo(ATM + RANGO + 30, False, _CONFIG, True) is True


@pytest.mark.parametrize("puertas", [False, None])
def test_regla_no_aplica_sin_puertas_cerradas(puertas):
    assert aire_reposo(ATM, True, _CONFIG, puertas) is None


@pytest.mark.parametrize("config", [{}, {"presion_admosferica": ATM},
                                    {"presion_admosferica": 0, "rango_presion_atm": 5},
                                    {"presion_admosferica": True, "rango_presion_atm": 5}])
def test_regla_no_aplica_sin_referencia_atmosferica(config):
    assert aire_reposo(ATM, True, config, True) is None


# ------------------------------------------------- espera tras COMPLETADO
def _ciclo_completado(monkeypatch, pres, puertas=True):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 25.0}
    estado.sensores_pres = {"pres_camara": pres}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: _CONFIG.get(k, d)
    ciclo = CicloState(estado, set_do, cycle, config, MagicMock())
    ciclo.reset()
    # reset() puede copiar el programa: el modo se fija en el que queda
    ciclo.cycle.get_param.side_effect = (
        lambda *a, default=None: 1 if a == ("descompresion", "modo") else default)
    monkeypatch.setattr(ciclo_mod, "puertas_confirmadas_cerradas", lambda *a: puertas)
    monkeypatch.setattr(ciclo_mod.vigencia_ai, "leer", lambda e: (True, 1))
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    return ciclo, set_do


def test_completado_en_banda_aire_abierto_y_escape_del_modo(monkeypatch):
    ciclo, set_do = _ciclo_completado(monkeypatch, ATM)
    ciclo._mantener_valvula_reposo()
    set_do.aire_admosferico_camara_on.assert_called()
    set_do.aire_admosferico_camara_off.assert_not_called()
    set_do.descompresion_rapida_on.assert_called()          # escape sigue abierto


def test_completado_sobrepresion_cierra_el_aire(monkeypatch):
    ciclo, set_do = _ciclo_completado(monkeypatch, ATM + RANGO + 1)
    ciclo._mantener_valvula_reposo()
    set_do.aire_admosferico_camara_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_called()


def test_completado_sin_lectura_aire_abierto(monkeypatch):
    ciclo, set_do = _ciclo_completado(monkeypatch, None)
    ciclo._mantener_valvula_reposo()
    set_do.aire_admosferico_camara_on.assert_called()


def test_completado_puerta_abierta_como_antes(monkeypatch):
    ciclo, set_do = _ciclo_completado(monkeypatch, ATM, puertas=False)
    ciclo._mantener_valvula_reposo()
    set_do.aire_admosferico_camara_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


# ------------------------------------------- protocolo de fallo / cancelado
def _protocolo(di, vigentes=True, ai=True):
    estado = MagicMock()
    estado.sensores_di = di
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: _CONFIG.get(k, d)
    p = ProtocoloFallo(estado, MagicMock(), MagicMock(), config)
    p.profile = None                       # 2 puertas por defecto
    p.di_vigentes = vigentes
    p._ai_vigente_tick = ai
    return p


def test_protocolo_regla_con_puertas_cerradas():
    p = _protocolo({"puerta_1_cerrada": 1, "puerta_2_cerrada": 1})
    assert p._regla_aire_reposo(ATM) is True
    assert p._regla_aire_reposo(None) is True
    assert p._regla_aire_reposo(ATM + RANGO + 1) is False


def test_protocolo_regla_no_aplica_con_puerta_abierta_o_di_no_vigentes():
    assert _protocolo({"puerta_1_cerrada": 0, "puerta_2_cerrada": 1})._regla_aire_reposo(ATM) is None
    assert _protocolo({"puerta_1_cerrada": 1, "puerta_2_cerrada": 1},
                      vigentes=False)._regla_aire_reposo(ATM) is None


def test_protocolo_sin_di_vigentes_por_defecto():
    """Sin que CicloState la fije, la regla no aplica (lógica anterior)."""
    estado = MagicMock()
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1}
    p = ProtocoloFallo(estado, MagicMock(), MagicMock(), MagicMock())
    assert p.di_vigentes is False
