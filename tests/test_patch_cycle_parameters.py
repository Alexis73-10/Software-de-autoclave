import json
import pytest
from unittest.mock import MagicMock, patch
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.core.cycle_manager import CycleManager


# ── BackendClient.patch() ────────────────────────────────────────────

def test_patch_envia_body_correcto():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.patch", return_value=mock_resp) as mock_req:
        result = client.patch("/cycle/parameters", {"tiempo_secado": 15.0})
        mock_req.assert_called_once_with(
            "http://localhost:8000/cycle/parameters",
            json={"tiempo_secado": 15.0},
            timeout=0.8,
        )
        assert result == {"ok": True}


def test_patch_body_none_envia_dict_vacio():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.patch", return_value=mock_resp) as mock_req:
        client.patch("/cycle/parameters")
        mock_req.assert_called_once_with(
            "http://localhost:8000/cycle/parameters",
            json={},
            timeout=0.8,
        )


# ── CycleManager._path ───────────────────────────────────────────────

def test_cycle_manager_asigna_path_al_cargar(tmp_path):
    cycle_data = {
        "cycle_id": "ciclo_test",
        "display_name": "Test",
        "parameters": {
            "secado": {
                "tiempo_secado": {
                    "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 120
                }
            }
        },
    }
    cycle_file = tmp_path / "ciclo_test.json"
    cycle_file.write_text(json.dumps(cycle_data), encoding="utf-8")

    cm = CycleManager()
    cm._load_from_folder(str(tmp_path), source="user")

    cycle = cm.cycles.get("ciclo_test")
    assert cycle is not None
    assert hasattr(cycle, "_path")
    assert cycle._path == str(cycle_file)
    assert cycle.source == "user"


def test_cycle_manager_asigna_source_factory(tmp_path):
    cycle_data = {
        "cycle_id": "ciclo_fab",
        "display_name": "Fábrica",
        "parameters": {},
    }
    (tmp_path / "ciclo_fab.json").write_text(json.dumps(cycle_data), encoding="utf-8")

    cm = CycleManager()
    cm._load_from_folder(str(tmp_path), source="factory")

    assert cm.cycles["ciclo_fab"].source == "factory"
