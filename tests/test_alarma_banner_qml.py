# tests/test_alarma_banner_qml.py
#
# Alarma severidad 2 (Aviso: banner, sin ack) y 3 (Alarma: banner
# parpadeante, con ack) — mismo componente, `parpadea`/`requiereAck` como
# propiedades (alarmSeverity de tokens.json). Componente presentacional
# puro, sin controller.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QSignalSpy

_QML = "src/autoclave/ui_qml/components/alarms/AlarmaBanner.qml"


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


def test_muestra_la_descripcion():
    obj = _crear(descripcion="Presión de cámara fuera de rango")
    texto = obj.findChild(QObject, "bannerTexto")
    assert texto.property("text") == "Presión de cámara fuera de rango"


def test_sin_boton_reconocer_cuando_no_requiere_ack():
    # Severidad 2 (Aviso): ackRequired=false.
    obj = _crear(requiereAck=False)
    boton = obj.findChild(QObject, "botonReconocer")
    assert boton is not None
    assert boton.property("visible") is False


def test_con_boton_reconocer_cuando_requiere_ack():
    # Severidad 3 (Alarma): ackRequired=true.
    obj = _crear(requiereAck=True)
    boton = obj.findChild(QObject, "botonReconocer")
    assert boton is not None
    assert boton.property("visible") is True


def test_boton_reconocer_emite_senal():
    obj = _crear(requiereAck=True)
    spy = QSignalSpy(obj.reconocida)
    boton = obj.findChild(QObject, "botonReconocer")
    from PySide6.QtCore import QMetaObject
    QMetaObject.invokeMethod(boton, "clicked")
    assert spy.count() == 1


def test_parpadeo_inactivo_por_defecto():
    obj = _crear()
    assert obj.property("parpadea") is False


def test_parpadeo_activa_animacion():
    obj = _crear(parpadea=True)
    blink = obj.findChild(QObject, "blinkAnimation")
    assert blink is not None
    assert blink.property("running") is True


def test_sin_parpadeo_animacion_no_corre():
    obj = _crear(parpadea=False)
    blink = obj.findChild(QObject, "blinkAnimation")
    assert blink is not None
    assert blink.property("running") is False
