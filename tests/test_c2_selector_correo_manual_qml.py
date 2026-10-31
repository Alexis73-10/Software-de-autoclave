# tests/test_c2_selector_correo_manual_qml.py
#
# C2 (tanda 7): correo escrito a mano en SelectorDestino.qml. Causa raíz del
# fallo reportado por Cristian: el panel de teclado entrega lo escrito AL
# INSTANTE (escritura en vivo, cada tecla llama al callback), y el selector
# tomaba ese callback como "elegido": la primera dirección parcial con forma
# válida ("Juan@gmail.c") se enviaba antes de terminar de escribir. Aquí se
# exige que nada se elija mientras se escribe, que Confirmar lleve a un paso
# de confirmación y que el usuario decida: solo la dirección escrita, o junto
# con las guardadas. Una dirección mal escrita se avisa sin enviar.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    property var elegidos: []
    property int cancelaciones: 0
    property var guardados: [{"nombre": "Mantenimiento", "correo": "mant@x.com"},
                             {"nombre": "Calidad", "correo": "cal@x.com"}]
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
            onElegido: correo => ventana.elegidos = ventana.elegidos.concat([correo])
            onCancelado: ventana.cancelaciones++
        }
        PanelTeclado { id: panel; objectName: "panelTeclado" }
    }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml.controllers import teclado_numerico_controller  # noqa: F401
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, qml = sys.argv[1], sys.argv[2]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_selector_c2.qml"))
    w = comp.createWithInitialProperties({})
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

    panel = item(raiz, "panelTeclado")
    from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import \
        TecladoAlfanumericoController
    ctrl = [o for o in item(raiz, "tecladoAlfanumerico").findChildren(QObject)
            if isinstance(o, TecladoAlfanumericoController)][0]

    def escribir(texto):
        for ch in texto:
            ctrl.presionarCaracter(ch)
            QTest.qWait(5)

    def elegidos():
        v = w.property("elegidos")
        return list(v.toVariant() if hasattr(v, "toVariant") else v)

    r = {}
    escenario = sys.argv[3]
    if escenario == "todos":
        tocar("destinoTodos")
        print("RESULTADO=" + json.dumps({"elegidos": elegidos(), "avisos": avisos}))
        sys.exit(0)
    tocar("destinoOtro")
    r["teclado_abierto"] = panel.property("abierto")
    if escenario == "solo":
        escribir("juan@gmail.com")
        r["elegidos_al_escribir"] = elegidos()
        ctrl.confirmar(); QTest.qWait(50)
        r["teclado_tras_confirmar"] = panel.property("abierto")
        r["confirmacion_visible"] = visible("confirmacionManual")
        r["boton_mixto_visible"] = visible("botonManualYGuardados")
        r["texto_manual"] = item(raiz, "textoCorreoManual").property("text")
        tocar("botonSoloManual")
    elif escenario == "mixto":
        escribir("juan@gmail.com")
        ctrl.confirmar(); QTest.qWait(50)
        tocar("botonManualYGuardados")
    elif escenario == "invalido":
        escribir("juan@gmail")
        ctrl.confirmar(); QTest.qWait(50)
        r["confirmacion_visible"] = visible("confirmacionManual")
        r["aviso_invalido"] = visible("avisoCorreoInvalido")
        r["boton_solo_habilitado"] = item(raiz, "botonSoloManual").property("habilitado")
        tocar("botonSoloManual")
        r["elegidos_invalido"] = elegidos()
        tocar("botonCorregirManual")
        r["teclado_corregir"] = panel.property("abierto")
        r["valor_corregir"] = ctrl.property("texto")
        escribir("juan@gmail.com")     # el teclado reemplaza el valor abierto al escribir
        ctrl.confirmar(); QTest.qWait(50)
        tocar("botonSoloManual")
    elif escenario == "cancelar":
        escribir("juan@gmail.com")
        ctrl.cancelar(); QTest.qWait(50)
        r["confirmacion_visible"] = visible("confirmacionManual")
    r["elegidos"] = elegidos()
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


def _correr(escenario):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML, escenario],
                          capture_output=True, text=True, encoding="utf-8", env=env,
                          timeout=90, cwd=RAIZ_QML.parents[3])
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_escribir_no_elige_nada_hasta_confirmar_y_enviar_solo_a_la_manual():
    r = _correr("solo")
    assert r["avisos"] == []
    assert r["teclado_abierto"] is True
    # causa raíz: antes cada tecla elegía la dirección a medio escribir
    assert r["elegidos_al_escribir"] == []
    assert r["teclado_tras_confirmar"] is False
    assert r["confirmacion_visible"] is True and r["boton_mixto_visible"] is True
    assert r["texto_manual"].lower() == "juan@gmail.com"
    assert [e.lower() for e in r["elegidos"]] == ["juan@gmail.com"]


def test_manual_junto_con_las_guardadas():
    r = _correr("mixto")
    assert r["avisos"] == []
    assert [e.lower() for e in r["elegidos"]] == ["juan@gmail.com,mant@x.com,cal@x.com"]


def test_direccion_invalida_se_avisa_y_se_puede_corregir():
    r = _correr("invalido")
    assert r["avisos"] == []
    assert r["confirmacion_visible"] is True and r["aviso_invalido"] is True
    assert r["boton_solo_habilitado"] is False and r["elegidos_invalido"] == []
    assert r["teclado_corregir"] is True and r["valor_corregir"].lower() == "juan@gmail"
    assert [e.lower() for e in r["elegidos"]] == ["juan@gmail.com"]


def test_cancelar_el_teclado_no_elige_nada():
    r = _correr("cancelar")
    assert r["avisos"] == []
    assert r["confirmacion_visible"] is False and r["elegidos"] == []


def test_todos_los_guardados():
    r = _correr("todos")
    assert r["avisos"] == []
    assert r["elegidos"] == ["mant@x.com,cal@x.com"]
