# tests/banco/opciones_qml_banco.py
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

RAIZ = Path(__file__).resolve().parents[2]
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
    from autoclave.cliente.session_manager import SessionManager

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
        width: %d; height: %d; visible: true
        Binding { target: Escala; property: "factor"; value: %f }
        QtObject { id: puenteFalso; objectName: "puente"; property string machineState: "%s"
                   property bool connected: true }
        Opciones { objectName: "opciones"; anchors.fill: parent; puente: puenteFalso }
    }
    """ % (cfg["ancho"], cfg["alto"], cfg["ancho"] / 1200.0, cfg["estado"])
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

    # U10b (tanda 10, D10-1.5): con `revisar`, cada capturar() revisa además
    # los textos de la ventana (tests/helpers/textos_caben_qml.FUNCION_REVISAR) y deja
    # el resultado en salida["revisiones"][archivo]
    revisor = None
    if cfg.get("funcion"):
        from PySide6.QtCore import QMetaObject, QUrl as _QUrl, Q_ARG, Q_RETURN_ARG
        from PySide6.QtQml import QQmlComponent
        _c = QQmlComponent(engine)
        _c.setData(chr(10).join(["import QtQuick", "QtObject {", cfg["funcion"], "}", ""]).encode("utf-8"),
                   _QUrl.fromLocalFile(QML_DIR + "/_revisor_textos.qml"))
        revisor = _c.create()

    def revisar_textos(nombre, desde=None):
        esperar(250)
        r = json.loads(QMetaObject.invokeMethod(revisor, "revisarDesde", Q_RETURN_ARG("QVariant"),
                                                Q_ARG("QVariant", desde or w.contentItem())))
        salida.setdefault("revisiones", {})[nombre] = r

    def capturar(archivo):
        if revisor is not None:
            revisar_textos(archivo)
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
           capturas: bool = False, dir_capturas: Path | None = None,
           ancho: int = 1200, alto: int = 1920, revisar: bool = False) -> dict:
    """U10b: `ancho`/`alto` (Escala.factor = ancho/1200) y `revisar` (cada
    capturar() revisa los textos; ver tests/helpers/textos_caben_qml.py)."""
    destino = Path(dir_capturas or CAPTURAS)
    if capturas:
        destino.mkdir(parents=True, exist_ok=True)
    cfg = {"rol": rol, "estado": estado, "rutas": rutas or {}, "pasos": textwrap.dedent(pasos),
           "capturas": str(destino) if capturas else "", "ancho": ancho, "alto": alto}
    if revisar:
        from tests.helpers.textos_caben_qml import FUNCION_REVISAR
        cfg["funcion"] = FUNCION_REVISAR
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
