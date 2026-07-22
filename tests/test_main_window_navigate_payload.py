import sys
import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_navigate_to_sin_payload_no_falla():
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    win.navigate_to("home")
    assert win._stack.currentWidget() is win._home


def test_navigate_to_con_payload_llama_set_context():
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    calls = []
    win._calibracion_sensor.set_context = lambda **kw: calls.append(kw)
    win.navigate_to("calibracion_sensor", {"tipo": "temperature", "sensor": "temp_camara"})
    assert calls == [{"tipo": "temperature", "sensor": "temp_camara"}]
    assert win._stack.currentWidget() is win._calibracion_sensor


def test_navigate_to_payload_none_no_llama_set_context():
    from autoclave.ui_pyside.main_window import MainWindowFluent
    win = MainWindowFluent()
    calls = []
    win._calibracion_sensor.set_context = lambda **kw: calls.append(kw)
    win.navigate_to("calibracion_sensor")
    assert calls == []
