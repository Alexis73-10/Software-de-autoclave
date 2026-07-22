import sys
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QPointF


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _click(widget):
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)


def test_temp_card_click_navega_con_payload_correcto():
    from autoclave.ui_pyside.views.entrdas_salidas.io_temp import TemperaturasView
    calls = []
    view = TemperaturasView(nav_callback=lambda name, payload=None: calls.append((name, payload)))
    _click(view._cards["temp_camara"])
    assert calls == [("calibracion_sensor", {"tipo": "temperature", "sensor": "temp_camara"})]


def test_pres_card_click_navega_con_payload_correcto():
    from autoclave.ui_pyside.views.entrdas_salidas.io_pres import PresionesView
    calls = []
    view = PresionesView(nav_callback=lambda name, payload=None: calls.append((name, payload)))
    _click(view._cards["pres_chaqueta"])
    assert calls == [("calibracion_sensor", {"tipo": "pressure", "sensor": "pres_chaqueta"})]
