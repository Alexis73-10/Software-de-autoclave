import sys
import json
import importlib
import pytest
from unittest.mock import MagicMock, patch

from autoclave.core.managers.cycle_manager import Cycle


def _make_cycle(tmp_path, source="user"):
    parameters = {
        "esterilizacion": {
            "temperatura_esterilizacion": {
                "value": 134.0, "type": "float", "unit": "°C", "min": 100, "max": 140
            }
        },
        "descompresion": {
            "modo_3": {
                "presion_cambio": {"value": 150, "type": "int", "unit": "kPa", "min": 0, "max": 500}
            }
        },
    }
    cycle_path = tmp_path / "ciclo_test.json"
    cycle_path.write_text(
        json.dumps({"cycle_id": "ciclo_test", "display_name": "Test", "parameters": parameters}),
        encoding="utf-8",
    )
    cycle = Cycle(cycle_id="ciclo_test", name="Test", parameters=parameters)
    cycle.source = source
    cycle._path = str(cycle_path)
    return cycle, cycle_path


@pytest.fixture
def param_client(tmp_path):
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


def test_patch_actualiza_valor_en_memoria_y_lo_persiste(param_client):
    client, cycle, cycle_path = param_client
    resp = client.patch("/cycle/parameter", json={
        "cycle_id": "ciclo_test",
        "fase": "esterilizacion",
        "path": ["temperatura_esterilizacion"],
        "value": 135.0,
    })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "value": 135.0}
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 135.0

    persisted = json.loads(cycle_path.read_text(encoding="utf-8"))
    assert persisted["parameters"]["esterilizacion"]["temperatura_esterilizacion"]["value"] == 135.0


def test_patch_soporta_path_anidado(param_client):
    client, cycle, _ = param_client
    resp = client.patch("/cycle/parameter", json={
        "cycle_id": "ciclo_test",
        "fase": "descompresion",
        "path": ["modo_3", "presion_cambio"],
        "value": 200,
    })
    assert resp.status_code == 200
    assert cycle.parameters["descompresion"]["modo_3"]["presion_cambio"]["value"] == 200


def test_patch_404_si_ciclo_no_existe(param_client):
    client, _, _ = param_client
    resp = client.patch("/cycle/parameter", json={
        "cycle_id": "no_existe",
        "fase": "esterilizacion",
        "path": ["temperatura_esterilizacion"],
        "value": 135.0,
    })
    assert resp.status_code == 404


def test_patch_422_si_fase_no_existe(param_client):
    client, _, _ = param_client
    resp = client.patch("/cycle/parameter", json={
        "cycle_id": "ciclo_test",
        "fase": "no_existe",
        "path": ["x"],
        "value": 1,
    })
    assert resp.status_code == 422


def test_patch_422_si_valor_fuera_de_rango(param_client):
    client, cycle, _ = param_client
    resp = client.patch("/cycle/parameter", json={
        "cycle_id": "ciclo_test",
        "fase": "esterilizacion",
        "path": ["temperatura_esterilizacion"],
        "value": 999.0,
    })
    assert resp.status_code == 422
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 134.0


def test_patch_no_persiste_ciclos_factory(tmp_path):
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

    original_contents = cycle_path.read_text(encoding="utf-8")
    resp = client.patch("/cycle/parameter", json={
        "cycle_id": "ciclo_test",
        "fase": "esterilizacion",
        "path": ["temperatura_esterilizacion"],
        "value": 135.0,
    })
    assert resp.status_code == 200
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 135.0
    assert cycle_path.read_text(encoding="utf-8") == original_contents
