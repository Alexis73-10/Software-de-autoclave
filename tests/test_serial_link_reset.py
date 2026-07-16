from unittest.mock import patch, MagicMock
from autoclave.protocols.serial_link import SerialLink

_WINERROR_31 = Exception(
    "Cannot configure port, something went wrong. Original message: "
    "PermissionError(13, 'Uno de los dispositivos conectados al sistema no funciona.', None, 31)"
)
_WINERROR_5 = Exception(
    "could not open port 'COM4': PermissionError(13, 'Acceso denegado.', None, 5)"
)


def _make_link():
    link = SerialLink()
    link._scan_ports = lambda: "COM4"
    return link


def test_reset_se_dispara_tras_threshold_fallos_consecutivos():
    link = _make_link()

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_31), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD - 1):
            assert link._connect() is False
        mock_reset.assert_not_called()

        assert link._connect() is False
        mock_reset.assert_called_once_with("COM4")


def test_reset_solo_se_dispara_una_vez():
    link = _make_link()

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_31), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD * 2):
            link._connect()

        mock_reset.assert_called_once()


def test_reset_no_se_dispara_tras_conexion_exitosa():
    link = _make_link()
    fake_serial = MagicMock()

    with patch("autoclave.protocols.serial_link.serial.Serial", return_value=fake_serial):
        assert link._connect() is True

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_31), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD * 2):
            link._connect()

        mock_reset.assert_not_called()


def test_falla_distinta_a_winerror_31_no_dispara_reset():
    link = _make_link()

    with patch("autoclave.protocols.serial_link.serial.Serial", side_effect=_WINERROR_5), \
         patch("autoclave.protocols.serial_link.device_reset.reset_usb_serial_device") as mock_reset:
        for _ in range(SerialLink.GEN_FAILURE_RESET_THRESHOLD * 3):
            link._connect()

        mock_reset.assert_not_called()
