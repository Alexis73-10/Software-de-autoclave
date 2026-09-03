# tests/test_alarma_bloqueante_qml.py
#
# Alarma severidad 4 (Fallo crítico): pantalla completa, bloqueante,
# siempre requiere ack (alarmSeverity de tokens.json). El hallazgo UI-05
# marca esta presentación como "definida en tokens.json, sin maqueta" —
# no hay mockup de referencia, el diseño visual concreto queda a criterio
# de esta implementación dentro de las restricciones del sistema de diseño
# (D-08: sin 3D en tiempo real).

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QSignalSpy

_QML = "src/autoclave/ui_qml/components/alarms/AlarmaBloqueante.qml"


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _crear(**props):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    for nombre, valor in props.items():
        obj.setProperty(nombre, valor)
    obj._keepalive = (engine, component)
    return obj


def test_instancia_sin_error():
    obj = _crear()
    assert obj is not None


def test_cubre_todo_el_ancho_y_alto_configurados():
    obj = _crear(width=800, height=1280)
    assert obj.property("width") == 800
    assert obj.property("height") == 1280


def test_muestra_la_descripcion():
    obj = _crear(descripcion="Fallo de sensor de temperatura de cámara")
    texto = obj.findChild(QObject, "bloqueanteTexto")
    assert texto.property("text") == "Fallo de sensor de temperatura de cámara"


def test_siempre_tiene_boton_reconocer():
    # Severidad 4: ackRequired=true siempre, sin propiedad para desactivarlo.
    obj = _crear()
    boton = obj.findChild(QObject, "botonReconocer")
    assert boton is not None


def test_boton_reconocer_emite_senal():
    obj = _crear()
    spy = QSignalSpy(obj.reconocida)
    boton = obj.findChild(QObject, "botonReconocer")
    from PySide6.QtCore import QMetaObject
    QMetaObject.invokeMethod(boton, "clicked")
    assert spy.count() == 1
