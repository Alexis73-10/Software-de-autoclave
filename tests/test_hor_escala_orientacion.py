"""Tanda horizontal (9-nov): la orientación del lienzo la decide el tamaño
real de la ventana raíz.

Con la ventana vertical (alto > ancho) rige el lienzo vertical de siempre,
1200x1920; con la ventana horizontal (ancho >= alto), el lienzo 1920x1200.
Si la ventana cambia de tamaño (Windows gira el monitor y la ventana a
pantalla completa lo sigue), la orientación cambia con ella. Se carga la
ventana raíz real ReposoInstalacionVentana.qml en un subproceso."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r'''
    import json
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge import i18n_qml

    i18n.cargar(); i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    eng = QQmlApplicationEngine()
    eng.addImportPath(QML_DIR)
    eng.load(QUrl.fromLocalFile(QML_DIR + "/ReposoInstalacionVentana.qml"))
    v = eng.rootObjects()[0]
    esc = eng.singletonInstance("Tema", "Escala")
    salida = {}
    def medir(nombre, w, h):
        v.setProperty("width", w); v.setProperty("height", h)
        QTest.qWait(80)
        salida[nombre] = {k: esc.property(k) for k in
                          ("horizontal", "anchoDiseno", "altoDiseno", "factor")}
    medir("defecto", v.property("width"), v.property("height"))
    medir("vertical", 1200, 1920)
    medir("horizontal", 1920, 1200)
    medir("horizontal_chica", 960, 600)
    medir("cuadrada", 1000, 1000)
    medir("vuelve_vertical", 1080, 1920)
    print("RESULTADO=" + json.dumps(salida))
''')


@pytest.fixture(scope="module")
def medidas():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


def test_la_ventana_por_defecto_sigue_vertical(medidas):
    assert medidas["defecto"]["horizontal"] is False
    assert (medidas["defecto"]["anchoDiseno"], medidas["defecto"]["altoDiseno"]) == (1200, 1920)


def test_vertical_es_el_lienzo_de_siempre(medidas):
    m = medidas["vertical"]
    assert m == {"horizontal": False, "anchoDiseno": 1200, "altoDiseno": 1920, "factor": 1.0}


def test_horizontal_usa_el_lienzo_1920x1200_con_la_misma_escala(medidas):
    m = medidas["horizontal"]
    assert m == {"horizontal": True, "anchoDiseno": 1920, "altoDiseno": 1200, "factor": 1.0}
    assert medidas["horizontal_chica"]["factor"] == pytest.approx(0.5)


def test_cuadrada_cuenta_como_horizontal(medidas):
    assert medidas["cuadrada"]["horizontal"] is True


def test_al_girar_de_nuevo_vuelve_al_vertical(medidas):
    m = medidas["vuelve_vertical"]
    assert m["horizontal"] is False
    assert m["factor"] == pytest.approx(1080 / 1200)
