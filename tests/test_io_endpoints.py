import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module")
def io_client():
    mock_setdo = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.setdo = mock_setdo

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_setdo


def test_reset_all_devuelve_ok(io_client):
    client, mock_setdo = io_client
    resp = client.post("/io/test/reset_all")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_setdo.reset_all_outputs.assert_called_once()


def test_set_output_activa_vapor_generador(io_client):
    client, mock_setdo = io_client
    mock_setdo.set_output.reset_mock()
    resp = client.patch("/io/test/output/vapor_generador", json={"value": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"ok": True, "name": "vapor_generador", "value": True}
    mock_setdo.set_output.assert_called_once_with(0, True)


def test_set_output_apaga_vapor_caldera(io_client):
    client, mock_setdo = io_client
    mock_setdo.set_output.reset_mock()
    resp = client.patch("/io/test/output/vapor_caldera", json={"value": False})
    assert resp.status_code == 200
    mock_setdo.set_output.assert_called_once_with(1, False)


def test_set_output_404_para_nombre_invalido(io_client):
    client, _ = io_client
    resp = client.patch("/io/test/output/no_existe", json={"value": True})
    assert resp.status_code == 404


def test_reset_all_se_puede_llamar_varias_veces(io_client):
    client, mock_setdo = io_client
    mock_setdo.reset_all_outputs.reset_mock()
    client.post("/io/test/reset_all")
    client.post("/io/test/reset_all")
    assert mock_setdo.reset_all_outputs.call_count == 2
