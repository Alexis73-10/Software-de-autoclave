"""P4 (tanda 16, D-14.4), QML: el historial (ListaCiclos y DetalleCiclo)
rotula NO CONFORME los ciclos guardados con esa marca. Tanda 21 (FC-08): la
franja y el reconocimiento de la pantalla final se retiraron (ver
test_t21_pantalla_fin_ciclo_qml.py); los ciclos viejos se siguen mostrando
tal como quedaron. Offscreen; los textos se inyectan desde
docs/informes/tanda16/i18n/s5.json."""

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
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
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

    r = {}
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


def test_historial_rotula_no_conforme(r):
    assert r["lista"]["resultado_1"] == "NO CONFORME"
    assert r["lista"]["resultado_2"] == "R:COMPLETADO"
    assert r["detalle_nc"] is True and r["detalle_ok"] is False


def test_sin_avisos_qml(r):
    assert r["avisos"] == []
