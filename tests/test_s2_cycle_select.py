"""S2 (tanda 2, decisión 2 de Cristian): POST /cycle/select sin sesión y en
FALLA es lo deseado (ningún fallo exige técnico) y se conserva. Pero el cambio
se rechaza con un ciclo EN CURSO en sentido amplio: CICLO, estado seguro en
curso o pendiente de confirmar, recuperación pendiente tras un reinicio y paro
activo. Un programa dañado sigue rechazado (RB-04.4) y cada cambio queda
registrado con el origen. D9-6 (tanda 9): ese registro pasó de la bitácora
(audit_log) al log de desarrollo (`_log_desarrollo`)."""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_set_active_cycle import _FakeEstado, _make_control_loop


# ── ControlLoop.set_active_cycle ─────────────────────────────────────────────

def _loop(estado_maquina=GlobalState.FALLA):
    estado = _FakeEstado()
    estado.set_machine_state(estado_maquina)
    loop, _, inicial, _ = _make_control_loop(estado)
    return loop, inicial, estado


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_en_falla_sin_nada_en_curso_se_permite(_sm):
    loop, _, _ = _loop()
    assert loop.set_active_cycle(MagicMock())[0] is True


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_rechaza_con_paro_activo(sm):
    loop, inicial, estado = _loop()
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)       # U4: sin datos el motivo habla de la tarjeta
    sm.reset_mock()
    ok, motivo = loop.set_active_cycle(MagicMock())
    assert ok is False and "paro" in motivo.lower()
    assert loop.cycle is inicial
    sm.assert_not_called()


@pytest.mark.parametrize("requiere", [True, False])
@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_rechaza_con_estado_seguro_en_curso_o_por_confirmar(sm, requiere):
    loop, inicial, _ = _loop()
    loop.estado_seguro._protocolo = MagicMock()          # activo
    loop.estado_seguro.requiere_confirmacion = requiere
    sm.reset_mock()
    ok, motivo = loop.set_active_cycle(MagicMock())
    assert ok is False and "estado seguro" in motivo.lower()
    assert loop.cycle is inicial
    sm.assert_not_called()


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_rechaza_con_recuperacion_pendiente(sm):
    loop, inicial, _ = _loop(GlobalState.PREPARACION)
    loop._recuperacion_pendiente = MagicMock()
    sm.reset_mock()
    ok, _ = loop.set_active_cycle(MagicMock())
    assert ok is False and loop.cycle is inicial
    sm.assert_not_called()


# ── Endpoint ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cliente():
    nuevo = Cycle(cycle_id="instrumental_121", name="Instrumental 121", parameters={})
    nuevo.source = "user"
    danado = Cycle(cycle_id="roto", name="Roto", parameters={})
    danado.source = "user"
    danado.danado = ["temperatura_esterilizacion fuera del catálogo"]
    ctx = MagicMock()
    ctx.cycle_manager.cycles = {"instrumental_121": nuevo, "roto": danado}
    ctx.control_loop.set_active_cycle.return_value = (True, "")
    ctx.control_loop.cycle.id = "instrumental_134"
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    for k in list(sys.modules):
        if "autoclave.backend.server" in k:
            del sys.modules[k]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    return TestClient(srv.app), ctx


def _auditorias(ctx, evento):
    """D9-6: la selección ya no va a audit_log; esto debe quedar vacío."""
    return [c for c in ctx.db.registrar_auditoria.call_args_list if c.args[0] == evento]


@pytest.fixture
def log_dev(cliente):
    with patch.object(sys.modules["autoclave.backend.server"], "_log_desarrollo") as m:
        yield m


def _registros(log_dev, evento):
    return [c for c in log_dev.call_args_list if c.args[0] == evento]


def test_cambio_sin_sesion_en_falla_queda_en_el_log_con_el_origen(cliente, log_dev):
    client, ctx = cliente
    r = client.post("/cycle/select", json={"cycle_id": "instrumental_121", "origen": "puerta_1"})
    assert r.status_code == 200
    assert _auditorias(ctx, "PROGRAMA_SELECCIONADO") == []    # D9-6: fuera de la bitácora
    (llamada,) = _registros(log_dev, "PROGRAMA_SELECCIONADO")
    kw = llamada.kwargs
    assert kw["anterior"] == "instrumental_134"
    assert kw["nuevo"] == "instrumental_121"
    assert llamada.args == ("PROGRAMA_SELECCIONADO",)     # sin sesión
    assert kw["detalle"]["origen"] == "puerta_1"
    assert kw["detalle"]["estado"] == "FALLA"
    assert kw["detalle"]["cliente"]                         # dirección del cliente HTTP


def test_sin_origen_declarado_queda_como_desconocido(cliente, log_dev):
    client, ctx = cliente
    assert client.post("/cycle/select", json={"cycle_id": "instrumental_121"}).status_code == 200
    (llamada,) = _registros(log_dev, "PROGRAMA_SELECCIONADO")
    assert llamada.kwargs["detalle"]["origen"] == "desconocido"


def test_rechazo_del_control_loop_no_cambia_ni_audita_el_cambio(cliente, log_dev):
    client, ctx = cliente
    ctx.control_loop.set_active_cycle.return_value = (False, "estado seguro en curso")
    r = client.post("/cycle/select", json={"cycle_id": "instrumental_121", "origen": "puerta_2"})
    assert r.status_code == 409
    ctx.cycle_manager.set_default_cycle.assert_not_called()
    assert _registros(log_dev, "PROGRAMA_SELECCIONADO") == []
    assert _auditorias(ctx, "PROGRAMA_SELECCION_RECHAZADA") == []
    (rechazo,) = _registros(log_dev, "PROGRAMA_SELECCION_RECHAZADA")
    assert rechazo.kwargs["detalle"]["origen"] == "puerta_2"


def test_programa_danado_sigue_rechazado(cliente):
    client, ctx = cliente
    r = client.post("/cycle/select", json={"cycle_id": "roto"})
    assert r.status_code == 409 and r.json()["codigo"] == "PROGRAMA_NO_EDITABLE"
    ctx.control_loop.set_active_cycle.assert_not_called()


# ── Revisión de S2 ───────────────────────────────────────────────────────────

@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_rechaza_con_inicio_ya_pedido(_sm):
    """Un /cycle/start validado con el programa anterior no se descarta en
    silencio ni arranca con otro programa (S2-01 / TMG-02)."""
    loop, inicial, estado = _loop(GlobalState.PREPARADO)
    estado.set_flag("START_CICLO", True)
    ok, motivo = loop.set_active_cycle(MagicMock())
    assert ok is False and "inicio" in motivo.lower() and loop.cycle is inicial


@pytest.mark.parametrize("atributo, valor", [("_apagando", True), ("_bloqueo_config", "x")])
@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_rechaza_apagando_o_con_configuracion_invalida(_sm, atributo, valor):
    loop, _, _ = _loop()
    setattr(loop, atributo, valor)
    assert loop.set_active_cycle(MagicMock())[0] is False


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_rechaza_con_modo_prueba(_sm):
    loop, _, _ = _loop()
    loop._test_mode.set()
    assert loop.set_active_cycle(MagicMock())[0] is False


def test_origen_desconocido_se_rechaza_y_queda_en_el_log(cliente, log_dev):
    client, ctx = cliente
    r = client.post("/cycle/select", json={"cycle_id": "instrumental_121", "origen": "hacker"})
    assert r.status_code == 422 and r.json()["codigo"] == "origen_invalido"
    ctx.control_loop.set_active_cycle.assert_not_called()
    assert _auditorias(ctx, "PROGRAMA_SELECCION_RECHAZADA") == []
    assert len(_registros(log_dev, "PROGRAMA_SELECCION_RECHAZADA")) == 1


@pytest.mark.parametrize("cycle_id, codigo", [("no_existe", "programa_no_encontrado"),
                                              ("roto", "PROGRAMA_NO_EDITABLE")])
def test_todos_los_rechazos_quedan_en_el_log_con_el_origen(cliente, log_dev, cycle_id, codigo):
    client, ctx = cliente
    r = client.post("/cycle/select", json={"cycle_id": cycle_id, "origen": "puerta_2"})
    assert r.json()["codigo"] == codigo
    assert _auditorias(ctx, "PROGRAMA_SELECCION_RECHAZADA") == []
    (rechazo,) = _registros(log_dev, "PROGRAMA_SELECCION_RECHAZADA")
    assert rechazo.kwargs["detalle"]["origen"] == "puerta_2"
    assert rechazo.kwargs["detalle"]["origen_autenticado"] is False


def test_lazo_y_cycle_manager_cambian_bajo_el_mismo_lock(cliente):
    """TMG-01 de la revisión: set_active_cycle y set_default_cycle juntos."""
    client, ctx = cliente
    dentro = []
    lock = MagicMock()
    lock.__enter__.side_effect = lambda *a: dentro.append("entra")
    lock.__exit__.side_effect = lambda *a: dentro.append("sale")
    ctx.control_loop.bloqueo_maquina.return_value = lock
    ctx.control_loop.set_active_cycle.side_effect = lambda c: dentro.append("lazo") or (True, "")
    ctx.cycle_manager.set_default_cycle.side_effect = lambda i: dentro.append("manager")
    assert client.post("/cycle/select", json={"cycle_id": "instrumental_121"}).status_code == 200
    assert dentro == ["entra", "lazo", "manager", "sale"]
