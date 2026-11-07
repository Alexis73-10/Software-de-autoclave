"""Tanda 32 (LIQ-01/LIQ-02/LIQ-03): integración de EnfriamientoContrapresion
en la fase DESCOMPRESION (modos 4 y 5)."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CIC_22, CIC_23, CIC_24, CIC_25
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloState

ATM = 101.3


class Reloj:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(time, "monotonic", r)
    return r


def _fase(modo=4, pres=150.0, pchq=300.0, temp=100.0, extra=None, alarmas=None):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres, "pres_chaqueta": pchq}
    estado.sensores_temp = {"temp_camara": temp}
    estado.avisos_ciclo = []
    config = MagicMock()
    config.get.side_effect = lambda k, *a: {"presion_admosferica": ATM,
                                            "rango_presion_atm": 20.0}.get(k)
    params = {
        ("descompresion", "modo"): modo,
        ("descompresion", "tiempo_pre_despresurizacion"): 0,
        ("descompresion", "presion_fin_descompresion"): 10,
    }
    for m in (4, 5):
        params.update({
            ("descompresion", f"modo_{m}", "presion_camara_enfriamiento"): 200,
            ("descompresion", f"modo_{m}", "temperatura_enfriamiento"): 80.0,
            ("descompresion", f"modo_{m}", "timeout"): 120,
            ("descompresion", f"modo_{m}", "presion_despresurizacion_chaqueta"): 20,
            ("descompresion", f"modo_{m}", "timeout_despresurizacion_chaqueta"): 3,
            ("descompresion", f"modo_{m}", "timeout_presurizacion_enfriamiento"): 3,
        })
    params[("descompresion", "modo_5", "descompresion_lenta_rapida")] = False
    params[("descompresion", "modo_5", "presion_cambio")] = 150
    params.update(extra or {})
    cycle = MagicMock()
    cycle.sensores = None
    cycle.get_param.side_effect = lambda *k, default=None: params.get(k, default)
    set_do = MagicMock()
    fase = DescompresionFase(estado, set_do, cycle, config,
                             alarm_manager=alarmas, cap=MagicMock())
    fase.reset()
    assert fase.update() == FaseResult.EN_CURSO      # entrada: _apagar_todo()
    set_do.reset_mock()
    return fase, estado, set_do


def _llamadas(set_do):
    return [c[0] for c in set_do.method_calls]


def _activas(am):
    return {i.codigo for i in am.activas()}


# ── LIQ-01: orden de salidas ─────────────────────────────────────────────

def test_orden_aire_chaqueta_y_agua_solo_con_a_y_b(reloj):
    fase, estado, set_do = _fase(pres=150.0, pchq=300.0)
    fase.update()
    llamadas = _llamadas(set_do)
    assert "aire_comprimido_camara_on" in llamadas
    assert "descompresion_chaqueta_on" in llamadas
    assert "agua_chaqueta_on" not in llamadas
    # (b) sola: sigue sin agua
    estado.sensores_pres["pres_chaqueta"] = ATM + 20
    set_do.reset_mock()
    reloj.t += 1
    fase.update()
    assert "agua_chaqueta_on" not in _llamadas(set_do)
    # (a) y (b): agua abierta y queda abierta (enclavadas)
    estado.sensores_pres["pres_camara"] = 200.0
    set_do.reset_mock()
    reloj.t += 1
    fase.update()
    assert "agua_chaqueta_on" in _llamadas(set_do)
    estado.sensores_pres["pres_chaqueta"] = 250.0
    set_do.reset_mock()
    reloj.t += 1
    fase.update()
    assert "agua_chaqueta_on" in _llamadas(set_do)
    assert "descompresion_chaqueta_off" not in _llamadas(set_do)


def test_agua_no_abre_solo_con_a(reloj):
    fase, estado, set_do = _fase(pres=200.0, pchq=300.0)
    for _ in range(5):
        reloj.t += 1
        fase.update()
    assert "agua_chaqueta_on" not in _llamadas(set_do)
    assert "agua_chaqueta_off" in _llamadas(set_do)


def test_modo_5_lenta_abierta_desde_el_primer_tick(reloj):
    fase, estado, set_do = _fase(modo=5)
    fase.update()
    assert "descompresion_lenta_on" in _llamadas(set_do)


def test_modo_4_no_toca_la_lenta_en_el_enfriamiento(reloj):
    fase, estado, set_do = _fase(modo=4)
    fase.update()
    assert "descompresion_lenta_on" not in _llamadas(set_do)


def test_ai_vencida_sin_aire_y_sin_contar_condiciones(reloj):
    fase, estado, set_do = _fase(pres=200.0, pchq=ATM)
    estado.lectura_ai = lambda: (False, None)
    vars(estado)["lectura_ai"] = estado.lectura_ai
    fase.update()
    assert "aire_comprimido_camara_on" not in _llamadas(set_do)
    assert "agua_chaqueta_on" not in _llamadas(set_do)


def test_chaqueta_en_enfriamiento_mantiene_vapor_de_chaqueta_apagado(reloj):
    fase, estado, set_do = _fase()
    fase.update()
    assert fase.chaqueta_en_enfriamiento is True
    assert fase.en_enfriamiento_con_contrapresion is True


# ── LIQ-01: topes → FALLO con código propio ──────────────────────────────

def test_tope_despresurizacion_chaqueta_falla_con_cic_22(reloj):
    fase, estado, set_do = _fase(pres=200.0, pchq=300.0)
    fase.update()
    reloj.t += 3 * 60 + 1
    set_do.reset_mock()
    assert fase.update() == FaseResult.FALLO
    codigo, valores = fase.alarma_fallo
    assert codigo == CIC_22
    assert valores["maximo"] == pytest.approx(ATM + 20) and valores["modo"] == 4
    llamadas = _llamadas(set_do)
    for salida in ("aire_comprimido_camara_off", "agua_chaqueta_off",
                   "descompresion_chaqueta_off"):
        assert salida in llamadas
    assert "agua_chaqueta_on" not in llamadas


def test_tope_presurizacion_falla_con_cic_23(reloj):
    fase, estado, set_do = _fase(modo=5, pres=150.0, pchq=ATM)
    fase.update()
    reloj.t += 3 * 60 + 1
    assert fase.update() == FaseResult.FALLO
    codigo, valores = fase.alarma_fallo
    assert codigo == CIC_23 and valores["objetivo"] == 200 and valores["modo"] == 5


def _armar(fase, estado, reloj):
    estado.sensores_pres.update({"pres_camara": 200.0, "pres_chaqueta": ATM})
    reloj.t += 1
    fase.update()


def test_aviso_contrapresion_no_bloqueante_y_se_despeja(reloj):
    am = AlarmManager()
    fase, estado, set_do = _fase(alarmas=am)
    _armar(fase, estado, reloj)              # T=100 °C → P_min ≈ 131,4 kPa
    estado.sensores_pres["pres_camara"] = 120.0
    reloj.t += 1
    fase.update()
    reloj.t += 10
    assert fase.update() == FaseResult.EN_CURSO
    assert CIC_25 in _activas(am)
    assert am.obtener(CIC_25).definicion.bloquea_inicio is False
    assert [a["clave"] for a in estado.avisos_ciclo] == ["ticket_ciclo.aviso_contrapresion"]
    estado.sensores_pres["pres_camara"] = 200.0
    reloj.t += 1
    fase.update()
    assert CIC_25 not in _activas(am)


def test_contrapresion_baja_sostenida_falla_con_cic_24(reloj):
    am = AlarmManager()
    fase, estado, set_do = _fase(alarmas=am)
    _armar(fase, estado, reloj)
    estado.sensores_pres["pres_camara"] = 120.0
    reloj.t += 1
    fase.update()
    reloj.t += 30
    fase.update()
    reloj.t += 30
    assert fase.update() == FaseResult.FALLO
    assert fase.alarma_fallo[0] == CIC_24
    assert CIC_25 not in _activas(am)        # el aviso se resuelve con el fallo


def test_ciclo_registra_la_alarma_propia_de_la_fase():
    am = AlarmManager()
    estado = MagicMock()
    fake = SimpleNamespace(alarm_manager=am, estado=estado)
    fake._registrar_fallo = lambda *a, **k: CicloState._registrar_fallo(fake, *a, **k)
    for codigo in (CIC_22, CIC_23, CIC_24):
        assert codigo in modulo_ciclo._ALARMAS_PROPIAS_FASE
    fase = SimpleNamespace(alarma_fallo=(CIC_22, {"maximo": 121.3, "margen": "20",
                                                   "minutos": "3", "modo": 4}))
    CicloState._registrar_fallo_de_fase(fake, "DESCOMPRESION", fase)
    assert estado.codigo_fallo == CIC_22
    assert CIC_22 in _activas(am)
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    assert CATALOGO[CIC_22].bloquea_inicio is True


def test_timeout_del_modo_resuelve_el_aviso(reloj):
    am = AlarmManager()
    fase, estado, set_do = _fase(alarmas=am)
    _armar(fase, estado, reloj)
    estado.sensores_pres["pres_camara"] = 120.0
    fase.update()
    reloj.t += 11
    fase.update()
    assert CIC_25 in _activas(am)
    fase._t_timeout = time.monotonic() - 1
    assert fase.update() == FaseResult.FALLO
    assert CIC_25 not in _activas(am)


# ── fin del enfriamiento y LIQ-03 ────────────────────────────────────────

def _enfriar(fase, estado, reloj):
    estado.sensores_temp["temp_camara"] = 79.0
    for _ in range(3):
        reloj.t += 1
        fase.update()
    assert fase._sub_etapa == "descompresion"


def test_modo_4_sin_cambio_al_terminar_el_enfriamiento(reloj):
    fase, estado, set_do = _fase(modo=4, extra={
        ("descompresion", "modo_5", "descompresion_lenta_rapida"): True})
    fase.update()
    set_do.reset_mock()
    _enfriar(fase, estado, reloj)
    llamadas = _llamadas(set_do)
    assert "descompresion_rapida_on" in llamadas
    assert "agua_chaqueta_off" in llamadas and "aire_comprimido_camara_off" in llamadas


def test_liq03_inactiva_modo_5_igual_que_hoy(reloj):
    fase, estado, set_do = _fase(modo=5)
    fase.update()
    set_do.reset_mock()
    _enfriar(fase, estado, reloj)
    llamadas = _llamadas(set_do)
    assert "descompresion_lenta_off" in llamadas
    assert "descompresion_rapida_on" in llamadas


def test_liq03_activa_lenta_hasta_presion_cambio_y_luego_rapida(reloj):
    fase, estado, set_do = _fase(modo=5, pres=200.0, extra={
        ("descompresion", "modo_5", "descompresion_lenta_rapida"): True})
    fase.update()
    set_do.reset_mock()
    _enfriar(fase, estado, reloj)
    assert "descompresion_rapida_on" not in _llamadas(set_do)
    estado.sensores_pres["pres_camara"] = 160.0
    set_do.reset_mock()
    fase.update()
    llamadas = _llamadas(set_do)
    assert "descompresion_lenta_on" in llamadas and "descompresion_chaqueta_on" in llamadas
    assert "descompresion_rapida_on" not in llamadas
    # sin lectura de presión no se cambia a la rápida
    estado.sensores_pres["pres_camara"] = None
    set_do.reset_mock()
    assert fase.update() == FaseResult.EN_CURSO
    assert "descompresion_rapida_on" not in _llamadas(set_do)
    # en presion_cambio: lenta OFF y rápida ON
    estado.sensores_pres["pres_camara"] = 150.0
    set_do.reset_mock()
    fase.update()
    llamadas = _llamadas(set_do)
    assert llamadas.index("descompresion_lenta_off") < llamadas.index("descompresion_rapida_on")
    # y sigue hasta el fin de siempre (atm + presion_fin_descompresion)
    estado.sensores_pres["pres_camara"] = 140.0
    assert fase.update() == FaseResult.EN_CURSO
    estado.sensores_pres["pres_camara"] = ATM + 5
    assert fase.update() == FaseResult.COMPLETADO


def test_transicion_resuelve_el_aviso(reloj):
    am = AlarmManager()
    fase, estado, set_do = _fase(alarmas=am)
    _armar(fase, estado, reloj)
    estado.sensores_pres["pres_camara"] = 120.0
    fase.update()
    reloj.t += 11
    fase.update()
    assert CIC_25 in _activas(am)
    _enfriar(fase, estado, reloj)
    assert CIC_25 not in _activas(am)
