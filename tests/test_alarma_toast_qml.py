# tests/test_alarma_toast_qml.py
#
# Alarma severidad 1 (Informativo): toast, no persistente, sin ack
# (alarmSeverity de tokens.json). Componente presentacional puro — no
# lleva controller: el host (futuro AlarmManager, F4) decide cuándo
# mostrarla y por cuánto tiempo.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

_QML = "src/autoclave/ui_qml/components/alarms/AlarmaToast.qml"


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
    obj = _crear(descripcion="Sensor recalibrado")
    from PySide6.QtCore import QObject
    texto = obj.findChild(QObject, "toastTexto")
    assert texto.property("text") == "Sensor recalibrado"


def test_sin_boton_de_reconocer():
    # Severidad 1 nunca requiere ack (alarmSeverity.1.ackRequired=false).
    obj = _crear()
    from PySide6.QtCore import QObject
    boton = obj.findChild(QObject, "botonReconocer")
    assert boton is None


def test_auto_dismiss_desactivado_por_defecto():
    obj = _crear()
    assert obj.property("autoDismissMs") == 0
