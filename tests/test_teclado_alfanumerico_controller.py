# tests/test_teclado_alfanumerico_controller.py
#
# Puente QObject entre domain/teclado_alfanumerico.py y QML: expone
# texto/mayusculas/capa/juegos de caracteres como Qt Properties con notify, y
# las teclas como Slots. Probado como objeto Python plano (sin motor QML).
# Reglas: TEC-D03/D05/D07/D09/D12 y §7 de planeacion_teclados_qml.md.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import (
    TecladoAlfanumericoController,
)


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class RelojFalso:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj():
    return RelojFalso()


@pytest.fixture
def controller(reloj):
    return TecladoAlfanumericoController(reloj=reloj)


def _escribir(controller, texto):
    for c in texto:
        controller.presionarCaracter(c)


def test_estado_inicial(controller):
    assert controller.texto == ""
    assert controller.mayusculas is True     # TEC-D05: inicia en mayúscula
    assert controller.capa == "letras"
    assert controller.longitudMaxima == 0    # sin límite hasta que el campo lo fije


# ── Aa de un solo uso (TEC-D05) ──────────────────────────────────────────

def test_primera_letra_en_mayuscula_y_siguientes_en_minuscula(controller):
    _escribir(controller, "juan")
    assert controller.texto == "Juan"
    assert controller.mayusculas is False


def test_aa_a_mitad_de_texto_solo_afecta_la_siguiente_letra(controller):
    _escribir(controller, "juan")
    controller.alternarMayusculas()
    assert controller.mayusculas is True
    _escribir(controller, "pe")
    assert controller.texto == "JuanPe"
    assert controller.mayusculas is False


def test_aa_armada_se_puede_desarmar(controller):
    controller.alternarMayusculas()   # estaba armada al abrir -> se desarma
    _escribir(controller, "a")
    assert controller.texto == "a"


def test_enie_segun_estado_de_aa(controller):
    _escribir(controller, "ññ")
    assert controller.texto == "Ññ"


def test_digitos_y_simbolos_no_consumen_aa(controller):
    _escribir(controller, "1@a")
    assert controller.texto == "1@A"


def test_caracter_fuera_del_juego_se_ignora(controller):
    _escribir(controller, "a#,é")
    assert controller.texto == "A"


def test_mayusculas_changed_se_emite(controller):
    spy = QSignalSpy(controller.mayusculasChanged)
    controller.alternarMayusculas()
    assert spy.count() == 1
    controller.alternarMayusculas()
    _escribir(controller, "a")          # consumir Aa también notifica
    assert spy.count() == 3


# ── capas (TEC-D03, §7) ──────────────────────────────────────────────────

def test_juegos_de_caracteres_expuestos(controller):
    assert list(controller.filasLetras) == ["qwertyuiop", "asdfghjklñ", "zxcvbnm"]
    assert controller.digitos == "0123456789"
    assert controller.simbolos == "@._-()?+*/="


def test_cambiar_capa(controller):
    spy = QSignalSpy(controller.capaChanged)
    controller.cambiarCapa("digitos")
    assert controller.capa == "digitos"
    controller.cambiarCapa("simbolos")
    assert controller.capa == "simbolos"
    controller.cambiarCapa("letras")
    assert controller.capa == "letras"
    assert spy.count() == 3


def test_capa_desconocida_se_ignora(controller):
    controller.cambiarCapa("emojis")
    assert controller.capa == "letras"


def test_cambio_de_capa_conserva_texto_y_no_confirma(controller):
    _escribir(controller, "ana")
    spy_texto = QSignalSpy(controller.textoChanged)
    spy_ok = QSignalSpy(controller.confirmado)
    controller.cambiarCapa("digitos")
    controller.cambiarCapa("simbolos")
    controller.cambiarCapa("letras")
    assert controller.texto == "Ana"
    assert spy_texto.count() == 0
    assert spy_ok.count() == 0


# ── longitud máxima (TEC-D09) ────────────────────────────────────────────

def test_longitud_maxima_bloquea_mas_caracteres(controller):
    controller.abrir("Operador", "", 30)
    _escribir(controller, "a" * 35)
    assert len(controller.texto) == 30


# ── borrar (TEC-D12) ─────────────────────────────────────────────────────

def test_borrar(controller):
    _escribir(controller, "ho")
    controller.borrar()
    assert controller.texto == "H"


def test_limpiar(controller):
    _escribir(controller, "hola")
    controller.limpiar()
    assert controller.texto == ""


def test_borrar_toque_corto_quita_un_caracter(controller, reloj):
    _escribir(controller, "hola")
    controller.presionarBorrar()
    reloj.t += 0.3
    controller.soltarBorrar()
    assert controller.texto == "Hol"


def test_borrar_mantenido_vacia_el_campo_una_vez(controller, reloj):
    _escribir(controller, "hola")
    controller.presionarBorrar()
    reloj.t += 0.6
    controller._borrado.vencer()
    assert controller.texto == ""
    reloj.t += 1.0
    controller.soltarBorrar()
    assert controller.texto == ""


# ── abrir / confirmar / cancelar (TEC-D07/D09/D13) ───────────────────────

def test_abrir_configura_campo(controller):
    controller.cambiarCapa("simbolos")
    controller.abrir("Nombre del operador", "Ana", 30)
    assert controller.titulo == "Nombre del operador"
    assert controller.texto == "Ana"
    assert controller.longitudMaxima == 30
    assert controller.mayusculas is False    # abre con texto: Aa no se arma
    assert controller.capa == "letras"


def test_texto_changed_se_emite_al_presionar_tecla(controller):
    spy = QSignalSpy(controller.textoChanged)
    controller.presionarCaracter("h")
    assert spy.count() == 1


def test_confirmar_entrega_el_texto_tal_cual(controller):
    controller.abrir("Operador", "", 30)
    _escribir(controller, "ana perez")
    spy = QSignalSpy(controller.confirmado)
    controller.confirmar()
    assert spy.count() == 1
    assert spy.at(0)[0] == "Ana perez"


def test_confirmar_vacio_entrega_texto_vacio(controller):
    controller.abrir("Operador", "", 30)
    spy = QSignalSpy(controller.confirmado)
    controller.confirmar()
    assert spy.count() == 1
    assert spy.at(0)[0] == ""


def test_cancelar_emite_cancelado_sin_confirmado_y_descarta(controller):
    controller.abrir("Operador", "Ana", 30)
    spy_ok = QSignalSpy(controller.confirmado)
    spy_cancel = QSignalSpy(controller.cancelado)
    controller.cancelar()
    assert spy_cancel.count() == 1
    assert spy_ok.count() == 0
    assert controller.texto == ""


# ── Aa se arma siempre que el texto queda vacío ──────────────────────────

def test_abrir_vacio_arma_aa_aunque_estuviera_desarmada(controller):
    controller.abrir("Operador", "Ana", 30)
    assert controller.mayusculas is False
    controller.abrir("Operador", "", 30)
    assert controller.mayusculas is True


def test_borrar_hasta_vaciar_arma_aa(controller):
    controller.abrir("Operador", "", 30)
    _escribir(controller, "ab")              # "Ab", Aa desarmada
    controller.borrar()
    assert controller.mayusculas is False    # queda "A": no se arma
    controller.borrar()
    assert controller.texto == ""
    assert controller.mayusculas is True
    _escribir(controller, "c")
    assert controller.texto == "C"


def test_borrado_total_por_pulsacion_larga_arma_aa(controller, reloj):
    controller.abrir("Operador", "Ana", 30)
    controller.presionarBorrar()
    reloj.t += 0.6
    controller._borrado.vencer()
    assert controller.texto == ""
    assert controller.mayusculas is True


def test_limpiar_arma_aa(controller):
    controller.abrir("Operador", "Ana", 30)
    controller.limpiar()
    assert controller.mayusculas is True


def test_tocar_aa_armada_con_campo_vacio_la_desarma(controller):
    controller.abrir("Operador", "", 30)
    controller.alternarMayusculas()
    assert controller.mayusculas is False
    _escribir(controller, "x")
    assert controller.texto == "x"
