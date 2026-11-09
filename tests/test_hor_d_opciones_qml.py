# tests/test_hor_d_opciones_qml.py
#
# Tanda horizontal, grupo D: Opciones en el lienzo horizontal (1920x1200,
# Escala.horizontal) con los mismos px de diseño que en vertical. Comprueba
# la disposición: el riel de secciones en dos columnas de iconos (las once
# entradas del ingeniero caben sin desplazarse), el contenido hasta el margen
# derecho y, en vertical, la disposición de siempre (una columna).

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
    import json, os, sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.cliente.session_manager import SessionManager

    ancho, alto = int(sys.argv[1]), int(sys.argv[2])

    class Sesion:
        sinConexion = False
        generacion = 0
        def enviar(self, metodo, ruta, cuerpo=None):
            return sesion_backend.Resultado("ok", {}, 200)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)
    sesion_backend.ventana = lambda: Sesion()
    SessionManager.login({"usuario": "ingeniero", "nombre": "Ingeniero", "rol": "ingeniero",
                          "debe_cambiar_clave": False}, token="t")
    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    Window {
        id: ventana
        width: %d; height: %d; visible: true
        Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(ventana.width, ventana.height) }
        Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }
        QtObject { id: puenteFalso; property string machineState: "PREPARADO"; property bool connected: true }
        Opciones { objectName: "opciones"; anchors.fill: parent; puente: puenteFalso }
    }
    """ % (ancho, alto)
    ruta = f"{QML_DIR}/_prueba_hor_d_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(400)
    op = w.findChild(QQuickItem, "opciones")

    def hijo(n, nodo=None):
        for it in (nodo or op).childItems():
            if it.objectName() == n:
                return it
            e = hijo(n, it)
            if e is not None:
                return e
        return None

    riel = hijo("rielOpciones")
    nav = hijo("navegacionOpciones")
    entradas = [i for i in nav.childItems() if i.objectName().startswith("entrada_")]
    contenido = hijo("contenidoOpciones")
    def borde(it):
        p = it.mapToScene(it.boundingRect().topLeft())
        return [p.x(), p.y(), p.x() + it.width(), p.y() + it.height()]
    r = {
        "avisos": [a for a in avisos if "Binding loop" not in a],
        "entradas": len(entradas),
        "xs": sorted({round(i.x()) for i in entradas}),
        "riel_cabe": riel.property("contentHeight") <= riel.height() + 0.5,
        "riel": borde(riel),
        "contenido": borde(contenido),
        "escala": op.property("escala"),
        "ventana": [w.width(), w.height()],
    }
    print("RESULTADO=" + json.dumps(r))
''')


def _correr(ancho, alto):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, str(ancho), str(alto)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-3000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


def test_horizontal_riel_en_dos_columnas_y_contenido_a_lo_ancho():
    r = _correr(1920, 1200)
    assert r["avisos"] == []
    assert r["entradas"] == 11
    assert len(r["xs"]) == 2                 # dos columnas de iconos
    assert r["riel_cabe"]                    # sin desplazarse
    # misma escala que el lienzo vertical (mismos px de diseño)
    assert abs(r["escala"] - 1200 / 1196) < 1e-6
    x0, y0, x1, y1 = r["contenido"]
    assert x0 > r["riel"][2]                 # a la derecha del riel
    assert abs((1920 - x1) - 54 * r["escala"]) < 2   # margen derecho de 54
    assert y1 < 1200


def test_vertical_riel_en_una_columna():
    r = _correr(1200, 1920)
    assert r["avisos"] == []
    assert r["entradas"] == 11
    assert len(r["xs"]) == 1
    x0, _, x1, _ = r["contenido"]
    assert abs(x1 - 1142 * 1200 / 1196) < 2
