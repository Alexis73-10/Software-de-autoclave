# Entrada y salida del modo prueba (planeacion_backend_autenticacion.md §4.5
# y §5.4): token de técnico o ingeniero, estados bloqueados y salida solo
# desde la sesión que entró.

import pytest
from unittest.mock import MagicMock

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor


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
    resp = client.post("/io/test/enter", headers=cab)
    if resp.status_code == 200:
        ctx.control_loop.test_mode_active = True
    return resp


def test_enter_test_mode_ok(io_client):
    client, ctx, srv = io_client
    resp = _entrar(client, ctx, cabecera(srv, "tecnico"))

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    ctx.control_loop.enter_test_mode.assert_called_once()
    assert ctx.db.registrar_auditoria.call_args.args[0] == "modo_prueba_entra"


def test_enter_test_mode_rechazado_devuelve_409_con_motivo(io_client):
    client, ctx, srv = io_client
    ctx.control_loop.enter_test_mode.return_value = (
        False, "No se puede activar el modo prueba con el paro de emergencia activado."
    )

    resp = client.post("/io/test/enter", headers=cabecera(srv, "tecnico"))

    assert resp.status_code == 409
    assert "paro de emergencia" in resp.json()["detail"]


@pytest.mark.parametrize("estado", [GlobalState.CICLO, GlobalState.HIBERNACION,
                                    GlobalState.EMERGENCIA])
def test_enter_bloqueado_en_ciclo_hibernacion_y_emergencia(io_client, estado):
    client, ctx, srv = io_client
    ctx.estado.get_machine_state.return_value = estado

    resp = client.post("/io/test/enter", headers=cabecera(srv, "ingeniero"))

    assert resp.status_code == 409
    ctx.control_loop.enter_test_mode.assert_not_called()


@pytest.mark.parametrize("estado", [GlobalState.PREPARACION, GlobalState.PREPARADO,
                                    GlobalState.FALLA])
def test_enter_permitido_fuera_de_ciclo(io_client, estado):
    client, ctx, srv = io_client
    ctx.estado.get_machine_state.return_value = estado
    assert client.post("/io/test/enter", headers=cabecera(srv, "tecnico")).status_code == 200


def test_enter_sin_token_401_y_admin_403(io_client):
    client, ctx, srv = io_client
    assert client.post("/io/test/enter").status_code == 401
    assert client.post("/io/test/enter", headers=cabecera(srv, "admin")).status_code == 403
    ctx.control_loop.enter_test_mode.assert_not_called()


def test_exit_test_mode_ok(io_client):
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)

    resp = client.post("/io/test/exit", headers=cab)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    ctx.control_loop.exit_test_mode.assert_called_once()


def test_exit_fuera_de_modo_prueba_409(io_client):
    client, ctx, srv = io_client
    resp = client.post("/io/test/exit", headers=cabecera(srv, "tecnico"))
    assert resp.status_code == 409
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_exit_desde_otra_sesion_409(io_client):
    client, ctx, srv = io_client
    _entrar(client, ctx, cabecera(srv, "tecnico", "tec1"))

    resp = client.post("/io/test/exit", headers=cabecera(srv, "ingeniero", "ing1"))

    assert resp.status_code == 409
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_enter_desde_otra_sesion_con_modo_prueba_activo_409(io_client):
    """Otra sesión no puede quitarle el modo prueba a la que entró."""
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico", "tec1")
    _entrar(client, ctx, cab)

    assert client.post("/io/test/enter", headers=cabecera(srv, "ingeniero", "ing1")).status_code == 409
    assert client.post("/io/test/exit", headers=cab).status_code == 200


def test_logout_de_la_sesion_que_entro_sale_del_modo_prueba(io_client):
    """Decisión 30: al invalidar el token que entró, el backend sale del modo
    prueba y apaga las salidas (exit_test_mode apaga todo)."""
    client, ctx, srv = io_client
    cab = cabecera(srv, "tecnico")
    _entrar(client, ctx, cab)

    assert client.post("/auth/logout", headers=cab).status_code == 200

    ctx.control_loop.exit_test_mode.assert_called_once()
    eventos = [c.args[0] for c in ctx.db.registrar_auditoria.call_args_list]
    assert "modo_prueba_sale" in eventos


def test_logout_de_otra_sesion_no_sale_del_modo_prueba(io_client):
    client, ctx, srv = io_client
    _entrar(client, ctx, cabecera(srv, "tecnico", "tec1"))

    assert client.post("/auth/logout", headers=cabecera(srv, "ingeniero", "ing1")).status_code == 200

    ctx.control_loop.exit_test_mode.assert_not_called()


def test_status_incluye_test_mode_active(io_client):
    client, ctx, _ = io_client
    ctx.control_loop.test_mode_active = True
    ctx.estado.Alarmas_activas = []
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["test_mode_active"] is True
