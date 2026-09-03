# tests/test_pantalla_inicio_qml.py
#
# Pantalla de arranque (/splash, §10.1 del sistema de diseño): fondo, logo,
# reloj + fecha, toca para avanzar. Sin campana ni engranaje (pedido
# explícito del usuario para esta primera entrega, difiere del sistema de
# diseño original). El reloj/fecha en sí ya está probado en
# test_reloj_splash.py (domain) y test_reloj_splash_controller.py (puente) —
# aquí solo se verifica el cableado de la vista.

import re
import sys

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QSignalSpy

import autoclave.ui_qml.design.register  # noqa: F401  (registra el singleton Tokens)
import autoclave.ui_qml.controllers.reloj_splash_controller  # noqa: F401  (registra el tipo QML)

_PANTALLA_QML = "src/autoclave/ui_qml/screens/PantallaInicio.qml"


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def pantalla():
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_PANTALLA_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj._keepalive = (engine, component)
    return obj


def test_instancia_sin_error(pantalla):
    assert pantalla is not None


def test_tiene_fondo(pantalla):
    fondo = pantalla.findChild(QObject, "fondo")
    assert fondo is not None
    assert "fondo-splash.png" in fondo.property("source").toString()


def test_tiene_logo(pantalla):
    logo = pantalla.findChild(QObject, "logo")
    assert logo is not None
    assert "logo-especifika-blanco.png" in logo.property("source").toString()


def test_muestra_hora_con_formato_hh_mm(pantalla):
    texto = pantalla.findChild(QObject, "textoHora")
    assert re.fullmatch(r"\d{2}:\d{2}", texto.property("text"))


def test_muestra_fecha_con_guion(pantalla):
    texto = pantalla.findChild(QObject, "textoFecha")
    assert " - " in texto.property("text")


def test_tocar_la_pantalla_emite_avanzar(pantalla):
    # Sin QQuickWindow con render loop no se puede simular un clic real
    # (mismo motivo que test_teclado_alfanumerico_qml.py) — se invoca
    # directamente la función invocable que el MouseArea llama al tocar.
    spy = QSignalSpy(pantalla.avanzar)
    QMetaObject.invokeMethod(pantalla, "tocar")
    assert spy.count() == 1


def test_reloj_es_hueco_relleno_transparente_con_borde(pantalla):
    # Feedback del usuario sobre el mockup: el reloj no es relleno
    # translúcido (alternativa que el propio sistema de diseño autorizaba)
    # sino contorno con el interior transparente. Text.Outline = 1
    # (QQuickText::TextStyle) dibuja el borde en styleColor y dejar color
    # transparente hace que el interior no pinte nada — verificado con un
    # grabToImage manual antes de este cambio (interior transparente, solo
    # el trazo visible).
    # PySide6 no puede convertir genéricamente el QVariant del enum
    # QQuickText::TextStyle vía .property("style"), de ahí la propiedad
    # auxiliar `esContorno` (bool, sin ese problema) declarada en el propio
    # Text de PantallaInicio.qml.
    texto = pantalla.findChild(QObject, "textoHora")
    assert texto.property("esContorno") is True
    assert texto.property("color").alpha() == 0
