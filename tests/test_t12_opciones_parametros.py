"""T12 (tanda 2026-10-14): OPCIONES › Parámetros del ciclo, Fases 2 a 4
(planeacion_opciones_parametros_ciclo.md rev. 3.1 §5.1 a §5.5, §6)."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.cycle_manager import CycleManager

RAIZ = Path(__file__).resolve().parents[1]


# ── Backend: GET /programas y GET /programas/{n}/seccion/{s} ───────────────

@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from tests.backend_doble import cargar_servidor
    cm = CycleManager()
    cm.load_all_cycles()
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.db.get_auditoria.return_value = [
        {"entidad": "liquidos/esterilizacion/tiempo_esterilizacion", "usuario": "tec1",
         "rol": "tecnico", "ts": "2026-10-16 08:00:00", "valor_anterior": "10", "valor_nuevo": "15"},
        {"entidad": "liquidos/esterilizacion/tiempo_esterilizacion", "usuario": "viejo",
         "rol": "tecnico", "ts": "2026-10-01 08:00:00", "valor_anterior": "5", "valor_nuevo": "10"},
    ]
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), cm


def test_programas_con_secciones_y_no_se_ejecuta(cliente):
    client, _ = cliente
    programas = client.get("/programas").json()["programas"]
    assert [p["numero"] for p in programas] == [1, 2, 3, 4]
    liq = next(p for p in programas if p["numero"] == 4)
    assert liq["editable"] is True and liq["danado"] is False
    secciones = {s["clave"]: s["no_se_ejecuta"] for s in liq["secciones"]}
    assert list(secciones)[:6] == ["precalentamiento", "prevacio", "calentamiento",
                                   "esterilizacion", "descompresion", "secado"]
    assert secciones["prevacio"] is True and secciones["secado"] is True       # Q-2
    assert secciones["esterilizacion"] is False


def test_seccion_con_defecto_rango_efectivo_y_ultima_modificacion(cliente):
    client, cm = cliente
    datos = client.get("/programas/4/seccion/esterilizacion").json()
    p = {x["clave"]: x for x in datos["parametros"]}
    t = p["tiempo_esterilizacion"]
    assert t["defecto"] == cm.fabrica[4].get_param("esterilizacion", "tiempo_esterilizacion")
    assert t["min"] == 1                       # catálogo ∩ JSON (mínimo 1 del catálogo)
    assert t["ultima_modificacion"]["usuario"] == "tec1"      # la más reciente
    assert t["modificado"] is False
    assert p["temperatura_esterilizacion"]["min"] == 100


def test_descompresion_muestra_solo_el_modo_activo(cliente):
    """Q-3: el modo y los parámetros del modo activo (Líquidos: modo 4)."""
    client, _ = cliente
    claves = [x["clave"] for x in client.get("/programas/4/seccion/descompresion").json()["parametros"]]
    assert "modo" in claves and "modo_4.temperatura_enfriamiento" in claves
    assert not any(c.startswith(("modo_1.", "modo_2.", "modo_3.", "modo_5.")) for c in claves)


def test_programa_de_usuario_modificado_lleva_asterisco(cliente):
    client, cm = cliente
    cm.cycles["liquidos"].parameters["esterilizacion"]["tiempo_esterilizacion"]["value"] = 20.0
    p = {x["clave"]: x for x in client.get("/programas/4/seccion/esterilizacion").json()["parametros"]}
    assert p["tiempo_esterilizacion"]["modificado"] is True


def test_programa_sin_perfil_de_fabrica_sin_defecto(cliente):
    """Q-4: sin perfil de fábrica del mismo número, "—" (None)."""
    client, cm = cliente
    cm.fabrica.pop(4)
    p = client.get("/programas/4/seccion/globals").json()["parametros"]
    assert all(x["defecto"] is None and x["modificado"] is False for x in p)


def test_seccion_inexistente(cliente):
    client, _ = cliente
    assert client.get("/programas/4/seccion/purga").status_code == 404
    assert client.get("/programas/99/seccion/globals").status_code == 404


# ── Controlador ────────────────────────────────────────────────────────────

pytest.importorskip("PySide6")


class _Sesion:
    """Doble de SesionVentana.enviar: respuestas por (método, ruta)."""

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        from autoclave.ui_qml.sesion_backend import Resultado
        self.enviados.append((metodo, ruta, cuerpo))
        r = self.respuestas.get((metodo, ruta.split("?")[0]))
        if callable(r):
            r = r(cuerpo)
        return r or Resultado("error_generico")


def _ok(datos):
    from autoclave.ui_qml.sesion_backend import Resultado
    return Resultado("ok", datos, 200)


_PROGRAMAS = {"programas": [{"numero": 4, "cycle_id": "liquidos", "nombre": "Líquidos",
                             "editable": True, "danado": False,
                             "secciones": [{"clave": "esterilizacion", "no_se_ejecuta": False}]}]}
_SECCION = {"editable": True, "parametros": [
    {"clave": "tiempo_esterilizacion", "path": ["tiempo_esterilizacion"], "tipo": "float",
     "valor": 15.0, "defecto": 15.0, "min": 1, "max": 9999, "unidad": "min", "opciones": [],
     "modificado": False, "ultima_modificacion": None}]}


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _control(extra=None):
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    resp = {("GET", "/programas"): _ok(_PROGRAMAS),
            ("GET", "/programas/4/seccion/esterilizacion"): _ok(_SECCION)}
    resp.update(extra or {})
    s = _Sesion(resp)
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    c.abrirSeccion("esterilizacion")
    return c, s


def test_controlador_carga_y_elige_el_primer_programa():
    c, _ = _control()
    assert c.numero == 4 and c.nombrePrograma == "Líquidos" and c.programaEditable
    assert [p["clave"] for p in c.parametros] == ["tiempo_esterilizacion"]


def test_guardar_envia_valor_anterior_esperado():
    c, s = _control({("PATCH", "/cycle/parameter"): _ok({"ok": True})})
    assert c.guardar("tiempo_esterilizacion", 20.0) is True
    metodo, ruta, cuerpo = next(e for e in s.enviados if e[0] == "PATCH")
    assert cuerpo == {"cycle_id": "liquidos", "fase": "esterilizacion",
                      "path": ["tiempo_esterilizacion"], "value": 20.0,
                      "valor_anterior_esperado": 15.0}
    assert c.mensaje == ""


def test_rechazo_muestra_el_mensaje_del_codigo():
    from autoclave.ui_qml.sesion_backend import Resultado
    c, _ = _control({("PATCH", "/cycle/parameter"):
                     Resultado("VALOR_CAMBIO", {"valor_actual": 18.0}, 409)})
    assert c.guardar("tiempo_esterilizacion", 20.0) is False
    assert c.mensaje == "opciones.err_valor_cambio" and c.detalleMensaje["valor"] == 18.0


def test_sin_respuesta_se_verifica_antes_de_informar():
    """§5.4 / D-15: un timeout es incierto; si al recargar el valor ya es el
    nuevo, se informa como guardado."""
    from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado
    guardado = json.loads(json.dumps(_SECCION))
    guardado["parametros"][0]["valor"] = 20.0
    c, s = _control({("PATCH", "/cycle/parameter"): Resultado(BACKEND_NO_RESPONDE)})
    s.respuestas[("GET", "/programas/4/seccion/esterilizacion")] = _ok(guardado)
    assert c.guardar("tiempo_esterilizacion", 20.0) is True
    s.respuestas[("GET", "/programas/4/seccion/esterilizacion")] = _ok(_SECCION)
    assert c.guardar("tiempo_esterilizacion", 25.0) is False
    assert c.mensaje == "opciones.err_sin_respuesta"


def test_sensores_todo_o_nada_con_asignacion_esperada():
    sensores = {"asignacion": {"temp_camara": "principal", "temp_2_camara": "no_en_uso",
                               "temp_ref": "no_en_uso"},
                "editable": True, "sensores": [{"id": "temp_camara"}]}
    c, s = _control({("GET", "/cycle/sensors"): _ok(sensores),
                     ("PUT", "/cycle/sensor-roles"): _ok({"ok": True})})
    c.cargarSensores()
    assert c.sensoresEditable and c.asignacion["temp_camara"] == "principal"
    nueva = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "referencia"}
    assert c.guardarSensores(nueva) is True
    _, ruta, cuerpo = next(e for e in s.enviados if e[0] == "PUT")
    assert cuerpo == {"programa": 4, "asignacion": nueva,
                      "asignacion_anterior_esperada": sensores["asignacion"]}


def test_codigos_nuevos_llegan_al_controlador():
    from autoclave.ui_qml.sesion_backend import interpretar
    r = interpretar(409, {"codigo": "VALOR_CAMBIO", "valor_actual": 3}, "/cycle/parameter")
    assert r.causa == "VALOR_CAMBIO" and r.datos["valor_actual"] == 3


# ── QML (offscreen): programa → sección → ajuste → sensores ────────────────

_SCRIPT_QML = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
import autoclave.ui_qml.bridge.i18n_qml
import autoclave.ui_qml.controllers  # registra Autoclave.Controllers
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.sesion_backend import Resultado

PROGRAMAS = json.loads(sys.argv[2])
SECCION = json.loads(sys.argv[3])
SENSORES = {"asignacion": {"temp_camara": "principal", "temp_2_camara": "no_en_uso"},
            "editable": True,
            "sensores": [{"id": "temp_camara", "nombre": "Cámara 1", "estado": "disponible", "lectura": 121.0},
                         {"id": "temp_2_camara", "nombre": "Cámara 2", "estado": "disponible", "lectura": 120.5}]}

class Sesion:
    def enviar(self, metodo, ruta, cuerpo=None):
        ruta = ruta.split("?")[0]
        datos = {"/programas": PROGRAMAS, "/cycle/sensors": SENSORES}.get(ruta, SECCION)
        return Resultado("ok", datos, 200)

sesion_backend.instalar(Sesion())
qml_dir = sys.argv[1]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
qml = b'''import QtQuick
import "Pantallas"
Item { width: 1088; height: 1400
  OpcionesParametrosCiclo { objectName: "vista"; anchors.fill: parent; edicionPermitida: true } }'''
comp = QQmlComponent(engine)
comp.setData(qml, QUrl.fromLocalFile(qml_dir + "/prueba_parametros.qml"))
raiz = comp.create()
assert raiz is not None, comp.errorString()
vista = raiz.findChild(QObject, "vista")
def hijo(n, nodo=None):
    # árbol VISUAL: los delegados de un Repeater no son hijos QObject
    nodo = nodo or raiz.findChild(QQuickItem, "vista")
    for item in nodo.childItems():
        if item.objectName() == n:
            return item
        encontrado = hijo(n, item)
        if encontrado is not None:
            return encontrado
    return None
r = {}
r["chip"] = hijo("programa_4") is not None
r["seccion_fila"] = hijo("seccion_esterilizacion") is not None
QMetaObject.invokeMethod(hijo("seccion_esterilizacion"), "pulsada")
r["vista_seccion"] = vista.property("vista") == "seccion"
app.processEvents()
r["param_fila"] = hijo("param_tiempo_esterilizacion") is not None
QMetaObject.invokeMethod(hijo("param_tiempo_esterilizacion"), "pulsada")
r["ajuste_visible"] = hijo("ventanaAjuste").property("visible")
QMetaObject.invokeMethod(hijo("cancelarAjuste"), "pulsado")
r["ajuste_cerrado"] = not hijo("ventanaAjuste").property("visible")
vista.setProperty("vista", "programa")
QMetaObject.invokeMethod(hijo("filaSensores"), "pulsada")
app.processEvents()
r["vista_sensores"] = vista.property("vista") == "sensores"
r["tarjeta_sensor"] = hijo("sensor_temp_2_camara") is not None
r["sin_cambios"] = vista.property("cambiosPendientes") is False
r["avisos"] = avisos
print("RES=" + json.dumps(r))
"""


def test_vista_qml_parametros_y_sensores():
    import subprocess
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    programas = json.dumps(_PROGRAMAS)
    seccion = json.dumps(_SECCION)
    r = subprocess.run([sys.executable, "-c", _SCRIPT_QML, str(qml), programas, seccion],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    linea = next(l for l in r.stdout.splitlines() if l.startswith("RES="))
    res = json.loads(linea[4:])
    assert res.pop("avisos") == []
    assert all(res.values()), res
