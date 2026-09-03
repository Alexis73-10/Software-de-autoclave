# tests/test_contenedor_escalado_qml.py
#
# Contenedor de escalado uniforme (§8.2 del plan de interfaz dual-
# pantalla, D-11): lienzo lógico fijo 800x1280, escalado uniforme con
# letterbox cuando la ventana no respeta la relación 5:8.
#   scale = min(anchoVentana / 800, altoVentana / 1280)
# "Ninguna vista contiene ramas condicionales por tamaño": el contenido
# siempre se dibuja al tamaño lógico fijo; este contenedor es el único
# que conoce la geometría real.

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

import autoclave.ui_qml.design.register  # noqa: F401  (registra el singleton Tokens)

_QML = "src/autoclave/ui_qml/components/ContenedorEscalado.qml"
_TOKENS_JSON = Path("docs/files UI Especifika/tokens.json")


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _crear(width, height, lienzo_ancho=800, lienzo_alto=1280):
    # lienzo_ancho/lienzo_alto fijan el tamaño lógico del lienzo de forma
    # explícita (en vez de depender del valor por defecto que viene de
    # Tokens.layout.canvas) para que estas pruebas de la matemática de
    # escalado no dependan de cuál sea el tamaño de producción vigente —
    # eso se prueba aparte, en test_lienzo_por_defecto_viene_del_token.
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj.setProperty("lienzoAncho", lienzo_ancho)
    obj.setProperty("lienzoAlto", lienzo_alto)
    obj.setProperty("width", width)
    obj.setProperty("height", height)
    obj._keepalive = (engine, component)
    return obj


def _contenido(obj):
    return obj.findChild(QObject, "contenidoEscalado")


def test_produccion_800x1280_escala_uno():
    obj = _crear(800, 1280)
    assert _contenido(obj).property("scale") == 1.0


def test_desarrollo_400x640_escala_media():
    # §8.2: dos ventanas de 400x640 (scale=0.5) para simetría/interlock en dev.
    obj = _crear(400, 640)
    assert _contenido(obj).property("scale") == 0.5


def test_contenido_mantiene_tamano_logico_fijo_sin_importar_la_ventana():
    for w, h in [(800, 1280), (400, 640), (1200, 1280), (800, 2000)]:
        obj = _crear(w, h)
        contenido = _contenido(obj)
        assert contenido.property("width") == 800
        assert contenido.property("height") == 1280


def test_letterbox_horizontal_cuando_la_ventana_es_mas_ancha():
    # 1200x1280 -> limita el alto (scale=1.0), sobra ancho -> letterbox lateral.
    obj = _crear(1200, 1280)
    contenido = _contenido(obj)
    assert contenido.property("scale") == 1.0
    assert contenido.property("x") == 200.0  # (1200-800)/2


def test_letterbox_vertical_cuando_la_ventana_es_mas_alta():
    # 800x2000 -> limita el ancho (scale=1.0), sobra alto -> letterbox arriba/abajo.
    obj = _crear(800, 2000)
    contenido = _contenido(obj)
    assert contenido.property("scale") == 1.0
    assert contenido.property("y") == 360.0  # (2000-1280)/2


def test_escala_no_estira_de_forma_no_uniforme():
    # Ventana desproporcionada: el factor debe ser el MENOR de los dos ejes,
    # nunca escalas distintas por eje (D-11: "escalado uniforme").
    obj = _crear(1600, 1280)  # ancho de sobra -> limita el alto
    assert _contenido(obj).property("scale") == 1.0  # min(1600/800, 1280/1280)=1.0


def test_lienzo_por_defecto_viene_del_token_layout_canvas():
    # Sin fijar lienzoAncho/lienzoAlto explícitamente (a diferencia de
    # _crear en el resto de este archivo), el valor por defecto debe salir
    # de Tokens.layout.canvas — antes eran números sueltos duplicados
    # también en app.py, y cambiar el tamaño de lienzo real (768x1024)
    # requería tocar cada copia por separado.
    tokens = json.loads(_TOKENS_JSON.read_text(encoding="utf-8"))
    ancho_esperado = tokens["layout"]["canvas"]["w"]
    alto_esperado = tokens["layout"]["canvas"]["h"]

    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj._keepalive = (engine, component)

    assert obj.property("lienzoAncho") == ancho_esperado
    assert obj.property("lienzoAlto") == alto_esperado
