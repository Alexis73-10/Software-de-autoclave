import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def status_client():
    mock_ctx = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
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


def test_status_alarmas_vacias_devuelve_lista_vacia(status_client):
    client, mock_ctx = status_client

    _stub_estado_collections(mock_ctx)

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["alarms"] == []


def test_status_publica_instancias_nuevas_con_compatibilidad(status_client):
    from datetime import datetime
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    from autoclave.state_machine.alarms.catalogo import PUE_01

    client, mock_ctx = status_client
    _stub_estado_collections(mock_ctx)
    am = AlarmManager(reloj=lambda: datetime(2026, 10, 7, 9, 30, 0))
    am.activar(PUE_01, origen="Puerta 1", puerta="Puerta 1")
    mock_ctx.alarm_manager = am

    cuerpo = client.get("/status").json()
    # I1 (tanda 5): campos nuevos de presentación por idioma, aparte
    for a in cuerpo["alarms"]:
        assert set(a.pop("textos")) == {"es", "en"} and isinstance(a.pop("valores"), dict)
    assert cuerpo["alarms"] == [{
        "clave": "PUE-01|Puerta 1", "codigo": "PUE-01", "nivel": "AVISO",
        "titulo": "Puerta abierta",
        "descripcion": "Puerta 1 está abierta. El ciclo no puede iniciar.",
        "accion": "Cierre la puerta.", "origen": "Puerta 1",
        "aparecida": "2026-10-07T09:30:00", "estado": "ACTIVA",
        "requiere_reconocimiento": False, "reconocida_por": None,
        "roles_visibles": [],       # LIC-02 (licencia L0): la ven todos
        "id": "PUE-01|Puerta 1", "level": "ALERTA",
        "description": "Puerta 1 está abierta. El ciclo no puede iniciar.",
        "source_state": "Puerta 1",
    }]
    assert cuerpo["eventos_recientes"] == []


def test_status_separa_activas_de_resueltas_sin_reconocer(status_client):
    from datetime import datetime
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    from autoclave.state_machine.alarms.catalogo import COM_01, PUE_01

    client, mock_ctx = status_client
    _stub_estado_collections(mock_ctx)
    am = AlarmManager(reloj=lambda: datetime(2026, 10, 7, 9, 30, 0))
    am.activar(PUE_01, origen="Puerta 1", puerta="Puerta 1")
    am.activar(COM_01)
    am.resolver(COM_01)          # ALARMA sin reconocer → RESUELTA_SIN_RECONOCER
    mock_ctx.alarm_manager = am

    cuerpo = client.get("/status").json()
    assert [a["clave"] for a in cuerpo["alarms"]] == ["PUE-01|Puerta 1"]
    assert [a["clave"] for a in cuerpo["alarmas_sin_reconocer"]] == ["COM-01"]
    assert cuerpo["alarmas_sin_reconocer"][0]["estado"] == "RESUELTA_SIN_RECONOCER"
    assert cuerpo["alarmas_sin_reconocer"][0]["requiere_reconocimiento"] is True


def test_status_alarmas_sin_reconocer_vacia_por_defecto(status_client):
    client, mock_ctx = status_client
    _stub_estado_collections(mock_ctx)
    assert client.get("/status").json()["alarmas_sin_reconocer"] == []
