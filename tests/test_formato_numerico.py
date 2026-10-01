# tests/test_formato_numerico.py
#
# Punto decimal en toda la interfaz, entrada y presentación (TEC-D14 de
# planeacion_teclados_qml.md, que revoca D-18/D-19 de planeacion_ui_dual_pantalla.md).
import pytest
from autoclave.ui_qml.domain.formato_numerico import formatear_decimal, parsear_decimal


# ── formatear_decimal ────────────────────────────────────────────────────

def test_formatea_con_punto_como_separador_decimal():
    assert formatear_decimal(134.0, 1) == "134.0"


def test_formatea_negativo_con_punto():
    assert formatear_decimal(-5.25, 2) == "-5.25"


def test_formatea_sin_decimales():
    assert formatear_decimal(134.0, 0) == "134"


def test_formatea_redondea_a_la_cantidad_de_decimales_pedida():
    assert formatear_decimal(134.567, 1) == "134.6"


def test_formatea_cero():
    assert formatear_decimal(0, 1) == "0.0"


def test_formatea_nunca_usa_coma():
    assert "," not in formatear_decimal(1234.5, 2)


# ── parsear_decimal ──────────────────────────────────────────────────────

def test_parsea_punto_a_float():
    assert parsear_decimal("134.5") == 134.5


def test_parsea_negativo():
    assert parsear_decimal("-12.3") == -12.3


def test_parsea_entero_sin_punto():
    assert parsear_decimal("134") == 134.0


def test_parsea_rechaza_coma_decimal():
    # El teclado numérico no tiene tecla de coma (TEC-D02/TEC-D14) — una coma
    # que llegue aquí es una entrada inválida, no un separador alternativo.
    with pytest.raises(ValueError):
        parsear_decimal("134,5")


@pytest.mark.parametrize("texto", ["-", ".", "-."])
def test_parsea_rechaza_texto_parcial(texto):
    with pytest.raises(ValueError):
        parsear_decimal(texto)


@pytest.mark.parametrize("texto", ["1e3", "inf", "nan", "1_000", " 12", "12 ", "+5", "1.2.3", "--5"])
def test_parsea_rechaza_formas_que_float_aceptaria(texto):
    # float() acepta notación científica, inf/nan, guiones bajos, espacios y
    # signo +; nada de eso sale del teclado, así que se trata como inválido.
    with pytest.raises(ValueError):
        parsear_decimal(texto)


def test_parsea_rechaza_texto_no_numerico():
    with pytest.raises(ValueError):
        parsear_decimal("abc")


def test_parsea_rechaza_cadena_vacia():
    with pytest.raises(ValueError):
        parsear_decimal("")


# ── round-trip ────────────────────────────────────────────────────────────

def test_round_trip_formatear_parsear():
    assert parsear_decimal(formatear_decimal(134.5, 2)) == 134.5
