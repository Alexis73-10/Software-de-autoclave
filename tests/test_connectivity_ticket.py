from datetime import datetime

from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket


def test_tarjeta_desconectada():
    texto = format_connectivity_ticket("TARJETA", False, datetime(2026, 7, 7, 14, 32, 10))
    assert "TARJETA: DESCONECTADA" in texto
    assert "2026-07-07 14:32:10" in texto


def test_tarjeta_reconectada():
    texto = format_connectivity_ticket("TARJETA", True, datetime(2026, 7, 7, 14, 33, 0))
    assert "TARJETA: RECONECTADA" in texto


def test_backend_sin_respuesta():
    texto = format_connectivity_ticket("BACKEND", False, datetime(2026, 7, 7, 14, 34, 0))
    assert "BACKEND: SIN RESPUESTA" in texto


def test_backend_reconectado():
    texto = format_connectivity_ticket("BACKEND", True, datetime(2026, 7, 7, 14, 35, 0))
    assert "BACKEND: RECONECTADO" in texto


def test_ticket_usa_ancho_48_y_separador():
    texto = format_connectivity_ticket("TARJETA", False, datetime(2026, 7, 7, 14, 32, 10))
    lineas = texto.split("\n")
    assert lineas[0] == "=" * 48
    assert lineas[2] == "=" * 48
