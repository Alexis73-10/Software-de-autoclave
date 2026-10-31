# tests/test_teclado_numerico.py
#
# Lógica pura del teclado numérico en pantalla (§13.1 del plan de interfaz
# dual-pantalla): acumulación de texto tecla-a-tecla y validación de rango
# en vivo, en `domain` — nunca dentro del componente QML (§13.3).
# Punto decimal, nunca coma (TEC-D14 de planeacion_teclados_qml.md).

import pytest

from autoclave.ui_qml.domain.teclado_numerico import (
    agregar_digito,
    agregar_punto,
    alternar_signo,
    borrar,
    evaluar,
    permite_negativo,
    texto_inicial,
    texto_limite,
    EstadoTecladoNumerico,
)


# ── agregar_digito ───────────────────────────────────────────────────────

def test_agregar_digito_concatena():
    assert agregar_digito("12", "3") == "123"


def test_agregar_digito_en_vacio():
    assert agregar_digito("", "5") == "5"


def test_agregar_digito_respeta_decimales_permitidos():
    # decimales=1: "134.5" admite ya el máximo, un segundo decimal se ignora.
    assert agregar_digito("134.", "5", decimales=1) == "134.5"
    assert agregar_digito("134.5", "5", decimales=1) == "134.5"


def test_agregar_digito_sin_punto_no_limita_la_parte_entera():
    assert agregar_digito("1345", "6", decimales=0) == "13456"


def test_agregar_digito_sin_decimales_indicados_no_limita():
    # Sin `decimales` (compatibilidad con llamadas previas) no hay tope.
    assert agregar_digito("1.23", "4") == "1.234"


# ── agregar_punto ────────────────────────────────────────────────────────

def test_agregar_punto():
    assert agregar_punto("134", decimales=1) == "134."


def test_agregar_punto_una_sola_vez():
    # Ya hay un punto -> segunda pulsación es no-op (evita "134.5.6").
    assert agregar_punto("134.5", decimales=1) == "134.5"


def test_agregar_punto_bloqueado_si_el_parametro_es_entero():
    assert agregar_punto("134", decimales=0) == "134"


def test_agregar_punto_en_vacio_y_tras_signo():
    # Valores intermedios de camino a ".5" / "-.5" (§7).
    assert agregar_punto("", decimales=1) == "."
    assert agregar_punto("-", decimales=1) == "-."


# ── alternar_signo ───────────────────────────────────────────────────────

def test_alternar_signo_agrega_negativo_si_permitido():
    assert alternar_signo("12", permite_negativo=True) == "-12"


def test_alternar_signo_quita_negativo_si_ya_presente():
    assert alternar_signo("-12", permite_negativo=True) == "12"


def test_alternar_signo_no_hace_nada_si_no_permitido():
    # Campo que no admite negativos (§7) -> tecla de signo inerte.
    assert alternar_signo("12", permite_negativo=False) == "12"


def test_alternar_signo_en_vacio_deja_menos_pendiente():
    assert alternar_signo("", permite_negativo=True) == "-"


def test_alternar_signo_sobre_menos_pendiente_lo_quita():
    assert alternar_signo("-", permite_negativo=True) == ""


def test_alternar_signo_invierte_el_valor_completo_con_decimales():
    assert alternar_signo("134.5", permite_negativo=True) == "-134.5"
    assert alternar_signo("-.5", permite_negativo=True) == ".5"


# ── permite_negativo ─────────────────────────────────────────────────────

def test_permite_negativo_solo_si_minimo_es_negativo():
    # Bloqueada si minimo >= 0 (§7).
    assert permite_negativo(-100) is True
    assert permite_negativo(-0.1) is True
    assert permite_negativo(0) is False
    assert permite_negativo(5) is False


def test_permite_negativo_sin_minimo():
    assert permite_negativo(None) is True
    assert permite_negativo(float("-inf")) is True


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
    r = evaluar("134.5")
    assert r.valido is True
    assert r.valor == 134.5


def test_evaluar_texto_incompleto_signo_solo_es_invalido():
    r = evaluar("-", minimo=-100, maximo=100)
    assert r.valido is False
    assert r.valor is None


@pytest.mark.parametrize("texto", [".", "-."])
def test_evaluar_texto_incompleto_punto_es_invalido(texto):
    r = evaluar(texto, minimo=-100, maximo=100)
    assert r.valido is False
    assert r.valor is None


def test_evaluar_coma_es_invalida():
    # Sin coma en ninguna forma (TEC-D02/TEC-D14).
    r = evaluar("134,5")
    assert r.valido is False
    assert r.valor is None


def test_evaluar_limite_inclusivo():
    assert evaluar("100", minimo=0, maximo=100).valido is True
    assert evaluar("0", minimo=0, maximo=100).valido is True


# ── texto_inicial ────────────────────────────────────────────────────────

def test_texto_inicial_con_los_decimales_del_campo():
    assert texto_inicial(134.0, decimales=1) == "134.0"
    assert texto_inicial(134.0, decimales=0) == "134"


def test_texto_inicial_redondea_a_los_decimales_del_campo():
    assert texto_inicial(134.26, decimales=1) == "134.3"


def test_texto_inicial_negativo():
    assert texto_inicial(-5.0, decimales=1) == "-5.0"


def test_texto_inicial_sin_valor_queda_vacio():
    assert texto_inicial(None, decimales=1) == ""
    assert texto_inicial(float("nan"), decimales=1) == ""
    assert texto_inicial(float("inf"), decimales=1) == ""


def test_texto_inicial_no_acepta_booleanos():
    assert texto_inicial(True, decimales=0) == ""


# ── texto_limite (rango mostrado al confirmar fuera de rango, PROV-04) ─

def test_texto_limite_con_punto_y_decimales_del_campo():
    assert texto_limite(105, decimales=1) == "105.0"
    assert texto_limite(-100, decimales=0) == "-100"


def test_texto_limite_sin_limite_queda_vacio():
    assert texto_limite(None, decimales=1) == ""
    assert texto_limite(float("inf"), decimales=1) == ""
    assert texto_limite(float("-inf"), decimales=1) == ""


# ── agregar_digito: solo dígitos ─────────────────────────────────────────

@pytest.mark.parametrize("tecla", [",", "a", "12", "", "-", "."])
def test_agregar_digito_ignora_lo_que_no_es_un_digito(tecla):
    # La coma nunca entra, ni siquiera por la tecla de dígito (TEC-D02).
    assert agregar_digito("1", tecla, decimales=1) == "1"


# ── distribución (pág. 24 de la especificación del diseñador) ────────────

def test_distribucion_de_calculadora():
    from autoclave.ui_qml.domain.teclado_numerico import FILAS_TECLAS, PUNTO, SIGNO
    assert FILAS_TECLAS == ("789", "456", "123", "-0.")
    assert (SIGNO, PUNTO) == ("-", ".")
