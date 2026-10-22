# tests/opciones_qml_doble.py
#
# Arnés offscreen para las pantallas de OPCIONES de la tanda 6 (O2b–O2e):
# carga Pantallas/Opciones.qml en una ventana de 1200x1920 con una sesión del
# rol pedido, la sección elegida y un backend falso (respuestas fijas por
# ruta GET). Devuelve los textos visibles y propiedades de objetos con nombre,
# y guarda una captura si se pide. Corre en un subproceso (QGuiApplication).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAPTURAS = RAIZ / "docs" / "informes" / "tanda6" / "capturas"

_SCRIPT = textwrap.dedent(r"""
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.sesion_backend import Resultado
    from autoclave.ui.service_ui.session_manager import SessionManager

    cfg = json.loads(sys.argv[1])
    enviados = []

    class Falsa:
        def enviar(self, metodo, ruta, cuerpo=None):
            enviados.append([metodo, ruta, cuerpo])
            base = ruta.split("?")[0]
            if metodo == "GET":
                return Resultado("ok", cfg["get"].get(base, {}), 200)
            causa = cfg.get("causa_escritura", "ok")
            return Resultado(causa, {"ok": True} if causa == "ok" else {}, 200 if causa == "ok" else 409)
    sesion_backend.ventana = lambda: Falsa()
    for modulo, nombre, valor in cfg.get("parches", []):
        setattr(__import__(modulo, fromlist=[nombre]), nombre, valor)
    SessionManager.login({"id": 1, "nombre": "Prueba", "usuario": cfg["usuario"], "rol": cfg["rol"]})

    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        QtObject { id: puenteFalso; objectName: "puente"; property string machineState: "%s"; property bool connected: true }
        PanelTeclado { id: tecladoFalso; objectName: "teclado"; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; z: 10 }
        Opciones { objectName: "pantalla"; anchors.fill: parent; puente: puenteFalso; teclado: tecladoFalso
                   Component.onCompleted: seccionActiva = "%s" }
    }
    ''' % (cfg.get("estado", "PREPARADO"), cfg["seccion"])
    ruta = f"{QML_DIR}/_prueba_t6_opciones_{os.getpid()}.qml"
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
    pantalla = w.findChild(QObject, "pantalla")

    def buscar(nombre):
        return w.findChild(QObject, nombre)

    def textos():
        r = []
        def rec(it):
            for h in it.childItems():
                if not h.isVisible():
                    continue
                if h.inherits("QQuickText"):
                    r.append(h.property("text"))
                rec(h)
        rec(pantalla)
        return r

    pasos = []
    for paso in cfg["pasos"]:
        for nombre, metodo, args in paso.get("llamar", []):
            obj = buscar(nombre)
            getattr(obj, metodo)(*args) if args is not None else None
        for nombre, prop, valor in paso.get("fijar", []):
            buscar(nombre).setProperty(prop, valor)
        QTest.qWait(300)
        props = {}
        for nombre, prop in paso.get("leer", []):
            obj = buscar(nombre)
            v = None if obj is None else obj.property(prop)
            props[f"{nombre}.{prop}"] = v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
        pasos.append({"textos": textos(), "props": props})
        if cfg.get("capturas") and paso.get("captura"):
            w.grabWindow().save(os.path.join(cfg["capturas"], paso["captura"]))
    print("RESULTADO=" + json.dumps({"avisos": avisos, "pasos": pasos, "enviados": enviados},
                                    ensure_ascii=False, default=str))
""")


def correr(seccion: str, rol: str, get: dict, pasos: list, usuario: str = "yo",
           estado: str = "PREPARADO", capturar: bool = False, parches=None) -> dict:
    cfg = {"seccion": seccion, "rol": rol, "usuario": usuario, "get": get, "pasos": pasos,
           "estado": estado, "parches": parches or [],
           "capturas": str(CAPTURAS) if (capturar or os.environ.get("T6_CAPTURAS")) else ""}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-3000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


# Secciones de OPCIONES de solo lectura para todos los roles (O2c–O2e, tanda 6),
# al final de la navegación; las pruebas de navegación las agregan a lo esperado.
COMUNES_T6 = ["fecha_hora", "info_sistema", "bitacora"]
