# tests/test_hor_d_desbordes_qml.py
#
# Tanda horizontal, grupo D (ronda 2): en el lienzo horizontal (1920x1200),
# con los datos de ejemplo de tests/banco/hor_escenarios_d.py (programas de
# fábrica, parámetros del equipo, usuarios, canales de E/S...), ningún texto
# visible de Opciones pasa de su propia caja (contentWidth > width o, con alto
# fijo, contentHeight > height), en español y en inglés. Recorre las
# secciones y las subvistas con los textos más largos (Chaqueta, salidas de
# E/S, fase de esterilización, sensores).

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
    from autoclave.cliente.session_manager import SessionManager

    idioma, banco = sys.argv[1], sys.argv[2]
    i18n.cargar(); i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None
    # datos de ejemplo del banco del grupo D (sin sus escenarios de captura)
    ns = {"os": os, "cfg": {"banco": banco, "tema": "claro", "idioma": idioma},
          "sesion_backend": sesion_backend, "QObject": QObject,
          "qml": lambda *a, **k: None, "arnes": lambda *a, **k: None, "ACCIONES": {}}
    exec(compile(open(os.path.join(banco, "hor_escenarios_d.py"), encoding="utf-8").read(),
                 "hor_escenarios_d.py", "exec"), ns)
    ns["_d_rutas"]()
    sesion_backend.ventana = lambda: ns["_SesionD"]()
    SessionManager.login({"usuario": "ingeniero", "nombre": "Ingeniero", "rol": "ingeniero",
                          "debe_cambiar_clave": False}, token="t")
    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        id: ventana
        width: 1920; height: 1200; visible: true
        Binding { target: Escala; property: "horizontal"; value: true }
        Binding { target: Escala; property: "factor"; value: 1 }
        QtObject { id: puenteFalso; property string machineState: "PREPARADO"; property bool connected: true }
        PanelTeclado { id: tec; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; z: 10 }
        Opciones { objectName: "opciones"; anchors.fill: parent; puente: puenteFalso; teclado: tec }
    }
    """
    ruta = f"{QML_DIR}/_prueba_hor_d_desb_{os.getpid()}.qml"
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

    def _item(n, nodo):
        for it in nodo.childItems():
            if it.objectName() == n:
                return it
            e = _item(n, it)
            if e is not None:
                return e
        return None

    def hijo(n):
        # ítems por el árbol visual; controladores (QObject) por findChild
        return _item(n, op) or op.findChild(QObject, n)

    def desbordes(paso):
        malos = []
        def rec(it):
            for h in it.childItems():
                if not h.isVisible() or h.opacity() == 0:
                    continue
                if h.inherits("QQuickText"):
                    texto = h.property("text") or ""
                    if texto.strip() and h.width() > 0:
                        cw, ch = h.property("contentWidth"), h.property("contentHeight")
                        if cw > h.width() + 1.5:
                            malos.append([paso, "ancho", texto[:50], round(cw), round(h.width())])
                        if h.height() > 0 and ch > h.height() + 2.5:
                            malos.append([paso, "alto", texto[:50], round(ch), round(h.height())])
                rec(h)
        rec(op)
        return malos

    pasos = [
        ("parametros_ciclo", None),
        ("parametros_ciclo", lambda: (hijo("parametrosCicloController").abrirSeccion("esterilizacion"),
                                      hijo("parametrosCiclo").setProperty("vista", "seccion"))),
        ("parametros_ciclo", lambda: (hijo("parametrosCicloController").cargarSensores(),
                                      hijo("parametrosCiclo").setProperty("vista", "sensores"))),
        ("parametros_sistema", None),
        ("parametros_sistema", lambda: hijo("parametrosEquipoController").abrirGrupo("chaqueta")),
        ("parametros_sistema", lambda: hijo("parametrosEquipoController").abrirGrupo("maquina")),
        ("usuarios", None),
        ("entradas_salidas", None),
        ("entradas_salidas", lambda: hijo("opcionesEntradasSalidas").setProperty("segmento", "salidas")),
        ("entradas_salidas", lambda: hijo("opcionesEntradasSalidas").setProperty("segmento", "temperatura")),
        ("mantenimiento", None),
        ("conectividad", None),
        ("respaldo", None),
        ("info_sistema", None),
        ("fecha_hora", None),
        ("bitacora", None),
        ("opciones_avanzadas", None),
    ]
    malos = []
    for i, (seccion, accion) in enumerate(pasos):
        op.setProperty("seccionActiva", seccion)
        QTest.qWait(500)
        if accion:
            accion()
            QTest.qWait(500)
        malos += desbordes(f"{i}:{seccion}")
    print("RESULTADO=" + json.dumps({"malos": malos,
                                      "avisos": [a for a in avisos if "Binding loop" not in a][:10]},
                                     ensure_ascii=False))
''')


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_horizontal_ningun_texto_pasa_de_su_caja(idioma):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, idioma, str(RAIZ / "tests" / "banco")],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=300)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-3000:] + p.stderr[-3000:]
    r = json.loads(linea[len("RESULTADO="):])
    assert r["malos"] == [], r["malos"]
