import sys
import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_home_view_tarjeta_impresion_general_navega_a_impresion_menu():
    from autoclave.ui_pyside.views.home import HomeView
    from qfluentwidgets import SubtitleLabel

    nav_calls = []
    view = HomeView(nav_callback=nav_calls.append)

    label = next(
        lbl for lbl in view.findChildren(SubtitleLabel)
        if "Impresión General" in lbl.text()
    )
    card = label.parentWidget()
    # mousePressEvent está sobreescrito directamente en la card (ver home.py)
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF, Qt

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.mousePressEvent(event)
    assert nav_calls == ["impresion_menu"]
