import sys
import json
import importlib
import pytest
from unittest.mock import MagicMock, patch

from autoclave.core.managers.cycle_manager import Cycle


def _make_cycle(tmp_path, source="user"):
    cycle_path = tmp_path / "ciclo_test.json"
    cycle_path.write_text(
        json.dumps({
            "cycle_id": "ciclo_test", "display_name": "Test",
            "parameters": {},
            "cycle_temperature_sensors": {"temp_camara": "principal"},
            "cycle_display_slots": [None, None, None],
        }),
        encoding="utf-8",
    )
    cycle = Cycle(
        cycle_id="ciclo_test", name="Test", parameters={},
        sensor_roles={"temp_camara": "principal"},
        display_slots=[None, None, None],
    )
    cycle.source = source
    cycle._path = str(cycle_path)
    return cycle, cycle_path


@pytest.fixture
def sensor_client(tmp_path):
    cycle, cycle_path = _make_cycle(tmp_path)

    mock_ctx = MagicMock()
    mock_ctx.cycle_manager.cycles = {"ciclo_test": cycle}

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), cycle, cycle_path


def test_patch_sensor_roles_actualiza_en_memoria_y_persiste(sensor_client):
    client, cycle, cycle_path = sensor_client
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "ciclo_test",
        "sensor_roles": {"temp_camara": "referencia", "temp_2_camara": "principal"},
    })
    assert resp.status_code == 200
    assert cycle.sensor_roles == {"temp_camara": "referencia", "temp_2_camara": "principal"}

    persisted = json.loads(cycle_path.read_text(encoding="utf-8"))
    assert persisted["cycle_temperature_sensors"] == {
        "temp_camara": "referencia", "temp_2_camara": "principal"
    }


def test_patch_sensor_roles_422_si_hay_dos_principales(sensor_client):
    client, cycle, _ = sensor_client
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "ciclo_test",
        "sensor_roles": {"temp_camara": "principal", "temp_2_camara": "principal"},
    })
    assert resp.status_code == 422
    assert cycle.sensor_roles == {"temp_camara": "principal"}  # sin mutar


def test_patch_sensor_roles_404_si_ciclo_no_existe(sensor_client):
    client, _, _ = sensor_client
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "no_existe", "sensor_roles": {},
    })
    assert resp.status_code == 404


def test_patch_display_slots_actualiza_en_memoria_y_persiste(sensor_client):
    client, cycle, cycle_path = sensor_client
    resp = client.patch("/cycle/display-slots", json={
        "cycle_id": "ciclo_test",
        "display_slots": ["temp_camara", "pres_camara", None],
    })
    assert resp.status_code == 200
    assert cycle.display_slots == ["temp_camara", "pres_camara", None]

    persisted = json.loads(cycle_path.read_text(encoding="utf-8"))
    assert persisted["cycle_display_slots"] == ["temp_camara", "pres_camara", None]


def test_patch_display_slots_422_si_longitud_incorrecta(sensor_client):
    client, _, _ = sensor_client
    resp = client.patch("/cycle/display-slots", json={
        "cycle_id": "ciclo_test", "display_slots": ["temp_camara"],
    })
    assert resp.status_code == 422


def test_patch_sensor_config_no_persiste_ciclos_factory(tmp_path):
    cycle, cycle_path = _make_cycle(tmp_path, source="factory")
    mock_ctx = MagicMock()
    mock_ctx.cycle_manager.cycles = {"ciclo_test": cycle}

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    client = TestClient(srv.app)

    original = cycle_path.read_text(encoding="utf-8")
    resp = client.patch("/cycle/sensor-roles", json={
        "cycle_id": "ciclo_test", "sensor_roles": {"temp_camara": "referencia"},
    })
    assert resp.status_code == 200
    assert cycle_path.read_text(encoding="utf-8") == original
