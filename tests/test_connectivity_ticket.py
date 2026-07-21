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


def test_ticket_usa_el_mismo_formato_corto_que_ticket_formatter():
    """connectivity_ticket.py debe usar el mismo estilo de divisor corto
    ("-" * 24, sin barras de 48 "=" ni título centrado) que ya está
    confirmado funcionando en ticket_formatter.py — el formato viejo con
    barras de 48 caracteres fue el que se abandonó ahí por dar problemas
    de impresión, y connectivity_ticket.py se había quedado con él."""
    texto = format_connectivity_ticket("TARJETA", False, datetime(2026, 7, 7, 14, 32, 10))
    lineas = texto.split("\n")
    assert "-" * 24 in lineas
    assert "=" * 48 not in texto
    assert "ESPECIFIKA" not in texto


def test_ticket_termina_con_avance_de_papel_para_corte():
    texto = format_connectivity_ticket("TARJETA", False, datetime(2026, 7, 7, 14, 32, 10))
    lineas = texto.split("\n")
    assert lineas[-5:] == [""] * 5
