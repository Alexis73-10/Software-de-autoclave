import sys
import logging


def test_print_raw_sin_pywin32_loguea_warning(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "win32print", None)
    from autoclave.devices.printer.win32_printer import print_raw
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.win32_printer"):
        print_raw("texto de prueba")
    assert "win32print no disponible" in caplog.text
