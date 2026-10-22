# tests/i4_truncado_banco.py
#
# I4 (tanda 6): revisión de truncado en una pantalla de 1024 px de ancho
# (1024x1638, proporción 5:8 del lienzo; Escala.factor = 1024/1200). Cada
# pantalla QML se carga sola, offscreen, en un subproceso, sin backend (la
# sesión HTTP es un doble que responde 200 {}), en el idioma pedido. Devuelve
# los textos visibles truncados (`truncated`, el elide de Qt) o desbordados
# (sin elide ni ajuste de línea y más anchos que su caja) y, si se pide,
# guarda una captura en docs/informes/tanda6/capturas/I4_<idioma>_<pantalla>.png.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAPTURAS = RAIZ / "docs" / "informes" / "tanda6" / "capturas"
ANCHO, ALTO = 1024, 1638

# Pantallas del equipo (las secciones de Opciones se cargan solas).
PANTALLAS = [
    "IntroArranque", "Login", "CambioClave", "NuevoUsuario", "MenuPrincipal",
    "PantallaPreciclo", "PantallaCicloEnCurso", "Instalacion", "Reposo", "Opciones",
    "OpcionesParametrosCiclo", "OpcionesParametrosEquipo", "OpcionesUsuarios",
    "OpcionesFechaHora", "OpcionesInfoSistema", "OpcionesBitacora", "OpcionesCalibracionAtm",
    "OpcionesCalibracionSensor", "OpcionesConectividad", "OpcionesRespaldo",
    "OpcionesEntradasSalidas", "OpcionesMantenimiento",
]

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui.service_ui.session_manager import SessionManager

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None        # sin backend: no cambia el idioma

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
        width: %d; height: %d; visible: true
        // elide/wrapMode son enums: se leen aquí, en JS, como enteros
            function revisar() {
                const raiz = contentItem
                const malos = []; const vistos = []
                function rec(it) {
                    const hijos = it.children || []
                    for (let i = 0; i < hijos.length; ++i) {
                        const h = hijos[i]
                        if (!h.visible || h.opacity === 0) continue
                        if (h.truncated !== undefined && h.elide !== undefined
                                && typeof h.text === "string" && h.text.trim() !== "") { vistos.push(h.text)
                            if (h.truncated)
                                malos.push({tipo: "truncado", texto: h.text, obj: h.objectName,
                                            ancho: Math.round(h.width)})
                            else if (h.elide === Text.ElideNone && h.wrapMode === Text.NoWrap
                                     && h.width > 0 && h.contentWidth > h.width + 2)
                                malos.push({tipo: "desborda", texto: h.text, obj: h.objectName,
                                            ancho: Math.round(h.width),
                                            contenido: Math.round(h.contentWidth)})
                        }
                        rec(h)
                    }
                }
                rec(raiz)
                return JSON.stringify({malos: malos, vistos: vistos})
            }
        Binding { target: Escala; property: "factor"; value: %f }
        QtObject { id: puenteFalso; property string machineState: "PREPARADO"
                   property bool connected: true }
        %s { objectName: "pantalla"; anchors.fill: parent }
    }
    """ % (cfg["ancho"], cfg["alto"], cfg["ancho"] / 1200.0, cfg["pantalla"])
    ruta = f"{QML_DIR}/_prueba_i4_truncado_{os.getpid()}.qml"
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
    QTest.qWait(700)

    from PySide6.QtCore import QMetaObject, Q_RETURN_ARG
    _r = json.loads(QMetaObject.invokeMethod(w, "revisar", Q_RETURN_ARG("QVariant")))
    malos, vistos = _r["malos"], _r["vistos"]
    if cfg.get("captura"):
        w.grabWindow().save(cfg["captura"])
    print("RESULTADO=" + json.dumps({"malos": malos, "vistos": vistos, "avisos": avisos[:20]}, ensure_ascii=False))
''')


def revisar(pantalla: str, idioma: str, captura: bool = False) -> dict:
    archivo = str(CAPTURAS / f"I4_{idioma}_{pantalla}.png") if captura else ""
    cfg = {"pantalla": pantalla, "idioma": idioma, "ancho": ANCHO, "alto": ALTO, "captura": archivo}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, pantalla + "\n" + p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


if __name__ == "__main__":
    for idioma in ("es", "en"):
        for nombre in PANTALLAS:
            r = revisar(nombre, idioma, captura=True)
            print(idioma, nombre, json.dumps(r["malos"], ensure_ascii=False))
