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


def test_di_card_activo_muestra_verde():
    from autoclave.ui_pyside.views.io_di import _DiCard
    card = _DiCard("aire_comprimido")
    card.set_value(1)
    assert "ACTIVO" in card._lbl_state.text()


def test_di_card_inactivo_muestra_gris():
    from autoclave.ui_pyside.views.io_di import _DiCard
    card = _DiCard("presion_agua")
    card.set_value(0)
    assert "INACTIVO" in card._lbl_state.text()


def test_entradas_digitales_view_tiene_14_cards():
    from autoclave.ui_pyside.views.io_di import EntradasDigitalesView
    view = EntradasDigitalesView(nav_callback=lambda x: None)
    assert len(view._cards) == 14


def test_temp_card_muestra_valor_con_decimal():
    from autoclave.ui_pyside.views.io_temp import _TempCard
    card = _TempCard("temp_camara")
    card.set_value(121.5)
    assert "121.5 °C" in card._lbl_value.text()


def test_temp_card_none_muestra_guiones():
    from autoclave.ui_pyside.views.io_temp import _TempCard
    card = _TempCard("temp_ref")
    card.set_value(None)
    assert "---" in card._lbl_value.text()


def test_temperaturas_view_tiene_6_cards():
    from autoclave.ui_pyside.views.io_temp import TemperaturasView
    view = TemperaturasView(nav_callback=lambda x: None)
    assert len(view._cards) == 6


def test_pres_card_muestra_valor_con_dos_decimales():
    from autoclave.ui_pyside.views.io_pres import _PresCard
    card = _PresCard("pres_camara")
    card.set_value(2.15)
    assert "2.15 bar" in card._lbl_value.text()


def test_presiones_view_tiene_4_cards():
    from autoclave.ui_pyside.views.io_pres import PresionesView
    view = PresionesView(nav_callback=lambda x: None)
    assert len(view._cards) == 4
