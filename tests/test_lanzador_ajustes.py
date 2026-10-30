# tests/test_lanzador_ajustes.py
#
# LanzadorAjustes (ui_qml/bridge/lanzador_ajustes.py): el engrane abre el menú
# de configuración PySide como subproceso. Popen y la ventana son simulados.

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from autoclave.ui_qml.bridge import lanzador_ajustes as mod
from autoclave.ui_qml.bridge.lanzador_ajustes import LanzadorAjustes


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class _Proc:
    def __init__(self):
        self.codigo = None
        self.pid = 1234
        self.terminate = MagicMock()

    def poll(self):
        return self.codigo


def _lanzador():
    procs = []

    def popen(cmd, env):
        p = _Proc()
        p.cmd, p.env = cmd, env
        procs.append(p)
        return p

    lanzador = LanzadorAjustes(popen=popen)
    lanzador.ventana = MagicMock()
    return lanzador, procs


def test_abrir_lanza_el_menu_y_oculta_la_ventana():
    lanzador, procs = _lanzador()
    lanzador.abrir()
    assert len(procs) == 1
    assert procs[0].cmd == [sys.executable, "-m", "autoclave.ui_pyside.app"]
    lanzador.ventana.hide.assert_called_once()
    assert lanzador.abierto is True


def test_segundo_toque_con_el_menu_abierto_se_ignora():
    lanzador, procs = _lanzador()
    lanzador.abrir()
    lanzador.abrir()
    assert len(procs) == 1


def test_al_cerrar_el_menu_la_ventana_vuelve_a_pantalla_completa():
    lanzador, procs = _lanzador()
    lanzador.abrir()
    lanzador._vigilar()                        # sigue abierto
    lanzador.ventana.showFullScreen.assert_not_called()

    procs[0].codigo = 0                        # el operador cerró el menú
    lanzador._vigilar()
    lanzador.ventana.showFullScreen.assert_called_once()
    assert lanzador.abierto is False
    assert not lanzador._timer.isActive()

    lanzador.abrir()                           # se puede volver a abrir
    assert len(procs) == 2


def test_error_al_lanzar_no_oculta_la_ventana():
    def popen(cmd, env):
        raise OSError("no existe")

    lanzador = LanzadorAjustes(popen=popen)
    lanzador.ventana = MagicMock()
    lanzador.abrir()
    lanzador.ventana.hide.assert_not_called()
    assert lanzador.abierto is False


def test_cerrar_la_ui_termina_el_menu_abierto():
    lanzador, procs = _lanzador()
    lanzador.abrir()
    lanzador.cerrar()
    procs[0].terminate.assert_called_once()


def test_build_congelado_usa_autoclave_settings_exe(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", os.path.join("C:\\app", "AutoclaveUI.exe"))
    assert mod.comando_ajustes() == [os.path.join("C:\\app", "AutoclaveSettings.exe")]


def test_entorno_sin_meipass2(monkeypatch):
    monkeypatch.setenv("_MEIPASS2", "x")
    assert "_MEIPASS2" not in mod.entorno_ajustes()
