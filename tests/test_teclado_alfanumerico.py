# tests/test_teclado_alfanumerico.py
#
# Lógica pura del teclado alfanumérico en pantalla (§13.2): acumulación de
# texto, alternancia mayúsculas/minúsculas y capa de símbolos. Vive en
# domain (§13.3) — el componente QML solo llama estas funciones.

from autoclave.ui_qml.domain.teclado_alfanumerico import (
    agregar_caracter,
    borrar,
    alternar_mayusculas,
    alternar_capa_simbolos,
    transformar_caracter,
    FILAS_QWERTY_ES,
    FILAS_SIMBOLOS,
)


# ── agregar_caracter ─────────────────────────────────────────────────────

def test_agregar_caracter_concatena():
    assert agregar_caracter("ho", "l") == "hol"


def test_agregar_caracter_en_vacio():
    assert agregar_caracter("", "a") == "a"


# ── borrar ───────────────────────────────────────────────────────────────

def test_borrar_quita_ultimo_caracter():
    assert borrar("hola") == "hol"


def test_borrar_en_vacio_no_rompe():
    assert borrar("") == ""


# ── alternar_mayusculas ──────────────────────────────────────────────────

def test_alternar_mayusculas_activa():
    assert alternar_mayusculas(False) is True


def test_alternar_mayusculas_desactiva():
    assert alternar_mayusculas(True) is False


# ── alternar_capa_simbolos ───────────────────────────────────────────────

def test_alternar_capa_simbolos_activa():
    assert alternar_capa_simbolos(False) is True


def test_alternar_capa_simbolos_desactiva():
    assert alternar_capa_simbolos(True) is False


# ── transformar_caracter ─────────────────────────────────────────────────

def test_transformar_caracter_mayuscula():
    assert transformar_caracter("q", mayusculas=True) == "Q"


def test_transformar_caracter_minuscula():
    assert transformar_caracter("Q", mayusculas=False) == "q"


def test_transformar_caracter_enie_mayuscula():
    # ñ es obligatoria en el teclado (§13.2) y no debe tratarse distinto.
    assert transformar_caracter("ñ", mayusculas=True) == "Ñ"


def test_transformar_caracter_simbolo_no_cambia():
    assert transformar_caracter("@", mayusculas=True) == "@"
    assert transformar_caracter("1", mayusculas=True) == "1"


# ── distribución QWERTY español ──────────────────────────────────────────

def test_filas_qwerty_es_tienen_enie_sin_tildes():
    texto = "".join(FILAS_QWERTY_ES)
    assert "ñ" in texto
    # Sin tildes (D-18/§13.2): ninguna vocal acentuada en la distribución.
    assert not any(c in texto for c in "áéíóúÁÉÍÓÚ")


def test_filas_qwerty_es_veintiseis_letras():
    total = sum(len(fila) for fila in FILAS_QWERTY_ES)
    assert total == 27  # 26 letras del alfabeto + ñ


def test_filas_simbolos_incluye_arroba():
    texto = "".join(FILAS_SIMBOLOS)
    assert "@" in texto
