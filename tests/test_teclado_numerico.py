# tests/test_teclado_numerico.py
#
# Lógica pura del teclado numérico en pantalla (§13.1 del plan de interfaz
# dual-pantalla): acumulación de texto tecla-a-tecla y validación de rango
# en vivo, en `domain` — nunca dentro del componente QML (§13.3).

from autoclave.ui_qml.domain.teclado_numerico import (
    agregar_digito,
    agregar_coma,
    alternar_signo,
    borrar,
    evaluar,
    EstadoTecladoNumerico,
)


# ── agregar_digito ───────────────────────────────────────────────────────

def test_agregar_digito_concatena():
    assert agregar_digito("12", "3") == "123"


def test_agregar_digito_en_vacio():
    assert agregar_digito("", "5") == "5"


# ── agregar_coma ─────────────────────────────────────────────────────────

def test_agregar_coma():
    assert agregar_coma("134") == "134,"


def test_agregar_coma_una_sola_vez():
    # Ya hay una coma -> segunda pulsación es no-op (evita "134,5,6").
    assert agregar_coma("134,5") == "134,5"


# ── alternar_signo ───────────────────────────────────────────────────────

def test_alternar_signo_agrega_negativo_si_permitido():
    assert alternar_signo("12", permite_negativo=True) == "-12"


def test_alternar_signo_quita_negativo_si_ya_presente():
    assert alternar_signo("-12", permite_negativo=True) == "12"


def test_alternar_signo_no_hace_nada_si_no_permitido():
    # Campo que no admite negativos (D-18 §13.1) -> tecla de signo inerte.
    assert alternar_signo("12", permite_negativo=False) == "12"


# ── borrar ───────────────────────────────────────────────────────────────

def test_borrar_quita_ultimo_caracter():
    assert borrar("123") == "12"


def test_borrar_en_vacio_no_rompe():
    assert borrar("") == ""


# ── evaluar ──────────────────────────────────────────────────────────────

def test_evaluar_texto_vacio_es_invalido():
    r = evaluar("", minimo=0, maximo=100)
    assert r == EstadoTecladoNumerico(texto="", valor=None, valido=False)


def test_evaluar_dentro_de_rango_es_valido():
    r = evaluar("50", minimo=0, maximo=100)
    assert r.valido is True
    assert r.valor == 50.0


def test_evaluar_fuera_de_rango_por_debajo_es_invalido():
    r = evaluar("-5", minimo=0, maximo=100)
    assert r.valido is False
    assert r.valor == -5.0  # se parseó, pero está fuera de rango


def test_evaluar_fuera_de_rango_por_encima_es_invalido():
    r = evaluar("150", minimo=0, maximo=100)
    assert r.valido is False
    assert r.valor == 150.0


def test_evaluar_sin_limites_solo_requiere_parseo_valido():
    r = evaluar("134,5")
    assert r.valido is True
    assert r.valor == 134.5


def test_evaluar_texto_incompleto_signo_solo_es_invalido():
    r = evaluar("-", minimo=-100, maximo=100)
    assert r.valido is False
    assert r.valor is None


def test_evaluar_texto_incompleto_coma_sola_es_invalida():
    r = evaluar(",", minimo=0, maximo=100)
    assert r.valido is False
    assert r.valor is None


def test_evaluar_limite_inclusivo():
    assert evaluar("100", minimo=0, maximo=100).valido is True
    assert evaluar("0", minimo=0, maximo=100).valido is True
