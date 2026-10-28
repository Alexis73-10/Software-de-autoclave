# tests/test_cancelacion_ciclo_en_curso_qml.py
#
# Flujo de CANCELAR CICLO / CONFIRMAR en PantallaCicloEnCurso
# (planeacion_pantalla_ciclo_en_curso.md §10): el botón abre un modal
# (ModalConfirmacion, FC-09 de la tanda 21) y solo su acción envía la
# cancelación; tocar fuera o "Volver" no envía nada; al terminar el ciclo el
# botón abre el modal de CONFIRMAR y su acción envía la confirmación; un error
# del envío abre un aviso.
# Los comandos se simulan con un QtObject en QML.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"
ES_JSON = RAIZ_QML.parents[1] / "i18n" / "es.json"

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        property int cancelaciones: 0
        property int confirmaciones: 0
        property bool ocupado: false
        property string error: ""
        function cancelar() { cancelaciones++ }
        function confirmar() { confirmaciones++ }
        function descartarError() { error = "" }
    }
    QtObject {
        id: progresoFalso
        property string resultado: ""
        property bool activo: false
    }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        id: pantalla
        anchors.fill: parent
        comandos: comandos
        progreso: progresoFalso
        datosVigentes: true
    }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, es_json, qml = sys.argv[1], sys.argv[2], sys.argv[3]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_cancelacion.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(300)
    hijos = ventana.findChildren(QObject)
    pantalla = [o for o in hijos if o.metaObject().className().startswith("PantallaCicloEnCurso_QML")][0]
    comandos = [o for o in hijos if o.metaObject().indexOfProperty("cancelaciones") >= 0][0]
    s = 600 / 1196   # px de la ventana por px del mockup

    def tocar(x, y):  # px del mockup (y desde abajo si es negativo)
        yy = y if y >= 0 else 1917 + y
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(x * s), int(yy * s)))
        QTest.qWait(80)

    def modal(nombre="modalCancelarCiclo"):
        return [o for o in ventana.findChildren(QObject) if o.objectName() == nombre][0]

    def dialogo():
        return modal()

    def accion(m):
        b = [o for o in m.findChildren(QQuickItem) if o.objectName() == "botonAccionModal"][0]
        c = b.mapToScene(b.boundingRect().center())
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
        QTest.qWait(80)

    def aviso():
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith("PanelModal_QML") and o.property("titulo") == "AVISO"][0]

    r = {}
    tocar(960, 1812)                                  # CANCELAR CICLO
    r["dialogo_abre"] = dialogo().property("visible")
    r["sin_envio_al_abrir"] = comandos.property("cancelaciones")
    tocar(598, 150)                                   # fondo oscurecido: descartar
    r["fondo_descarta"] = not dialogo().property("visible")
    r["sin_envio_al_descartar"] = comandos.property("cancelaciones")

    tocar(960, 1812)
    accion(dialogo())                                 # "Cancelar ciclo" del modal
    r["confirmar_envia"] = comandos.property("cancelaciones")
    r["dialogo_cierra"] = not dialogo().property("visible")

    comandos.setProperty("ocupado", True)            # envío en curso: botón deshabilitado
    QTest.qWait(50)
    tocar(960, 1812)
    r["ocupado_no_abre"] = not dialogo().property("visible")
    comandos.setProperty("ocupado", False)

    comandos.setProperty("error", "cancelar")         # el envío falló
    QTest.qWait(50)
    r["error_abre_aviso"] = aviso().property("visible")
    aviso().setProperty("visible", False)
    QTest.qWait(50)
    r["cerrar_aviso_descarta_error"] = comandos.property("error")

    pantalla.setProperty("resultado", "exitoso")      # ciclo terminado: CONFIRMAR
    QTest.qWait(50)
    tocar(960, 1812)
    r["confirmar_sin_modal_no_envia"] = comandos.property("confirmaciones")
    r["modal_confirmar_abre"] = modal("modalConfirmarCiclo").property("visible")
    accion(modal("modalConfirmarCiclo"))
    r["confirmar_fin"] = comandos.property("confirmaciones")
    r["sin_dialogo_al_confirmar"] = not dialogo().property("visible")
    r["avisos"] = avisos
    print(json.dumps(r))
""")


def test_flujo_cancelar_y_confirmar():
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), str(ES_JSON), _QML],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["avisos"] == []
    assert s["dialogo_abre"] is True
    assert s["sin_envio_al_abrir"] == 0
    assert s["fondo_descarta"] is True
    assert s["sin_envio_al_descartar"] == 0
    assert s["confirmar_envia"] == 1
    assert s["dialogo_cierra"] is True
    assert s["ocupado_no_abre"] is True
    assert s["error_abre_aviso"] is True
    assert s["cerrar_aviso_descarta_error"] == ""
    assert s["confirmar_sin_modal_no_envia"] == 0
    assert s["modal_confirmar_abre"] is True
    assert s["confirmar_fin"] == 1
    assert s["sin_dialogo_al_confirmar"] is True
