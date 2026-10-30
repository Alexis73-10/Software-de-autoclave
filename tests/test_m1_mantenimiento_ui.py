"""M1 (tanda 3): controlador y pantalla de OPCIONES › Mantenimiento."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

RAIZ = Path(__file__).resolve().parents[1]


class _Sesion:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        r = self.respuestas.get((metodo, ruta))
        return r() if callable(r) else (r or Resultado("error_generico"))


def _controlador(respuestas):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.mantenimiento_controller import MantenimientoController
    s = _Sesion(respuestas)
    return MantenimientoController(sesion=s), s


_OK = {"estado": "ok", "vencido": False, "proximo_fecha": "2027-04-24", "ultimo_fecha": None,
       "ciclos_restantes": None}


def test_carga_los_datos_formateados():
    c, _ = _controlador({("GET", "/maintenance"): Resultado("ok", _OK, 200)})
    c.cargar()
    assert c.proximo == "24/04/2027" and c.ultimo == "—" and c.vencido is False


def test_vencido_y_sin_dato():
    c, _ = _controlador({("GET", "/maintenance"): Resultado(
        "ok", {**_OK, "estado": "vencido", "vencido": True}, 200)})
    c.cargar()
    assert c.vencido is True
    c, _ = _controlador({("GET", "/maintenance"): Resultado("ok", {"estado": "sin_dato"}, 200)})
    c.cargar()
    assert c.proximo == "—" and c.estado == "sin_dato"


def test_sin_respuesta_no_inventa_nada():
    c, _ = _controlador({("GET", "/maintenance"): Resultado(BACKEND_NO_RESPONDE)})
    c.cargar()
    assert c.proximo == "—" and c.mensaje == "opciones.err_sin_respuesta"


def test_registrar_envia_el_tipo_y_recarga():
    c, s = _controlador({("GET", "/maintenance"): Resultado("ok", _OK, 200),
                         ("POST", "/maintenance/records"): Resultado("ok", {"ok": True}, 200)})
    assert c.registrar("preventivo") is True
    assert ("POST", "/maintenance/records", {"tipo": "preventivo", "observaciones": ""}) in s.enviados
    assert [e[1] for e in s.enviados][-1] == "/maintenance"       # recarga


def test_registrar_rechazado_muestra_el_motivo():
    c, _ = _controlador({("GET", "/maintenance"): Resultado("ok", _OK, 200),
                         ("POST", "/maintenance/records"): Resultado("reloj_invalido", {}, 409)})
    assert c.registrar("correctivo") is False and c.mensaje == "opciones.mant_err_reloj"


def test_tipo_desconocido_no_sale_a_la_red():
    c, s = _controlador({})
    assert c.registrar("inventado") is False and s.enviados == []


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
Item { width: 800; height: 1200; OpcionesMantenimiento { anchors.fill: parent; edicionPermitida: true } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_mant.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
for nombre in ("datoProximoVencimiento", "datoUltimoMantenimiento", "datoCiclosRestantes",
               "botonRegistrarMantenimiento", "confirmarMantenimiento"):
    assert raiz.findChild(QObject, nombre) is not None, nombre
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()]}))
"""
    r = subprocess.run([sys.executable, "-c", guion, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-1500:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["avisos"] == []
