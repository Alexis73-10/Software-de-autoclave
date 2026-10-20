"""P2 (tanda 5): OPCIONES › Parámetros del equipo, interruptor de impresora."""

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

_RAIZ = Path(__file__).resolve().parents[1]


class _Sesion:
    def __init__(self, habilitada=True, put=None):
        self.habilitada = habilitada
        self.put = put
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            return Resultado("ok", {"habilitada": self.habilitada}, 200)
        if self.put is not None:
            return self.put
        self.habilitada = cuerpo["habilitada"]
        return Resultado("ok", {"ok": True}, 200)


def _ctrl(**kw):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import (
        ParametrosEquipoController)
    s = _Sesion(**kw)
    c = ParametrosEquipoController(sesion=s)
    c.cargar()
    return c, s


def test_lee_y_cambia_la_bandera():
    c, s = _ctrl()
    assert c.impresoraConocida and c.impresoraHabilitada
    assert c.fijarImpresora(False)
    assert ("PUT", "/printer/config", {"habilitada": False}) in s.enviados
    assert c.impresoraHabilitada is False and c.mensaje == ""


@pytest.mark.parametrize("causa, clave", [("rol_sin_permiso", "opciones.err_rol"),
                                          (BACKEND_NO_RESPONDE, "opciones.err_sin_respuesta"),
                                          ("ARCHIVO_NO_ESCRIBIBLE", "opciones.equipo_err_guardar")])
def test_rechazo_muestra_el_motivo_y_relee(causa, clave):
    c, s = _ctrl(put=Resultado(causa))
    assert not c.fijarImpresora(False)
    assert c.mensaje == clave
    assert c.impresoraHabilitada is True            # releído del backend
    assert s.enviados[-1][0] == "GET"


def test_sin_dato_no_inventa_el_valor():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import (
        ParametrosEquipoController)

    class _Caida:
        def enviar(self, *a, **k):
            return Resultado(BACKEND_NO_RESPONDE)
    c = ParametrosEquipoController(sesion=_Caida())
    c.cargar()
    assert c.impresoraConocida is False


def test_textos_en_es_y_en():
    import json
    for lang in ("es", "en"):
        d = json.loads((_RAIZ / f"src/autoclave/i18n/{lang}.json").read_text(encoding="utf-8"))
        for k in ("equipo_impresora", "equipo_impresora_ayuda", "equipo_si", "equipo_no",
                  "equipo_err_guardar"):
            assert d["opciones"][k], (lang, k)


def test_opciones_carga_la_pantalla_en_parametros_del_equipo():
    texto = (_RAIZ / "src/autoclave/ui_qml/qml/Pantallas/Opciones.qml").read_text(encoding="utf-8")
    assert 'active: raiz.seccionActiva === "parametros_sistema"' in texto
    assert "OpcionesParametrosEquipo {" in texto


def test_la_pantalla_carga_sin_avisos():
    import json
    import subprocess
    qml = _RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
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
Item { width: 800; height: 1200; OpcionesParametrosEquipo { anchors.fill: parent; edicionPermitida: true } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_equipo.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
for nombre in ("filaImpresoraHabilitada", "interruptorImpresora", "estadoImpresora"):
    assert raiz.findChild(QObject, nombre) is not None, nombre
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()]}))
"""
    r = subprocess.run([sys.executable, "-c", guion, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=_RAIZ, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-1500:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["avisos"] == []
