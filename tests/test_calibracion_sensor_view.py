import sys
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_view():
    from autoclave.ui_pyside.views.entrdas_salidas.calibracion_sensor import CalibracionSensorView
    calls = []
    view = CalibracionSensorView(nav_callback=lambda *a, **kw: calls.append((a, kw)))
    return view, calls


def test_sin_sesion_bloquea_formulario():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.logout()
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.0, "offset": 0.0, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
    assert view._formulario_visible() is False


def test_rol_operador_bloquea_formulario():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Juan", "usuario": "juan", "rol": "operador"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.0, "offset": 0.0, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
    assert view._formulario_visible() is False
    SessionManager.logout()


def test_rol_admin_habilita_formulario_y_muestra_info():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False,
            "last_change": {"usuario": "tecnico1", "timestamp": "2026-07-20 10:00"},
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
    assert view._formulario_visible() is True
    assert "1.3466" in view._lbl_info.text()
    assert "tecnico1" in view._lbl_info.text()
    SessionManager.logout()


def test_preview_se_calcula_localmente_sin_llamar_backend():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
        view._input_shown_low.setValue(12.0)
        view._input_real_low.setValue(9.54)
        view._input_shown_high.setValue(322.0)
        view._input_real_high.setValue(300.0)
        view._on_inputs_changed()
        mock_client.save_calibration.assert_not_called()
    assert round(view._preview_gain, 6) == pytest.approx(1.261721, abs=1e-6)
    assert view._btn_guardar.isEnabled() is True
    SessionManager.logout()


def test_preview_invalida_deshabilita_guardar():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False, "last_change": None,
        }
        view.set_context(tipo="pressure", sensor="pres_camara")
        view._input_shown_low.setValue(12.0)
        view._input_real_low.setValue(9.54)
        view._input_shown_high.setValue(12.0)   # igual al bajo -> invalido
        view._input_real_high.setValue(300.0)
        view._on_inputs_changed()
    assert view._btn_guardar.isEnabled() is False
    SessionManager.logout()


def test_guardar_llama_save_calibration_con_usuario():
    from autoclave.ui_pyside.services.session_manager import SessionManager
    SessionManager.login({"id": 1, "nombre": "Tecnico Uno", "usuario": "tec1", "rol": "tecnico"})
    view, _ = _make_view()
    with patch.object(view, "_client") as mock_client:
        mock_client.get_calibration.return_value = {
            "gain": 1.3466, "offset": -67.11, "poly": None, "is_poly": False, "last_change": None,
        }
        mock_client.save_calibration.return_value = {"ok": True, "gain": 1.261721, "offset": -64.583518}
        view.set_context(tipo="pressure", sensor="pres_camara")
        view._input_shown_low.setValue(12.0)
        view._input_real_low.setValue(9.54)
        view._input_shown_high.setValue(322.0)
        view._input_real_high.setValue(300.0)
        view._on_inputs_changed()
        view._on_guardar()
        mock_client.save_calibration.assert_called_once_with(
            "pressure", "pres_camara",
            {
                "shown_low": 12.0, "real_low": 9.54,
                "shown_high": 322.0, "real_high": 300.0,
                "usuario": "Tecnico Uno",
            },
        )
    SessionManager.logout()
