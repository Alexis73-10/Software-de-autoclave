"""OPCIONES > Entradas / Salidas: las dos pantallas QML cargan sin avisos y exponen
los elementos que el plan exige (§5, §6.1)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]

_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))

vivos = []

def cargar(fuente, nombre):
    c = QQmlComponent(e)
    vivos.append(c)
    c.setData(fuente, QUrl.fromLocalFile(qml_dir + "/" + nombre))
    raiz = c.create()
    assert raiz is not None, c.errorString()
    vivos.append(raiz)
    return raiz

pantalla = cargar(b'''import QtQuick
import "Pantallas"
Item { width: 1100; height: 1500; OpcionesEntradasSalidas { anchors.fill: parent } }''', "prueba_es.qml")
for nombre in ("opcionesEntradasSalidas", "selectorSegmentosES", "entradasSalidasController",
               "dialogoModoPrueba", "botonHabilitarModoPrueba", "pieEnlaceES", "bannerModoPrueba",
               "botonSalirModoPrueba"):
    assert pantalla.findChild(QObject, nombre) is not None, nombre

cal = cargar(b'''import QtQuick
import Autoclave.Controllers
import "Pantallas"
Item { width: 1100; height: 1500
  EntradasSalidasController { id: c }
  OpcionesCalibracionSensor { anchors.fill: parent; controlador: c
      segmento: "temperatura"; sensor: "temp_camara"; nombreSensor: "Temperatura camara" } }''',
             "prueba_cal.qml")
for nombre in ("opcionesCalibracionSensor", "botonVolverCalibracion", "lecturaVivaCalibracion",
               "capturar_bajo", "capturar_alto", "resultadoCalibracion", "botonRestaurarUltimo",
               "botonRestaurarDefecto", "botonAplicarCalibracion",
               "dialogoCalibracionFueraDeRango", "dialogoRestaurarCalibracion"):
    assert cal.findChild(QObject, nombre) is not None, nombre
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()]}))
"""


def test_las_dos_pantallas_cargan_sin_avisos():
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["avisos"] == []
