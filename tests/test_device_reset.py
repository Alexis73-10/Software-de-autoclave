from unittest.mock import patch, MagicMock
from autoclave.protocols import device_reset


def test_is_device_not_functioning_error_true_para_winerror_31():
    exc = Exception(
        "Cannot configure port, something went wrong. Original message: "
        "PermissionError(13, 'Uno de los dispositivos conectados al sistema no funciona.', None, 31)"
    )
    assert device_reset.is_device_not_functioning_error(exc) is True


def test_is_device_not_functioning_error_false_para_winerror_5():
    exc = Exception(
        "could not open port 'COM4': PermissionError(13, 'Acceso denegado.', None, 5)"
    )
    assert device_reset.is_device_not_functioning_error(exc) is False


def test_is_device_not_functioning_error_false_para_excepcion_generica():
    exc = Exception(
        "could not open port 'COM9': FileNotFoundError(2, 'El sistema no puede "
        "encontrar el archivo especificado.', None, 2)"
    )
    assert device_reset.is_device_not_functioning_error(exc) is False


def test_reset_usb_serial_device_true_cuando_powershell_reporta_ok():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="OK\r\n", returncode=0)
        assert device_reset.reset_usb_serial_device("COM4") is True


def test_reset_usb_serial_device_false_cuando_no_encuentra_dispositivo():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="NOTFOUND\r\n", returncode=0)
        assert device_reset.reset_usb_serial_device("COM4") is False


def test_reset_usb_serial_device_false_cuando_subprocess_falla():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("powershell no disponible")
        assert device_reset.reset_usb_serial_device("COM4") is False


def test_reset_usb_serial_device_incluye_nombre_de_puerto_en_el_comando():
    with patch("autoclave.protocols.device_reset.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="OK\r\n", returncode=0)
        device_reset.reset_usb_serial_device("COM4")

        args = mock_run.call_args[0][0]
        assert args[0] == "powershell"
        script = args[-1]
        assert "COM4" in script
