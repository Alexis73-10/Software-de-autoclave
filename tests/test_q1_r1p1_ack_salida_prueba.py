# Q1 / R1-P1 (tanda 7, decisión 1.3 de Cristian): exit_test_mode devuelve el
# ACK del ALL_OFF y la bitácora lo anota, sin cambiar qué se apaga.

import pytest
from unittest.mock import MagicMock

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend
from tests.test_control_loop_test_mode import _make_control_loop


@pytest.mark.parametrize("ack, esperado", [(True, True), (False, False), (None, False)])
def test_exit_test_mode_devuelve_el_ack_del_all_off(ack, esperado):
    loop, _, _ = _make_control_loop()
    loop.enter_test_mode()
    loop.set_do.reset_all_outputs.reset_mock()
    loop.set_do.reset_all_outputs.return_value = ack

    resultado = loop.exit_test_mode()

    assert resultado is esperado
    loop.set_do.reset_all_outputs.assert_called_once()   # lo que se apaga no cambia
    assert loop.test_mode_active is False


@pytest.fixture
def io_client():
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.control_loop.enter_test_mode.return_value = (True, "")
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)
    from fastapi.testclient import TestClient
    return TestClient(srv.app), ctx, srv


def _entrar(client, ctx, cab):
    assert client.post("/io/test/enter", headers=cab).status_code == 200
    ctx.control_loop.test_mode_active = True


def _detalle_sale(ctx):
    for c in ctx.db.registrar_auditoria.call_args_list:
        if c.args[0] == "modo_prueba_sale":
            return c.kwargs["detalle"]
    raise AssertionError("no se registró modo_prueba_sale")


@pytest.mark.parametrize("ack", [True, False])
def test_salida_normal_anota_el_ack_en_bitacora_y_respuesta(io_client, ack):
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)
    ctx.control_loop.exit_test_mode.return_value = ack

    resp = client.post("/io/test/exit", headers=cab)

    assert resp.status_code == 200
    assert resp.json()["all_off_confirmado"] is ack
    assert _detalle_sale(ctx)["all_off_confirmado"] is ack


def test_salida_por_logout_anota_el_ack(io_client):
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)
    ctx.control_loop.exit_test_mode.return_value = False

    assert client.post("/auth/logout", headers=cab).status_code == 200

    detalle = _detalle_sale(ctx)
    assert detalle["motivo"] == "sesión cerrada"
    assert detalle["all_off_confirmado"] is False


def test_salida_forzada_anota_el_ack(io_client):
    client, ctx, srv = io_client
    _entrar(client, ctx, cabecera(srv, "tecnico", "tec1"))
    ctx.control_loop.exit_test_mode.return_value = True
    modulo_backend("dependencias").tokens.invalidar(next(iter(modulo_backend("dependencias").tokens.sesiones_de("tec1"))).token)

    resp = client.post("/io/test/force-exit", headers=cabecera(srv, "ingeniero", "ing1"),
                       json={"confirmar": True, "motivo": "huérfano"})

    assert resp.status_code == 200, resp.text
    assert _detalle_sale(ctx)["all_off_confirmado"] is True
