# tests/test_t27_a2_standby_modo_prueba.py
#
# A2 (tanda 27): sin standby en modo prueba; entrar al modo prueba es actividad.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.cliente.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.standby import Standby


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Reloj:
    t = 5000.0

    def __call__(self):
        return self.t


def _ui(prueba):
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_flag.return_value = False
    ui.get_campo.side_effect = lambda c, d=None: (
        prueba["v"] if c == "test_mode_active" else ({} if c == "estado_seguro" else d))
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_inactividad_ui.return_value = None
    ui.get_config_param.side_effect = lambda n: 5 if n == "tiempo_standby" else None
    ui.get_alarmas.return_value = []
    return ui


def _standby(ui, reloj):
    backend = MagicMock()
    s = Standby(ui, backend, reloj=reloj, ejecutar=lambda t: t(), iniciar=False)
    return s, backend


def test_modo_prueba_impide_el_standby_aunque_pase_el_tiempo():
    reloj, prueba = _Reloj(), {"v": False}
    s, _ = _standby(_ui(prueba), reloj)
    s.evaluar()
    reloj.t += 30                    # fuera de la gracia de arranque
    prueba["v"] = True
    s.evaluar()
    assert s.activo is False
    reloj.t += 3600
    s.evaluar()
    assert s.activo is False


def test_entrar_al_modo_prueba_cuenta_como_actividad():
    reloj, prueba = _Reloj(), {"v": False}
    s, backend = _standby(_ui(prueba), reloj)
    s.evaluar()
    reloj.t += 30
    backend.post.reset_mock()
    prueba["v"] = True
    s.evaluar()
    backend.post.assert_called_with("/ui/activity")
    assert s._ultima_local == reloj.t


def test_al_salir_del_modo_prueba_rige_todo_el_tiempo_de_standby():
    reloj, prueba = _Reloj(), {"v": False}
    s, _ = _standby(_ui(prueba), reloj)
    s.evaluar()
    reloj.t += 30
    prueba["v"] = True
    s.evaluar()
    reloj.t += 600
    prueba["v"] = False
    s.evaluar()
    assert s.activo is False         # la salida reinicia el conteo
    reloj.t += 5 * 60 + 1
    s.evaluar()
    assert s.activo is True
