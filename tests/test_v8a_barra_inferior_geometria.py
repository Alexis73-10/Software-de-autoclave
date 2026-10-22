"""V8a (tanda 8): D8-5.2 y D8-5.10, barra inferior flotante.

D8-5.2: la barra inferior flotante tiene EXACTAMENTE el mismo ancho (y el
mismo borde izquierdo) que la tarjeta de contenido que está encima, en todas
las pantallas que la llevan. Prueba de geometría por pantalla, en dos
resoluciones.
D8-5.10: en Opciones la barra es flotante (fuera de la tarjeta, debajo) en
todas sus secciones.
"""

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
    from PySide6.QtCore import QUrl, QMetaObject, Q_RETURN_ARG, Q_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401 (la raíz llega como QQuickWindow)
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui.service_ui.session_manager import SessionManager

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma("es")
    i18n_qml.instancia._consultar = lambda: None

    class Sesion:
        sinConexion = False
        def enviar(self, metodo, ruta, cuerpo=None):
            return sesion_backend.Resultado("ok", {}, 200)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)

    if cfg["pantalla"].startswith("Opciones"):
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
        function buscar(it, n) {
            if (it.objectName === n) return it
            const hijos = it.children || []
            for (let i = 0; i < hijos.length; ++i) {
                const r = buscar(hijos[i], n)
                if (r) return r
            }
            return null
        }
        function rect(n) {
            const it = buscar(contentItem, n)
            if (!it) return null
            const p = it.mapToItem(contentItem, 0, 0)
            return {x: p.x, y: p.y, w: it.width, h: it.height, visible: it.visible}
        }
        function seccion(s) { buscar(contentItem, "pantalla").seccionActiva = s }
        function secciones() {
            const l = buscar(contentItem, "pantalla").secciones || []
            return JSON.stringify(l.map(x => x.clave))
        }
        function medir(barra, tarjetas) {
            const r = {barra: rect(barra), tarjetas: tarjetas.map(t => rect(t))}
            return JSON.stringify(r)
        }
        Binding { target: Escala; property: "factor"; value: %f }
        QtObject { id: puenteFalso; property string machineState: "PREPARADO"
                   property bool connected: true }
        %s { objectName: "pantalla"; anchors.fill: parent }
    }
    """ % (cfg["ancho"], cfg["alto"], cfg["ancho"] / 1200.0, cfg["pantalla"])
    ruta = f"{QML_DIR}/_prueba_v8a_barra_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(400)

    def medir():
        return json.loads(QMetaObject.invokeMethod(w, "medir", Q_RETURN_ARG("QVariant"),
                                                   Q_ARG("QVariant", cfg["barra"]),
                                                   Q_ARG("QVariant", cfg["tarjetas"])))
    salida = {"medidas": {}}
    if cfg.get("secciones"):
        secciones = json.loads(QMetaObject.invokeMethod(w, "secciones", Q_RETURN_ARG("QVariant")))
        salida["secciones"] = secciones
        for s in [""] + secciones:
            QMetaObject.invokeMethod(w, "seccion", Q_ARG("QVariant", s))
            QTest.qWait(250)
            salida["medidas"][s or "inicio"] = medir()
            if cfg.get("capturas"):
                w.grabWindow().save(os.path.join(cfg["capturas"], f"opciones_{s or 'inicio'}.png"))
    else:
        salida["medidas"]["pantalla"] = medir()
        if cfg.get("capturas"):
            w.grabWindow().save(os.path.join(cfg["capturas"], cfg["pantalla"] + ".png"))
    print("RESULTADO=" + json.dumps(salida))
''')

# pantalla, barra, tarjeta(s) de encima. MenuPrincipal no tiene tarjeta
# única: la barra mide lo mismo que la grilla de tarjetas (de la primera a la
# derecha de la segunda) — DECISIÓN SIN CONFIRMAR de V8a.
PANTALLAS = [
    ("Login", "barraInferiorLogin", ["tarjetaLogin"]),
    ("CambioClave", "barraInferiorCambioClave", ["tarjetaCambioClave"]),
    ("NuevoUsuario", "barraInferiorNuevoUsuario", ["tarjetaNuevoUsuario"]),
    ("MenuPrincipal", "barraInferiorMenu", ["tarjetaIniciarSesion", "tarjetaHistorial"]),
    ("PantallaPreciclo", "barraInferiorPreciclo", ["tarjetaPreciclo"]),
    ("PantallaCicloEnCurso", "barraInferiorCicloEnCurso", ["tarjetaCicloEnCurso"]),
    ("Opciones", "barraInferiorOpciones", ["tarjetaOpciones"]),
]
RESOLUCIONES = [(1200, 1920), (1024, 1638)]


def correr(pantalla, barra, tarjetas, ancho, alto, secciones=False, capturas=""):
    cfg = {"pantalla": pantalla, "barra": barra, "tarjetas": tarjetas, "ancho": ancho,
           "alto": alto, "secciones": secciones, "capturas": capturas}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, pantalla + "\n" + p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


def _comprobar(m, nombre):
    b = m["barra"]
    assert b is not None and b["visible"], (nombre, "sin barra")
    ts = m["tarjetas"]
    assert all(t is not None for t in ts), (nombre, "sin tarjeta")
    izquierda = ts[0]["x"]
    derecha = max(t["x"] + t["w"] for t in ts)
    assert abs(b["x"] - izquierda) < 0.5, (nombre, b, ts)
    assert abs(b["w"] - (derecha - izquierda)) < 0.5, (nombre, b, ts)
    # flotante: la barra queda debajo de la tarjeta, sin solaparse
    assert b["y"] >= max(t["y"] + t["h"] for t in ts) - 0.5, (nombre, b, ts)


@pytest.mark.parametrize("ancho, alto", RESOLUCIONES)
@pytest.mark.parametrize("pantalla, barra, tarjetas", PANTALLAS[:-1])
def test_barra_mide_lo_mismo_que_la_tarjeta(pantalla, barra, tarjetas, ancho, alto):
    r = correr(pantalla, barra, tarjetas, ancho, alto)
    _comprobar(r["medidas"]["pantalla"], pantalla)


@pytest.mark.parametrize("ancho, alto", RESOLUCIONES)
def test_opciones_barra_flotante_en_todas_las_secciones(ancho, alto):
    pantalla, barra, tarjetas = PANTALLAS[-1]
    r = correr(pantalla, barra, tarjetas, ancho, alto, secciones=True)
    assert len(r["secciones"]) >= 10, r["secciones"]
    for nombre, m in r["medidas"].items():
        _comprobar(m, "Opciones/" + nombre)
