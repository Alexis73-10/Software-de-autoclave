import sys
import pytest

# QApplication debe existir antes de crear cualquier widget
@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_format_name_convierte_snake_case():
    from autoclave.ui_pyside.views._io_base import _format_name
    assert _format_name("aire_comprimido") == "Aire Comprimido"
    assert _format_name("pres_camara") == "Pres Camara"
    assert _format_name("buzer_alarma") == "Buzer Alarma"


def test_monitor_base_instancia_sin_crash():
    from autoclave.ui_pyside.views._io_base import _MonitorBase
    view = _MonitorBase("TEST", "home", lambda x: None)
    assert view is not None


def test_monitor_base_timer_arranca_en_show():
    from autoclave.ui_pyside.views._io_base import _MonitorBase
    from unittest.mock import patch

    view = _MonitorBase("TEST", "home", lambda x: None)
    with patch.object(view, "_refresh") as mock_refresh:
        view.show()
        assert view._timer.isActive()
        view.hide()
        assert not view._timer.isActive()


def test_io_menu_instancia_sin_crash():
    from autoclave.ui_pyside.views.io_menu import EntradasSalidasMenuView
    nav_calls = []
    view = EntradasSalidasMenuView(nav_callback=nav_calls.append)
    assert view is not None


def test_io_menu_tiene_cuatro_botones():
    from autoclave.ui_pyside.views.io_menu import _IO_OPTIONS
    assert len(_IO_OPTIONS) == 4
