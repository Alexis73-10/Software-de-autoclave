import sys
import logging


def test_print_raw_sin_pywin32_loguea_warning(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "win32print", None)
    from autoclave.devices.printer.win32_printer import print_raw
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.win32_printer"):
        print_raw("texto de prueba")
    assert "win32print no disponible" in caplog.text


# ── estado de la impresora antes de reimprimir (Historial) ───────────────

import pytest
from types import SimpleNamespace


def _win32(status=0, atributos=0x40, abre=True):
    def abrir(nombre):
        if not abre:
            raise OSError("impresora no encontrada")
        return "h"
    return SimpleNamespace(
        OpenPrinter=abrir,
        GetPrinter=lambda h, nivel: {"Status": status, "Attributes": atributos},
        ClosePrinter=lambda h: None)


@pytest.mark.parametrize("win32, estado", [
    (_win32(), "lista"),
    (_win32(atributos=0x640), "desconectada"),     # WORK_OFFLINE: USB desenchufada
    (_win32(status=0x80), "desconectada"),         # PRINTER_STATUS_OFFLINE
    (_win32(status=0x1000), "desconectada"),       # PRINTER_STATUS_NOT_AVAILABLE
    (_win32(status=0x10), "sin_papel"),
    (_win32(status=0x02), "error"),
    (_win32(status=0x08), "error"),                # atasco
    (_win32(status=0x400000), "error"),            # tapa abierta
    (_win32(status=0x01), "error"),                # en pausa
    (_win32(abre=False), "no_instalada"),
])
def test_estado_impresora(monkeypatch, win32, estado):
    monkeypatch.setitem(sys.modules, "win32print", win32)
    from autoclave.devices.printer.win32_printer import estado_impresora
    assert estado_impresora("Impresora_Termica") == estado


def test_estado_impresora_sin_pywin32(monkeypatch):
    monkeypatch.setitem(sys.modules, "win32print", None)
    from autoclave.devices.printer.win32_printer import estado_impresora
    assert estado_impresora("Impresora_Termica") == "no_instalada"
