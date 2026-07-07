import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def io_client():
    mock_ctx = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx


def test_enter_test_mode_ok(io_client):
    client, mock_ctx = io_client
    mock_ctx.control_loop.enter_test_mode.return_value = (True, "")

    resp = client.post("/io/test/enter")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_ctx.control_loop.enter_test_mode.assert_called_once()


def test_enter_test_mode_rechazado_devuelve_409_con_motivo(io_client):
    client, mock_ctx = io_client
    mock_ctx.control_loop.enter_test_mode.return_value = (
        False, "No se puede activar el modo prueba durante un ciclo en curso."
    )

    resp = client.post("/io/test/enter")

    assert resp.status_code == 409
    assert "ciclo en curso" in resp.json()["detail"]


def test_exit_test_mode_ok(io_client):
    client, mock_ctx = io_client

    resp = client.post("/io/test/exit")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_ctx.control_loop.exit_test_mode.assert_called_once()


def test_set_output_usa_el_canal_do_fisico_1_indexado(io_client):
    """map_do es 0-indexado (vapor_camara=3) pero serial_link.set_output()
    espera el número de DO físico 1-indexado (DO4). Enviar el índice crudo
    activa el canal anterior (DO3 = vapor_chaqueta)."""
    client, mock_ctx = io_client

    resp = client.patch("/io/test/output/vapor_camara", json={"value": True})

    assert resp.status_code == 200
    mock_ctx.setdo.set_output.assert_called_once_with(4, True)


def test_status_incluye_test_mode_active(io_client):
    client, mock_ctx = io_client
    mock_ctx.control_loop.test_mode_active = True
    mock_ctx.estado.Alarmas_activas = []
    mock_ctx.estado.estado_puertas = {}
    mock_ctx.estado.sensores_temp = {}
    mock_ctx.estado.sensores_pres = {}
    mock_ctx.estado.sensores_di = {}
    mock_ctx.estado.salidas_do = {}
    mock_ctx.estado.flags = {}

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["test_mode_active"] is True
