# tests/test_t27_a7_incoherencia_parametros.py
#
# A7 (tanda 27, Cristian 5-nov): el rechazo por incoherencia de Parámetros del
# equipo decía siempre el texto de empaque (también al cambiar el suministro
# de vapor). Se comprueba:
#   - cada regla de ConfigManager da su código (incoherente_empaque /
#     incoherente_limites) y su `detalle.regla`, sin cambiar la decisión;
#   - PATCH /global_params responde 422 con el código y el detalle;
#   - el controlador elige el texto de la regla con sus valores; suministro >=
#     alivio da el texto de límites, nunca el de empaque;
#   - min_efectivo/max_efectivo de describir() coinciden con la validación;
#   - cobertura por AST de todas las causas de PATCH/POST /global_params:
#     llegan al cliente en su ruta y tienen texto es/en;
#   - la ventana de ajuste muestra el mensaje dentro (sin elide) y el rango
#     efectivo.

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autoclave.core.managers import config_manager as cmm
from autoclave.core.managers.config_manager import ConfigManager, ErrorParametro

pytestmark = pytest.mark.req("AJ27-A7")

_RAIZ = Path(__file__).resolve().parents[1]
_SRC = _RAIZ / "src" / "autoclave"
_I18N = {i: json.loads((_SRC / "i18n" / f"{i}.json").read_text(encoding="utf-8"))
         for i in ("es", "en")}


def _texto(idioma, clave):
    nodo = _I18N[idioma]
    for parte in clave.split("."):
        nodo = nodo[parte]
    return nodo


@pytest.fixture
def cm(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    c = ConfigManager()
    c.load_config()
    d = DbManager(db_path=tmp_path / "t.db")
    c.vincular_bd(d)
    yield c
    d.close()


# ── reglas → código y detalle ──────────────────────────────────────────────

CASOS_LIMITES = [
    ("presion_suministro_vapor", 385, "suministro_bajo_alivio"),
    ("presion_suministro_vapor", 400, "suministro_bajo_alivio"),
    ("presion_alivio_chaqueta", 350, "suministro_bajo_alivio"),
    ("presion_alivio_camara", 401, "alivio_bajo_fondo"),
    ("presion_fondo_escala", 380, "alivio_bajo_fondo"),
    ("presion_alivio_chaqueta", 380, "corte_bajo_alivio_chaqueta"),
    ("presion_max_chaqueta_control", 376, "corte_bajo_alivio_chaqueta"),
]
CASOS_EMPAQUE = [
    ("presion_empaque", 100, "empaque_chequeo_ciclo"),     # 60 <= 75
    ("presion_empaque", 120, "empaque_chequeo_ciclo"),
    ("vacio_empaque", 70, "vacio_bajo_atm"),               # 70 > 75 - 10
    ("vacio_empaque", 100, "vacio_bajo_atm"),
]
CINCO = set(cmm.CLAVES_LIMITES_PRESION)


@pytest.mark.parametrize("clave,valor,regla", CASOS_LIMITES)
def test_limites_codigo_y_detalle(cm, clave, valor, regla):
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(clave, valor, "ing")
    assert e.value.codigo == "incoherente_limites"
    d = e.value.detalle
    assert d["regla"] == regla and d["clave"] == clave
    assert set(d["vigentes"]) == CINCO and set(d["propuestos"]) == CINCO
    assert d["propuestos"][clave] == valor and d["vigentes"][clave] == cm.get(clave)
    assert d["margen_corte_bajo_alivio"] == 10.0


@pytest.mark.parametrize("clave,valor,regla", CASOS_EMPAQUE)
def test_empaque_codigo_y_detalle(cm, clave, valor, regla):
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(clave, valor, "tec")
    assert e.value.codigo == "incoherente_empaque"
    d = e.value.detalle
    assert d["regla"] == regla and d[clave] == valor
    assert d["presion_atmosferica"] == 75
    assert (d["margen_empaque_sobre_atm"], d["margen_vacio_bajo_atm"]) == (20.0, 10.0)


def test_empaque_sobre_atm(cm):
    cm.config["presion_atmosferica"]["value"] = 110.0      # calibrada alta
    cm.config["presion_empaque"]["value"] = 300
    with pytest.raises(ErrorParametro) as e:
        cm.fijar("presion_empaque", 125)                    # 125 < 110 + 20
    assert e.value.codigo == "incoherente_empaque"
    assert e.value.detalle["regla"] == "empaque_sobre_atm"


@pytest.mark.parametrize("clave,familia,codigo", [
    ("presion_atmosferica", "presion_empaque", "incoherente_empaque"),
    ("presion_alivio_camara", "presion_suministro_vapor", "incoherente_limites"),
])
def test_sin_referencia_falla_cerrado(cm, clave, familia, codigo):
    cm.config[clave]["value"] = None
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(familia, cm.get(familia) or 300)
    assert e.value.codigo == codigo and e.value.detalle["regla"] == "sin_referencia"


def test_valores_validos_no_cambian(cm):
    # mismas reglas: lo que antes se aceptaba se sigue aceptando
    assert cm.fijar("presion_suministro_vapor", 384)[1] == 384
    assert cm.fijar("presion_empaque", 126)[1] == 126
    assert cm.fijar("vacio_empaque", 65)[1] == 65
    assert cm.fijar("presion_max_chaqueta_control", 375)[1] == 375


def test_calibracion_atm_conserva_incoherente(api, monkeypatch):
    """La calibración atmosférica (pantalla y bitácora) sigue con 'incoherente'."""
    from unittest.mock import MagicMock
    m = sys.modules["autoclave.backend.rutas.mantenimiento"]
    cm = MagicMock()
    cm.fijar.side_effect = ErrorParametro("incoherente_empaque", detalle={"regla": "x"})
    cm.lock_cambios = MagicMock()
    ctx = MagicMock(); ctx.config_manager = cm
    monkeypatch.setattr(m, "context", ctx)
    with pytest.raises(ErrorParametro) as e:
        m._aplicar_presion_atmosferica(200.0, "tec")
    assert e.value.codigo == "incoherente"


# ── rango efectivo ─────────────────────────────────────────────────────────

ACOPLADOS = (*cmm.CLAVES_LIMITES_PRESION, *cmm.CLAVES_EMPAQUE)


def _acepta(cm, clave, v):
    e = cm.config[clave]
    nv, err = cm._validar(clave, e, v, permitir_solo_lectura=True)
    return not err and not cm._incoherencia(clave, nv)


@pytest.mark.parametrize("clave", ACOPLADOS)
def test_rango_efectivo_coincide_con_la_validacion(cm, clave):
    d = cm.describir(clave)
    lo, hi = d["min_efectivo"], d["max_efectivo"]
    assert lo is not None and hi is not None and d["min"] <= lo <= d["valor"] <= hi <= d["max"]
    paso = 1 if d["tipo"] == "int" else 0.01
    assert _acepta(cm, clave, lo) and _acepta(cm, clave, hi)
    if lo - paso >= d["min"]:
        assert not _acepta(cm, clave, round(lo - paso, 2))
    if hi + paso <= d["max"]:
        assert not _acepta(cm, clave, round(hi + paso, 2))
    if d["tipo"] == "int":                     # barrido completo: es un intervalo
        validos = [v for v in range(int(d["min"]), int(d["max"]) + 1) if _acepta(cm, clave, v)]
        assert (min(validos), max(validos)) == (lo, hi)
        assert validos == list(range(int(lo), int(hi) + 1))


def test_rango_efectivo_fabrica_esperado(cm):
    r = {c: (cm.describir(c)["min_efectivo"], cm.describir(c)["max_efectivo"]) for c in ACOPLADOS}
    assert r["presion_suministro_vapor"] == (100, 384)
    assert r["presion_alivio_camara"] == (351, 400)
    assert r["presion_alivio_chaqueta"] == (385, 400)
    assert r["presion_fondo_escala"] == (385, 1000)
    assert r["presion_max_chaqueta_control"] == (300, 375)
    assert r["presion_empaque"] == (126, 400)
    assert r["vacio_empaque"] == (0, 65)
    assert r["presion_atmosferica"] == (50.0, 110.0)          # 0,6·300 = 180: sin acotar


def test_rango_efectivo_sigue_al_vigente(cm):
    cm.fijar("presion_alivio_chaqueta", 395)
    assert cm.describir("presion_max_chaqueta_control")["max_efectivo"] == 385
    assert cm.describir("presion_suministro_vapor")["max_efectivo"] == 384


def test_sin_acople_rango_nominal(cm):
    d = cm.describir("timeout_puerta")
    assert (d["min_efectivo"], d["max_efectivo"]) == (d["min"], d["max"])


# ── API ────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, cabecera
    ctx.db.close()


def test_api_suministro_sobre_alivio_da_limites(api):
    client, srv, cab = api
    r = client.patch("/global_params/presion_suministro_vapor", json={"valor": 385},
                     headers=cab(srv, "ingeniero"))
    assert r.status_code == 422
    b = r.json()
    assert b["codigo"] == "incoherente_limites"
    assert b["detalle"]["regla"] == "suministro_bajo_alivio"
    assert b["detalle"]["propuestos"]["presion_suministro_vapor"] == 385
    assert "empaque" not in b["detail"].lower()


def test_api_empaque(api):
    client, srv, cab = api
    r = client.patch("/global_params/vacio_empaque", json={"valor": 70},
                     headers=cab(srv, "tecnico"))
    assert r.status_code == 422 and r.json()["codigo"] == "incoherente_empaque"
    assert r.json()["detalle"]["regla"] == "vacio_bajo_atm"


def test_api_system_params_publica_rango_efectivo(api):
    client, srv, cab = api
    ps = {p["clave"]: p for p in client.get("/system_params").json()["parametros"]}
    assert ps["presion_suministro_vapor"]["max_efectivo"] == 384
    assert all("min_efectivo" in p and "max_efectivo" in p for p in ps.values())


# ── cliente: texto por regla ───────────────────────────────────────────────

def _detalle_de(cm, clave, valor):
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(clave, valor)
    return e.value.codigo, {"codigo": e.value.codigo, "detalle": e.value.detalle}


@pytest.mark.parametrize("clave,valor,regla", CASOS_LIMITES + CASOS_EMPAQUE)
def test_controlador_texto_de_la_regla(cm, clave, valor, regla):
    from autoclave.ui_qml.controllers.parametros_equipo_controller import (
        _MENSAJES_REGLA, mensaje_rechazo)
    codigo, datos = _detalle_de(cm, clave, valor)
    texto, valores = mensaje_rechazo(codigo, datos)
    assert texto == _MENSAJES_REGLA[(codigo, regla)][0]
    for idioma in ("es", "en"):
        plantilla = _texto(idioma, texto)
        for marcador in valores:
            assert "{" + marcador + "}" in plantilla, (idioma, texto, marcador)
    if codigo == "incoherente_limites":
        assert "empaque" not in texto


def test_suministro_nunca_texto_de_empaque(cm):
    from autoclave.ui_qml.controllers.parametros_equipo_controller import mensaje_rechazo
    codigo, datos = _detalle_de(cm, "presion_suministro_vapor", 385)
    texto, valores = mensaje_rechazo(codigo, datos)
    assert texto == "opciones.equipo_err_suministro_bajo_alivio"
    assert valores == {"suministro": {"v": 385.0, "dif": False},
                       "alivio_camara": {"v": 385.0, "dif": False},
                       "alivio_chaqueta": {"v": 385.0, "dif": False}}
    # sin detalle (o detalle de otra versión): el general de límites, no el de empaque
    assert mensaje_rechazo("incoherente_limites", {})[0] == "opciones.equipo_err_limites"
    assert mensaje_rechazo("incoherente_limites",
                           {"detalle": {"regla": "otra"}})[0] == "opciones.equipo_err_limites"


def test_todas_las_reglas_tienen_texto_es_en():
    from autoclave.ui_qml.controllers.parametros_equipo_controller import _MENSAJES_REGLA
    pares = ([("incoherente_empaque", r) for r in cmm.REGLAS_EMPAQUE]
             + [("incoherente_limites", r) for r in cmm.REGLAS_LIMITES])
    assert set(_MENSAJES_REGLA) == set(pares)
    for par in pares:
        clave, marcadores = _MENSAJES_REGLA[par]
        for idioma in ("es", "en"):
            plantilla = _texto(idioma, clave)
            assert plantilla
            for m in marcadores:
                assert "{" + m + "}" in plantilla, (idioma, clave, m)


def test_controlador_flujo_guardar_rechazado():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.sesion_backend import Resultado
    from tests.test_f2_parametros_equipo_async import _ctrl
    c, s, resueltos = _ctrl()
    assert c.guardar("presion_suministro_vapor", 385) is True
    cuerpo = {"codigo": "incoherente_limites", "detail": "x",
              "detalle": {"regla": "suministro_bajo_alivio",
                          "propuestos": {"presion_suministro_vapor": 385,
                                         "presion_alivio_camara": 385,
                                         "presion_alivio_chaqueta": 390}}}
    s.responder("PATCH", "/global_params/presion_suministro_vapor",
                Resultado("incoherente_limites", cuerpo, 422))
    assert resueltos[-1] == ("param:presion_suministro_vapor", False,
                             "opciones.equipo_err_suministro_bajo_alivio")
    assert c.valoresMensaje["alivio_chaqueta"] == {"v": 390.0, "dif": False}
    c.limpiarMensaje()
    assert c.valoresMensaje == {}


# ── cobertura por AST de las causas de /global_params ──────────────────────

def _codigos_config_manager() -> set:
    arbol = ast.parse((_SRC / "core" / "managers" / "config_manager.py").read_text(encoding="utf-8"))
    constantes = {}
    for n in arbol.body:
        if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    constantes[t.id] = n.value.value
    codigos = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "ErrorParametro" and n.args:
            a = n.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                codigos.add(a.value)
        if isinstance(n, ast.FunctionDef) and n.name in ("_validar", "_incoherencia_detalle",
                                                          "_incoherencia_limites"):
            for r in ast.walk(n):
                if isinstance(r, ast.Return) and isinstance(r.value, ast.Tuple) and len(r.value.elts) == 2:
                    a, b = r.value.elts
                    for x in (a, b):
                        if isinstance(x, ast.Constant) and isinstance(x.value, str) and x.value:
                            codigos.add(x.value)
                        if isinstance(x, ast.Name) and x.id in constantes:
                            codigos.add(constantes[x.id])
    return codigos


def _codigos_rutas() -> set:
    fuente = (_SRC / "backend" / "rutas" / "sistema.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    codigos = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.FunctionDef) and n.name in ("_cambiar_parametro_sistema",
                                                          "_cambiar_serializado", "_parametro_o_404"):
            for c in ast.walk(n):
                if isinstance(c, ast.Call) and getattr(c.func, "id", None) in ("_rechazar", "RechazoApi"):
                    if len(c.args) >= 2 and isinstance(c.args[1], ast.Constant):
                        codigos.add(c.args[1].value)
    return codigos


def test_ast_encuentra_los_codigos():
    cm_codigos = _codigos_config_manager()
    assert {"solo_lectura", "tipo_invalido", "fuera_de_rango", "no_existe",
            "sin_base_de_datos", "incoherente_empaque", "incoherente_limites"} <= cm_codigos
    assert "incoherente" not in cm_codigos
    assert {"solo_lectura", "calibracion_en_curso", "no_existe"} <= _codigos_rutas()


def test_toda_causa_de_global_params_llega_y_tiene_texto():
    from autoclave.backend.rutas import sistema
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.controllers.parametros_equipo_controller import mensaje_de
    cm_codigos = _codigos_config_manager()
    # todo código del ConfigManager tiene estado y motivo en la ruta
    assert cm_codigos <= set(sistema._CODIGO_PARAMETRO)
    assert "incoherente" not in sistema._CODIGO_PARAMETRO
    # guard_estado (409) y requiere_rol (401/403) también responden aquí
    causas = cm_codigos | _codigos_rutas() | {"estado_no_permitido", "rol_sin_permiso",
                                              "sesion_invalida"}
    for ruta in ("/global_params/presion_suministro_vapor",
                 "/global_params/presion_suministro_vapor/reset"):
        conocidos = sesion_backend.codigos_conocidos(ruta)
        for causa in causas:
            assert causa in conocidos, (ruta, causa)
            assert sesion_backend.interpretar(422, {"codigo": causa}, ruta).causa == causa
    for causa in causas:
        clave = mensaje_de(causa)
        assert clave != "opciones.err_generico" or causa == "no_existe", causa
        for idioma in ("es", "en"):
            assert _texto(idioma, clave), (idioma, causa)


# ── pantalla: mensaje dentro de la ventana y rango efectivo ────────────────

_GUION = r"""
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, ".")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.bridge.unidades_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.sesion_backend import Resultado
from tests.test_o2a_parametros_equipo import _SesionUI
cuerpo = {"codigo": "incoherente_limites", "detail": "x",
          "detalle": {"regla": "suministro_bajo_alivio",
                      "propuestos": {"presion_suministro_vapor": 385, "presion_alivio_camara": 385,
                                     "presion_alivio_chaqueta": 386}}}
sesion = _SesionUI(Resultado("incoherente_limites", cuerpo, 422))
sesion_backend.ventana = lambda: sesion
qml_dir = sys.argv[1]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
c = QQmlComponent(e)
c.setData(('import QtQuick\nimport "Pantallas"\nItem { width: 1100; height: 1500; '
           'OpcionesParametrosEquipo { objectName: "p"; anchors.fill: parent; '
           'edicionPermitida: true; rol: "ingeniero"; estadoMaquina: "PREPARADO" } }').encode(),
          QUrl.fromLocalFile(qml_dir + "/prueba_a7.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
from PySide6.QtQuick import QQuickItem as _QI
p = raiz.findChild(_QI, "p")
ctrl = p.findChild(QObject, "parametrosEquipoController")
def buscar(item, nombre):
    if item.objectName() == nombre:
        return item
    for h in item.childItems():
        r = buscar(h, nombre)
        if r is not None:
            return r
    return None
ctrl.abrirGrupo("chaqueta"); app.processEvents()
ajuste = buscar(p, "ventanaAjusteEquipo")
ajuste.setProperty("param", ctrl.parametro("presion_suministro_vapor"))
ajuste.setProperty("abierto", True); app.processEvents()
rango = buscar(p, "rangoEfectivoEquipo")
r = {"rango_visible": rango.property("visible"), "rango": rango.property("text")}
ctrl.guardar("presion_suministro_vapor", 385); app.processEvents()
err = buscar(p, "errorIngresoEquipo")
r["error"] = err.property("text"); r["error_visible"] = err.property("visible")
r["dentro"] = buscar(ajuste, "errorIngresoEquipo") is not None
r["banda"] = buscar(p, "errorParametrosEquipo").childItems()[0].property("text")
print(json.dumps(r, ensure_ascii=True))
"""


def test_ventana_muestra_mensaje_y_rango_efectivo():
    pytest.importorskip("PySide6")
    r = subprocess.run([sys.executable, "-c", _GUION, str(_SRC / "ui_qml" / "qml")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=_RAIZ, timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["rango_visible"] is True and "384" in d["rango"] and "100" in d["rango"]
    assert d["dentro"] and d["error_visible"] is True
    assert "suministro de vapor" in d["error"] and "385" in d["error"] and "386" in d["error"]
    assert "empaque" not in d["error"].lower()
    assert "empaque" not in d["banda"].lower() and "suministro" in d["banda"]


def test_textos_del_mensaje_y_rango_sin_elide():
    """D8-5.4 (tests/test_v8b_textos.py): el error y el rango efectivo de la
    ventana ajustan con WordWrap, sin elide."""
    qml = (_SRC / "ui_qml" / "qml" / "Pantallas" / "OpcionesParametrosEquipo.qml").read_text(encoding="utf-8")
    for nombre in ("errorIngresoEquipo", "rangoEfectivoEquipo"):
        i = qml.index('objectName: "%s"' % nombre)
        bloque = qml[i:qml.index("\n                }", i)]
        assert "elide" not in bloque and "Text.WordWrap" in bloque, nombre
