# tests/opciones_qml_banco.py
#
# Banco para probar secciones de OPCIONES en QML sin backend (O2f, O2g, O2h;
# tanda 6). Corre en un subproceso offscreen: abre Opciones.qml en una ventana
# de 1200x1920 con una sesión de SessionManager del rol pedido, un puente
# falso (machineState) y sesion_backend.ventana() reemplazada por un doble que
# responde según un diccionario "MÉTODO /ruta" -> (estado_http, datos).
# El paso a paso es código Python (ver `correr`): tiene a mano `raiz`,
# `buscar(nombre)`, `esperar(ms)`, `capturar(archivo)`, `rutas` (editable),
# `enviados` y `salida` (dict que se devuelve como JSON).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAPTURAS = RAIZ / "docs" / "informes" / "tanda6" / "capturas"

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui.service_ui.session_manager import SessionManager

    cfg = json.loads(sys.argv[1])
    rutas = {k: tuple(v) for k, v in cfg["rutas"].items()}
    enviados = []

    class Sesion:
        sinConexion = False
        def enviar(self, metodo, ruta, cuerpo=None):
            enviados.append([metodo, ruta, cuerpo])
            clave = f"{metodo} {ruta.split('?')[0]}"
            estado, datos = rutas.get(clave, (200, {}))
            if 200 <= estado < 300:
                return sesion_backend.Resultado("ok", datos, estado)
            causa = (datos or {}).get("codigo") or "error_generico"
            return sesion_backend.Resultado(causa, datos, estado)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)

    sesion_backend.ventana = lambda: Sesion()
    SessionManager.login({"usuario": "usuario_" + cfg["rol"], "nombre": cfg["rol"].capitalize(),
                          "rol": cfg["rol"], "debe_cambiar_clave": False}, token="t")
    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        QtObject { id: puenteFalso; objectName: "puente"; property string machineState: "%s"
                   property bool connected: true }
        Opciones { objectName: "opciones"; anchors.fill: parent; puente: puenteFalso }
    }
    """ % cfg["estado"]
    ruta = f"{QML_DIR}/_prueba_opciones_doble_{os.getpid()}.qml"
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
    raiz = w.findChild(QQuickItem, "opciones")

    def buscar(nombre, desde=None):
        def rec(it):
            if it.objectName() == nombre:
                return it
            for h in it.childItems():
                r = rec(h)
                if r is not None:
                    return r
            return None
        r = rec(desde or raiz)
        return r if r is not None else (desde or raiz).findChild(QObject, nombre)

    def esperar(ms=200):
        QTest.qWait(ms)

    def capturar(archivo):
        if cfg.get("capturas"):
            esperar(250)
            w.grabWindow().save(os.path.join(cfg["capturas"], archivo))

    def textos(desde=None):
        r = []
        def rec(it):
            for h in it.childItems():
                if not h.isVisible():
                    continue
                if h.inherits("QQuickText"):
                    r.append(h.property("text"))
                rec(h)
        rec(desde or raiz)
        return r

    salida = {}
    esperar(200)
    exec(cfg["pasos"])
    salida["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
    salida["enviados"] = enviados
    print("RESULTADO=" + json.dumps(salida, ensure_ascii=False, default=str))
''')


def correr(rol: str, pasos: str, rutas: dict | None = None, estado: str = "PREPARADO",
           capturas: bool = False, dir_capturas: Path | None = None) -> dict:
    destino = Path(dir_capturas or CAPTURAS)
    if capturas:
        destino.mkdir(parents=True, exist_ok=True)
    cfg = {"rol": rol, "estado": estado, "rutas": rutas or {}, "pasos": textwrap.dedent(pasos),
           "capturas": str(destino) if capturas else ""}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-3000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


def quieren_capturas() -> bool:
    return os.environ.get("TANDA6_CAPTURAS") == "1"
