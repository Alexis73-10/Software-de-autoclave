import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def status_client():
    mock_ctx = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx


def _stub_estado_collections(mock_ctx) -> None:
    mock_ctx.estado.estado_puertas = {}
    mock_ctx.estado.sensores_temp = {}
    mock_ctx.estado.sensores_pres = {}
    mock_ctx.estado.sensores_di = {}
    mock_ctx.estado.salidas_do = {}
    mock_ctx.estado.flags = {}


def test_status_incluye_description_y_source_state_por_alarma(status_client):
    client, mock_ctx = status_client

    fake_alarm = MagicMock()
    fake_alarm.id = "PUERTA_NO_CERRADA"
    fake_alarm.type.name = "FALLA"
    fake_alarm.description = "Puerta frontal no cerrada"
    fake_alarm.source_state = "PREPARACION"

    mock_ctx.estado.Alarmas_activas = [fake_alarm]
    _stub_estado_collections(mock_ctx)

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["alarms"] == [{
        "id": "PUERTA_NO_CERRADA",
        "level": "FALLA",
        "description": "Puerta frontal no cerrada",
        "source_state": "PREPARACION",
    }]


def test_status_alarmas_vacias_devuelve_lista_vacia(status_client):
    client, mock_ctx = status_client

    mock_ctx.estado.Alarmas_activas = []
    _stub_estado_collections(mock_ctx)

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["alarms"] == []
