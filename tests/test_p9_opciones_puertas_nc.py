# tests/test_p9_opciones_puertas_nc.py
#
# P9 (tanda 9): D9-3 (equipos con puertas simples), D9-4 (refresco de
# Parámetros del equipo al guardar) y D9-5 (entradas NC interpretadas).

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.devices.puertas.door_type import DoorType

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"
FABRICA = json.loads((RAIZ / "config" / "global_params.json").read_text(encoding="utf-8"))


# ── D9-3: perfil ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tipo,esperado", [
    (DoorType.SIMPLE, True), (DoorType.ADVANCED, False), (DoorType.MOTORIZED, False),
    (DoorType.LOCKING, False), (DoorType.MOTORIZED_LOCKING, False)])
def test_puertas_simples_por_tipo(tipo, esperado):
    from autoclave.installation.profile import puertas_simples
    assert puertas_simples(SimpleNamespace(door_type=tipo)) is esperado


def test_sin_perfil_no_se_ocultan():
    from autoclave.installation.profile import puertas_simples
    assert puertas_simples(None) is False


# ── D9-3: grupos de Parámetros del equipo ───────────────────────────────────

def test_camara_segura_en_archivo_de_fabrica():
    assert FABRICA["temp_max_apertura"]["grupo"] == "camara_segura"
    assert FABRICA["rango_presion_atm"]["grupo"] == "camara_segura"
    assert FABRICA["timeout_puerta"]["grupo"] == "puerta"


def test_grupos_visibles_por_tipo_de_puerta():
    from autoclave.core.managers.config_manager import GRUPOS, grupos_visibles
    assert "camara_segura" in GRUPOS
    assert grupos_visibles(False) == list(GRUPOS)
    simples = grupos_visibles(True)
    assert "puerta" not in simples and "empaque" not in simples
    assert "camara_segura" in simples
    # todo parámetro del archivo de fábrica tiene un grupo conocido
    assert {e["grupo"] for e in FABRICA.values()} <= set(GRUPOS)


# ── D9-3: backend ───────────────────────────────────────────────────────────

_FINALIZACION = {
    "tiempo_espera_apertura": {"value": 60, "type": "int", "unit": "seg", "min": 0, "max": 3600},
    "temp_max_apertura": {"value": 80.0, "type": "float", "unit": "°C", "clase": "absoluto",
                          "min": 0, "max": 150},
    "timeout_temperatura": {"value": 30, "type": "int", "unit": "min", "min": 1, "max": 120},
    "apertura_automatica": {"value": False, "type": "bool", "unit": ""},
}


@pytest.fixture
def entorno(tmp_path):
    from fastapi.testclient import TestClient

    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.core.managers.cycle_manager import Cycle
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cargar_servidor
    db = DbManager(db_path=tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    ctx.sin_base_de_datos = False
    ctx.profile = SimpleNamespace(door_type=DoorType.SIMPLE, door_count=1)
    cm = ConfigManager(); cm.load_config()
    ctx.config_manager = cm
    parametros = {"finalizacion": json.loads(json.dumps(_FINALIZACION))}
    archivo = tmp_path / "prog.json"
    archivo.write_text(json.dumps({"cycle_id": "p", "cycle_number": 2, "parameters": parametros}),
                       encoding="utf-8")
    prog = Cycle("p", "Prog", parametros, number=2)
    prog.source, prog._path = "user", str(archivo)
    ctx.cycle_manager.cycles = {"p": prog}
    ctx.cycle_manager.defecto = lambda n: None
    ctx.control_loop.cycle = prog
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), ctx, srv, prog
    db.close()


def _apertura(client, srv, valor=True):
    from tests.backend_doble import cabecera
    return client.patch("/cycle/parameter", headers=cabecera(srv, "ingeniero"),
                        json={"cycle_id": "p", "fase": "finalizacion",
                              "path": ["apertura_automatica"], "value": valor})


def test_apertura_automatica_rechazada_con_puertas_simples(entorno):
    client, ctx, srv, prog = entorno
    r = _apertura(client, srv)
    assert r.status_code == 422 and r.json()["codigo"] == "apertura_automatica_no_disponible"
    assert prog.get_param("finalizacion", "apertura_automatica") is False
    assert _apertura(client, srv, False).status_code == 200     # desactivar siempre se permite


def test_apertura_automatica_permitida_con_puertas_automaticas(entorno):
    client, ctx, srv, prog = entorno
    ctx.profile.door_type = DoorType.ADVANCED
    assert _apertura(client, srv).status_code == 200
    assert prog.get_param("finalizacion", "apertura_automatica") is True


@pytest.mark.parametrize("tipo,visibles", [
    (DoorType.SIMPLE, ["temp_max_apertura", "timeout_temperatura"]),
    (DoorType.ADVANCED, ["tiempo_espera_apertura", "temp_max_apertura", "timeout_temperatura",
                         "apertura_automatica"])])
def test_seccion_finalizacion_por_tipo_de_puerta(entorno, tipo, visibles):
    client, ctx, srv, prog = entorno
    ctx.profile.door_type = tipo
    r = client.get("/programas/2/seccion/finalizacion")
    assert r.status_code == 200
    assert [p["clave"] for p in r.json()["parametros"]] == visibles


@pytest.mark.parametrize("tipo", [DoorType.SIMPLE, DoorType.ADVANCED])
def test_system_params_entrega_grupos_filtrados(entorno, tipo):
    client, ctx, srv, prog = entorno
    ctx.profile.door_type = tipo
    d = client.get("/system_params").json()
    simples = tipo == DoorType.SIMPLE
    assert ("puerta" in d["grupos"], "empaque" in d["grupos"]) == (not simples, not simples)
    assert "camara_segura" in d["grupos"]
    grupos_param = {p["grupo"] for p in d["parametros"]}
    assert grupos_param <= set(d["grupos"])
    claves = {p["clave"] for p in d["parametros"]}
    assert {"temp_max_apertura", "rango_presion_atm"} <= claves
    assert ("timeout_puerta" in claves) is (not simples)


# ── D9-3 / D9-4: controlador de Parámetros del equipo ───────────────────────

class _SesionUI:
    """Doble de sesion_backend: GET /system_params devuelve lo que diga
    `self.lista`/`self.grupos`; un PATCH cambia el valor en `self.lista`."""

    def __init__(self, simples=False):
        from autoclave.core.managers.config_manager import ConfigManager, grupos_visibles
        from autoclave.ui_qml.sesion_backend import Resultado
        self.R = Resultado
        c = ConfigManager(); c.load_config()
        self.grupos = grupos_visibles(simples)
        self.lista = [p for p in c.describir() if p["grupo"] in self.grupos]
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            datos = {"/system_params": {"parametros": self.lista, "grupos": self.grupos},
                     "/printer/config": {"habilitada": True},
                     "/units": {"temperatura": "C", "presion": "kPa"},
                     "/language": {"idioma": "es"}}.get(ruta, {})
            return self.R("ok", datos, 200)
        if metodo == "PATCH" and ruta.startswith("/global_params/"):
            clave = ruta.rsplit("/", 1)[-1]
            for p in self.lista:
                if p["clave"] == clave:
                    p["valor"] = cuerpo["valor"]
        return self.R("ok", {"ok": True}, 200)


def _ctrl(simples=False):
    import sys as _sys
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(_sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import ParametrosEquipoController

    class Perfil:
        serial_number, model_id = "S-1", "M-1"
    s = _SesionUI(simples)
    c = ParametrosEquipoController(sesion=s, perfil=lambda: Perfil())
    c.cargar()
    return c, s


@pytest.mark.parametrize("simples", [False, True])
def test_controlador_grupos_del_backend(simples):
    c, _ = _ctrl(simples)
    assert c.grupos[-1] == "maquina"
    assert ("puerta" in c.grupos) is (not simples)
    assert ("empaque" in c.grupos) is (not simples)
    assert "camara_segura" in c.grupos
    c.abrirGrupo("puerta")
    assert c.grupo == ("" if simples else "puerta")


def test_controlador_sin_grupos_en_respuesta_usa_todos():
    c, s = _ctrl()
    s.grupos = None
    c.cargar()
    from autoclave.core.managers.config_manager import GRUPOS
    assert c.grupos == list(GRUPOS) + ["maquina"]


def test_parametros_grupo_es_propiedad_que_cambia_al_guardar():
    c, s = _ctrl()
    avisos = []
    c.parametrosGrupoChanged.connect(lambda: avisos.append(1))
    c.abrirGrupo("camara_segura")
    assert [p["clave"] for p in c.parametrosGrupo] == ["temp_max_apertura", "rango_presion_atm"]
    n = len(avisos)
    assert c.guardar("temp_max_apertura", 75)
    assert len(avisos) > n
    assert next(p for p in c.parametrosGrupo if p["clave"] == "temp_max_apertura")["valor"] == 75


def test_textos_camara_segura_es_en():
    for lang in ("es", "en"):
        d = json.loads((RAIZ / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d["opciones"]["equipo_grupos"]["camara_segura"]
        assert d["opciones"]["equipo_grupos_desc"]["camara_segura"]
        assert d["opciones"]["err_apertura_puertas_simples"]
        assert d["io"]["ui"]["nivel_crudo"]


# ── D9-4: refresco en pantalla al guardar (QML) ─────────────────────────────

_GUION_REFRESCO = r"""
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, ".")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.bridge.unidades_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml import sesion_backend
from tests.test_p9_opciones_puertas_nc import _SesionUI
qml_dir, simples = sys.argv[1], sys.argv[2] == "1"
sesion = _SesionUI(simples)
sesion_backend.ventana = lambda: sesion
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(('import QtQuick\nimport "Pantallas"\nItem { width: 1100; height: 1500; '
           'OpcionesParametrosEquipo { objectName: "p"; anchors.fill: parent; '
           'edicionPermitida: true; rol: "ingeniero"; estadoMaquina: "PREPARADO" } }').encode(),
          QUrl.fromLocalFile(qml_dir + "/prueba_p9.qml"))
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
r = {"tarjetas": sorted(g for g in ["puerta", "camara_segura", "impresion", "drenaje", "empaque",
                                     "chaqueta", "sistema", "maquina"]
                        if buscar(p, "tarjeta_" + g) is not None)}
ctrl.abrirGrupo("camara_segura"); app.processEvents()
fila = buscar(p, "paramEquipo_temp_max_apertura")
r["antes"] = fila.property("valor")
ctrl.guardar("temp_max_apertura", 75); app.processEvents()
fila = buscar(p, "paramEquipo_temp_max_apertura")
r["despues"] = fila.property("valor")
r["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
print(json.dumps(r))
"""


def _correr_guion(guion, *args):
    import os
    import subprocess
    import sys as _sys
    pytest.importorskip("PySide6")
    raiz = Path(__file__).resolve().parents[1]
    r = subprocess.run([_sys.executable, "-c", guion, str(RAIZ / "ui_qml" / "qml"), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=raiz, timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
                                                  "PYTHONPATH": str(raiz / "src") + os.pathsep
                                                  + str(raiz)})
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("simples", [False, True])
def test_pantalla_equipo_tarjetas_y_refresco_al_guardar(simples):
    d = _correr_guion(_GUION_REFRESCO, "1" if simples else "0")
    esperadas = {"camara_segura", "impresion", "drenaje", "chaqueta", "sistema", "maquina"}
    if not simples:
        esperadas |= {"puerta", "empaque"}
    assert set(d["tarjetas"]) == esperadas
    assert d["antes"].startswith("80") and d["despues"].startswith("75")
    assert d["avisos"] == []


# ── D9-5: entradas NC ───────────────────────────────────────────────────────

def test_yaml_declara_nc_por_entrada():
    from autoclave.core.runtime import io_names
    nc = io_names.leer_nc()
    io = io_names.leer_io_enabled()
    assert set(nc) == set(io["DI"])            # cada DI del máximo físico declara nc
    assert {n for n, v in nc.items() if v} == {"paro_emergencia", "atrapamiento_puerta_1",
                                               "atrapamiento_puerta_2"}


def test_sin_seccion_nc_rige_la_del_codigo(tmp_path):
    from autoclave.core.runtime import io_names
    (tmp_path / "instances").mkdir()
    (tmp_path / "active_instances.yaml").write_text("active_instance: X\n", encoding="utf-8")
    (tmp_path / "instances" / "X.yaml").write_text(
        "io_enabled:\n  DI: [paro_emergencia, aire_comprimido]\n", encoding="utf-8")
    nc = io_names.leer_nc(tmp_path)
    assert nc["paro_emergencia"] is True and nc["aire_comprimido"] is False


def test_canales_di_traen_nc():
    from autoclave.core.runtime import io_names
    canales = {c["name"]: c for c in io_names.canales_digitales("DI")}
    assert canales["paro_emergencia"]["nc"] is True
    assert canales["aire_comprimido"]["nc"] is False


def test_atrapamiento_solo_con_puertas_con_atrapamiento():
    from autoclave.core.runtime import io_names
    from autoclave.installation.profile import InstallationProfile  # noqa: F401
    io = io_names._leer_yaml(None)
    simples = io_names.filtrar_por_perfil(io, _perfil(DoorType.SIMPLE))
    avanzadas = io_names.filtrar_por_perfil(io, _perfil(DoorType.ADVANCED))
    assert not any(n.startswith("atrapamiento") for n in simples["DI"])
    assert "atrapamiento_puerta_1" in avanzadas["DI"]


def _perfil(tipo):
    from autoclave.installation import profile as pf
    perfil = object.__new__(pf.InstallationProfile)
    for campo, valor in {"door_type": tipo, "door_count": 2, "supply_inputs": None,
                         "temperature_probes": None, "vapor_source": None}.items():
        object.__setattr__(perfil, campo, valor)
    return perfil


def _status(di):
    return {"estado_tarjeta": "ok", "card_connected": True,
            "sensors": {"digital_inputs": di}}


@pytest.mark.parametrize("crudo,activo", [(1, False), (0, True), (None, None)])
def test_entrada_nc_interpretada(crudo, activo):
    from autoclave.ui_qml.domain.entradas_salidas import presentar_entradas
    canales = [{"name": "paro_emergencia", "i18n": "io.di.paro_emergencia", "id": "DI 11",
                "estado_key": "paro_emergencia", "nc": True}]
    e = presentar_entradas(canales, _status({"paro_emergencia": crudo}))[0]
    assert e["nc"] is True and e["activo"] is activo
    assert e["nivel"] == (None if crudo is None else bool(crudo))


def test_entrada_nc_sin_enlace_queda_sin_datos():
    from autoclave.ui_qml.domain.entradas_salidas import presentar_entradas
    canales = [{"name": "paro_emergencia", "i18n": "x", "id": "DI 11",
                "estado_key": "paro_emergencia", "nc": True}]
    e = presentar_entradas(canales, {"estado_tarjeta": "sin_enlace"})[0]
    assert e["activo"] is None and e["nivel"] is None


@pytest.mark.parametrize("crudo,activo", [(1, True), (0, False), (None, None)])
def test_entrada_no_nc_sigue_cruda(crudo, activo):
    from autoclave.ui_qml.domain.entradas_salidas import presentar_entradas
    canales = [{"name": "aire_comprimido", "i18n": "x", "id": "DI 01",
                "estado_key": "aire_comprimido", "nc": False}]
    e = presentar_entradas(canales, _status({"aire_comprimido": crudo}))[0]
    assert e["nc"] is False and e["activo"] is activo


# ── D9-4: Parámetros del ciclo también refresca al guardar (QML) ────────────

def test_pantalla_ciclo_refresca_al_guardar():
    from tests.test_v8a_parametros_ciclo_qml import _correr, _p
    antes = {"editable": True, "parametros": [
        _p("timeout_temperatura", "int", 30, 30, mn=1, mx=120)]}
    despues = {"editable": True, "parametros": [
        _p("timeout_temperatura", "int", 45, 30, mn=1, mx=120)]}
    pasos = (
        "control.abrirSeccion('finalizacion'); vista.setProperty('vista', 'seccion')\n"
        "app.processEvents()\n"
        "r['antes'] = hijo('param_timeout_temperatura').property('valor')\n"
        "cfg['rutas']['GET /programas/4/seccion/finalizacion'] = [200, json.loads(%r)]\n"
        "r['ok'] = control.guardar('timeout_temperatura', 45)\n"
        "app.processEvents()\n"
        "r['despues'] = hijo('param_timeout_temperatura').property('valor')\n"
    ) % json.dumps(despues)
    res = _correr(pasos, {"GET /programas/4/seccion/finalizacion": [200, antes],
                          "PATCH /cycle/parameter": [200, {"ok": True, "value": 45}]})
    assert res["ok"] is True
    assert res["antes"].startswith("30") and res["despues"].startswith("45")
