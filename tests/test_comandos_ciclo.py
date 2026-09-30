# tests/test_comandos_ciclo.py
#
# ComandoIniciarCiclo (ui_qml/bridge/comandos_ciclo.py): misma lógica que el
# "Iniciar ciclo" de tkinter (_upd_listo + start_cycle). UIServiceBackend
# simulado; el "hilo" se inyecta.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.ui_qml.bridge.comandos_ciclo import ComandoIniciarCiclo


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Puente:
    def __init__(self, listo=True, connected=True):
        self.listoParaCiclo = listo
        self.connected = connected


class _EjecutorManual:
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self):
        self.tareas.pop(0)()
        QCoreApplication.processEvents()


def _ui(ok=True):
    ui = MagicMock(spec=UIServiceBackend)
    ui.start_cycle.return_value = ok
    return ui


def test_listo_envia_start_cycle():
    ui, ejecutor = _ui(), _EjecutorManual()
    comando = ComandoIniciarCiclo(_Puente(), ui, ejecutar=ejecutor)
    comando.iniciar()
    assert comando.ocupado is True
    ejecutor.correr()
    ui.start_cycle.assert_called_once_with()
    assert comando.ocupado is False


@pytest.mark.parametrize("puente", [_Puente(listo=False), _Puente(connected=False)])
def test_no_listo_o_sin_conexion_no_envia_nada(puente):
    ui, ejecutor = _ui(), _EjecutorManual()
    ComandoIniciarCiclo(puente, ui, ejecutar=ejecutor).iniciar()
    assert ejecutor.tareas == []
    ui.start_cycle.assert_not_called()


def test_segundo_toque_en_curso_se_ignora():
    ui, ejecutor = _ui(), _EjecutorManual()
    comando = ComandoIniciarCiclo(_Puente(), ui, ejecutar=ejecutor)
    comando.iniciar()
    comando.iniciar()
    assert len(ejecutor.tareas) == 1


def test_rechazo_solo_se_registra_como_en_tkinter(caplog):
    ui, ejecutor = _ui(ok=False), _EjecutorManual()
    comando = ComandoIniciarCiclo(_Puente(), ui, ejecutar=ejecutor)
    comando.iniciar()
    ejecutor.correr()
    assert comando.ocupado is False
    assert "rechazó el inicio del ciclo" in caplog.text


def test_excepcion_se_trata_como_rechazo():
    ui, ejecutor = _ui(), _EjecutorManual()
    ui.start_cycle.side_effect = RuntimeError("x")
    comando = ComandoIniciarCiclo(_Puente(), ui, ejecutar=ejecutor)
    comando.iniciar()
    ejecutor.correr()
    assert comando.ocupado is False
