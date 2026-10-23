"""O1 (tanda 5): controlador y pantalla de Parámetros del ciclo — gestión de
programas y entradas mostradas."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import Resultado

RAIZ = Path(__file__).resolve().parents[1]

_PROGRAMAS = {"programas": [
    {"numero": 2, "cycle_id": "134_instrumental", "nombre": "instrumental 134", "origen": "user",
     "danado": False, "editable": True, "habilitado": True, "personalizado": False, "secciones": []},
    {"numero": 5, "cycle_id": "programa_5", "nombre": "Copia", "origen": "user",
     "danado": False, "editable": True, "habilitado": False, "personalizado": True, "secciones": []},
]}


class _Sesion:
    def __init__(self, extra=None):
        self.enviados = []
        self.extra = extra or {}

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if (metodo, ruta) in self.extra:
            return self.extra[(metodo, ruta)]
        if ruta == "/programas":
            return Resultado("ok", _PROGRAMAS, 200)
        if ruta.startswith("/cycle/display-inputs?"):
            return Resultado("ok", {"entradas": ["temp_camara"], "editable": True,
                                    "habilitadas": ["temp_camara", "pres_camara"]}, 200)
        return Resultado("ok", {"ok": True, "numero": 6}, 200)


def _ctrl(extra=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    s = _Sesion(extra)
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    return c, s


def test_propiedades_de_gestion():
    c, _ = _ctrl()
    assert c.programaHabilitado and not c.programaPersonalizado
    c.elegirPrograma(5)
    assert not c.programaHabilitado and c.programaPersonalizado


# C9 (tanda 9, D9-10): habilitar, duplicar y borrar se movieron a Opciones
# avanzadas › Manejo de ciclos (tests/test_c9_manejo_ciclos_ui.py)


def test_entradas_mostradas_carga_y_valida_cantidad():
    c, s = _ctrl()
    c.cargarEntradas()
    assert c.entradas == ["temp_camara"] and c.entradasHabilitadas == ["temp_camara", "pres_camara"]
    assert not c.guardarEntradas([])
    assert c.mensaje == "opciones.err_entradas_cantidad"
    assert not c.guardarEntradas(["a", "b", "c", "d"])
    assert c.guardarEntradas(["pres_camara", "temp_camara"])
    assert ("PUT", "/cycle/display-inputs",
            {"programa": 2, "entradas": ["pres_camara", "temp_camara"]}) in s.enviados


def test_la_pantalla_carga_sin_avisos():
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    guion = r"""
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
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item { width: 800; height: 1200; OpcionesParametrosCiclo { anchors.fill: parent; edicionPermitida: true } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_o1.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
for nombre in ("filaEntradas", "vistaEntradas", "guardarEntradas", "programaDeshabilitado",
               "gestionMovida"):
    assert raiz.findChild(QObject, nombre) is not None, nombre
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()]}))
"""
    r = subprocess.run([sys.executable, "-c", guion, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-1500:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["avisos"] == []
