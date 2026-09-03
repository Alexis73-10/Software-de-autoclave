# tests/test_teclado_alfanumerico_qml.py
#
# Vista QML del teclado alfanumérico (§13.2). La lógica de acumulación,
# mayúsculas y capa de símbolos ya está probada en domain/controller — aquí
# se verifica el cableado: la grilla de teclas se reconstruye por capa
# (usando Component.createObject, no Repeater — ver TecladoNumerico.qml
# para la razón: Repeater no incuba delegates sin una QQuickWindow con
# render loop activo, y eso no se puede garantizar en pruebas headless).

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

import autoclave.ui_qml.controllers.teclado_alfanumerico_controller  # noqa: F401

_TECLADO_QML = "src/autoclave/ui_qml/components/TecladoAlfanumerico.qml"

_TOTAL_LETRAS = len("qwertyuiop") + len("asdfghjklñ") + len("zxcvbnm")       # 27
_TOTAL_SIMBOLOS = len("1234567890") + len("@#$%&*-+=") + len("!?,.;:()/")    # 28


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _crear_teclado():
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_TECLADO_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj._keepalive = (engine, component)
    return obj


def _controller(obj):
    return obj.findChild(QObject, "controller")


def test_teclado_instancia_sin_error():
    obj = _crear_teclado()
    assert obj is not None


def test_capa_letras_por_defecto_tiene_27_teclas():
    obj = _crear_teclado()
    teclas = obj.findChildren(QObject, "teclaCaracter")
    assert len(teclas) == _TOTAL_LETRAS


def test_teclas_caracter_tienen_al_menos_48px():
    obj = _crear_teclado()
    for tecla in obj.findChildren(QObject, "teclaCaracter"):
        assert tecla.property("width") >= 48
        assert tecla.property("height") >= 48


def test_alternar_capa_simbolos_reconstruye_la_grilla():
    obj = _crear_teclado()
    controller = _controller(obj)
    controller.alternarCapaSimbolos()
    # reconstruirFilas() destruye las teclas anteriores con Item.destroy(),
    # que difiere la eliminación al próximo ciclo del event loop (como
    # deleteLater()) — sin dejarlo correr, findChildren aún las ve.
    QTest.qWait(50)
    teclas = obj.findChildren(QObject, "teclaCaracter")
    assert len(teclas) == _TOTAL_SIMBOLOS


def test_arroba_presente_en_capa_simbolos():
    obj = _crear_teclado()
    controller = _controller(obj)
    controller.alternarCapaSimbolos()
    QTest.qWait(50)
    etiquetas = [t.property("text") for t in obj.findChildren(QObject, "teclaCaracter")]
    assert "@" in etiquetas


def test_enie_presente_en_capa_letras():
    obj = _crear_teclado()
    etiquetas = [t.property("text") for t in obj.findChildren(QObject, "teclaCaracter")]
    assert "ñ" in etiquetas


def test_mayusculas_cambia_etiquetas_a_mayuscula():
    obj = _crear_teclado()
    controller = _controller(obj)
    controller.alternarMayusculas()
    QTest.qWait(50)
    etiquetas = [t.property("text") for t in obj.findChildren(QObject, "teclaCaracter")]
    assert "Q" in etiquetas
    assert "Ñ" in etiquetas
    assert "q" not in etiquetas


def test_presionar_tecla_caracter_actualiza_texto():
    obj = _crear_teclado()
    controller = _controller(obj)
    tecla_q = next(
        t for t in obj.findChildren(QObject, "teclaCaracter")
        if t.property("text") == "q"
    )
    # Simula el click invocando el slot Qt directamente sobre la Button.
    from PySide6.QtCore import QMetaObject
    QMetaObject.invokeMethod(tecla_q, "clicked")
    assert controller.texto == "q"


def test_boton_confirmar_deshabilitado_con_texto_vacio():
    obj = _crear_teclado()
    boton = obj.findChild(QObject, "botonConfirmar")
    assert boton.property("enabled") is False


def test_boton_confirmar_habilitado_con_texto():
    obj = _crear_teclado()
    controller = _controller(obj)
    controller.presionarCaracter("a")
    boton = obj.findChild(QObject, "botonConfirmar")
    assert boton.property("enabled") is True


def test_tecla_mayusculas_oculta_en_capa_simbolos():
    obj = _crear_teclado()
    controller = _controller(obj)
    tecla_mayus = obj.findChild(QObject, "teclaMayusculas")
    assert tecla_mayus.property("visible") is True
    controller.alternarCapaSimbolos()
    assert tecla_mayus.property("visible") is False
