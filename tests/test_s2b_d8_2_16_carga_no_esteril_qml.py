"""D8-2.16 (tanda 8, Q1-P7): la pantalla de resultado del ciclo (PantallaCicloEnCurso
terminada) muestra "CARGA NO ESTÉRIL" en todo ciclo que no termine COMPLETADO
(cancelado, fallo, emergencia o cualquier resultado desconocido), igual que el
ticket (T2-c de la tanda 7). Mientras el ciclo corre o si fue exitoso, no."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
I18N = RAIZ / "src" / "autoclave" / "i18n"


def test_clave_en_es_y_en():
    es = json.loads((I18N / "es.json").read_text(encoding="utf-8"))
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    assert es["ciclo"]["carga_no_esteril"] == "CARGA NO ESTÉRIL"
    assert en["ciclo"]["carga_no_esteril"] == "LOAD NOT STERILE"


_QML = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject { id: progresoFalso; property string resultado: ""; property bool activo: true }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        anchors.fill: parent
        progreso: progresoFalso
        datosVigentes: true
    }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
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
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_d8_2_16.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(200)
    progreso = [o for o in ventana.findChildren(QObject) if o.metaObject().indexOfProperty("activo") >= 0
                and o.metaObject().indexOfProperty("resultado") >= 0
                and not o.metaObject().className().startswith("PantallaCicloEnCurso")][0]
    marca = [o for o in ventana.findChildren(QQuickItem) if o.objectName() == "cargaNoEsteril"][0]
    texto = i18n.t("ciclo.carga_no_esteril")
    textos = lambda: [o.property("text") for o in marca.findChildren(QQuickItem)
                      if o.metaObject().className() == "QQuickText"]
    r = {}
    for res in ("", "exitoso", "cancelado", "fallo", "otro_desconocido", "exitoso"):
        progreso.setProperty("resultado", res)
        QTest.qWait(40)
        r[res or "en_curso"] = marca.isVisible()
    r["texto"] = texto in textos()
    r["avisos"] = avisos
    print(json.dumps(r))
""")


def test_pantalla_muestra_carga_no_esteril_si_no_es_exitoso():
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["en_curso"] is False
    assert s["exitoso"] is False
    assert s["cancelado"] is True
    assert s["fallo"] is True
    assert s["otro_desconocido"] is True       # falla cerrada: desconocido = no estéril
    assert s["texto"] is True
    assert s["avisos"] == []
