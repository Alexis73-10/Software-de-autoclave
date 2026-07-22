from unittest.mock import patch, MagicMock
from autoclave.ui.service_ui.backend_client import BackendClient


def test_get_calibration_llama_get_con_ruta_correcta():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"gain": 1.0, "offset": 0.0}
    mock_resp.raise_for_status.return_value = None
    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = client.get_calibration("temperature", "temp_camara")
    mock_get.assert_called_once_with(
        "http://localhost:8000/calibration/temperature/temp_camara", timeout=0.8
    )
    assert result == {"gain": 1.0, "offset": 0.0}


def test_save_calibration_llama_patch_con_body():
    client = BackendClient("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "gain": 1.26, "offset": -64.5}
    mock_resp.raise_for_status.return_value = None
    body = {"shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0}
    with patch("requests.patch", return_value=mock_resp) as mock_patch:
        result = client.save_calibration("pressure", "pres_camara", body)
    mock_patch.assert_called_once_with(
        "http://localhost:8000/calibration/pressure/pres_camara",
        json=body, timeout=0.8,
    )
    assert result == {"ok": True, "gain": 1.26, "offset": -64.5}
