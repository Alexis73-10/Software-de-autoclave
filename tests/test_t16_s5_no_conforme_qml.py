"""P4 (tanda 16, D-14.4), QML: la pantalla final de un ciclo NO CONFORME
muestra la franja roja «CICLO NO CONFORME — carga no liberable: punto de
referencia sin verificar» y el botón «Reconozco que la carga no es
liberable»; CONFIRMAR queda deshabilitado (y no envía nada) hasta el
reconocimiento. El historial (ListaCiclos y DetalleCiclo) rotula NO CONFORME.
Un ciclo conforme no cambia. Pantalla real, offscreen, con dobles en QML; los
textos nuevos se inyectan desde docs/informes/tanda16/i18n/s5.json."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.req("T16-S5")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
S5 = RAIZ / "docs" / "informes" / "tanda16" / "i18n" / "s5.json"

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
import "Componentes"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        objectName: "comandosFalsos"
        property int confirmaciones: 0
        property int reconocimientos: 0
        property bool ocupado: false
        property string error: ""
        property string aviso: ""
        signal terminado(string accion, bool ok)
        function cancelar() {}
        function confirmar() { confirmaciones++ }
        function reconocerNoConforme() { reconocimientos++ }
        function descartarError() { error = "" }
    }
    QtObject {
        id: progresoFalso
        objectName: "progresoFalso"
        property string resultado: ""
        property bool activo: true
        property bool noConforme: false
        property bool noConformeReconocido: false
        property int refrescos: 0
        function refrescar() { refrescos++ }
    }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        anchors.fill: parent
        comandos: comandos
        progreso: progresoFalso
        datosVigentes: true
    }
    ListaCiclos {
        objectName: "listaFalsa"
        opacity: 0; z: -1   // visible (para que la lista cree sus filas) pero sin tapar la pantalla
        width: 500; height: 300
        ciclos: [
            { id: 1, numero: "000001", fecha: "f", hora: "h", programa: "01", programa_nombre: "—",
              resultado: "COMPLETADO", resultado_detalle: "", operador: "—", no_conforme: true },
            { id: 2, numero: "000002", fecha: "f", hora: "h", programa: "01", programa_nombre: "—",
              resultado: "COMPLETADO", resultado_detalle: "", operador: "—", no_conforme: false }
        ]
        textoResultado: function (clave) { return "R:" + clave }
    }
    DetalleCiclo { objectName: "detalleNC"; opacity: 0; z: -1; width: 500; height: 600; noConforme: true }
    DetalleCiclo { objectName: "detalleOK"; opacity: 0; z: -1; width: 500; height: 600 }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave import i18n
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, qml, s5 = sys.argv[1], sys.argv[2], sys.argv[3]
    cats = i18n._todos()
    for idioma, textos in json.load(open(s5, encoding="utf-8")).items():
        for clave, texto in textos.items():
            nodo = cats[idioma]
            *ruta, hoja = clave.split(".")
            for p in ruta:
                nodo = nodo.setdefault(p, {})
            nodo.setdefault(hoja, texto)

    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t16_s5.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(200)

    def obj(nombre):
        return [o for o in ventana.findChildren(QObject) if o.objectName() == nombre][0]

    progreso, comandos = obj("progresoFalso"), obj("comandosFalsos")
    franja, boton = obj("franjaNoConforme"), obj("botonReconocerNoConforme")
    reconocido, confirmar = obj("noConformeReconocidoTexto"), obj("botonCancelarCiclo")

    def pulsar(item):
        c = item.mapToScene(item.boundingRect().center())
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
        QTest.qWait(40)

    def textos(item):
        return [o.property("text") for o in item.findChildren(QQuickItem)
                if o.metaObject().className() == "QQuickText"]

    def fijar(resultado, nc, rec):
        progreso.setProperty("resultado", resultado)
        progreso.setProperty("noConforme", nc)
        progreso.setProperty("noConformeReconocido", rec)
        QTest.qWait(40)

    def foto():
        return {"franja": franja.isVisible(), "boton": boton.isVisible(),
                "reconocido": reconocido.isVisible(), "confirmar": confirmar.isEnabled()}

    r = {}
    fijar("exitoso", False, False); r["conforme"] = foto()
    pulsar(confirmar); r["conforme_confirma"] = comandos.property("confirmaciones")
    comandos.setProperty("confirmaciones", 0)
    fijar("", True, False); r["en_curso"] = foto()
    fijar("exitoso", True, False); r["nc"] = foto()
    r["texto_franja"] = i18n.t("ciclo.no_conforme_franja") in textos(franja)
    r["texto_boton"] = i18n.t("ciclo.no_conforme_reconocer") in textos(boton)
    pulsar(confirmar); r["nc_confirma"] = comandos.property("confirmaciones")
    pulsar(boton); r["reconocimientos"] = comandos.property("reconocimientos")
    comandos.terminado.emit("reconocer_no_conforme", True); QTest.qWait(20)
    r["refrescos"] = progreso.property("refrescos")
    fijar("exitoso", True, True); r["rec"] = foto()
    pulsar(confirmar); r["rec_confirma"] = comandos.property("confirmaciones")
    fijar("fallo", True, False); r["fallo_nc"] = foto()

    lista = obj("listaFalsa")
    def items(raiz):   # árbol visual (las filas de la ListView no cuelgan del árbol QObject)
        for hijo in raiz.childItems():
            yield hijo
            yield from items(hijo)
    r["lista"] = {o.objectName(): o.property("text") for o in items(lista)
                  if o.objectName().startswith("resultado_")}
    r["detalle_nc"] = obj("detalleNC").findChildren(QQuickItem, "franjaNoConformeDetalle")[0].property("visible")
    r["detalle_ok"] = obj("detalleOK").findChildren(QQuickItem, "franjaNoConformeDetalle")[0].property("visible")
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=True))
""")


@pytest.fixture(scope="module")
def r():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML, str(S5)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}, timeout=90,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_ciclo_conforme_no_cambia(r):
    assert r["conforme"] == {"franja": False, "boton": False, "reconocido": False, "confirmar": True}
    assert r["conforme_confirma"] == 1


def test_sin_franja_mientras_el_ciclo_corre(r):
    assert r["en_curso"]["franja"] is False
    assert r["en_curso"]["confirmar"] is True      # es CANCELAR CICLO: no se bloquea


def test_no_conforme_muestra_franja_y_bloquea_confirmar(r):
    assert r["nc"] == {"franja": True, "boton": True, "reconocido": False, "confirmar": False}
    assert r["texto_franja"] and r["texto_boton"]
    assert r["nc_confirma"] == 0                    # el toque no envía nada


def test_reconocer_envia_y_refresca(r):
    assert r["reconocimientos"] == 1
    assert r["refrescos"] >= 1


def test_tras_reconocer_confirmar_se_habilita(r):
    assert r["rec"] == {"franja": True, "boton": False, "reconocido": True, "confirmar": True}
    assert r["rec_confirma"] == 1


def test_no_conforme_con_fallo_tambien_exige_reconocer(r):
    assert r["fallo_nc"]["franja"] is True and r["fallo_nc"]["confirmar"] is False


def test_historial_rotula_no_conforme(r):
    assert r["lista"]["resultado_1"] == "NO CONFORME"
    assert r["lista"]["resultado_2"] == "R:COMPLETADO"
    assert r["detalle_nc"] is True and r["detalle_ok"] is False


def test_sin_avisos_qml(r):
    assert r["avisos"] == []
