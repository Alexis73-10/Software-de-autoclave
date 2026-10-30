"""T5 (E3, tanda 2026-10-14 §1.2): protocolo de fallo con enfriamiento con
contrapresión en modos 4/5 (PF-19), carga líquida sin descompresión rápida
mientras esté caliente, presión desconocida = lenta sin escalar, y cierre de
todas las válvulas al terminar (PF-10)."""

from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
import autoclave.state_machine.cycle_phases.protocolo_fallo as modulo


def _protocolo(modo, pres=300.0, temp=120.0, tipo_carga="solido", t_enfr=80.0):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres}
    estado.sensores_temp = {"temp_camara": temp}
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {"presion_admosferica": 101.3,
                                                "rango_presion_atm": 10.0,
                                                "temp_max_apertura": 80.0}.get(k, d)
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.sensores = None

    def get_param(*args, default=None):
        tabla = {
            ("descompresion", "modo"): modo,
            ("globals", "tipo_carga"): tipo_carga,
            ("descompresion", f"modo_{modo}", "temperatura_enfriamiento"): t_enfr,
            ("descompresion", f"modo_{modo}", "presion_camara_enfriamiento"): 200,
            ("descompresion", f"modo_{modo}", "timeout"): 30,
        }
        return tabla.get(args, default)

    cycle.get_param.side_effect = get_param
    return ProtocoloFallo(estado, set_do, cycle, config), set_do, estado


@pytest.mark.parametrize("tipo_carga", ["solido", "liquido"])
@pytest.mark.parametrize("modo", [4, 5])
def test_modos_4_5_enfrian_antes_de_despresurizar(modo, tipo_carga):
    p, set_do, estado = _protocolo(modo, pres=150.0, temp=120.0, tipo_carga=tipo_carga)
    p.ejecutar()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_called()      # contrapresión (150 < 200)
    set_do.agua_chaqueta_on.assert_called()
    if modo == 5:
        set_do.descompresion_lenta_on.assert_called()


def test_modo_4_despresuriza_al_llegar_a_temperatura_de_enfriamiento():
    p, set_do, estado = _protocolo(4, pres=200.0, temp=120.0, tipo_carga="liquido")
    p.ejecutar()
    estado.sensores_temp["temp_camara"] = 79.0
    p.update()
    p.update()
    set_do.descompresion_rapida_on.assert_not_called()     # debounce: 2 lecturas
    p.update()
    set_do.agua_chaqueta_off.assert_called()
    set_do.descompresion_chaqueta_on.assert_called()
    set_do.descompresion_rapida_on.assert_called()


@pytest.mark.parametrize("modo", [1, 2, 3])
def test_liquido_nunca_usa_la_rapida_en_modos_1_2_3(modo):
    p, set_do, estado = _protocolo(modo, pres=300.0, temp=120.0, tipo_carga="liquido")
    p.ejecutar()
    for _ in range(3):
        p.update()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_called()


def test_solido_escala_a_rapida_tras_timeout(monkeypatch):
    p, set_do, estado = _protocolo(4, pres=300.0, temp=120.0)
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: reloj[0])
    p.ejecutar()
    set_do.descompresion_rapida_on.assert_not_called()
    reloj[0] += 31 * 60
    p.update()
    set_do.descompresion_rapida_on.assert_called()


def test_liquido_caliente_no_escala_tras_timeout(monkeypatch):
    p, set_do, estado = _protocolo(4, pres=300.0, temp=120.0, tipo_carga="liquido")
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: reloj[0])
    p.ejecutar()
    reloj[0] += 31 * 60
    p.update()
    p.update()
    set_do.descompresion_rapida_on.assert_not_called()


def test_presion_desconocida_abre_lenta_sin_escalar(monkeypatch):
    p, set_do, estado = _protocolo(1, pres=None)
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: reloj[0])
    p.ejecutar()
    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_finalizar_cierra_todas_las_valvulas():
    p, set_do, _ = _protocolo(4)
    p.ejecutar()
    p.finalizar()
    for salida in ("descompresion_rapida_off", "descompresion_lenta_off",
                   "descompresion_chaqueta_off", "aire_comprimido_camara_off",
                   "agua_chaqueta_off", "aire_admosferico_camara_off"):
        getattr(set_do, salida).assert_called()


def test_modo_0_se_trata_como_lenta_con_timeout_del_modo_2():
    p, set_do, _ = _protocolo(0, pres=300.0, tipo_carga="solido")
    p.ejecutar()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


# ── Válvula de reposo ───────────────────────────────────────────────────────

from autoclave.state_machine.cycle_phases.valvula_reposo import abrir_valvula_modo  # noqa: E402


@pytest.mark.parametrize("modo", [1, 2, 3, 4, 5])
def test_reposo_liquido_caliente_usa_lenta(modo):
    set_do = MagicMock()
    abrir_valvula_modo(set_do, modo, liquido=True, enfriada=False)
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_called_once()


def test_reposo_liquido_enfriado_modo_4_usa_chaqueta_y_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 4, liquido=True, enfriada=True)
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_chaqueta_on.assert_called_once()


def test_reposo_solido_sin_cambios():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 1)
    set_do.descompresion_rapida_on.assert_called_once()


# ── Correcciones de la revisión de seguridad de T5 ─────────────────────────

def test_sin_presurizar_al_disparo_no_aplica_contrapresion():
    # SAF-03: una cámara a presión atmosférica no se presuriza con aire
    p, set_do, _ = _protocolo(4, pres=101.3, temp=120.0, tipo_carga="liquido")
    p.ejecutar()
    p.update()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_principal_sin_lectura_lenta_sin_escalar_y_motivo(monkeypatch):
    # SAF-04
    p, set_do, estado = _protocolo(4, pres=300.0, temp=None)
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: reloj[0])
    p.ejecutar()
    reloj[0] += 31 * 60
    p.update()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_called()
    assert "Principal sin lectura" in p.bloqueado_motivo


def test_escalada_apaga_la_contrapresion(monkeypatch):
    # SAF-02 (a)
    p, set_do, _ = _protocolo(4, pres=150.0, temp=120.0)
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: reloj[0])
    p.ejecutar()
    set_do.aire_comprimido_camara_on.assert_called()
    reloj[0] += 31 * 60
    p.update()
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.agua_chaqueta_off.assert_called()
    set_do.descompresion_rapida_on.assert_called()


def test_sin_presion_en_enfriamiento_apaga_el_aire_comprimido():
    # SAF-02 (c)
    p, set_do, estado = _protocolo(4, pres=150.0, temp=120.0)
    p.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    p.update()
    set_do.aire_comprimido_camara_off.assert_called()


def test_tipo_carga_ilegible_se_trata_como_liquido():
    # SAF-12
    p, set_do, _ = _protocolo(1, pres=300.0)
    p.cycle.get_param.side_effect = RuntimeError("programa ilegible")
    assert p.es_liquido() is True


def test_liquido_escala_solo_con_enfriamiento_confirmado(monkeypatch):
    # Residuo de la verificación de T5: una lectura baja espuria no basta
    p, set_do, estado = _protocolo(1, pres=300.0, temp=120.0, tipo_carga="liquido")
    reloj = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: reloj[0])
    p.ejecutar()
    reloj[0] += 31 * 60
    estado.sensores_temp["temp_camara"] = 70.0       # una sola lectura baja
    p.update()
    set_do.descompresion_rapida_on.assert_not_called()
