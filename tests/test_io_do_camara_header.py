import sys
from unittest.mock import patch
import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _status(temp_camara=None, pres_camara=None):
    return {
        "sensors": {
            "digital_outputs": {},
            "temperature": {"camara": temp_camara},
            "pressure": {"camara": pres_camara},
        },
        "test_mode_active": False,
    }


def test_salidas_digitales_view_tiene_labels_de_camara():
    from autoclave.ui_pyside.views.entrdas_salidas.io_do import SalidasDigitalesView

    view = SalidasDigitalesView(nav_callback=lambda x: None)
    assert view._lbl_temp_camara.text() == "🌡️ -- °C"
    assert view._lbl_pres_camara.text() == "📊 -- kPa"


def test_refresh_actualiza_temperatura_y_presion_de_camara():
    from autoclave.ui_pyside.views.entrdas_salidas.io_do import SalidasDigitalesView

    view = SalidasDigitalesView(nav_callback=lambda x: None)
    with patch.object(view._client, "get_status", return_value=_status(45.2, 12.3)):
        view._refresh()

    assert view._lbl_temp_camara.text() == "🌡️ 45.2 °C"
    assert view._lbl_pres_camara.text() == "📊 12.30 kPa"


def test_refresh_con_sensor_none_muestra_guiones():
    from autoclave.ui_pyside.views.entrdas_salidas.io_do import SalidasDigitalesView

    view = SalidasDigitalesView(nav_callback=lambda x: None)
    with patch.object(view._client, "get_status", return_value=_status(None, None)):
        view._refresh()

    assert view._lbl_temp_camara.text() == "🌡️ -- °C"
    assert view._lbl_pres_camara.text() == "📊 -- kPa"


def test_refresh_sin_backend_muestra_guiones_en_camara():
    from autoclave.ui_pyside.views.entrdas_salidas.io_do import SalidasDigitalesView

    view = SalidasDigitalesView(nav_callback=lambda x: None)
    with patch.object(view._client, "get_status", side_effect=ConnectionError("sin backend")):
        view._refresh()

    assert view._lbl_temp_camara.text() == "🌡️ -- °C"
    assert view._lbl_pres_camara.text() == "📊 -- kPa"
