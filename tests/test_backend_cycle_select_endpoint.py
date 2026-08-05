import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.state_machine.machine.enum_global import GlobalState


def _make_cycles():
    user_cycle = Cycle(cycle_id="bowe_dick", name="Bowe & Dick", parameters={})
    user_cycle.source = "user"
    factory_cycle = Cycle(cycle_id="fabrica_x", name="Fábrica X", parameters={})
    factory_cycle.source = "factory"
    return user_cycle, factory_cycle


@pytest.fixture
def select_client():
    user_cycle, factory_cycle = _make_cycles()

    mock_ctx = MagicMock()
    mock_ctx.cycle_manager.cycles = {"bowe_dick": user_cycle, "fabrica_x": factory_cycle}
    mock_ctx.control_loop.set_active_cycle.return_value = (True, "")

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx, user_cycle, factory_cycle


def test_list_cycles_incluye_todos_con_source(select_client):
    client, *_ = select_client
    resp = client.get("/cycles")
    assert resp.status_code == 200
    body = resp.json()
    assert {"id": "bowe_dick", "name": "Bowe & Dick", "source": "user"} in body
    assert {"id": "fabrica_x", "name": "Fábrica X", "source": "factory"} in body


def test_select_cycle_ok_llama_control_loop_y_sincroniza_cycle_manager(select_client):
    client, mock_ctx, user_cycle, _ = select_client
    resp = client.post("/cycle/select", json={"cycle_id": "bowe_dick"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "id": "bowe_dick", "name": "Bowe & Dick"}
    mock_ctx.control_loop.set_active_cycle.assert_called_once_with(user_cycle)
    mock_ctx.cycle_manager.set_default_cycle.assert_called_once_with("bowe_dick")


def test_select_cycle_404_si_no_existe(select_client):
    client, mock_ctx, *_ = select_client
    resp = client.post("/cycle/select", json={"cycle_id": "no_existe"})
    assert resp.status_code == 404
    mock_ctx.control_loop.set_active_cycle.assert_not_called()


def test_select_cycle_422_si_es_de_fabrica(select_client):
    client, mock_ctx, *_ = select_client
    resp = client.post("/cycle/select", json={"cycle_id": "fabrica_x"})
    assert resp.status_code == 422
    mock_ctx.control_loop.set_active_cycle.assert_not_called()


def test_select_cycle_409_si_control_loop_rechaza(select_client):
    client, mock_ctx, *_ = select_client
    mock_ctx.control_loop.set_active_cycle.return_value = (
        False, "No se puede cambiar de ciclo mientras hay uno en curso."
    )
    resp = client.post("/cycle/select", json={"cycle_id": "bowe_dick"})
    assert resp.status_code == 409
    assert "ciclo" in resp.json()["detail"].lower()
    mock_ctx.cycle_manager.set_default_cycle.assert_not_called()
