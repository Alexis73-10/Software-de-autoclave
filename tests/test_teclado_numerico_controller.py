# tests/test_teclado_numerico_controller.py
#
# Puente QObject entre la lógica pura de domain/teclado_numerico.py y QML:
# expone texto/valor/valido como Qt Properties con notify, y las teclas
# como Slots. Se prueba como objeto Python plano (sin motor QML) — los
# Property/Slot de PySide6 son accesibles como atributos/métodos normales.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.controllers.teclado_numerico_controller import (
    TecladoNumericoController,
)


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


@pytest.fixture
def controller():
    return TecladoNumericoController()


def test_estado_inicial_vacio_invalido(controller):
    assert controller.texto == ""
    assert controller.valor is None
    assert controller.valido is False


def test_presionar_digito_actualiza_texto(controller):
    controller.presionarDigito("1")
    controller.presionarDigito("3")
    controller.presionarDigito("4")
    assert controller.texto == "134"


def test_presionar_coma(controller):
    controller.presionarDigito("1")
    controller.presionarComa()
    controller.presionarDigito("5")
    assert controller.texto == "1,5"


def test_presionar_signo_respeta_permite_negativo(controller):
    controller.permiteNegativo = False
    controller.presionarDigito("5")
    controller.presionarSigno()
    assert controller.texto == "5"  # inerte: el campo no admite negativos

    controller.permiteNegativo = True
    controller.presionarSigno()
    assert controller.texto == "-5"


def test_borrar(controller):
    controller.presionarDigito("1")
    controller.presionarDigito("2")
    controller.borrar()
    assert controller.texto == "1"


def test_limpiar(controller):
    controller.presionarDigito("1")
    controller.presionarDigito("2")
    controller.limpiar()
    assert controller.texto == ""


def test_valido_refleja_rango_configurado(controller):
    controller.minimo = 0.0
    controller.maximo = 100.0
    controller.presionarDigito("5")
    controller.presionarDigito("0")
    assert controller.valido is True
    assert controller.valor == 50.0

    controller.limpiar()
    controller.presionarDigito("1")
    controller.presionarDigito("5")
    controller.presionarDigito("0")
    assert controller.valido is False  # 150 > maximo=100
    assert controller.valor == 150.0


def test_texto_changed_se_emite_al_presionar_tecla(controller):
    spy = QSignalSpy(controller.textoChanged)
    controller.presionarDigito("1")
    assert spy.count() == 1


def test_valido_changed_se_emite_solo_al_cruzar_el_umbral(controller):
    controller.minimo = 0.0
    controller.maximo = 100.0
    spy = QSignalSpy(controller.validoChanged)

    controller.presionarDigito("5")   # "5" -> válido (era inválido) -> emite
    assert spy.count() == 1

    controller.presionarDigito("0")   # "50" -> sigue válido -> no vuelve a emitir
    assert spy.count() == 1

    controller.presionarDigito("0")   # "500" -> inválido (> 100) -> emite
    assert spy.count() == 2
