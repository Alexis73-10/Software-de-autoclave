"""P1 (tanda 7): OPCIONES > Entradas/Salidas, modo prueba. La lista de salidas
se refresca cada 1 s (GET /status). Con un Repeater sobre la lista entera, cada
refresco destruía y recreaba todas las tarjetas: la pulsación sostenida de una
salida momentánea (abrir/cerrar puerta, bomba de vacío) perdía su temporizador
de renovación y el backend la apagaba a los 1,5 s; un toque podía perderse.
La tarjeta debe sobrevivir al refresco y seguir mostrando el estado real."""

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
from PySide6.QtTest import QTest
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml import sesion_backend

estado = {"bomba": 0}
patches = []

def transporte(metodo, ruta, cuerpo, token, plazo):
    if ruta == "/io/channels":
        return 200, {"DI": [], "pressure": [],
                     "temperature": [{"name": "temp_camara", "estado_key": "temp_camara",
                                      "i18n": "io.ai.temp_camara", "id": "AI 01", "raw_index": 0}],
                     "DO": [{"name": "bomba_vacio", "estado_key": "bomba_vacio",
                             "i18n": "io.do.bomba_vacio", "id": "DO 05", "momentanea": True,
                             "bloqueada": False}]}
    if ruta == "/status":
        return 200, {"estado_tarjeta": "ok", "card_connected": True, "test_mode_active": True,
                     "machine_state": "PREPARADO",
                     "sensors": {"digital_outputs": {"bomba_vacio": estado["bomba"]},
                                 "temperature": {"camara": 25.0 + estado["bomba"]}}}
    if metodo == "PATCH":
        patches.append(cuerpo)
    return 200, {"ok": True}

qml_dir = sys.argv[1]
app = QGuiApplication([])
sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                      cierre_s=30, intervalo_ms=50)
sesion_backend.instalar(sesion)
from autoclave.ui.service_ui.session_manager import SessionManager
SessionManager.login({"usuario": "tec1", "nombre": "Tec", "rol": "tecnico",
                      "debe_cambiar_clave": False}, token="t")
e = QQmlEngine(); e.addImportPath(qml_dir)
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item { width: 1100; height: 1500
  OpcionesEntradasSalidas { objectName: "es"; anchors.fill: parent; segmento: "salidas" } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_p1.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
from PySide6.QtQuick import QQuickItem
es = raiz.findChild(QQuickItem, "es")
ctl = es.findChild(QObject, "entradasSalidasController")
ctl.actualizar()

def items(i):
    for h in i.childItems():
        yield h
        yield from items(h)

def buscar(nombre):
    return next((o for o in items(es) if o.objectName() == nombre), None)

def tarjeta():
    return buscar("salida_bomba_vacio")

QTest.qWait(50)
t0 = tarjeta()
assert t0 is not None, ctl.property("salidas")
t0.setProperty("marcaP1", 1)
buscar("sensor_temp_camara").setProperty("marcaP1", 1)
estado["bomba"] = 1
for _ in range(3):
    ctl.actualizar()
QTest.qWait(50)
t1 = tarjeta()
s1 = buscar("sensor_temp_camara")
v1 = buscar("valorSensor_temp_camara")
print(json.dumps({"sobrevive": t1 is not None and t1.property("marcaP1") == 1,
                  "sensor_sobrevive": s1 is not None and s1.property("marcaP1") == 1,
                  "valor_sensor": v1.property("text") if v1 is not None else None,
                  "estado_on": any(o.property("text") == "ON" for o in t1.findChildren(QObject)
                                   if o.property("text") is not None)}))
"""


def test_tarjeta_de_salida_sobrevive_al_refresco_y_muestra_el_estado():
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert datos["estado_on"], "la tarjeta no refleja el estado ON de /status"
    assert datos["sobrevive"], "el refresco de 1 s recreó la tarjeta (se pierde la pulsación)"
    assert datos["sensor_sobrevive"], "el refresco recreó la tarjeta del sensor"
    assert datos["valor_sensor"].startswith("26.0"), datos["valor_sensor"]
