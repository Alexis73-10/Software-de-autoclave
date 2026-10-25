# tests/test_comandos_ciclo_en_curso.py
#
# ComandosCicloEnCurso (ui_qml/bridge/comandos_ciclo_en_curso.py): CANCELAR
# (POST /cycle/abort) y CONFIRMAR (POST /cycle/acknowledge) de la pantalla de
# ciclo en curso (planeacion_pantalla_ciclo_en_curso.md §10). UIServiceBackend
# simulado; el "hilo" se inyecta.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.cliente.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.comandos_ciclo_en_curso import ComandosCicloEnCurso


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Puente:
    def __init__(self, connected=True):
        self.connected = connected


class _Ejecutor:
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self):
        self.tareas.pop(0)()
        QCoreApplication.processEvents()


def _ui(abort=True, ack=True):
    ui = MagicMock(spec=UIServiceBackend)
    ui.abort_cycle.return_value = abort
    ui.acknowledge_cycle.return_value = ack
    return ui


def _nuevo(ui, conectado=True):
    ejecutor = _Ejecutor()
    return ComandosCicloEnCurso(_Puente(conectado), ui, ejecutar=ejecutor), ejecutor


def test_cancelar_envia_abort_y_avisa():
    ui = _ui()
    c, ejecutor = _nuevo(ui)
    terminados = []
    c.terminado.connect(lambda accion, ok: terminados.append((accion, ok)))
    c.cancelar()
    assert c.ocupado is True
    ejecutor.correr()
    ui.abort_cycle.assert_called_once_with()
    assert c.ocupado is False
    assert c.error == ""
    assert terminados == [("cancelar", True)]


def test_cancelar_rechaza_doble_toque():
    ui = _ui()
    c, ejecutor = _nuevo(ui)
    c.cancelar()
    c.cancelar()
    c.confirmar()
    assert len(ejecutor.tareas) == 1


def test_cancelar_fallido_deja_error_y_no_da_por_cancelado():
    ui = _ui(abort=False)
    c, ejecutor = _nuevo(ui)
    terminados = []
    c.terminado.connect(lambda accion, ok: terminados.append((accion, ok)))
    c.cancelar()
    ejecutor.correr()
    assert c.error == "cancelar"
    assert c.ocupado is False
    assert terminados == [("cancelar", False)]


def test_excepcion_inesperada_cuenta_como_fallo():
    ui = _ui()
    ui.abort_cycle.side_effect = RuntimeError("x")
    c, ejecutor = _nuevo(ui)
    c.cancelar()
    ejecutor.correr()
    assert c.error == "cancelar"


def test_sin_conexion_no_envia_y_avisa():
    ui = _ui()
    c, ejecutor = _nuevo(ui, conectado=False)
    c.cancelar()
    assert ejecutor.tareas == []
    assert c.error == "cancelar"
    ui.abort_cycle.assert_not_called()


def test_confirmar_envia_acknowledge():
    ui = _ui()
    c, ejecutor = _nuevo(ui)
    c.confirmar()
    ejecutor.correr()
    ui.acknowledge_cycle.assert_called_once_with()
    assert c.error == ""


def test_confirmar_fallido_deja_error():
    ui = _ui(ack=False)
    c, ejecutor = _nuevo(ui)
    c.confirmar()
    ejecutor.correr()
    assert c.error == "confirmar"


def test_nuevo_intento_limpia_el_error():
    ui = _ui(abort=False)
    c, ejecutor = _nuevo(ui)
    c.cancelar(); ejecutor.correr()
    assert c.error == "cancelar"
    ui.abort_cycle.return_value = True
    c.cancelar()
    assert c.error == ""
    ejecutor.correr()
    assert c.error == ""


def test_descartar_error():
    ui = _ui(abort=False)
    c, ejecutor = _nuevo(ui)
    c.cancelar(); ejecutor.correr()
    c.descartarError()
    assert c.error == ""
