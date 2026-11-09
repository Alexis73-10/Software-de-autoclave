# tests/test_hor_b_textos_contraste_qml.py
#
# Tanda horizontal, ronda 2 (grupo B): en el lienzo horizontal 1920x1200, con
# los textos más largos en español y en inglés, ningún texto de Preciclo (en
# FALLA, con RECONOCER FALLA / ACKNOWLEDGE FAULT) ni de Ciclo en curso pasa su
# propia caja ni su contenedor (el botón, el recuadro «Programa» entre los
# divisores 351 y 839 del mockup). Y el contraste WCAG de los pares corregidos
# en oscuro (chevrón de «Tiempos» de la gráfica). Subproceso offscreen.

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tests"))
from test_tema_oscuro import _contraste  # noqa: E402

LARGO = "INSTRUMENTAL ENVUELTO 134 °C CON TEXTO MUY LARGO"

_GUION = textwrap.dedent(r'''
    import json, os, sys
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QUrl, QPointF
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml

    idioma, largo = sys.argv[1], sys.argv[2]
    i18n.cargar(); i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None
    app = QGuiApplication([])
    _cargar_fuentes()

    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    Window {
        id: ventana
        width: 1920; height: 1200; visible: true
        Binding { target: Escala; property: "horizontal"; value: true }
        Binding { target: Escala; property: "factor"; value: 1 }
        Binding { target: Escala; property: "altoLienzo"; value: 1200 }
        QtObject {
            id: puenteP
            property bool connected: true
            property string estadoModuloEs: "ok"
            property string cicloActivo: "04"
            property string programa: "%(largo)s"
            property string tempEsterilizacion: "134.0"
            property string tiempoEsterilizacion: "3.5"
            property string tiempoSecado: "15"
            property string tempCamara: "098.2"
            property string tempReferencia: "096.4"
            property string presionCamara: "084.1"
            property string estadoEquipo: "no_preparado"
            property string machineState: "FALLA"
            property int door: 1
            property string doorState: "CERRADO"
            property bool doorOpen: false
            property bool puertaConActuador: true
            property bool listoParaCiclo: false
            property bool inicioCicloVisible: false
        }
        Item {
            width: 1920; height: 1200
            PantallaPreciclo { objectName: "pre"; anchors.fill: parent; visible: true; puente: puenteP }
        }
        Item {
            width: 1920; height: 1200
            PantallaCicloEnCurso { objectName: "ciclo"; anchors.fill: parent; visible: false; puente: puenteP
                                   resultado: "exitoso"; entregada: false; forzable: true }
        }
    }
    """ % {"largo": largo}
    eng = QQmlApplicationEngine()
    eng.addImportPath(QML_DIR)
    ruta = QML_DIR + "/_hor_b_textos_%d.qml" % os.getpid()
    open(ruta, "w", encoding="utf-8").write(QML)
    eng.load(QUrl.fromLocalFile(ruta))
    os.remove(ruta)
    w = eng.rootObjects()[0]
    QTest.qWait(300)

    def items(r):
        pila = [r]
        while pila:
            it = pila.pop()
            yield it
            pila.extend(it.childItems())

    def visible(it):
        return it.isVisible() and it.opacity() > 0

    salida = {}
    for nombre in ("pre", "ciclo"):
        pant = [o for o in items(w.contentItem()) if o.objectName() == nombre][0]
        for o in items(w.contentItem()):
            if o.objectName() in ("pre", "ciclo"):
                o.setProperty("visible", o.objectName() == nombre)
        QTest.qWait(200)
        malos, textos = [], []
        for t in items(pant):
            if not visible(t) or t.property("contentWidth") is None or t.property("text") is None:
                continue
            texto = str(t.property("text"))
            if not texto.strip():
                continue
            p = t.mapToScene(QPointF(0, 0))
            caja = [p.x(), p.y(), t.width(), t.height()]
            cw, ch = t.property("contentWidth"), t.property("contentHeight")
            textos.append({"texto": texto[:50], "obj": t.objectName(), "caja": caja, "cw": cw})
            if cw > t.width() + 1:
                malos.append({"texto": texto[:50], "obj": t.objectName(), "cw": cw, "w": t.width()})
        salida[nombre] = {"malos": malos, "textos": textos}
    print("SALIDA=" + json.dumps(salida))
''')


def _medir(idioma):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _GUION, idioma, LARGO],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=300)
    for linea in p.stdout.splitlines():
        if linea.startswith("SALIDA="):
            return json.loads(linea[len("SALIDA="):])
    raise AssertionError(p.stderr[-3000:])


@pytest.fixture(scope="module", params=["es", "en"])
def medida(request):
    return request.param, _medir(request.param)


def test_ningun_texto_pasa_su_caja(medida):
    idioma, m = medida
    for nombre in ("pre", "ciclo"):
        assert m[nombre]["malos"] == [], (idioma, nombre)


def test_reconocer_falla_cabe_en_su_boton(medida):
    idioma, m = medida
    boton = [t for t in m["pre"]["textos"] if t["obj"] == "textoBotonAccion"
             and t["texto"] in ("RECONOCER FALLA", "ACKNOWLEDGE FAULT")]
    assert boton, idioma
    assert boton[0]["cw"] <= boton[0]["caja"][2] + 1


def test_programa_largo_entre_los_divisores(medida):
    idioma, m = medida
    s = 1200 / 1196
    for nombre in ("pre", "ciclo"):
        t = [x for x in m[nombre]["textos"] if x["texto"] == LARGO[:50]]
        assert t, (idioma, nombre)
        x, _, w, _ = t[0]["caja"]
        centro = x + w / 2
        assert centro - t[0]["cw"] / 2 >= 351 * s and centro + t[0]["cw"] / 2 <= 839 * s


# ─────────────────────────── contraste (oscuro) ───────────────────────────

def _colores():
    texto = (RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Tema" / "Colores.qml").read_text(encoding="utf-8")
    out = {}
    for n, osc, cla in re.findall(r'property color (\w+):\s*oscuro \? "(#[0-9A-Fa-f]{6})" : "(#[0-9A-Fa-f]{6})"', texto):
        out[n] = ("#FF" + osc[1:].upper(), "#FF" + cla[1:].upper())
    return out


def test_chevron_tiempos_en_horizontal_contrasta_en_oscuro():
    c = _colores()
    # antes: el SVG negro (#000000) sobre fondoTarjeta oscuro (#152130): 1,29:1
    assert _contraste("#FF000000", c["fondoTarjeta"][0]) < 3
    # ahora (solo horizontal): IconoColor con textoNegro; elemento gráfico >= 3:1
    assert _contraste(c["textoNegro"][0], c["fondoTarjeta"][0]) >= 3
    # en claro el chevrón sigue negro sobre blanco
    assert c["textoNegro"][1] == "#FF000000"
    qml = (RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Componentes" / "GraficaCiclo.qml").read_text(encoding="utf-8")
    bloque = qml[qml.index('objectName: "chevronTiempos"') - 200:][:600]
    assert "IconoColor" in bloque and "Escala.horizontal" in bloque and "Colores.textoNegro" in bloque
