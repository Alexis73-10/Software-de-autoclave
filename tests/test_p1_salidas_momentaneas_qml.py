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

estado = {"bomba": 0, "modulo_es": "ok"}
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
        return 200, {"estado_tarjeta": estado["modulo_es"],
                     "card_connected": estado["modulo_es"] == "ok", "test_mode_active": True,
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
from autoclave.cliente.session_manager import SessionManager
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
# pulsación sostenida a través de refrescos: renueva ON, y al soltar apaga y no renueva más
from PySide6.QtCore import QMetaObject
boton = buscar("botonSalida_bomba_vacio")
patches.clear()
QMetaObject.invokeMethod(boton, "presionado")
for _ in range(3):
    QTest.qWait(400)
    ctl.actualizar()
encendidos = sum(1 for c in patches if c.get("value") is True)
QMetaObject.invokeMethod(boton, "soltado")
ultimo = dict(patches[-1]) if patches else {}
n = len(patches)
QTest.qWait(1200)
tras_soltar = len(patches) - n

s1 = buscar("sensor_temp_camara")
v1 = buscar("valorSensor_temp_camara")
valor_ok = v1.property("text")
estado_on = any(o.property("text") == "ENCENDIDA" for o in t1.findChildren(QObject)
                if o.property("text") is not None)
estado["modulo_es"] = "desconectada"
es.setProperty("segmento", "temperatura")
ctl.actualizar()
QTest.qWait(50)
textos_desconectada = [o.property("text") for o in items(buscar("sensor_temp_camara"))
                       if o.isVisible() and isinstance(o.property("text"), str)]
print(json.dumps({"sobrevive": t1 is not None and t1.property("marcaP1") == 1,
                  "sensor_sobrevive": s1 is not None and s1.property("marcaP1") == 1,
                  "valor_sensor": valor_ok,
                  "estado_on": estado_on,
                  "textos_sensor_desconectada": textos_desconectada,
                  "encendidos": encendidos, "ultimo": ultimo, "tras_soltar": tras_soltar}))
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


def test_sensor_con_modulo_es_desconectado_no_culpa_al_cableado():
    """U4: sin enlace con el módulo E/S, la tarjeta del sensor no debe decir
    'revise el cableado del sensor' (no es el sensor): dice que no hay enlace."""
    es = json.loads((RAIZ / "src" / "autoclave" / "i18n" / "es.json").read_text(encoding="utf-8"))
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    textos = json.loads(r.stdout.strip().splitlines()[-1])["textos_sensor_desconectada"]
    assert es["io"]["ui"]["sin_lectura"] not in textos, textos
    assert es["io"]["ui"]["enlace_perdido"] in textos, textos
    assert not any("undefined" in t for t in textos), textos


def test_pulsacion_sostenida_renueva_y_al_soltar_apaga_sin_renovar_mas():
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["encendidos"] >= 3, d          # el primer ON y renovaciones cada 500 ms
    assert d["ultimo"] == {"value": False}, d
    assert d["tras_soltar"] == 0, d
