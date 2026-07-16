from unittest.mock import patch, MagicMock
import requests
from autoclave import main as main_module


def test_hardware_connected_true_sin_alarma_no_hay_conexion():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"alarms": []}
    with patch("autoclave.main.requests.get", return_value=resp):
        assert main_module._hardware_connected() is True


def test_hardware_connected_false_con_alarma_no_hay_conexion():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"alarms": [{"id": "NO_HAY_CONEXION"}]}
    with patch("autoclave.main.requests.get", return_value=resp):
        assert main_module._hardware_connected() is False


def test_hardware_connected_false_si_status_no_responde_200():
    resp = MagicMock(status_code=500)
    with patch("autoclave.main.requests.get", return_value=resp):
        assert main_module._hardware_connected() is False


def test_hardware_connected_false_si_request_lanza_excepcion():
    with patch("autoclave.main.requests.get", side_effect=requests.RequestException("boom")):
        assert main_module._hardware_connected() is False
