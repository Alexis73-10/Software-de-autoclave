# tests/test_teclado_alfanumerico_controller.py
#
# Puente QObject entre domain/teclado_alfanumerico.py y QML: expone
# texto/mayusculas/capaSimbolos/filas como Qt Properties con notify, y las
# teclas como Slots. Probado como objeto Python plano (sin motor QML).

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


@pytest.fixture
def controller():
    return TecladoAlfanumericoController()


def test_estado_inicial(controller):
    assert controller.texto == ""
    assert controller.mayusculas is False
    assert controller.capaSimbolos is False


def test_presionar_caracter_en_minuscula(controller):
    controller.presionarCaracter("q")
    assert controller.texto == "q"


def test_presionar_caracter_aplica_mayusculas(controller):
    controller.alternarMayusculas()
    controller.presionarCaracter("q")
    assert controller.texto == "Q"


def test_presionar_caracter_enie(controller):
    controller.alternarMayusculas()
    controller.presionarCaracter("ñ")
    assert controller.texto == "Ñ"


def test_presionar_caracter_simbolo_no_se_afecta_por_mayusculas(controller):
    controller.alternarMayusculas()
    controller.presionarCaracter("@")
    assert controller.texto == "@"


def test_borrar(controller):
    controller.presionarCaracter("h")
    controller.presionarCaracter("i")
    controller.borrar()
    assert controller.texto == "h"


def test_limpiar(controller):
    controller.presionarCaracter("h")
    controller.limpiar()
    assert controller.texto == ""


def test_alternar_mayusculas_dos_veces_vuelve_al_estado_original(controller):
    controller.alternarMayusculas()
    controller.alternarMayusculas()
    assert controller.mayusculas is False


def test_alternar_capa_simbolos(controller):
    controller.alternarCapaSimbolos()
    assert controller.capaSimbolos is True


def test_filas_letras_expuestas():
    controller = TecladoAlfanumericoController()
    assert list(controller.filasLetras) == ["qwertyuiop", "asdfghjklñ", "zxcvbnm"]


def test_filas_simbolos_expuestas():
    controller = TecladoAlfanumericoController()
    assert "@" in "".join(controller.filasSimbolos)


def test_texto_changed_se_emite_al_presionar_tecla(controller):
    spy = QSignalSpy(controller.textoChanged)
    controller.presionarCaracter("a")
    assert spy.count() == 1


def test_mayusculas_changed_se_emite_al_alternar(controller):
    spy = QSignalSpy(controller.mayusculasChanged)
    controller.alternarMayusculas()
    assert spy.count() == 1
