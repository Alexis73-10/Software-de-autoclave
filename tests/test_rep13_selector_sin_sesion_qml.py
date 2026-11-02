# tests/test_rep13_selector_sin_sesion_qml.py
#
# REP-13 (DR-D10, tanda dashboard-reportes): SelectorDestino.qml sin sesión no
# ofrece escribir otra dirección («Otro correo…» ni su confirmación); muestra
# los guardados y la nota «Inicie sesión para escribir otro correo». Sin sesión
# y sin guardados no hay destino (`hayDestino` false) y el Menú Principal
# deshabilita Enviar con «No hay destinatarios guardados». Con sesión, nada
# cambia (lo cubre además tests/test_c2_selector_correo_manual_qml.py).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_QML_SELECTOR = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    property var elegidos: []
    property bool sesion: false
    property var guardados: []
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    Item {
        anchors.fill: parent
        SelectorDestino {
            id: selector
            objectName: "selector"
            anchors.fill: parent
            escala: 0.5
            destinos: ventana.guardados
            teclado: panel
            sesionActiva: ventana.sesion
            onElegido: correo => ventana.elegidos = ventana.elegidos.concat([correo])
        }
        PanelTeclado { id: panel; objectName: "panelTeclado" }
    }
}
"""

_QML_MENU = r"""
import QtQuick
import Tema
import "Pantallas"
import "Componentes"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    property bool sesion: false
    property var guardados: []
    QtObject {
        id: accionesFalsas
        property bool correoConfigurado: true
        property bool ocupado: false
        property var destinos: ventana.guardados
        function actualizarCorreo() {}
    }
    MenuPrincipal {
        anchors.fill: parent
        acciones: accionesFalsas
        sesionActiva: ventana.sesion
        teclado: panel
    }
    PanelTeclado { id: panel; objectName: "panelTeclado" }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, qml, escenario = sys.argv[1], sys.argv[2], sys.argv[3]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_rep13.qml"))
    guardados = [{"nombre": "Mantenimiento", "correo": "mant@x.com"},
                 {"nombre": "Calidad", "correo": "cal@x.com"}]
    inicial = {
        "sin_sesion": {"sesion": False, "guardados": guardados},
        "sin_sesion_sin_guardados": {"sesion": False, "guardados": []},
        "con_sesion_sin_guardados": {"sesion": True, "guardados": []},
        "cierre_escribiendo": {"sesion": True, "guardados": guardados},
        "menu_sin_sesion_sin_guardados": {"sesion": False, "guardados": []},
        "menu_sin_sesion_con_guardados": {"sesion": False, "guardados": guardados},
        "menu_con_sesion_sin_guardados": {"sesion": True, "guardados": []},
    }[escenario]
    w = comp.createWithInitialProperties(inicial)
    assert w is not None, comp.errorString()
    w.show()
    QTest.qWait(200)

    def item(o, nombre):
        for h in o.childItems():
            if h.objectName() == nombre:
                return h
            encontrado = item(h, nombre)
            if encontrado is not None:
                return encontrado
        return None

    raiz = w.contentItem()
    def tocar(nombre):
        o = item(raiz, nombre)
        assert o is not None, nombre
        c = o.mapToScene(o.boundingRect().center()).toPoint()
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, c)
        QTest.qWait(30)

    def visible(nombre):
        o = item(raiz, nombre)
        return bool(o is not None and o.isVisible())

    def elegidos():
        v = w.property("elegidos")
        return list(v.toVariant() if hasattr(v, "toVariant") else v)

    r = {}
    if escenario.startswith("menu_"):
        # Reportes ya no vive en el menú (pantalla propia, cubierta en test_rep_pantalla_reportes_qml)
        for nombre in ("botonEnviarCiclo", "botonEnviarMarcados"):
            o = item(raiz, nombre)
            assert o is not None, nombre
            r[nombre] = {"texto": o.property("texto"), "habilitado": o.property("habilitado")}
        r["avisos"] = avisos
        print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
        sys.exit(0)

    panel = item(raiz, "panelTeclado")
    selector = item(raiz, "selector")
    r["otro_visible"] = visible("destinoOtro")
    r["nota_sesion"] = visible("notaInicieSesion")
    r["nota_sin_guardados"] = visible("notaSinGuardados")
    r["textos_notas"] = [item(raiz, "notaInicieSesion").property("text"),
                         item(raiz, "notaSinGuardados").property("text")]
    r["hay_destino"] = selector.property("hayDestino")
    r["destinos_visibles"] = [visible("destino_Mantenimiento"), visible("destino_Calidad")]
    if escenario in ("sin_sesion", "sin_sesion_sin_guardados"):
        # aunque alguien llame abrirManual (o toque donde estaba la opción), no se abre
        QMetaObject.invokeMethod(selector, "abrirManual")
        QTest.qWait(30)
        r["teclado_tras_abrir_manual"] = panel.property("abierto")
        r["confirmacion_visible"] = visible("confirmacionManual")
        if escenario == "sin_sesion":
            tocar("destino_Mantenimiento")
            tocar("destinoTodos")
    elif escenario == "cierre_escribiendo":
        from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import \
            TecladoAlfanumericoController
        ctrl = [o for o in item(raiz, "tecladoAlfanumerico").findChildren(QObject)
                if isinstance(o, TecladoAlfanumericoController)][0]
        tocar("destinoOtro")
        r["teclado_abierto"] = panel.property("abierto")
        for ch in "juan@gmail.com":
            ctrl.presionarCaracter(ch)
            QTest.qWait(5)
        w.setProperty("sesion", False)       # la sesión se cierra (inactividad, standby)
        QTest.qWait(50)
        r["teclado_tras_cierre"] = panel.property("abierto")
        r["confirmacion_tras_cierre"] = visible("confirmacionManual")
        r["otro_tras_cierre"] = visible("destinoOtro")
        r["manual_tras_cierre"] = selector.property("manual")
    r["elegidos"] = elegidos()
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


def _correr(qml, escenario):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, str(RAIZ_QML), qml, escenario],
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          timeout=90, cwd=RAIZ_QML.parents[3])
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


_NOTA_SESION = "Inicie sesión para escribir otro correo"
_SIN_GUARDADOS = "No hay destinatarios guardados"


def test_sin_sesion_solo_guardados_y_nota():
    r = _correr(_QML_SELECTOR, "sin_sesion")
    assert r["avisos"] == []
    assert r["otro_visible"] is False
    assert r["nota_sesion"] is True and r["nota_sin_guardados"] is False
    assert r["destinos_visibles"] == [True, True] and r["hay_destino"] is True
    assert r["teclado_tras_abrir_manual"] is False and r["confirmacion_visible"] is False
    # los guardados se siguen eligiendo
    assert r["elegidos"] == ["mant@x.com", "mant@x.com,cal@x.com"]


def test_sin_sesion_sin_guardados_no_hay_destino():
    r = _correr(_QML_SELECTOR, "sin_sesion_sin_guardados")
    assert r["avisos"] == []
    assert r["otro_visible"] is False and r["nota_sesion"] is False
    assert r["nota_sin_guardados"] is True and r["hay_destino"] is False
    assert r["teclado_tras_abrir_manual"] is False and r["elegidos"] == []


def test_con_sesion_sin_guardados_conserva_otro_correo():
    r = _correr(_QML_SELECTOR, "con_sesion_sin_guardados")
    assert r["avisos"] == []
    assert r["otro_visible"] is True and r["hay_destino"] is True
    assert r["nota_sesion"] is False and r["nota_sin_guardados"] is False


def test_cerrar_la_sesion_mientras_se_escribe_descarta_la_direccion():
    r = _correr(_QML_SELECTOR, "cierre_escribiendo")
    assert r["avisos"] == []
    assert r["otro_visible"] is True and r["teclado_abierto"] is True
    assert r["teclado_tras_cierre"] is False and r["confirmacion_tras_cierre"] is False
    assert r["otro_tras_cierre"] is False and r["manual_tras_cierre"] == ""
    assert r["elegidos"] == []


def test_textos_de_las_notas_es():
    r = _correr(_QML_SELECTOR, "sin_sesion")
    assert r["textos_notas"] == [_NOTA_SESION, _SIN_GUARDADOS]


_BOTONES = ("botonEnviarCiclo", "botonEnviarMarcados")


def test_menu_sin_sesion_sin_guardados_enviar_deshabilitado():
    r = _correr(_QML_MENU, "menu_sin_sesion_sin_guardados")
    assert r["avisos"] == []
    for b in _BOTONES:
        assert r[b]["habilitado"] is False, b
        assert r[b]["texto"] == _SIN_GUARDADOS, b


def test_menu_con_guardados_o_con_sesion_enviar_como_antes():
    for escenario in ("menu_sin_sesion_con_guardados", "menu_con_sesion_sin_guardados"):
        r = _correr(_QML_MENU, escenario)
        # Ciclo del Historial: solo dependen de ocupado y correo
        assert r["botonEnviarCiclo"] == {"texto": "ENVIAR POR CORREO", "habilitado": True}, escenario
        for b in _BOTONES:
            assert r[b]["texto"] == "ENVIAR POR CORREO", (escenario, b)


# Trazabilidad (matriz REQ-37..REQ-50, dashboard de Reportes)
import pytest as _pytest  # noqa: E402

pytestmark = [_pytest.mark.req("REQ-49")]
