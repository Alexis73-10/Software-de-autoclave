# tests/test_t34_esp_barra_espera_qml.py
#
# Tanda 34, ESP-01/ESP-02 (prompt_claude_code_tanda34.md): con el resultado y la
# cámara sin entregar, la barra inferior de Ciclo en curso muestra solo el
# mensaje de espera («Esperando cámara segura» o, en la espera fija tras un
# COMPLETADO, «Esperando condiciones de apertura: m:ss»), nunca el motivo; el
# motivo con valor y límite está en la fila NO ABRIR del panel de alarmas y
# avisos (campana, grupo «Alarmas»), que abre su detalle al tocarla. El modal
# de confirmación forzada conserva el motivo completo en su nota.
# PantallaCicloEnCurso real, offscreen; puente y progreso simulados.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.req("T34-ESP")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

MOTIVO_ES = "Temperatura 92 °C, máximo 80 °C"

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        property bool ocupado: false
        property string error: ""
        property string rechazo: ""
        property bool rolIngeniero: true
        function cancelar() {}
        function confirmar() {}
        function confirmarForzado(c) {}
        function refrescarRol() {}
        function descartarError() { error = "" }
    }
    QtObject {
        id: progresoFalso
        objectName: "progresoFalso"
        property string resultado: "fallo"
        property bool entregada: false
        property bool forzable: true
        property bool activo: true
        property int revisionFin: 1
        property string texto: "Esperando cámara segura: MOTIVO"
        function textoEntrega(idioma) { return texto }
        function armarFin(idioma) { return ({}) }
    }
    QtObject {
        id: puenteFalso
        property bool connected: true
        property string estadoModuloEs: "ok"
        property string cicloActivo: "03"
        property bool ackConfirmaEstadoSeguro: false
        property bool noAbrir: true
        property string noAbrirMotivo: "MOTIVO"
        property bool noAbrirPorSensor: false
        property bool paroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property bool modoPrueba: false
        property var contextoAviso: ({ "noAbrir": { "codigo": "temp_alta", "valores": { "temp": 92.0 },
            "limites": { "temp_max_apertura": 80.0, "temp_max_apertura_ciclo": 80.0 },
            "motivo": "MOTIVO", "textos": { "es": "MOTIVO" } },
            "apariciones": { "no_abrir": "2026-11-08T10:00:00" } })
    }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        objectName: "pantalla"
        anchors.fill: parent
        comandos: comandos
        progreso: progresoFalso
        puente: puenteFalso
    }
}
""".replace("MOTIVO", MOTIVO_ES)

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    import autoclave.ui_qml.bridge.i18n_qml  # noqa: F401  (singleton I18n)
    import autoclave.ui_qml.bridge.detalle_aviso_qml  # noqa: F401  (singleton DetalleAviso)
    from autoclave import i18n
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    i18n.cargar(); i18n.fijar_idioma("es")
    qml_dir, qml = sys.argv[1], sys.argv[2]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t34_esp.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(250)

    def obj(nombre, raiz=None):
        h = [o for o in (raiz or ventana).findChildren(QObject) if o.objectName() == nombre]
        return h[0] if h else None

    def visibles(raiz, nombre):
        return [o for o in raiz.findChildren(QQuickItem) if o.objectName() == nombre and o.isVisible()]

    def pulsar(item):
        c = item.mapToScene(item.boundingRect().center())
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
        QTest.qWait(300)

    progreso = obj("progresoFalso")
    r = {"indicador": obj("indicadorEntrega").isVisible(), "barra": obj("textoEntrega").property("text"),
         "barra_cabe": [obj("textoEntrega").property(p) for p in
                        ("contentWidth", "width", "contentHeight", "height")]}

    # panel de alarmas y avisos (campana): grupo «Alarmas» con la fila NO ABRIR
    panel = [o for o in ventana.findChildren(QObject)
             if o.metaObject().className().startswith("PanelNotificaciones_QML")][0]
    panel.setProperty("visible", True)
    QTest.qWait(100)
    obj("grupoAlarmas", panel).setProperty("expandido", True)
    QTest.qWait(150)
    seccion = obj("seguridad_alarma", panel)
    fila = obj("filaNoAbrir", seccion)
    r["fila_visible"] = fila.isVisible()
    r["fila_texto"] = fila.property("descripcion")
    area = visibles(fila, "areaFilaAlarma")
    pulsar(area[0] if area else fila)
    detalle = obj("detalleAvisoSeguridad", seccion)
    r["detalle_abre"] = detalle is not None and detalle.property("abierta") is True
    textos = []
    def tx(it):
        for h in it.childItems():
            if h.isVisible() and h.inherits("QQuickText"):
                textos.append(h.property("text"))
            tx(h)
    tx(ventana.contentItem())
    r["textos_detalle"] = textos
    if detalle is not None:
        detalle.setProperty("abierta", False)
    panel.setProperty("visible", False)
    QTest.qWait(100)

    # modal forzado: conserva el motivo completo en la nota
    r["nota_forzado"] = obj("modalConfirmarForzado").property("nota")

    # espera fija tras COMPLETADO: «Esperando condiciones de apertura: m:ss»
    progreso.setProperty("texto", "Esperando condiciones de apertura: 2:05")
    progreso.setProperty("revisionFin", 2)
    QTest.qWait(60)
    r["barra_espera"] = obj("textoEntrega").property("text")
    # falla cerrada: sin texto, el mensaje sin motivo
    progreso.setProperty("texto", "")
    progreso.setProperty("revisionFin", 3)
    QTest.qWait(60)
    r["barra_vacia"] = obj("textoEntrega").property("text")
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=True))
""")


@pytest.fixture(scope="module")
def r():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
             "PYTHONPATH": str(RAIZ / "src")}, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_barra_inferior_sin_el_motivo(r):
    assert r["indicador"] is True
    assert r["barra"] == "Esperando cámara segura"
    assert "92" not in r["barra"] and "máximo" not in r["barra"]


def test_barra_el_texto_cabe_en_su_cuadro(r):
    cw, w, ch, h = r["barra_cabe"]
    assert cw <= w + 0.5 and ch <= h + 0.5, r["barra_cabe"]


def test_fuente_barra_letra_que_se_ajusta_sin_elide():
    codigo = (RAIZ_QML / "Pantallas" / "PantallaCicloEnCurso.qml").read_text(encoding="utf-8")
    i = codigo.index('objectName: "textoEntrega"')
    bloque = codigo[i:codigo.index("}", i)]
    assert "fontSizeMode: Text.Fit" in bloque and "elide" not in bloque


def test_fila_no_abrir_con_el_motivo_valor_y_limite(r):
    assert r["fila_visible"] is True
    assert MOTIVO_ES in r["fila_texto"]


def test_tocar_la_fila_abre_su_detalle(r):
    assert r["detalle_abre"] is True
    todo = " | ".join(r["textos_detalle"])
    assert "92" in todo and "80" in todo, todo


def test_modal_forzado_conserva_el_motivo(r):
    assert MOTIVO_ES in r["nota_forzado"]


def test_espera_fija_se_muestra_con_su_tiempo(r):
    assert r["barra_espera"] == "Esperando condiciones de apertura: 2:05"


def test_sin_texto_falla_cerrada_al_mensaje_sin_motivo(r):
    assert r["barra_vacia"] == "Esperando cámara segura"
