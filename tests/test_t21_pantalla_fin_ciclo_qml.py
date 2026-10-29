# tests/test_t21_pantalla_fin_ciclo_qml.py
#
# Tanda 21, ola 2 (planeacion_fin_de_ciclo.md), PantallaCicloEnCurso real,
# offscreen, con dobles en QML:
#   - FC-01: el panel de fin de ciclo reemplaza a la gráfica con fallo,
#     cancelado, emergencia y resultado desconocido (falla cerrada); no con
#     exitoso ni mientras el ciclo corre. Sin franja NO CONFORME ni recuadro.
#   - FC-05: «Ver gráfica» muestra la gráfica y la píldora roja; el regreso
#     automático (tiempo inyectable) vuelve al panel y cierra la pantalla
#     completa; un toque reinicia la cuenta; con un modal abierto se detiene.
#   - FC-07: exitoso con alarmas: píldora ámbar que abre el panel de
#     observaciones; el modal de CONFIRMAR lleva la nota.
#   - FC-09: CONFIRMAR abre su modal (fallo / exitoso / estado seguro).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.req("T21-FC")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        objectName: "comandosFalsos"
        property int confirmaciones: 0
        property int cancelaciones: 0
        property bool ocupado: false
        property string error: ""
        function cancelar() { cancelaciones++ }
        function confirmar() { confirmaciones++ }
        function descartarError() { error = "" }
    }
    QtObject {
        id: progresoFalso
        objectName: "progresoFalso"
        property string resultado: ""
        property bool activo: true
        property int revisionFin: 0
        property var datosFin: ({})
        function armarFin(idioma) { return datosFin }
    }
    QtObject {
        id: puenteFalso
        objectName: "puenteFalso"
        property bool connected: true
        property string estadoModuloEs: "ok"
        property string cicloActivo: "03"
        property bool ackConfirmaEstadoSeguro: false
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
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n

    qml_dir, qml = sys.argv[1], sys.argv[2]
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t21_fin.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(250)

    def obj(nombre):
        return [o for o in ventana.findChildren(QObject) if o.objectName() == nombre][0]

    pantalla, progreso, comandos, puente = (obj("pantalla"), obj("progresoFalso"),
                                            obj("comandosFalsos"), obj("puenteFalso"))
    panel, grafica, pildora, regreso = (obj("panelFinCiclo"), obj("graficaCicloEnCurso"),
                                        obj("pildoraFinCiclo"), obj("regresoPanel"))
    regreso.setProperty("intervaloTickMs", 10)   # 30 «segundos» = 0,3 s

    def pulsar(item):
        c = item.mapToScene(item.boundingRect().center())
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
        QTest.qWait(40)

    def textos(item):
        # QQuickText y los derivados (TextoAjustable)
        return [o.property("text") for o in item.findChildren(QQuickItem)
                if o.metaObject().indexOfProperty("baselineOffset") >= 0
                and isinstance(o.property("text"), str) and o.isVisible()]

    def fijar(resultado, fin):
        progreso.setProperty("datosFin", fin)
        progreso.setProperty("revisionFin", progreso.property("revisionFin") + 1)
        progreso.setProperty("resultado", resultado)
        QTest.qWait(60)

    def vista():
        return {"panel": panel.isVisible(), "grafica": grafica.isVisible(),
                "pildora": pildora.isVisible() and pildora.property("tipo")}

    causa = {"titulo": "Fallo en esterilización", "subtitulo": "Aire", "hora": "13:21:07",
             "descripcion": "Desc", "queHacer": "Hacer", "meta": "Meta", "nivel": "fallo"}
    alarmas = [{"titulo": "Alarma A", "hora": "13:19:40", "nivel": "media", "descripcion": "d",
                "queHacer": "", "meta": "m"},
               {"titulo": "Alarma B", "hora": "13:02:15", "nivel": "baja", "descripcion": "d",
                "queHacer": "", "meta": "m"}]
    fallo = {"modo": "fallo", "horaFin": "13:21", "causa": causa, "alarmas": alarmas, "cantidad": 3,
             "notaObservaciones": ""}

    r = {}
    r["en_curso"] = vista()
    fijar("fallo", fallo)
    r["fallo"] = vista()
    r["textos_panel"] = textos(panel)
    r["sin_restos"] = [n for n in ("franjaNoConforme", "cargaNoEsteril", "dialogoCancelarCiclo",
                                   "dialogoEstadoSeguro")
                       if [o for o in ventana.findChildren(QObject) if o.objectName() == n]]

    pulsar(obj("botonVerGrafica"))
    r["ver_grafica"] = vista()
    r["texto_pildora"] = pildora.property("texto")
    pantalla.setProperty("pantallaCompleta", True)
    QTest.qWait(20)
    r["completa_abierta"] = pantalla.property("pantallaCompleta")
    QTest.qWait(600)
    r["tras_regreso"] = vista()
    r["completa_tras_regreso"] = pantalla.property("pantallaCompleta")

    # un toque reinicia la cuenta
    pulsar(obj("botonVerGrafica"))
    QTest.qWait(150)
    antes = regreso.property("restante")
    c = grafica.mapToScene(grafica.boundingRect().center())
    QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y()) + 80))
    QTest.qWait(5)
    r["toque"] = [antes, regreso.property("restante")]

    # con un modal abierto la cuenta se detiene
    pulsar(obj("botonCancelarCiclo"))       # CONFIRMAR: abre su modal
    modal = obj("modalConfirmarCiclo")
    r["modal_confirmar"] = modal.property("visible")
    r["titulo_modal_fallo"] = modal.property("titulo")
    QTest.qWait(600)
    r["con_modal"] = vista()
    r["confirmaciones_sin_aceptar"] = comandos.property("confirmaciones")
    pulsar([o for o in modal.findChildren(QQuickItem) if o.objectName() == "botonAccionModal"][0])
    r["confirmaciones"] = comandos.property("confirmaciones")
    QTest.qWait(600)
    r["tras_modal"] = vista()

    # cancelado, emergencia y desconocido: panel (falla cerrada)
    fijar("cancelado", {**fallo, "modo": "cancelado"})
    r["cancelado"] = vista()
    fijar("raro", {})
    r["desconocido"] = vista()
    r["modo_desconocido"] = panel.property("modo")

    # exitoso sin alarmas: gráfica, sin píldora
    fijar("exitoso", {"modo": "", "cantidad": 0, "alarmas": [], "causa": {}, "horaFin": "10:00",
                      "notaObservaciones": ""})
    r["exitoso"] = vista()
    # exitoso con observaciones: píldora ámbar; tocarla abre el panel
    nota = "Observación: Referencia 1 sin lectura desde las 09:40 (fase Esterilización)."
    fijar("exitoso", {"modo": "observaciones", "cantidad": 1, "alarmas": alarmas[:1], "causa": {},
                      "horaFin": "10:00", "notaObservaciones": nota})
    r["exitoso_obs"] = vista()
    r["texto_pildora_obs"] = pildora.property("texto")
    pulsar(pildora)
    r["obs_panel"] = vista()
    r["textos_obs"] = textos(panel)
    QTest.qWait(400)
    r["obs_sin_regreso"] = vista()
    pulsar(obj("botonCancelarCiclo"))
    r["nota_modal"] = obj("modalConfirmarCiclo").property("nota")
    r["titulo_modal_exitoso"] = obj("modalConfirmarCiclo").property("titulo")
    obj("modalConfirmarCiclo").setProperty("visible", False)

    # estado seguro tras un paro
    puente.setProperty("ackConfirmaEstadoSeguro", True)
    QTest.qWait(20)
    pulsar(obj("botonCancelarCiclo"))
    r["modal_estado_seguro"] = obj("modalEstadoSeguro").property("visible")
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=True))
""")


@pytest.fixture(scope="module")
def r():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_panel_con_fallo_y_no_mientras_corre(r):
    assert r["en_curso"] == {"panel": False, "grafica": True, "pildora": False}
    assert r["fallo"] == {"panel": True, "grafica": False, "pildora": False}
    assert "CARGA NO ESTÉRIL" in r["textos_panel"]
    assert any("Fallo en esterilizaci" in t for t in r["textos_panel"])
    assert any(t.startswith("Ciclo 03 ") for t in r["textos_panel"])
    assert r["sin_restos"] == []


def test_ver_grafica_muestra_pildora_roja(r):
    assert r["ver_grafica"] == {"panel": False, "grafica": True, "pildora": "alarmas"}
    assert r["texto_pildora"].startswith("Alarmas (3)")


def test_regreso_automatico_cierra_la_pantalla_completa(r):
    assert r["completa_abierta"] is True
    assert r["tras_regreso"] == {"panel": True, "grafica": False, "pildora": False}
    assert r["completa_tras_regreso"] is False


def test_un_toque_reinicia_la_cuenta(r):
    antes, despues = r["toque"]
    assert antes < 30 and despues == 30


def test_la_cuenta_se_detiene_con_un_modal(r):
    assert r["modal_confirmar"] is True
    assert r["titulo_modal_fallo"] == "Confirmar resultado del ciclo"
    assert r["con_modal"]["grafica"] is True and r["con_modal"]["panel"] is False
    assert r["confirmaciones_sin_aceptar"] == 0 and r["confirmaciones"] == 1
    assert r["tras_modal"]["panel"] is True        # al cerrar, la cuenta sigue y vence


def test_cancelado_y_desconocido_muestran_el_panel(r):
    assert r["cancelado"]["panel"] is True
    assert r["desconocido"]["panel"] is True and r["modo_desconocido"] == "fallo"


def test_exitoso_sin_y_con_observaciones(r):
    assert r["exitoso"] == {"panel": False, "grafica": True, "pildora": False}
    assert r["exitoso_obs"] == {"panel": False, "grafica": True, "pildora": "observaciones"}
    assert r["texto_pildora_obs"] == "Observaciones (1)"
    assert r["obs_panel"]["panel"] is True
    assert "OBSERVACIONES DEL CICLO" in r["textos_obs"]
    assert r["obs_sin_regreso"]["panel"] is True   # sin regreso automático en exitoso
    assert r["nota_modal"].startswith("Observaci") and "Referencia 1" in r["nota_modal"]
    assert r["titulo_modal_exitoso"] == "Confirmar ciclo"


def test_estado_seguro_en_su_modal(r):
    assert r["modal_estado_seguro"] is True
