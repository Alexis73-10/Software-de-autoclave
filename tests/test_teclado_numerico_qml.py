# tests/test_teclado_numerico_qml.py
#
# Vista QML del teclado numérico (§13.1). La lógica de acumulación y
# validación ya está probada en test_teclado_numerico.py (domain) y
# test_teclado_numerico_controller.py (puente QObject) — aquí solo se
# verifica el cableado: que la vista instancia, que sus alias exponen el
# controller, y que el botón de confirmar reacciona a `valido` en vivo.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

import autoclave.ui_qml.controllers.teclado_numerico_controller  # noqa: F401  (registra el tipo QML)

_TECLADO_QML = "src/autoclave/ui_qml/components/TecladoNumerico.qml"


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _crear_teclado(**props):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_TECLADO_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    for nombre, valor in props.items():
        obj.setProperty(nombre, valor)
    # Los delegates de Repeater se instancian de forma asíncrona: sin dejar
    # correr el event loop, findChild(ren) no los ve todavía.
    QTest.qWait(50)
    obj._keepalive = (engine, component)
    return obj


def _controller(obj):
    return obj.findChild(QObject, "controller")


def test_teclado_instancia_sin_error():
    obj = _crear_teclado()
    assert obj is not None


def test_alias_minimo_maximo_llegan_al_controller():
    obj = _crear_teclado(minimo=0.0, maximo=100.0)
    controller = _controller(obj)
    assert controller.minimo == 0.0
    assert controller.maximo == 100.0


def test_alias_permite_negativo_llega_al_controller():
    obj = _crear_teclado(permiteNegativo=True)
    controller = _controller(obj)
    assert controller.permiteNegativo is True


def test_boton_confirmar_deshabilitado_sin_texto():
    obj = _crear_teclado(minimo=0.0, maximo=100.0)
    boton = obj.findChild(QObject, "botonConfirmar")
    assert boton is not None
    assert boton.property("enabled") is False


def test_boton_confirmar_se_habilita_dentro_de_rango():
    obj = _crear_teclado(minimo=0.0, maximo=100.0)
    controller = _controller(obj)
    controller.presionarDigito("5")
    controller.presionarDigito("0")

    boton = obj.findChild(QObject, "botonConfirmar")
    assert boton.property("enabled") is True


def test_boton_confirmar_sigue_deshabilitado_fuera_de_rango():
    obj = _crear_teclado(minimo=0.0, maximo=100.0)
    controller = _controller(obj)
    controller.presionarDigito("1")
    controller.presionarDigito("5")
    controller.presionarDigito("0")

    boton = obj.findChild(QObject, "botonConfirmar")
    assert boton.property("enabled") is False


def test_teclas_numericas_tienen_al_menos_64px():
    obj = _crear_teclado()
    teclas = obj.findChildren(QObject, "teclaNumerica")
    assert len(teclas) == 10  # 0-9
    for tecla in teclas:
        assert tecla.property("width") >= 64
        assert tecla.property("height") >= 64
