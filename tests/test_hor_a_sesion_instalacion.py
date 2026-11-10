"""Tanda horizontal (9-nov), grupo A: sesión, asistente e intro en el lienzo
1920x1200.

Cada pantalla se carga en una ventana horizontal (Escala.horizontal = true,
factor 1) y se mide su geometría: la barra flotante conserva el tamaño del
vertical (escala del lienzo de 1200 de ancho, no 1,6 veces más grande), los
controles quedan dentro de su tarjeta, los campos de sesión caben sobre el
teclado en pantalla (55 % de arriba) y los textos de la intro no se enciman.
El vertical lo cubren las pruebas existentes, sin cambios."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r'''
    import json, os
    from PySide6.QtCore import QObject, QUrl, QPointF
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.bridge import i18n_qml

    i18n.cargar(); i18n_qml.instancia._consultar = lambda: None

    class Sesion:
        sinConexion = False
        def enviar(self, *a, **k):
            return sesion_backend.Resultado("ok", {}, 200)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)
    sesion_backend.ventana = lambda: Sesion()
    qapp = QGuiApplication([])

    PUENTE_NU = ("QtObject { property var roles: [{valor: 'operador', etiqueta: 'Operador'}];"
                 " property var longitudesMaximas: ({}); property bool operacionEnCurso: false;"
                 " property int altaActual: 0; signal guardadoResuelto(string e, var x, string m, int a);"
                 " function estadoDe(x) { return '' } function abandonarPreparacion() {}"
                 " function navegar(d) {} function guardar() { return { enviado: false, errores: {} } } }")
    PANTALLAS = {
        "login": "Login { anchors.fill: parent }",
        "cambio": "CambioClave { anchors.fill: parent }",
        "nuevo": "NuevoUsuario { anchors.fill: parent; puente: " + PUENTE_NU + " }",
        "intro": "IntroArranque { anchors.fill: parent }",
    }

    def cargar(cuerpo):
        ruta = f"{QML_DIR}/_hor_a_{os.getpid()}.qml"
        open(ruta, "w", encoding="utf-8").write("""
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        id: ventana
        width: 1920; height: 1200; visible: true
        Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(ventana.width, ventana.height) }
        Binding { target: Escala; property: "factor"; value: 1.0 }
        Item { objectName: "lienzo"; width: 1920; height: 1200
            %s
        }
    }
    """ % cuerpo)
        eng = QQmlApplicationEngine()
        eng.addImportPath(QML_DIR)
        eng.load(QUrl.fromLocalFile(ruta))
        os.remove(ruta)
        return eng, eng.rootObjects()[0]

    def caja(o):
        p = o.mapToScene(QPointF(0, 0))
        return [p.x(), p.y(), o.width(), o.height()]

    salida = {}
    motores = []
    for nombre, cuerpo in PANTALLAS.items():
        eng, win = cargar(cuerpo)
        motores.append(eng)
        if nombre == "intro":
            QTest.qWait(3900)   # último cuadro de la intro (3,5 s)
        else:
            QTest.qWait(150)
        objs = {o.objectName(): o for o in win.findChildren(QQuickItem) if o.objectName()}
        d = {"horizontal": eng.singletonInstance("Tema", "Escala").property("horizontal")}
        for n in ("tarjetaLogin", "barraInferiorLogin", "campoUsuario", "campoClave", "botonIniciarSesion",
                  "tarjetaCambioClave", "barraInferiorCambioClave", "campo_clave_actual", "campo_clave_nueva",
                  "campo_confirmacion", "botonCambiarClave",
                  "tarjetaNuevoUsuario", "barraInferiorNuevoUsuario", "campoNombre", "campoUsuario",
                  "campoClave", "campoConfirmacion", "campoRol", "interruptorActivo", "botonGuardarUsuario",
                  "rielArranque", "procesoArranque", "pieArranque"):
            if n in objs:
                d[n] = caja(objs[n])
        if nombre == "intro":
            # los delegados del Repeater no son hijos QObject de la ventana: se
            # recorre el árbol visual
            def items(it):
                yield it
                for h in it.childItems():
                    yield from items(h)
            textos = [o for o in items(win.contentItem()) if o.property("text") in
                      ("Tecnología para esterilizar.", "Ingeniería para responder.")]
            d["eslogan"] = sorted(caja(t) for t in textos)
        salida[nombre] = d
    print("RESULTADO=" + json.dumps(salida))
''')


@pytest.fixture(scope="module")
def m():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


ESCALA_VERTICAL = 1200 / 1196   # px por unidad del mockup en el lienzo vertical
TOPE_TECLADO = 1200 * 0.55      # el teclado ocupa hasta el 45 % de abajo


def _dentro(hijo, padre):
    x, y, w, h = hijo
    px, py, pw, ph = padre
    return x >= px - 1 and y >= py - 1 and x + w <= px + pw + 1 and y + h <= py + ph + 1


@pytest.mark.parametrize("pantalla,barra", [("login", "barraInferiorLogin"),
                                            ("cambio", "barraInferiorCambioClave"),
                                            ("nuevo", "barraInferiorNuevoUsuario")])
def test_barra_flotante_con_el_tamano_del_vertical(m, pantalla, barra):
    assert m[pantalla]["horizontal"] is True
    x, y, w, h = m[pantalla][barra]
    assert h == pytest.approx(139 * ESCALA_VERTICAL, abs=0.5)
    assert y + h <= 1200 - 31 * ESCALA_VERTICAL + 1   # mismo margen inferior que en vertical
    assert x == pytest.approx(24) and w == pytest.approx(1920 - 48)


@pytest.mark.parametrize("pantalla,tarjeta,campos", [
    ("login", "tarjetaLogin", ["campoUsuario", "campoClave", "botonIniciarSesion"]),
    ("cambio", "tarjetaCambioClave", ["campo_clave_actual", "campo_clave_nueva", "campo_confirmacion",
                                      "botonCambiarClave"]),
    ("nuevo", "tarjetaNuevoUsuario", ["campoNombre", "campoUsuario", "campoClave", "campoConfirmacion",
                                      "campoRol", "interruptorActivo", "botonGuardarUsuario"]),
])
def test_controles_dentro_de_la_tarjeta(m, pantalla, tarjeta, campos):
    t = m[pantalla][tarjeta]
    for c in campos:
        assert _dentro(m[pantalla][c], t), c
    assert t[1] + t[3] <= m[pantalla]["barraInferior" + {"login": "Login", "cambio": "CambioClave",
                                                         "nuevo": "NuevoUsuario"}[pantalla]][1]


@pytest.mark.parametrize("pantalla,campos", [
    ("login", ["campoUsuario", "campoClave"]),
    ("cambio", ["campo_clave_actual", "campo_clave_nueva", "campo_confirmacion"]),
])
def test_campos_de_sesion_sobre_el_teclado(m, pantalla, campos):
    for c in campos:
        x, y, w, h = m[pantalla][c]
        assert y + h <= TOPE_TECLADO, c


def test_intro_sin_textos_encimados(m):
    d = m["intro"]
    e1, e2 = d["eslogan"]
    assert e1[1] + e1[3] <= e2[1] + 1                  # las dos líneas del eslogan, una debajo de otra
    assert e2[1] + e2[3] < d["rielArranque"][1]          # el riel debajo del eslogan
    assert d["rielArranque"][2] == pytest.approx(0.72 * 1200, abs=1)   # el ancho del vertical
    assert d["procesoArranque"][1] + d["procesoArranque"][3] <= d["pieArranque"][1]
    assert d["pieArranque"][1] + d["pieArranque"][3] <= 1200
