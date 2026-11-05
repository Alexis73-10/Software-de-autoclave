"""P1 (tanda 7): OPCIONES > Entradas/Salidas, modo prueba. La lista de salidas
se refresca cada 1 s (caché de /status de UIServiceBackend desde 2026-11-02). Con un Repeater sobre la lista entera, cada
refresco destruía y recreaba todas las tarjetas: la pulsación sostenida de una
salida momentánea (abrir/cerrar puerta, bomba de vacío) perdía su temporizador
de renovación y el backend la apagaba a los 1,5 s; un toque podía perderse.
La tarjeta debe sobrevivir al refresco y seguir mostrando el estado real.
Tanda 27 (A4, HAZ-IO-07): ya no hay salidas momentáneas; la bomba de vacío
(y las puertas) son interruptor."""

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
                             "i18n": "io.do.bomba_vacio", "id": "DO 05",
                             "bloqueada": False}]}
    if ruta == "/status":
        return 200, {"estado_modulo_es": estado["modulo_es"],
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

class FuenteStatus:   # caché de /status de UIServiceBackend (AJUSTES 2026-11-02)
    def status_vigente(self):
        return transporte("GET", "/status", None, None, None)[1], True, 0.0

from autoclave.cliente import ui_service_backend
ui_service_backend.instalar_servicio(FuenteStatus())
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
# Tanda 27 (A4): interruptor. Con la bomba apagada, un toque envía un solo ON
# (sin "momentanea") y no se renueva; el botón dice Activar/Apagar, nunca Mantener
from PySide6.QtCore import QMetaObject
boton = buscar("botonSalida_bomba_vacio")
texto_boton_on = boton.property("texto")
estado["bomba"] = 0
ctl.actualizar()
QTest.qWait(50)
texto_boton_off = boton.property("texto")
patches.clear()
QMetaObject.invokeMethod(boton, "presionado")
QMetaObject.invokeMethod(boton, "pulsado")
QMetaObject.invokeMethod(boton, "soltado")
primeros = [dict(c) for c in patches]
n = len(patches)
for _ in range(4):
    QTest.qWait(400)
    ctl.actualizar()
tras_tocar = len(patches) - n
estado["bomba"] = 1
ctl.actualizar()

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
                  "primeros": primeros, "tras_tocar": tras_tocar,
                  "texto_boton_on": texto_boton_on, "texto_boton_off": texto_boton_off}))
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


def test_bomba_de_vacio_es_interruptor_sin_renovacion_ni_mantener():
    """Tanda 27 (A4, HAZ-IO-07): un toque envía un solo ON sin "momentanea";
    soltar no apaga y no hay renovación de 500 ms; el botón dice Activar /
    Apagar, nunca «Mantener pulsado»."""
    es = json.loads((RAIZ / "src" / "autoclave" / "i18n" / "es.json").read_text(encoding="utf-8"))
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=90,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["primeros"] == [{"value": True}], d
    assert d["tras_tocar"] == 0, d
    assert d["texto_boton_on"] == es["io"]["ui"]["apagar"], d
    assert d["texto_boton_off"] == es["io"]["ui"]["activar"], d
    assert "mantener" not in es["io"]["ui"]


def test_qml_sin_rastro_de_salidas_momentaneas():
    texto = (RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas"
             / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    for fragmento in ("momentanea", "renovacion", "soltarMomentanea", "io.ui.mantener"):
        assert fragmento not in texto, fragmento
