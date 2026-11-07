"""Tanda 29: T29-02 (avisos de preparación fuera del ciclo y sostenidos),
T29-04 (rige la temperatura de apertura del programa) y T29-08 (aire
atmosférico abierto fuera de ciclo con las puertas confirmadas cerradas)."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.state_machine.alarms.catalogo import (PRE_01, PRE_02, PRE_03, PRE_04, PRE_05,
                                                     PRE_06)
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states import control_banda
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from tests.helpers.alarmas_helpers import codigos_activados, codigos_resueltos
from tests.test_adenda_estados import _make

ATM, RANGO = 101.3, 5.0


class _Reloj:
    def __init__(self, monkeypatch, t=1000.0):
        self.t = t
        monkeypatch.setattr(time, "monotonic", lambda: self.t)


def _cfg(extra=None):
    valores = {"presion_admosferica": ATM, "rango_presion_atm": RANGO,
               "tiempo_estable_alarma": 5, "temp_max_apertura": 80,
               "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
               "presion_empaque": 300}
    valores.update(extra or {})
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, *d: valores.get(k, d[0] if d else None)
    return cfg


def _preparado(pres=ATM, **di):
    obj, am, set_do = _make(preparado_state, None, pres_camara=pres, **di)
    obj.config = _cfg()
    obj._di_vigentes = True
    return obj, am, set_do


def _preparacion(pres=ATM, vigentes=True, **di):
    obj, am, set_do = _make(preparacion_state, None, pres_camara=pres, **di)
    obj.config = _cfg()
    obj.di_vigentes = vigentes
    return obj, am, set_do


# ── T29-08: aire atmosférico fuera de ciclo ─────────────────────────────────

def test_preparado_puertas_cerradas_presion_en_banda_aire_abierto():
    obj, _, set_do = _preparado()
    assert obj.mantener_presion_camara() is True
    set_do.aire_admosferico_camara_on.assert_called_once()
    set_do.aire_admosferico_camara_off.assert_not_called()


def test_preparado_puerta_abierta_comportamiento_anterior():
    obj, _, set_do = _preparado(puerta_2_cerrada=0)
    for _ in range(3):
        obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called_once()     # ConfirmadorApagado


def test_preparado_sin_dato_de_puerta_cuenta_como_abierta():
    obj, _, set_do = _preparado()
    del obj.estado.sensores_di["puerta_1_cerrada"]
    obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_preparado_di_no_vigentes_no_abre():
    obj, _, set_do = _preparado()
    obj._di_vigentes = False
    obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_preparado_run_toma_la_vigencia_del_tick():
    obj, _, set_do = _preparado()
    obj.run(datos_vigentes=False)
    set_do.aire_admosferico_camara_on.assert_not_called()
    obj.run(datos_vigentes=True)
    set_do.aire_admosferico_camara_on.assert_called()


@pytest.mark.parametrize("pres", [None, float("nan")])
def test_preparado_sin_lectura_cierra_el_aire_en_el_mismo_tick(pres):
    obj, _, set_do = _preparado()
    obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.reset_mock()
    obj.estado.sensores_pres["pres_camara"] = pres
    assert obj.mantener_presion_camara() is False
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_preparado_sobrepresion_cierra_el_aire_y_ventea():
    obj, _, set_do = _preparado()
    obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.reset_mock()
    obj.estado.sensores_pres["pres_camara"] = ATM + RANGO + 0.1
    obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()
    # venteo como antes (programa sólido de _make: rápida)
    assert (set_do.descompresion_rapida_on.called or set_do.descompresion_lenta_on.called)


def test_preparado_trama_ai_vencida_cierra_el_aire():
    obj, _, set_do = _preparado()
    obj.mantener_presion_camara()
    obj.estado.lectura_ai = lambda: (False, None)
    vars(obj.estado)["lectura_ai"] = obj.estado.lectura_ai
    set_do.aire_admosferico_camara_on.reset_mock()
    obj.mantener_presion_camara()
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_preparacion_puertas_cerradas_en_banda_aire_abierto():
    obj, _, set_do = _preparacion()
    assert obj.igualar_presion_camara() == (True, False)
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_preparacion_puerta_abierta_comportamiento_anterior():
    obj, _, set_do = _preparacion(puerta_1_cerrada=0)
    for _ in range(3):
        obj.igualar_presion_camara()
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_preparacion_sin_lectura_cierra_y_no_ordena_venteo():
    obj, _, set_do = _preparacion()
    obj.igualar_presion_camara()
    obj.estado.sensores_pres["pres_camara"] = None
    assert obj.igualar_presion_camara() == (False, None)
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_preparacion_sin_lectura_puerta_abierta_sin_orden_como_antes():
    obj, _, set_do = _preparacion(puerta_1_cerrada=0, pres=None)
    assert obj.igualar_presion_camara() == (False, None)
    set_do.aire_admosferico_camara_off.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_preparacion_sobrepresion_cierra_el_aire():
    obj, _, set_do = _preparacion(pres=ATM + RANGO + 1)
    assert obj.igualar_presion_camara() == (False, True)
    set_do.aire_admosferico_camara_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_preparacion_di_no_vigentes_no_abre():
    obj, _, set_do = _preparacion(vigentes=False)
    obj.igualar_presion_camara()
    set_do.aire_admosferico_camara_on.assert_not_called()


def _maquina(estado_inicial, pres=ATM, puertas=1):
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.state_machine.state_machine import StateMachine
    estado = EstadoAutoclave()
    for k in estado.sensores_di:
        estado.sensores_di[k] = 1
    estado.sensores_di["agua_camara"] = 0
    estado.sensores_di["puerta_1_cerrada"] = puertas
    estado.sensores_di["puerta_2_cerrada"] = puertas
    estado.sensores_pres["pres_camara"] = pres
    estado.set_machine_state(estado_inicial)
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.return_value = None
    sm = StateMachine(None, estado, set_do, cycle, _cfg(), alarm_manager=MagicMock())
    sm.prev_state = estado_inicial
    return sm, estado, set_do


def test_falla_con_puertas_cerradas_deja_el_aire_abierto():
    sm, _, set_do = _maquina(GlobalState.FALLA)
    sm.update(datos_vigentes=True)
    set_do.aire_admosferico_camara_on.assert_called()


def test_falla_con_di_no_vigentes_no_abre():
    sm, _, set_do = _maquina(GlobalState.FALLA)
    sm.update(datos_vigentes=False)
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_falla_sobrepresion_cierra_el_aire():
    sm, _, set_do = _maquina(GlobalState.FALLA, pres=ATM + RANGO + 2)
    sm.update(datos_vigentes=True)
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_entrar_a_ciclo_cierra_el_aire_y_resuelve_los_avisos_de_preparacion():
    sm, _, set_do = _maquina(GlobalState.PREPARADO)
    sm.ciclo.reset = MagicMock()
    sm.on_state_entry(GlobalState.CICLO)
    set_do.aire_admosferico_camara_off.assert_called_once()
    resueltos = codigos_resueltos(sm.alarm_manager)
    assert set(resueltos) >= {PRE_01, PRE_02, PRE_03, PRE_04, PRE_05, PRE_06}


def test_modo_prueba_no_corre_la_regla_del_aire():
    # T29-08 no aplica en modo prueba: el ControlLoop no corre la máquina de
    # estados (pausada) y el aire solo se mueve por orden manual
    from tests.test_control_loop_test_mode import _make_control_loop, _run_one_tick
    loop, mock_sm, _ = _make_control_loop()
    loop.enter_test_mode()
    _run_one_tick(loop)
    mock_sm.update.assert_not_called()
    loop.set_do.aire_admosferico_camara_on.assert_not_called()


def test_puertas_confirmadas_cerradas_falla_cerrada():
    est = SimpleNamespace(sensores_di={"puerta_1_cerrada": 1, "puerta_2_cerrada": 1})
    assert control_banda.puertas_confirmadas_cerradas(est, None, True) is True
    assert control_banda.puertas_confirmadas_cerradas(est, None, False) is False
    est.sensores_di["puerta_2_cerrada"] = None
    assert control_banda.puertas_confirmadas_cerradas(est, None, True) is False
    est.sensores_di["puerta_2_cerrada"] = True
    assert control_banda.puertas_confirmadas_cerradas(est, None, True) is True
    assert control_banda.puertas_confirmadas_cerradas(object(), None, True) is False


# ── T29-02: PRE-03/PRE-04 sostenidos fuera de ciclo ─────────────────────────

@pytest.mark.parametrize("pres, codigo", [(ATM - RANGO - 3, PRE_03), (ATM + RANGO + 3, PRE_04)])
def test_preparacion_aviso_solo_tras_tiempo_estable_seguido(monkeypatch, pres, codigo):
    reloj = _Reloj(monkeypatch)
    obj, am, _ = _preparacion(pres=pres)
    obj.igualar_presion_camara()
    reloj.t += 4.9
    obj.igualar_presion_camara()
    assert codigo not in codigos_activados(am)
    reloj.t += 0.2
    obj.igualar_presion_camara()
    assert codigo in codigos_activados(am)


def test_preparacion_un_tick_en_banda_reinicia_la_cuenta(monkeypatch):
    reloj = _Reloj(monkeypatch)
    obj, am, _ = _preparacion(pres=ATM - RANGO - 3)
    obj.igualar_presion_camara()
    reloj.t += 4.0
    obj.estado.sensores_pres["pres_camara"] = ATM
    obj.igualar_presion_camara()
    obj.estado.sensores_pres["pres_camara"] = ATM - RANGO - 3
    reloj.t += 0.5
    obj.igualar_presion_camara()
    reloj.t += 4.0
    obj.igualar_presion_camara()
    assert PRE_03 not in codigos_activados(am)


def test_preparado_temporizador_viejo_no_dispara_el_aviso(monkeypatch):
    # Antes, generar_alarma_temporizada compartía un temporizador que no se
    # reiniciaba: tras un ciclo el aviso salía en el primer tick
    reloj = _Reloj(monkeypatch)
    obj, am, _ = _preparado(pres=ATM + RANGO + 4)
    obj.timer_estabilidad = reloj.t - 3600
    obj.mantener_presion_camara()
    assert PRE_04 not in codigos_activados(am)
    reloj.t += 5.0
    obj.mantener_presion_camara()
    assert PRE_04 in codigos_activados(am)


def test_ciclo_no_activa_pre06_con_el_drenaje_caliente():
    from tests.test_ciclo_drenaje import _make_ciclo
    ciclo, set_do, am, _ = _make_ciclo(temp_drenaje=90.0, temp_segura=60.0)
    for _ in range(5):
        ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    am.activar.assert_not_called()


# ── T29-04: rige la temperatura de apertura del programa ────────────────────

@pytest.mark.parametrize("prog, equipo, esperado", [
    (100.0, 80, 100.0),       # el del programa aunque sea mayor
    (70.0, 80, 70.0),
    (None, 80, 80.0),         # sin programa, el del equipo
    ("x", 80, 80.0),
    (150.0, 80, camara_segura.TECHO_TEMP_MAX_APERTURA),
    (None, None, None),
])
def test_temp_max_vigente(prog, equipo, esperado):
    assert camara_segura.temp_max_vigente({"temp_max_apertura": equipo}, prog) == esperado


def _estado_camara(temp):
    return SimpleNamespace(sensores_pres={"pres_camara": ATM}, sensores_temp={"temp_camara": temp})


_CFG_CS = {"presion_admosferica": ATM, "rango_presion_atm": RANGO, "temp_max_apertura": 80}


def test_camara_segura_con_programa_mayor_rige_el_programa():
    segura, _ = camara_segura.evaluar(_estado_camara(90.0), _CFG_CS, None, temp_max_ciclo=100.0)
    assert segura is True


def test_camara_segura_con_programa_menor_rige_el_programa():
    segura, motivo = camara_segura.evaluar(_estado_camara(75.0), _CFG_CS, None, temp_max_ciclo=70.0)
    assert segura is False and motivo.codigo == "temp_alta"
    assert motivo.valores["temp_max"] == 70.0


def test_camara_segura_sin_programa_rige_el_equipo():
    segura, motivo = camara_segura.evaluar(_estado_camara(85.0), _CFG_CS, None)
    assert segura is False and motivo.valores["temp_max"] == 80.0


def test_motivos_usan_el_limite_del_programa():
    lista = camara_segura.motivos(_estado_camara(95.0), _CFG_CS, None, temp_max_ciclo=90.0)
    assert [m.valores.get("temp_max") for m in lista] == [90.0]


def test_temp_max_tras_ciclo_en_ciclo_es_la_del_programa_en_curso():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    programa = MagicMock()
    programa.get_param.return_value = 100.0
    estado = MagicMock()
    estado.get_machine_state.return_value = GlobalState.CICLO
    loop = SimpleNamespace(estado=estado,
                           state_machine=SimpleNamespace(ciclo=SimpleNamespace(
                               programa_en_curso=programa)),
                           _programa_ultimo_ciclo=None, _recuperacion_pendiente=None)
    assert ControlLoop.temp_max_tras_ciclo(loop) == 100.0
    estado.get_machine_state.return_value = GlobalState.PREPARADO
    assert ControlLoop.temp_max_tras_ciclo(loop) is None


def test_apertura_automatica_usa_el_limite_del_programa(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    from tests.test_ciclo_apertura_automatica import _make_ciclo
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.get_status.return_value = "CERRADO"
    door_service.request_open.return_value = (True, "")
    ciclo, *_ = _make_ciclo(door_service=door_service, apertura_automatica=True,
                            tiempo_espera=0, temp_max=100.0, temp_camara=90.0)
    ciclo.config.get.side_effect = lambda n: 80.0 if n == "temp_max_apertura" else None
    monkeypatch.setattr(ciclo_module.time, "monotonic", lambda: 14_000_000.0)
    ciclo._mantener_apertura_automatica()
    # 90 °C <= 100 del programa (antes, min(100, 80) = 80 -> no abría)
    door_service.request_open.assert_called_once()


def test_limites_publicados_con_programa_mayor(monkeypatch):
    from autoclave.backend import server  # noqa: F401  (orden de carga)
    from autoclave.backend.rutas import sistema
    monkeypatch.setattr(sistema, "context", SimpleNamespace(config_manager=_CFG_CS))
    lim = sistema._limites_camara_segura(100.0)
    assert lim["temp_max_apertura"] == 100.0
    assert lim["temp_max_apertura_equipo"] == 80.0
    assert sistema._limites_camara_segura(None)["temp_max_apertura"] == 80.0
