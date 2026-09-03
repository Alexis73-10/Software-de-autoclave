# tests/test_tokens_singleton_registration.py
#
# Registro de Tokens.qml como singleton QML importable (`import
# Autoclave.Design 1.0`), para que los demás componentes puedan leer
# `Tokens.color...` en vez de declarar colores propios (§7.2/§0.2 del
# sistema de diseño: "prohibido declarar hexadecimales en cualquier
# componente"). Sin este registro, Tokens.qml solo era cargable por URL de
# archivo directa (como en test_tokens_qml_runtime.py) — no importable
# desde otro QML.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

import autoclave.ui_qml.design.register  # noqa: F401  (registra el singleton)


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _cargar(engine, qml_text: str):
    component = QQmlComponent(engine)
    component.setData(qml_text.encode("utf-8"), QUrl())
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj._keepalive = component
    return obj


def test_tokens_importable_desde_otro_qml():
    engine = QQmlEngine()
    obj = _cargar(engine, '''
        import QtQuick
        import Autoclave.Design 1.0
        Item {
            property color primary: Tokens.color.primary["500"]
        }
    ''')
    assert obj.property("primary").name().upper() == "#1168F6"


def test_dark_toggle_del_singleton_afecta_a_todos_los_consumidores():
    # El singleton es UNA instancia por QQmlEngine, compartida entre todos
    # los componentes cargados en ese mismo engine: cambiar Tokens.dark
    # desde uno debe verse reflejado en otro (D-21 — "conmuta la tabla
    # activa del singleton, sin recompilar"). Por eso ambos componentes se
    # cargan en el mismo QQmlEngine — engines distintos tendrían cada uno
    # su propia instancia del singleton, sin nada que compartir.
    engine = QQmlEngine()

    consumidor_1 = _cargar(engine, '''
        import QtQuick
        import Autoclave.Design 1.0
        Item {
            property color surfaceCard: Tokens.color.surface["card"]
        }
    ''')
    claro = consumidor_1.property("surfaceCard").name().upper()

    controlador_tema = _cargar(engine, '''
        import QtQuick
        import Autoclave.Design 1.0
        Item {
            Component.onCompleted: Tokens.dark = true
        }
    ''')

    consumidor_2 = _cargar(engine, '''
        import QtQuick
        import Autoclave.Design 1.0
        Item {
            property color surfaceCard: Tokens.color.surface["card"]
        }
    ''')
    oscuro = consumidor_2.property("surfaceCard").name().upper()

    assert claro != oscuro
    assert claro == "#FFFFFF"
    assert oscuro == "#16202B"
