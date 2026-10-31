"""Tanda 24 (RSB-03..08): reasignación de E/S en la UI.

- RSB-05 (prueba de regla): todo código que pueden emitir POST /io/assignment,
  /io/assignment/factory, /io/assignment/verify y GET /io/assignment (extraído
  del código de server_reasignacion.py, asignacion_io.py y dependencias.py)
  llega al controlador (sesion_backend.codigos_conocidos de esas rutas) y
  tiene su texto propio en ReasignacionController._MENSAJES, en es y en en.
- RSB-04: cada código muestra su texto (no el genérico).
- RSB-03: `aviso_camara` aparece y desaparece en los diálogos de Aplicar y de
  Restaurar fábrica.
- RSB-06: los códigos retirados ya no están en el controlador ni el catálogo.
- RSB-07: el diálogo de Verificar de una analógica muestra la lectura actual
  y no pide calibrar.
- RSB-08: la columna Tipo dice «RTD» en las temperaturas y «AI» en las
  presiones; el tipo interno sigue siendo "AI".
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import Resultado, codigos_conocidos, interpretar  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
_BACKEND = RAIZ / "src" / "autoclave" / "backend"
_RUTAS = ("/io/assignment", "/io/assignment/factory", "/io/assignment/verify")
_RETIRADOS = ("estado_seguro", "estado_seguro_confirmar", "estado_seguro_liquido",
              "sensor_camara_no_segura", "calibracion_requerida")

_CODIGO_DICT = re.compile(r'"codigo"\s*:\s*"([a-z_]+)"')
_RECHAZOS = {"RechazoApi", "_rechazar", "_Rechazo"}
# funciones de server_reasignacion.py que sirven al respaldo (/backup/*), no a
# las rutas de la reasignación
_SOLO_RESPALDO = {"contenido_respaldo", "validar_respaldo", "restaurar_respaldo"}


def _constantes(nodo) -> set:
    return {c.value for c in ast.walk(nodo)
            if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value}


def _devoluciones(fuente: str, funcion: str) -> set:
    """Literales de cadena no vacíos que devuelve `funcion` (return "x" o
    `"" if ... else "x"`)."""
    salida = set()
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == funcion:
            for r in ast.walk(nodo):
                if isinstance(r, ast.Return) and r.value is not None:
                    salida |= _constantes(r.value)
    return salida


def _codigos_de_rechazos(fuente: str, excluir=frozenset()) -> set:
    """Segundo argumento (el código) de cada RechazoApi/_rechazar/_Rechazo con
    literales, también dentro de un `a if c else b`; y el valor por defecto de
    `.get("codigo", "x")`."""
    salida = set()
    arbol = ast.parse(fuente)
    excluidos = {id(n) for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) and f.name in excluir
                 for n in ast.walk(f)}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or id(nodo) in excluidos:
            continue
        nombre = getattr(nodo.func, "attr", None) or getattr(nodo.func, "id", None)
        if nombre in _RECHAZOS and len(nodo.args) >= 2:
            salida |= _constantes(nodo.args[1])
        if (nombre == "get" and len(nodo.args) == 2 and isinstance(nodo.args[0], ast.Constant)
                and nodo.args[0].value == "codigo"):
            salida |= _constantes(nodo.args[1])
    return salida


def codigos_emitidos() -> set:
    reasig = (_BACKEND / "server_reasignacion.py").read_text(encoding="utf-8")
    aio = (RAIZ / "src/autoclave/core/runtime/asignacion_io.py").read_text(encoding="utf-8")
    dep = (_BACKEND / "dependencias.py").read_text(encoding="utf-8")
    codigos = _codigos_de_rechazos(reasig, _SOLO_RESPALDO) | _codigos_de_rechazos(dep)
    codigos |= set(_CODIGO_DICT.findall(aio)) | set(_CODIGO_DICT.findall(reasig))
    codigos |= _devoluciones(reasig, "_evidencia_que_falta")
    # el 429 del bloqueo por reautenticación (_bloquear_por_cambio_clave)
    codigos |= {"usuario_bloqueado"}
    return codigos


def test_rsb05_la_extraccion_encuentra_los_codigos_conocidos():
    """Control de la propia extracción (si el patrón dejara de casar, la regla
    pasaría sin comprobar nada)."""
    c = codigos_emitidos()
    for esperado in ("conflicto", "puerto_inexistente", "funcion_desconocida", "fabrica_invalida",
                     "asignacion_invalida", "sin_cambios", "confirmacion_requerida",
                     "confirmacion_reforzada", "nombre_no_coincide", "puerto_sin_calibracion",
                     "no_se_pudo_guardar", "reinicio_en_curso", "reinicio_pendiente", "no_pendiente",
                     "sin_cambio_observado", "sin_prueba_de_salida", "sin_lectura",
                     "estado_no_permitido", "reautenticacion_requerida", "reautenticacion_fallida",
                     "rol_sin_permiso", "validacion"):
        assert esperado in c, esperado


@pytest.mark.req("RSB-05")
def test_rsb05_todo_codigo_emitido_llega_y_tiene_texto():
    from autoclave import i18n
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    sin_ruta = {r: sorted(c for c in codigos_emitidos() if c not in codigos_conocidos(r))
                for r in _RUTAS}
    assert sin_ruta == {r: [] for r in _RUTAS}
    sin_texto = sorted(c for c in codigos_emitidos() if c not in rc._MENSAJES)
    assert sin_texto == []
    faltan = [(c, l) for c in codigos_emitidos() for l in ("es", "en")
              if not i18n.existe(rc._MENSAJES[c], l)]
    assert faltan == []


@pytest.mark.req("RSB-05")
def test_rsb05_motivos_del_bloqueo_tienen_texto():
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    fuente = (_BACKEND / "server_reasignacion.py").read_text(encoding="utf-8")
    motivos = {m for m in _devoluciones(fuente, "_motivo_bloqueo") if m.isidentifier()}
    assert motivos == {"ciclo", "estado", "modo_prueba", "apagando"}
    assert motivos <= rc._MOTIVOS


@pytest.mark.req("RSB-04")
@pytest.mark.parametrize("ruta", _RUTAS)
def test_rsb04_interpretar_deja_pasar_los_codigos_en_sus_rutas(ruta):
    r = interpretar(422, {"codigo": "conflicto", "errores": [{"codigo": "conflicto"}]}, ruta)
    assert r.causa == "conflicto" and r.datos["errores"]


def test_rsb04_fuera_de_la_reasignacion_no_cambia_nada():
    for codigo in ("conflicto", "confirmacion_requerida", "archivo_invalido", "sin_lectura"):
        assert interpretar(428, {"codigo": codigo}, "/backup/restore").causa == "error_generico"
        assert interpretar(428, {"codigo": codigo}, "/io/assignmentX").causa == "error_generico"
    assert codigos_conocidos("/io/assignment?x=1") == codigos_conocidos("/io/assignment")


# ── controlador ────────────────────────────────────────────────────────────

_FILAS = [
    {"funcion": "vapor_camara", "tipo": "DO", "i18n": "io.do.vapor_camara", "puerto_actual": 4,
     "id_actual": "DO 04", "puerto_guardado": 4, "puerto_fabrica": 4, "critica": True,
     "reforzada": False, "temperatura": False, "grupo": "DO"},
    {"funcion": "paro_emergencia", "tipo": "DI", "i18n": "io.di.paro_emergencia", "puerto_actual": 11,
     "id_actual": "DI 11", "puerto_guardado": 11, "puerto_fabrica": 11, "critica": True,
     "reforzada": True, "temperatura": False, "grupo": "DI"},
    {"funcion": "temp_camara", "tipo": "AI", "i18n": "io.ai.temp_camara", "puerto_actual": 4,
     "id_actual": "RTD 04", "puerto_guardado": 4, "puerto_fabrica": 1, "critica": True,
     "reforzada": False, "temperatura": True, "grupo": "AI_TEMP"},
    {"funcion": "pres_camara", "tipo": "AI", "i18n": "io.ai.pres_camara", "puerto_actual": 13,
     "id_actual": "AI 13", "puerto_guardado": 13, "puerto_fabrica": 1, "critica": True,
     "reforzada": False, "temperatura": False, "grupo": "AI_PRES"},
]
_DATOS = {
    "filas": _FILAS,
    "puertos": {"DI": list(range(1, 17)), "DO": list(range(1, 33)),
                "AI_TEMP": list(range(1, 7)), "AI_PRES": list(range(1, 17))},
    "ocupados": {"DI": {"11": "paro_emergencia"}, "DO": {"4": "vapor_camara"},
                 "AI_TEMP": {"4": "temp_camara"}, "AI_PRES": {"13": "pres_camara"}},
    "cambios_guardados": {}, "reinicio_pendiente": False, "error_archivo": "", "bloqueo": "",
    "pendientes": ["temp_camara", "pres_camara"],
    "verificacion": {"estado": "pendiente", "funciones": {
        "temp_camara": {"estado": "pendiente", "falta": "", "lectura": 25.46},
        "pres_camara": {"estado": "pendiente", "falta": "sin_lectura", "lectura": None}}},
    "editable": True, "motivo": "", "aviso_camara": False, "reinicio_disponible": True,
}


class _Sesion:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        r = self.respuestas.get((metodo, ruta))
        return r() if callable(r) else (r or Resultado("error_generico"))


def _ctrl(datos=None, extra=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController
    resp = {("GET", "/io/assignment"): Resultado("ok", json.loads(json.dumps(datos or _DATOS)), 200)}
    resp.update(extra or {})
    c = ReasignacionController(sesion=_Sesion(resp))
    c.cargar()
    return c


@pytest.mark.req("RSB-04")
@pytest.mark.parametrize("ruta,metodo", [("/io/assignment", "aplicar"),
                                         ("/io/assignment/factory", "restaurarFabrica"),
                                         ("/io/assignment/verify", "verificar")])
def test_rsb04_cada_codigo_muestra_su_texto(ruta, metodo):
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    for codigo in sorted(codigos_emitidos()):
        if codigo == "estado_no_permitido":
            continue                                   # con motivo: prueba aparte
        res = interpretar(409, {"codigo": codigo}, ruta)
        assert res.causa == codigo
        c = _ctrl(extra={("POST", ruta): res})
        if metodo == "aplicar":
            c.elegirPuerto("vapor_camara", 7)
            assert c.aplicar("clave") is False
        elif metodo == "verificar":
            assert c.verificar("temp_camara", "clave", "") is False
        else:
            assert c.restaurarFabrica("clave") is False
        assert c.mensaje == rc._MENSAJES[codigo] != "reasignacion.err_generico", codigo


@pytest.mark.req("RSB-04")
@pytest.mark.parametrize("motivo", ["ciclo", "estado", "modo_prueba", "apagando"])
def test_rsb04_estado_no_permitido_muestra_el_motivo(motivo):
    res = interpretar(409, {"codigo": "estado_no_permitido", "motivo": motivo}, "/io/assignment")
    c = _ctrl(extra={("POST", "/io/assignment"): res})
    c.elegirPuerto("vapor_camara", 7)
    assert c.aplicar("clave") is False
    assert c.mensaje == f"reasignacion.motivo_{motivo}"


def test_rsb04_desconocido_sigue_siendo_generico():
    c = _ctrl(extra={("POST", "/io/assignment"): interpretar(409, {"codigo": "otro_raro"},
                                                            "/io/assignment")})
    c.elegirPuerto("vapor_camara", 7)
    assert c.aplicar("clave") is False
    assert c.mensaje == "reasignacion.err_generico"


@pytest.mark.req("RSB-06")
def test_rsb06_retirados_fuera_del_controlador_y_del_catalogo():
    from autoclave import i18n
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    for codigo in _RETIRADOS:
        assert codigo not in rc._MENSAJES and codigo not in rc._MOTIVOS and codigo not in rc._FALTAS
    for clave in ("reasignacion.motivo_estado_seguro", "reasignacion.motivo_estado_seguro_confirmar",
                  "reasignacion.motivo_estado_seguro_liquido",
                  "reasignacion.err_sensor_camara_no_segura",
                  "reasignacion.falta_calibracion_requerida", "reasignacion.verificar_texto_ai"):
        for l in ("es", "en"):
            assert not i18n.existe(clave, l), (clave, l)
    qml = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/OpcionesReasignacion.qml").read_text(encoding="utf-8")
    assert "verificar_texto_ai" not in qml and "calibracion_requerida" not in qml


@pytest.mark.req("RSB-03")
def test_rsb03_aviso_camara_en_el_controlador():
    assert _ctrl().avisoCamara is False
    assert _ctrl({**_DATOS, "aviso_camara": True}).avisoCamara is True
    sin_campo = dict(_DATOS)
    sin_campo.pop("aviso_camara")
    assert _ctrl(sin_campo).avisoCamara is True          # falla hacia mostrar el aviso


@pytest.mark.req("RSB-07")
def test_rsb07_verificacion_trae_la_lectura_visible():
    v = {x["funcion"]: x for x in _ctrl().verificacion}
    assert v["temp_camara"]["lectura"] == "25.5 °C" and v["temp_camara"]["falta"] == ""
    assert v["pres_camara"]["lectura"] == "" and v["pres_camara"]["falta"] == "reasignacion.falta_sin_lectura"
    datos = json.loads(json.dumps(_DATOS))
    datos["verificacion"]["funciones"]["pres_camara"] = {"estado": "pendiente", "falta": "",
                                                         "lectura": 101.32}
    assert {x["funcion"]: x for x in _ctrl(datos).verificacion}["pres_camara"]["lectura"] == "101.3 kPa"


@pytest.mark.req("RSB-08")
def test_rsb08_tipo_visible_rtd_en_temperatura_ai_en_presion():
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    filas = {f["funcion"]: f for f in _ctrl().filas}
    assert filas["temp_camara"]["tipo_visible"] == "RTD"
    assert filas["pres_camara"]["tipo_visible"] == "AI"
    assert filas["vapor_camara"]["tipo_visible"] == "DO"
    assert filas["paro_emergencia"]["tipo_visible"] == "DI"
    # solo presentación: el tipo interno no cambia
    assert filas["temp_camara"]["tipo"] == "AI" and filas["pres_camara"]["tipo"] == "AI"
    # sin "grupo" (backend anterior) se deduce de "temperatura"
    assert rc.tipo_visible({"tipo": "AI", "temperatura": True}) == "RTD"
    assert rc.tipo_visible({"tipo": "AI", "temperatura": False}) == "AI"
    v = {x["funcion"]: x for x in _ctrl().verificacion}
    assert v["temp_camara"]["tipoVisible"] == "RTD" and v["temp_camara"]["tipo"] == "AI"


def test_rsb08_qml_toma_el_tipo_del_controlador():
    qml = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/OpcionesReasignacion.qml").read_text(encoding="utf-8")
    assert "fila.dato.tipo_visible" in qml
    assert "fila.dato.tipo ||" not in qml
    assert '"RTD"' not in qml                         # sin comparaciones repetidas en QML


# ── pantalla QML: diálogos ─────────────────────────────────────────────────

_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG, Q_RETURN_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave import i18n
qml_dir, datos = sys.argv[1], json.loads(sys.argv[2])
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(b'''import QtQuick
import "Pantallas"
Item {
    width: 1100; height: 1500
    OpcionesReasignacion { id: o; anchors.fill: parent }
    // los delegados de un Repeater no se ven con findChild: se buscan en QML
    function buscar(item, nombre) {
        if (!item) return null
        if (item.objectName === nombre) return item
        const hijos = item.contentItem ? [item.contentItem].concat(item.children) : item.children
        for (let i = 0; i < hijos.length; i++) {
            const x = buscar(hijos[i], nombre)
            if (x) return x
        }
        return null
    }
    function textoDe(nombre) { const x = buscar(o, nombre); return x ? x.text : "(no encontrado)" }
}''',
          QUrl.fromLocalFile(qml_dir + "/prueba_t24.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
pantalla = raiz.findChild(QObject, "opcionesReasignacion")
ctrl = raiz.findChild(QObject, "reasignacionController")
from autoclave.ui_qml.sesion_backend import Resultado

class S:
    def enviar(self, metodo, ruta, cuerpo=None):
        return Resultado("ok", json.loads(json.dumps(datos)), 200) if metodo == "GET" else Resultado("error_generico")

ctrl._sesion = S()
ctrl.cargar()
app.processEvents()
salida = {}
for nombre in ("dialogoReinicioReasignacion", "dialogoFabricaReasignacion"):
    salida[nombre] = raiz.findChild(QObject, nombre).property("mensaje")
for f in ("temp_camara", "pres_camara", "vapor_camara"):
    salida["tipo_" + f] = QMetaObject.invokeMethod(raiz, "textoDe", Q_RETURN_ARG("QVariant"),
                                                   Q_ARG("QVariant", "tipo_" + f))
for f in ("temp_camara", "pres_camara"):
    dato = [v for v in ctrl.property("verificacion") if v["funcion"] == f][0]
    QMetaObject.invokeMethod(pantalla, "iniciarVerificacion", Q_ARG("QVariant", dato))
    salida["verificar_" + f] = raiz.findChild(QObject, "dialogoVerificarReasignacion").property("mensaje")
salida["aviso_es"] = i18n.t("reasignacion.aviso_camara", "es")
salida["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
print(json.dumps(salida, ensure_ascii=True))
"""


def _pantalla(datos):
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    r = subprocess.run([sys.executable, "-c", _GUION, str(qml), json.dumps(datos)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.req("RSB-03")
def test_rsb03_aviso_aparece_y_desaparece_en_los_dos_dialogos():
    con = _pantalla({**_DATOS, "aviso_camara": True})
    sin = _pantalla({**_DATOS, "aviso_camara": False})
    assert con["avisos"] == [] and sin["avisos"] == []
    for nombre in ("dialogoReinicioReasignacion", "dialogoFabricaReasignacion"):
        assert con["aviso_es"] in con[nombre], nombre
        assert con["aviso_es"] not in sin[nombre], nombre
        # solo informa: el resto del texto es el mismo
        assert con[nombre].replace("\n\n" + con["aviso_es"], "") == sin[nombre]


@pytest.mark.req("RSB-07")
def test_rsb07_dialogo_verificar_muestra_la_lectura_y_no_pide_calibrar():
    s = _pantalla(_DATOS)
    assert "25.5 °C" in s["verificar_temp_camara"]
    assert "sin lectura válida" in s["verificar_pres_camara"]
    for clave in ("verificar_temp_camara", "verificar_pres_camara"):
        assert "calibr" not in s[clave].lower(), s[clave]


@pytest.mark.req("RSB-08")
def test_rsb08_columna_tipo_en_pantalla():
    s = _pantalla(_DATOS)
    assert s["tipo_temp_camara"] == "RTD"
    assert s["tipo_pres_camara"] == "AI"
    assert s["tipo_vapor_camara"] == "DO"
