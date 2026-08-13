import sys
import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def audio_client(tmp_path):
    mock_ctx = MagicMock()
    mock_ctx.audio_preferences = {"audio": {"enabled": True, "volume": 80}}
    mock_ctx._audio_disponible = True
    mock_ctx.announcer = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        with patch("autoclave.config.preferences.DEFAULT_PREFERENCES_PATH", tmp_path / "preferences.json"):
            srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx


def test_get_audio_config(audio_client):
    client, ctx = audio_client
    resp = client.get("/audio/config")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True, "volume": 80, "available": True}


def test_patch_audio_config_actualiza_volumen(audio_client):
    client, ctx = audio_client
    resp = client.patch("/audio/config", json={"volume": 42})
    assert resp.status_code == 200
    assert ctx.audio_preferences["audio"]["volume"] == 42


def test_patch_audio_config_volumen_fuera_de_rango_422(audio_client):
    client, ctx = audio_client
    resp = client.patch("/audio/config", json={"volume": 150})
    assert resp.status_code == 422
    assert ctx.audio_preferences["audio"]["volume"] == 80


def test_patch_audio_config_deshabilitar_vacia_cola(audio_client):
    client, ctx = audio_client
    resp = client.patch("/audio/config", json={"enabled": False})
    assert resp.status_code == 200
    ctx.announcer.disable_now.assert_called_once()


def test_post_audio_test_reproduce_evento(audio_client):
    client, ctx = audio_client
    resp = client.post("/audio/test")
    assert resp.status_code == 200
    ctx.announcer.say.assert_called_once_with("sys_prueba_audio")


def test_post_audio_test_reintenta_tras_fallo_previo(audio_client):
    """§7.2: tras autodeshabilitarse por 3 fallos consecutivos, el botón de
    prueba es el mecanismo de reintento — debe volver a intentar reproducir
    aunque _audio_disponible esté en False."""
    client, ctx = audio_client
    ctx._audio_disponible = False
    resp = client.post("/audio/test")
    assert resp.status_code == 200
    assert ctx._audio_disponible is True
    ctx.announcer.say.assert_called_once_with("sys_prueba_audio")


def test_post_audio_ui_ready_es_idempotente(audio_client):
    client, ctx = audio_client
    resp1 = client.post("/audio/ui-ready")
    resp2 = client.post("/audio/ui-ready")
    assert resp1.status_code == 200 and resp2.status_code == 200
    ctx.announcer.say.assert_called_once_with("sys_bienvenida")
