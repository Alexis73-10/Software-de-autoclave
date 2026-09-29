# tests/test_formato_numerico.py
import pytest
from autoclave.ui_qml.domain.formato_numerico import formatear_decimal, parsear_decimal


# ── formatear_decimal ────────────────────────────────────────────────────

def test_formatea_con_coma_como_separador_decimal():
    assert formatear_decimal(134.0, 1) == "134,0"


def test_formatea_negativo_con_coma():
    assert formatear_decimal(-5.25, 2) == "-5,25"


def test_formatea_sin_decimales():
    assert formatear_decimal(134.0, 0) == "134"


def test_formatea_redondea_a_la_cantidad_de_decimales_pedida():
    assert formatear_decimal(134.567, 1) == "134,6"


def test_formatea_cero():
    assert formatear_decimal(0, 1) == "0,0"


# ── parsear_decimal ──────────────────────────────────────────────────────

def test_parsea_coma_a_float():
    assert parsear_decimal("134,5") == 134.5


def test_parsea_negativo():
    assert parsear_decimal("-12,3") == -12.3


def test_parsea_entero_sin_coma():
    assert parsear_decimal("134") == 134.0


def test_parsea_rechaza_punto_decimal():
    # El teclado numérico no tiene tecla de punto (D-18/§13.1) — un punto que
    # llegue aquí es una entrada inválida, no un separador alternativo.
    with pytest.raises(ValueError):
        parsear_decimal("134.5")


def test_parsea_rechaza_texto_no_numerico():
    with pytest.raises(ValueError):
        parsear_decimal("abc")


def test_parsea_rechaza_cadena_vacia():
    with pytest.raises(ValueError):
        parsear_decimal("")


# ── round-trip ────────────────────────────────────────────────────────────

def test_round_trip_formatear_parsear():
    assert parsear_decimal(formatear_decimal(134.5, 2)) == 134.5
