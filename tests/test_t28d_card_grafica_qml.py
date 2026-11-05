"""Tanda 28 (A11): la card del cursor en GraficaCiclo.qml no cubre ninguna
curva ni el cursor y queda dentro del área; capturas en claro y oscuro
(docs/informes/tanda28d/capturas/, solo con A11_CAPTURAS=1)."""
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
CAPTURAS = RAIZ / "docs" / "informes" / "tanda28d" / "capturas"

_SCRIPT = textwrap.dedent(r"""
    import json, sys, os
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlProperty
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    qml_dir, qml, capturas, oscuro = sys.argv[1:5]
    from autoclave.ui_qml.app import _cargar_fuentes
    i18n.cargar(); i18n.fijar_idioma("es")
    i18n_qml.instancia._consultar = lambda: None
    app = QGuiApplication([]); _cargar_fuentes()
    engine = QQmlEngine(); engine.addImportPath(qml_dir)
    comp = QQmlComponent(engine)
    comp.setData(qml.encode(), QUrl.fromLocalFile(qml_dir + "/prueba_a11.qml"))
    ventana = comp.createWithInitialProperties({}); assert ventana is not None, comp.errorString()
    ventana.show(); QTest.qWait(100)
    todos = ventana.findChildren(QQuickItem)
    g = [o for o in todos if o.objectName() == "graficaPrueba"][0]
    def hijos(p, n):
        out = []
        for h in p.childItems():
            if h.objectName() == n: out.append(h)
            out.extend(hijos(h, n))
        return out
    g.setProperty("escala", 1.0); g.setProperty("width", 1129.0); g.setProperty("height", 794.0)
    N = 41
    ts = [i * 0.5 for i in range(N)]
    casos = {
        "altas": {"temp_camara": [120 + i * .2 for i in range(N)], "temp_ref": [118 + i * .2 for i in range(N)], "pres_camara": [260 + i for i in range(N)]},
        "bajas": {"temp_camara": [20 + i * .5 for i in range(N)], "temp_ref": [18 + i * .5 for i in range(N)], "pres_camara": [90 + i * .5 for i in range(N)]},
        "cruzadas": {"temp_camara": [60 + i * 1.0 for i in range(N)], "temp_ref": [100 - i * 1.0 for i in range(N)], "pres_camara": [150.0 for i in range(N)]},
    }
    salida = []
    for nombre, d in casos.items():
        g.setProperty("tiempoActualMin", 20.0)
        g.setProperty("datos", {"t_min": ts, **d})
        for cur in (0.0, 10.0, 20.0):
            g.setProperty("cursorMin", cur); QTest.qWait(300)
            globo = hijos(g, "globoGrafica")[0]
            p = globo.mapToItem(g, 0, 0)
            caja = [p.x(), p.y(), globo.width(), globo.height()]
            xc = g.property("xDato0") + cur / g.property("ejeX").toVariant()["maximo"] * (g.property("xDato1") - g.property("xDato0"))
            salida.append({"caso": nombre, "cursor": cur, "caja": caja, "xCursor": xc,
                           "yArriba": g.property("yArriba"), "yAbajo": g.property("yAbajo"),
                           "libre": globo.property("pos")["libre"]})
            if capturas and cur == 10.0:
                # la sombra (layer) no se pinta en offscreen: se quita solo para la captura
                QQmlProperty(globo, "layer.enabled").write(False); QTest.qWait(200)
                os.makedirs(capturas, exist_ok=True)
                ventana.grabWindow().save(f"{capturas}/card_{nombre}_{'oscuro' if oscuro == '1' else 'claro'}.png")
    print("RESULTADO=" + json.dumps(salida))
""")

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 1200; height: 900; visible: true
    color: Colores.fondoTarjeta
    Component.onCompleted: Colores.oscuro = %s
    GraficaCiclo { objectName: "graficaPrueba"; ocultarCursorMs: 600000 }
}
"""


def _correr(oscuro: bool):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    capt = str(CAPTURAS) if os.environ.get("A11_CAPTURAS") else ""
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML % ("true" if oscuro else "false"),
         capt, "1" if oscuro else "0"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        timeout=120, cwd=RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


@pytest.mark.parametrize("oscuro", [False, True], ids=["claro", "oscuro"])
def test_card_dentro_sin_tapar_el_cursor(oscuro):
    for c in _correr(oscuro):
        x, y, w, h = c["caja"]
        assert x >= 68 - 0.5 and x + w <= 1059 + 0.5, c
        assert y >= c["yArriba"] - 0.5 and y + h <= c["yAbajo"] + 0.5, c
        assert x + w <= c["xCursor"] or x >= c["xCursor"], c       # no tapa la línea
        assert c["libre"], c                                       # datos de la prueba: hay hueco
