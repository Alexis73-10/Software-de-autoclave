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
    mock_ctx.alarm_manager.activas.return_value = []
    mock_ctx.alarm_manager.eventos_recientes.return_value = []


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


def test_status_publica_instancias_nuevas_con_compatibilidad(status_client):
    from datetime import datetime
    from types import SimpleNamespace
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    from autoclave.state_machine.alarms.catalogo import PUE_01

    client, mock_ctx = status_client
    _stub_estado_collections(mock_ctx)
    mock_ctx.estado.Alarmas_activas = []
    am = AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]),
                      reloj=lambda: datetime(2026, 10, 7, 9, 30, 0))
    am.activar(PUE_01, origen="Puerta 1", puerta="Puerta 1")
    mock_ctx.alarm_manager = am

    cuerpo = client.get("/status").json()
    assert cuerpo["alarms"] == [{
        "clave": "PUE-01|Puerta 1", "codigo": "PUE-01", "nivel": "AVISO",
        "titulo": "Puerta abierta",
        "descripcion": "Puerta 1 está abierta. El ciclo no puede iniciar.",
        "accion": "Cierre la puerta.", "origen": "Puerta 1",
        "aparecida": "2026-10-07T09:30:00", "estado": "ACTIVA",
        "requiere_reconocimiento": False, "reconocida_por": None,
        "id": "PUE-01|Puerta 1", "level": "ALERTA",
        "description": "Puerta 1 está abierta. El ciclo no puede iniciar.",
        "source_state": "Puerta 1",
    }]
    assert cuerpo["eventos_recientes"] == []
