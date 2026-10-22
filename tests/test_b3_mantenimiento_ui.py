"""B3 (tanda 4): edición de los intervalos de mantenimiento en OPCIONES ›
Mantenimiento (controlador y pantalla)."""

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

_OK = {"estado": "ok", "vencido": False, "proximo_fecha": "2027-10-26", "ultimo_fecha": None,
       "ciclos_restantes": 1000, "configuracion": {"intervalo_dias": 365, "intervalo_ciclos": 1000}}


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


def test_carga_los_intervalos_configurados():
    c, _ = _controlador({("GET", "/maintenance"): Resultado("ok", _OK, 200)})
    assert (c.intervaloDias, c.intervaloCiclos) == (-1, -1)         # antes de cargar
    c.cargar()
    assert (c.intervaloDias, c.intervaloCiclos) == (365, 1000)
    assert (c.diasMax, c.ciclosMax) == (3650, 1_000_000)


def test_sin_respuesta_los_intervalos_se_desconocen():
    c, _ = _controlador({("GET", "/maintenance"): Resultado(BACKEND_NO_RESPONDE)})
    c.cargar()
    assert (c.intervaloDias, c.intervaloCiclos) == (-1, -1)


def test_guardar_envia_put_y_recarga():
    nuevo = {**_OK, "configuracion": {"intervalo_dias": 200, "intervalo_ciclos": 0}}
    c, s = _controlador({("GET", "/maintenance"): Resultado("ok", nuevo, 200),
                         ("PUT", "/maintenance/config"): Resultado("ok", {"ok": True}, 200)})
    assert c.guardarIntervalos(200, 0) is True
    assert ("PUT", "/maintenance/config", {"intervalo_dias": 200, "intervalo_ciclos": 0}) in s.enviados
    assert s.enviados[-1][1] == "/maintenance"                      # recarga
    assert c.intervaloDias == 200 and c.intervaloCiclos == 0 and c.mensaje == ""


@pytest.mark.parametrize("dias, ciclos", [(-1, 0), (0, -5), (3651, 0), (0, 1_000_001)])
def test_fuera_de_limites_no_sale_a_la_red(dias, ciclos):
    c, s = _controlador({})
    assert c.guardarIntervalos(dias, ciclos) is False
    assert s.enviados == [] and c.mensaje == "opciones.mant_err_validacion"


@pytest.mark.parametrize("causa, clave", [
    ("rol_sin_permiso", "opciones.err_rol"),
    ("sesion_invalida", "opciones.err_identidad"),
    ("estado_no_permitido", "opciones.err_bloqueada"),
    ("validacion", "opciones.mant_err_validacion"),
    (BACKEND_NO_RESPONDE, "opciones.err_sin_respuesta")])
def test_rechazos_muestran_su_motivo_y_no_cuentan_como_guardado(causa, clave):
    c, _ = _controlador({("GET", "/maintenance"): Resultado("ok", _OK, 200),
                         ("PUT", "/maintenance/config"): Resultado(causa, {}, 403)})
    assert c.guardarIntervalos(100, 5) is False
    assert c.mensaje == clave


def test_reloj_adelantado_tiene_su_mensaje():
    c, _ = _controlador({("GET", "/maintenance"): Resultado("ok", _OK, 200),
                         ("POST", "/maintenance/records"): Resultado("reloj_adelantado", {}, 409)})
    assert c.registrar("correctivo") is False and c.mensaje == "opciones.mant_err_reloj_adelantado"


def test_las_claves_nuevas_existen_en_es_y_en():
    base = RAIZ / "src" / "autoclave" / "i18n"
    claves = ["mant_err_reloj_adelantado", "mant_intervalos", "mant_intervalo_dias",
              "mant_intervalo_ciclos", "mant_unidad_dias", "mant_unidad_ciclos", "mant_no_aplica",
              "mant_intervalos_ayuda", "mant_guardar_intervalos"]
    for idioma in ("es", "en"):
        datos = json.loads((base / f"{idioma}.json").read_text(encoding="utf-8"))["opciones"]
        for k in claves:
            assert datos.get(k), (idioma, k)


def test_la_pantalla_de_intervalos_carga_sin_avisos():
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
Item { width: 800; height: 1400; OpcionesMantenimiento { anchors.fill: parent; edicionPermitida: true } }''',
          QUrl.fromLocalFile(qml_dir + "/prueba_mant.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
for nombre in ("campoIntervalo_dias", "campoIntervalo_ciclos", "botonGuardarIntervalos",
               "valorIntervalo_dias", "valorIntervalo_ciclos"):
    assert raiz.findChild(QObject, nombre) is not None, nombre
boton = raiz.findChild(QObject, "botonGuardarIntervalos")
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()],
                  "guardar_habilitado": bool(boton.property("habilitado"))}))
"""
    r = subprocess.run([sys.executable, "-c", guion, str(qml)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-1500:]
    salida = json.loads(r.stdout.strip().splitlines()[-1])
    assert salida["avisos"] == []
    assert salida["guardar_habilitado"] is False            # sin cambios no se puede guardar
