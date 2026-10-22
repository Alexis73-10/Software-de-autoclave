"""Q1 / T2-b (tanda 7, decisión 1.3 de Cristian; SAF-03 de T2): DESPEJAR de
COM-02/COM-03 exige que el enlace haya vuelto a "ok" (3 tramas vigentes
seguidas). No exige sesión: el operador despeja sin técnico (D-06)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CIC_03, COM_02, COM_03
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cargar_servidor


def _am(estado_maquina=GlobalState.PREPARACION, enlace=False):
    maquina = [estado_maquina]
    ok = [enlace]
    am = AlarmManager(SimpleNamespace(get_machine_state=lambda: maquina[0]))
    am.enlace_ok = lambda: ok[0]
    am.activar(COM_02, segundos=5.0, fase="Esterilización")
    am.activar(COM_03, causa="TARJETA_WATCHDOG", motivo="WD.", fase="Esterilización")
    return am, maquina, ok


def _activas(am):
    return sorted(i.codigo for i in am.activas() if i.estado.name == "ACTIVA")


def test_sin_enlace_ok_no_se_despeja_ni_se_reconoce():
    am, _, _ = _am(enlace=False)
    assert am.reconocer(COM_02, "operador") is False
    assert am.reconocer(COM_03, "operador") is False
    assert _activas(am) == [COM_02, COM_03]
    assert am.obtener(COM_02).reconocida_por is None
    assert am.despeje_bloqueado(COM_02) is True


def test_con_enlace_ok_se_despeja_como_antes():
    am, _, _ = _am(enlace=True)
    assert am.despeje_bloqueado(COM_02) is False
    assert am.reconocer(COM_02, "operador") is True
    assert am.reconocer(COM_03, "operador") is True
    assert _activas(am) == []


def test_otras_alarmas_no_dependen_del_enlace():
    am, _, _ = _am(enlace=False)
    am.activar(CIC_03, motivo="x")
    assert am.despeje_bloqueado(CIC_03) is False
    assert am.reconocer(CIC_03, "operador") is True


def test_en_ciclo_tampoco_se_reconoce_sin_enlace():
    am, maquina, ok = _am(GlobalState.CICLO, enlace=False)
    assert am.reconocer(COM_03, "operador") is False
    ok[0] = True
    assert am.reconocer(COM_03, "operador") is True
    assert _activas(am) == [COM_02, COM_03]            # en CICLO sigue activa (P-5)


def test_reinicio_no_resuelve_las_reconocidas_si_el_enlace_cayo_otra_vez():
    am, maquina, ok = _am(GlobalState.CICLO, enlace=True)
    am.reconocer(COM_03, "operador")
    ok[0] = False                                      # el enlace volvió a caer
    maquina[0] = GlobalState.FALLA
    am.resolver_todas_por_reinicio()
    assert COM_03 in _activas(am)
    ok[0] = True
    am.resolver_todas_por_reinicio()
    assert COM_03 not in _activas(am)


def test_reconocida_que_quedo_activa_se_despeja_al_volver_el_enlace():
    # reconocida en CICLO, el reinicio no la resolvió (enlace caído): fuera de
    # CICLO, otro DESPEJAR con el enlace ok la resuelve (no queda trabada)
    am, maquina, ok = _am(GlobalState.CICLO, enlace=True)
    am.reconocer(COM_03, "operador")
    ok[0] = False
    maquina[0] = GlobalState.PREPARACION
    am.resolver_todas_por_reinicio()
    assert COM_03 in _activas(am)
    assert am.reconocer(COM_03, "operador") is False
    ok[0] = True
    assert am.reconocer(COM_03, "operador") is True
    assert COM_03 not in _activas(am)


def test_sin_verificador_conectado_queda_como_antes():
    # DECISIÓN SIN CONFIRMAR: sin `enlace_ok` (dobles de prueba) no se exige
    maquina = [GlobalState.PREPARACION]
    am = AlarmManager(SimpleNamespace(get_machine_state=lambda: maquina[0]))
    am.activar(COM_02, segundos=5.0, fase="x")
    assert am.reconocer(COM_02, "operador") is True


def test_verificador_que_lanza_bloquea():
    am, _, _ = _am(enlace=True)

    def roto():
        raise RuntimeError("x")

    am.enlace_ok = roto
    assert am.reconocer(COM_02, "operador") is False


# ── ControlLoop: 3 tramas vigentes seguidas ─────────────────────────────────

def test_control_loop_confirma_el_enlace_tras_3_ticks_ok():
    from tests.test_control_loop_test_mode import _make_control_loop
    loop, _, _ = _make_control_loop()
    loop.link.puerto_presente.return_value = True
    loop.link.is_connected.return_value = True
    assert loop.enlace_confirmado_ok is False
    for i in range(3):
        loop._actualizar_estado_tarjeta(True, 0.0)
        loop._contar_enlace_ok()
        assert loop.enlace_confirmado_ok is (i == 2)
    loop.link.edad_ultima_di.return_value = 99.0         # DI vencida
    loop._actualizar_estado_tarjeta(True, 0.0)
    loop._contar_enlace_ok()
    assert loop.enlace_confirmado_ok is False


def test_contexto_verificador_del_enlace():
    from autoclave.backend.context import BackendContext
    ctx = BackendContext.__new__(BackendContext)
    ctx.control_loop = None
    assert ctx._enlace_confirmado_ok() is False           # sin lazo: falla cerrada
    ctx.control_loop = SimpleNamespace(enlace_confirmado_ok=True)
    assert ctx._enlace_confirmado_ok() is True
    ctx.control_loop = SimpleNamespace(enlace_confirmado_ok=MagicMock())
    assert ctx._enlace_confirmado_ok() is False


# ── endpoint ───────────────────────────────────────────────────────────────

@pytest.fixture
def cliente():
    ctx = MagicMock()
    am, maquina, ok = _am(enlace=False)
    ctx.alarm_manager = am
    srv, _ = cargar_servidor(ctx)
    from fastapi.testclient import TestClient
    return TestClient(srv.app), ok


def test_endpoint_responde_409_con_motivo_sin_enlace(cliente):
    client, ok = cliente
    r = client.post(f"/alarms/{COM_02}/acknowledge", json={"usuario": "operador"})
    assert r.status_code == 409
    assert "enlace" in r.json()["detail"].lower()


def test_endpoint_sin_sesion_despeja_con_enlace_ok(cliente):
    client, ok = cliente
    ok[0] = True
    r = client.post(f"/alarms/{COM_02}/acknowledge", json={"usuario": "operador"})
    assert r.status_code == 200
