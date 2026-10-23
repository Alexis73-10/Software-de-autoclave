"""R11 (tanda 11, D11-1): pantalla OPCIONES › Parámetros del equipo › Impresión.

Cambiar "Impresora habilitada" pide confirmación ("Se reiniciará el software
para aplicar el cambio"); con Cancelar no se envía nada. Al confirmar se envía
PUT /printer/config con `reiniciar` y, aceptado, la pantalla muestra el aviso
de reinicio con "Si el software no vuelve a abrir en 1 minuto, apague y
encienda el equipo". Rechazado (CICLO, sin lanzador), muestra el motivo."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import Resultado

_RAIZ = Path(__file__).resolve().parents[1]


class SesionReinicio:
    """Sesión simulada: `put` es la respuesta al PUT (por defecto, aceptado)."""

    def __init__(self, put=None):
        self.put = put
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            datos = {"/system_params": {"parametros": []},
                     "/printer/config": {"habilitada": True},
                     "/units": {"temperatura": "C", "presion": "kPa"},
                     "/language": {"idioma": "es"}}.get(ruta, {})
            return Resultado("ok", datos, 200)
        if self.put is not None:
            return self.put
        return Resultado("ok", {"ok": True, "habilitada": cuerpo["habilitada"],
                                "reiniciando": True}, 200)


def _ctrl(sesion):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import (
        ParametrosEquipoController)
    c = ParametrosEquipoController(sesion=sesion, perfil=lambda: None)
    c.cargar()
    return c


def test_confirmado_envia_reiniciar_y_queda_reiniciando_sin_releer():
    s = SesionReinicio()
    c = _ctrl(s)
    s.enviados.clear()
    assert c.fijarImpresoraYReiniciar(False)
    assert s.enviados == [("PUT", "/printer/config", {"habilitada": False, "reiniciar": True})]
    assert c.reiniciando is True and c.impresoraHabilitada is False and c.mensaje == ""


@pytest.mark.parametrize("causa, clave", [
    ("estado_no_permitido", "opciones.equipo_err_ciclo"),
    ("reinicio_no_disponible", "opciones.equipo_err_reinicio_no_disponible"),
    ("apagado_en_curso", "opciones.equipo_err_reinicio_en_curso"),
    # SAF-01 de la revisión
    ("estado_seguro_activo", "opciones.equipo_err_reinicio_estado_seguro"),
    ("confirmacion_pendiente", "opciones.equipo_err_reinicio_confirmacion"),
    ("modo_prueba_activo", "opciones.equipo_err_reinicio_modo_prueba"),
])
def test_rechazado_muestra_el_motivo_relee_y_no_reinicia(causa, clave):
    s = SesionReinicio(put=Resultado(causa))
    c = _ctrl(s)
    assert not c.fijarImpresoraYReiniciar(False)
    assert c.mensaje == clave and c.reiniciando is False
    assert c.impresoraHabilitada is True                   # releído del backend
    assert s.enviados[-1][0] == "GET"


def test_textos_en_es_y_en():
    for lang in ("es", "en"):
        d = json.loads((_RAIZ / f"src/autoclave/i18n/{lang}.json").read_text(encoding="utf-8"))
        for clave in ("equipo_reinicio_pregunta", "equipo_reinicio_aviso", "equipo_reiniciar",
                      "equipo_reiniciando", "equipo_err_reinicio_no_disponible",
                      "equipo_err_reinicio_en_curso", "equipo_err_reinicio_estado_seguro",
                      "equipo_err_reinicio_confirmacion", "equipo_err_reinicio_modo_prueba"):
            assert d["opciones"][clave], (lang, clave)
    es = json.loads((_RAIZ / "src/autoclave/i18n/es.json").read_text(encoding="utf-8"))
    assert es["opciones"]["equipo_reinicio_pregunta"] == \
        "Se reiniciará el software para aplicar el cambio."
    assert es["opciones"]["equipo_reinicio_aviso"] == \
        "Si el software no vuelve a abrir en 1 minuto, apague y encienda el equipo."


_GUION = r"""
import json, sys
sys.path.insert(0, sys.argv[2]); sys.path.insert(0, ".")
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.bridge.unidades_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml import sesion_backend
from tests.test_r11_reinicio_ui import SesionReinicio
sesion = SesionReinicio()
sesion_backend.ventana = lambda: sesion
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item { width: 1100; height: 1500; OpcionesParametrosEquipo { objectName: "p"; anchors.fill: parent;
       edicionPermitida: true; rol: "tecnico"; estadoMaquina: "PREPARADO" } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_r11.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
from PySide6.QtQuick import QQuickItem
p = raiz.findChild(QQuickItem, "p")
ctrl = p.findChild(QObject, "parametrosEquipoController")
ctrl.abrirGrupo("impresion")
dialogo = p.findChild(QQuickItem, "dialogoReinicioImpresora")
aviso = p.findChild(QQuickItem, "avisoReinicioSoftware")
puts = lambda: [x for x in sesion.enviados if x[0] == "PUT"]
r = {}
QMetaObject.invokeMethod(p, "pedirCambioImpresora", Q_ARG("QVariant", False))
r["abierto"] = dialogo.property("visible")
r["mensaje"] = dialogo.property("mensaje")
QMetaObject.invokeMethod(dialogo, "_descartar")
r["tras_cancelar"] = {"visible": dialogo.property("visible"), "puts": len(puts()),
                      "aviso": aviso.property("visible")}
QMetaObject.invokeMethod(p, "pedirCambioImpresora", Q_ARG("QVariant", False))
QMetaObject.invokeMethod(dialogo, "cerrar")
dialogo.confirmado.emit()
r["tras_confirmar"] = {"puts": puts(), "aviso": aviso.property("visible")}
r["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
print(json.dumps(r, ensure_ascii=False))
"""


def test_pantalla_confirmar_y_cancelar():
    qml = _RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml), str(_RAIZ / "src")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=_RAIZ, timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
                                                    "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["abierto"] is True
    assert "Se reiniciará el software para aplicar el cambio." in d["mensaje"]
    assert "apague y encienda el equipo" in d["mensaje"] and "\n\n" in d["mensaje"]
    assert d["tras_cancelar"] == {"visible": False, "puts": 0, "aviso": False}   # nada se guarda
    assert d["tras_confirmar"]["puts"] == [["PUT", "/printer/config",
                                            {"habilitada": False, "reiniciar": True}]]
    assert d["tras_confirmar"]["aviso"] is True
    assert d["avisos"] == []
