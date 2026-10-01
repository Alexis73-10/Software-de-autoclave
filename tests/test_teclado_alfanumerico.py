# tests/test_teclado_alfanumerico.py
#
# Lógica pura del teclado alfanumérico en pantalla: acumulación de texto con
# longitud máxima, tecla Aa de un solo uso y tres capas (letras, dígitos,
# símbolos). Vive en domain — el componente QML solo llama estas funciones.
# Reglas: TEC-D03/D05/D09 y §7 de planeacion_teclados_qml.md.

import pytest

from autoclave.ui_qml.domain.teclado_alfanumerico import (
    CAPAS,
    CAPA_INICIAL,
    DIGITOS,
    FILAS_QWERTY_ES,
    SIMBOLOS,
    aa_al_abrir,
    aa_tras_borrar,
    agregar_caracter,
    alternar_mayusculas,
    borrar,
    caracter_permitido,
    pulsar_caracter,
    transformar_caracter,
)


# ── agregar_caracter ─────────────────────────────────────────────────────

def test_agregar_caracter_concatena():
    assert agregar_caracter("ho", "l") == "hol"


def test_agregar_caracter_en_vacio():
    assert agregar_caracter("", "a") == "a"


def test_agregar_caracter_respeta_longitud_maxima():
    assert agregar_caracter("abc", "d", longitud_maxima=3) == "abc"
    assert agregar_caracter("ab", "c", longitud_maxima=3) == "abc"


def test_longitud_maxima_cero_es_sin_limite():
    assert agregar_caracter("x" * 100, "y", longitud_maxima=0) == "x" * 100 + "y"


# ── borrar ───────────────────────────────────────────────────────────────

def test_borrar_quita_ultimo_caracter():
    assert borrar("hola") == "hol"


def test_borrar_en_vacio_no_rompe():
    assert borrar("") == ""


# ── mayúsculas ───────────────────────────────────────────────────────────

def test_alternar_mayusculas_activa():
    assert alternar_mayusculas(False) is True


def test_alternar_mayusculas_desactiva():
    assert alternar_mayusculas(True) is False


def test_transformar_caracter_mayuscula():
    assert transformar_caracter("q", mayusculas=True) == "Q"


def test_transformar_caracter_minuscula():
    assert transformar_caracter("Q", mayusculas=False) == "q"


def test_transformar_caracter_enie_mayuscula():
    assert transformar_caracter("ñ", mayusculas=True) == "Ñ"
    assert transformar_caracter("Ñ", mayusculas=False) == "ñ"


def test_transformar_caracter_simbolo_no_cambia():
    assert transformar_caracter("@", mayusculas=True) == "@"
    assert transformar_caracter("1", mayusculas=True) == "1"


# ── pulsar_caracter: Aa de un solo uso (TEC-D05) ─────────────────────────

def test_letra_con_aa_armada_sale_en_mayuscula_y_desarma():
    assert pulsar_caracter("", "j", mayusculas=True, longitud_maxima=30) == ("J", False)


def test_letra_con_aa_desarmada_sale_en_minuscula():
    assert pulsar_caracter("J", "u", mayusculas=False, longitud_maxima=30) == ("Ju", False)


def test_enie_sigue_la_misma_regla():
    assert pulsar_caracter("", "ñ", mayusculas=True, longitud_maxima=30) == ("Ñ", False)
    assert pulsar_caracter("Ñ", "ñ", mayusculas=False, longitud_maxima=30) == ("Ññ", False)


@pytest.mark.parametrize("caracter", ["7", "@", ".", " "])
def test_digitos_simbolos_y_espacio_no_consumen_aa(caracter):
    # Aa afecta solo a letras: la siguiente letra sigue saliendo en mayúscula.
    assert pulsar_caracter("", caracter, mayusculas=True, longitud_maxima=30) == (caracter, True)


def test_letra_bloqueada_por_longitud_no_consume_aa():
    assert pulsar_caracter("abc", "d", mayusculas=True, longitud_maxima=3) == ("abc", True)


@pytest.mark.parametrize("caracter", ["#", "$", "%", "&", "!", ",", ";", ":", "á", "é", "ü", "ab", ""])
def test_caracter_no_permitido_se_ignora(caracter):
    assert pulsar_caracter("x", caracter, mayusculas=True, longitud_maxima=30) == ("x", True)


# ── juego de caracteres (TEC-D03) ────────────────────────────────────────

def test_filas_qwerty_es_tienen_enie_sin_tildes():
    texto = "".join(FILAS_QWERTY_ES)
    assert "ñ" in texto
    assert not any(c in texto for c in "áéíóúÁÉÍÓÚüÜ")


def test_filas_qwerty_es_distribucion_del_disenador():
    # Capa de letras de la pág. 25 de la especificación.
    assert FILAS_QWERTY_ES == ("qwertyuiop", "asdfghjklñ", "zxcvbnm")


def test_digitos():
    assert DIGITOS == "0123456789"


def test_once_simbolos_exactos():
    assert SIMBOLOS == "@._-()?+*/="
    assert len(SIMBOLOS) == 11


@pytest.mark.parametrize("caracter", list("#$%&!,;:"))
def test_simbolos_eliminados_no_estan_permitidos(caracter):
    assert caracter_permitido(caracter) is False


def test_permitidos_letras_digitos_simbolos_y_espacio():
    for c in "".join(FILAS_QWERTY_ES) + "".join(FILAS_QWERTY_ES).upper() + DIGITOS + SIMBOLOS + " ":
        assert caracter_permitido(c) is True, c


def test_capas():
    assert CAPAS == ("letras", "digitos", "simbolos")
    assert CAPA_INICIAL == "letras"


# ── Aa se arma con el campo vacío (instrucción de Cristian, 2026-09-30) ──

def test_aa_se_arma_al_abrir_vacio():
    assert aa_al_abrir("") is True


def test_aa_no_se_arma_al_abrir_con_texto():
    assert aa_al_abrir("Ana") is False


def test_aa_se_arma_si_borrar_deja_el_campo_vacio():
    assert aa_tras_borrar("", mayusculas=False) is True


def test_aa_no_cambia_si_borrar_deja_texto():
    assert aa_tras_borrar("An", mayusculas=False) is False
    assert aa_tras_borrar("An", mayusculas=True) is True
