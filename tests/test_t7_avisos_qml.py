"""T7 (E5): AvisosSeguridad.qml muestra NO ABRIR, paro, confirmación de estado
seguro y modo prueba según el puente; sin avisos de QML."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"

_QML = """
import QtQuick
import "Componentes"
Item {
    width: 600; height: 960
    property alias avisos: av
    QtObject {
        id: puenteFalso
        property bool noAbrir: true
        property string noAbrirMotivo: "Temperatura demasiado alta (95 °C)"
        property bool paroActivo: false
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property bool modoPrueba: false
    }
    QtObject {
        id: comandosFalsos
        property bool ocupado: false
        property int confirmaciones: 0
        function confirmarEstadoSeguro() { confirmaciones += 1 }
    }
    property alias puente: puenteFalso
    property alias comandos: comandosFalsos
    AvisosSeguridad { id: av; width: 600; puente: puenteFalso; comandos: comandosFalsos }
}
"""

_SCRIPT = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # registra I18n
qml_dir, qml = sys.argv[1], sys.argv[2]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_avisos.qml"))
raiz = comp.create()
assert raiz is not None, comp.errorString()

def visible(nombre):
    o = raiz.findChild(QObject, nombre)
    return bool(o.property("visible"))

r = {}
puente = raiz.property("puente")
r["no_abrir"] = visible("avisoNoAbrir")
r["paro_oculto"] = not visible("avisoParo")
puente.setProperty("paroActivo", True)
r["paro"] = visible("avisoParo")
r["no_abrir_oculto_con_paro"] = not visible("avisoNoAbrir")
puente.setProperty("paroActivo", False)
puente.setProperty("estadoSeguroActivo", True)
puente.setProperty("estadoSeguroRequiereConfirmacion", True)
r["confirmar"] = visible("avisoConfirmarEstadoSeguro")
r["en_curso_oculto"] = not visible("avisoEstadoSeguro")
puente.setProperty("estadoSeguroRequiereConfirmacion", False)
r["en_curso"] = visible("avisoEstadoSeguro")
puente.setProperty("noAbrir", False)
r["sin_no_abrir"] = not visible("avisoNoAbrir")
r["modo_prueba_oculto"] = not visible("avisoModoPrueba")
puente.setProperty("modoPrueba", True)
r["modo_prueba"] = visible("avisoModoPrueba")
r["avisos"] = avisos
print(json.dumps(r))
"""


def test_avisos_de_seguridad():
    raiz_repo = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
                       capture_output=True, text=True, encoding="utf-8", cwd=raiz_repo,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=60)
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s.pop("avisos") == []
    assert all(s.values()), s
