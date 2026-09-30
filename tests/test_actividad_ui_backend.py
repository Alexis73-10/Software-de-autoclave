# tests/test_actividad_ui_backend.py
#
# Actividad compartida de las pantallas QML en el backend (standby simultáneo):
# ActividadUI (reloj monotónico inyectable) y POST /ui/activity.

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from autoclave.backend.actividad_ui import ActividadUI


class _Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_sin_actividad_es_none():
    assert ActividadUI(reloj=_Reloj()).inactividad_s() is None


def test_inactividad_desde_el_ultimo_registro():
    reloj = _Reloj()
    act = ActividadUI(reloj=reloj)
    act.registrar()
    reloj.t += 42.5
    assert act.inactividad_s() == pytest.approx(42.5)
    act.registrar()
    assert act.inactividad_s() == 0.0


def test_reloj_que_retrocede_no_da_negativos():
    reloj = _Reloj()
    act = ActividadUI(reloj=reloj)
    act.registrar()
    reloj.t -= 5
    assert act.inactividad_s() == 0.0


@pytest.fixture
def servidor():
    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=MagicMock()):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    return TestClient(srv.app), srv


def test_post_ui_activity_reinicia_la_inactividad(servidor):
    client, srv = servidor
    assert srv.actividad_ui.inactividad_s() is None
    resp = client.post("/ui/activity")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert srv.actividad_ui.inactividad_s() is not None
    assert srv.actividad_ui.inactividad_s() < 5
