"""T3 (tanda 2026-10-14 §1.1): GET /cycle/sensors, PUT /cycle/sensor-roles,
verificación de sensores al iniciar (RS-06) y F0 solo en laboratorio."""

import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.installation.equipment import EquipmentClass
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor

_FABRICA = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"}
_CON_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.side_effect = lambda f: f == "LISTO_PARA_CICLO"
    ctx.estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": None, "temp_ref": 24.0}
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.aplicar_roles_sensores.return_value = (False, "sin_copias")
    ctx.sin_base_de_datos = False
    ctx.profile = SimpleNamespace(equipment_class=EquipmentClass.PISO_LAB,
                                  temperature_probes=None)
    archivo = tmp_path / "prog.json"
    archivo.write_text(json.dumps({"cycle_id": "p", "cycle_number": 2,
                                   "cycle_temperature_sensors": {"1": "temp_camara"},
                                   "parameters": {"globals": {"F0": {"value": False, "type": "bool"}}}}),
                       encoding="utf-8")
    prog = Cycle("p", "Prog", {"globals": {"F0": {"value": False, "type": "bool"}}}, number=2)
    prog.source, prog._path = "user", str(archivo)
    fabrica = Cycle("f", "Fab", {}, number=1)
    fabrica.source = "factory"
    ctx.cycle_manager.cycles = {"p": prog, "f": fabrica}
    ctx.control_loop.cycle = prog
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx, srv, prog, archivo


def _put(client, srv, asignacion, anterior=_FABRICA, rol="tecnico", programa=2):
    return client.put("/cycle/sensor-roles", headers=cabecera(srv, rol),
                      json={"programa": programa, "asignacion": asignacion,
                            "asignacion_anterior_esperada": anterior})


# ── GET /cycle/sensors ───────────────────────────────────────────────────────

def test_get_lista_sensores_con_estado_y_rol(entorno):
    client, ctx, srv, prog, _ = entorno
    r = client.get("/cycle/sensors", params={"programa": 2})
    assert r.status_code == 200
    datos = r.json()
    por_id = {s["id"]: s for s in datos["sensores"]}
    assert por_id["temp_camara"] == {"id": "temp_camara", "nombre": "Cámara 1", "tipo": "camara",
                                     "estado": "disponible", "lectura": 25.0, "rol": "principal"}
    assert por_id["temp_2_camara"]["estado"] == "sin_senal"
    assert datos["errores"] == [] and datos["editable"] is True


def test_get_no_lista_sensor_no_instalado_sin_rol(entorno):
    client, ctx, srv, prog, _ = entorno
    ctx.profile.equipment_class = EquipmentClass.PISO
    ids = [s["id"] for s in client.get("/cycle/sensors", params={"programa": 2}).json()["sensores"]]
    assert ids == ["temp_camara", "temp_ref"]


def test_get_programa_inexistente_404(entorno):
    client, *_ = entorno
    assert client.get("/cycle/sensors", params={"programa": 9}).status_code == 404


# ── PUT /cycle/sensor-roles ─────────────────────────────────────────────────

def test_put_guarda_audita_y_escribe_atomico(entorno):
    client, ctx, srv, prog, archivo = entorno
    r = _put(client, srv, _CON_REF)
    assert r.status_code == 200
    assert prog.sensores == _CON_REF and prog.sensores_formato_antiguo is False
    assert json.loads(archivo.read_text(encoding="utf-8"))["cycle_temperature_sensors"] == _CON_REF
    [fila] = ctx.db.get_auditoria(evento="ROLES_SENSOR")
    assert fila["entidad"] == "p/cycle_temperature_sensors"
    assert json.loads(fila["valor_anterior"]) == _FABRICA
    assert json.loads(fila["valor_nuevo"]) == _CON_REF
    assert not archivo.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("asignacion", [
    {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"},
    {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "principal"},
    {"temp_camara": "principal", "temp_chaqueta": "referencia"},
    {"temp_camara": "jefe"},
])
def test_put_invalida_422_todo_o_nada(entorno, asignacion):
    client, ctx, srv, prog, archivo = entorno
    antes = archivo.read_text(encoding="utf-8")
    r = _put(client, srv, asignacion)
    assert r.status_code == 422 and r.json()["codigo"] == "ASIGNACION_INVALIDA"
    assert prog.sensores == _FABRICA and archivo.read_text(encoding="utf-8") == antes


def test_put_sensor_sin_senal_422(entorno):
    client, ctx, srv, prog, _ = entorno
    r = _put(client, srv, {"temp_camara": "principal", "temp_2_camara": "referencia",
                           "temp_ref": "no_en_uso"})
    assert r.status_code == 422 and r.json()["codigo"] == "SENSOR_NO_DISPONIBLE"
    assert prog.sensores == _FABRICA


def test_put_asignacion_desfasada_409(entorno):
    client, ctx, srv, prog, _ = entorno
    r = _put(client, srv, _CON_REF, anterior=_CON_REF)
    assert r.status_code == 409 and r.json()["codigo"] == "asignacion_desfasada"
    assert prog.sensores == _FABRICA


@pytest.mark.parametrize("rol", ["admin", "operador", "biomedico"])
def test_put_roles_no_permitidos_403(entorno, rol):
    client, ctx, srv, prog, _ = entorno
    assert _put(client, srv, _CON_REF, rol=rol).status_code == 403


def test_put_tecnico_en_ciclo_409_ingeniero_si(entorno):
    client, ctx, srv, prog, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert _put(client, srv, _CON_REF, rol="tecnico").status_code == 409
    assert _put(client, srv, _CON_REF, rol="ingeniero").status_code == 200


def test_put_programa_de_fabrica_409(entorno):
    client, ctx, srv, prog, _ = entorno
    r = _put(client, srv, _CON_REF, programa=1)
    assert r.status_code == 409 and r.json()["codigo"] == "programa_de_fabrica"


# ── RS-06: inicio de ciclo ──────────────────────────────────────────────────

def test_start_rechaza_sensor_en_uso_sin_lectura(entorno):
    client, ctx, srv, prog, _ = entorno
    prog.sensores = _CON_REF
    ctx.estado.sensores_temp["temp_ref"] = None
    r = client.post("/cycle/start")
    assert r.status_code == 409 and r.json()["codigo"] == "SENSOR_NO_DISPONIBLE"
    assert ("START_CICLO", True) not in [c.args for c in ctx.estado.set_flag.call_args_list]


def test_start_rechaza_asignacion_invalida(entorno):
    client, ctx, srv, prog, _ = entorno
    prog.sensores = {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso",
                     "temp_ref": "no_en_uso"}
    r = client.post("/cycle/start")
    assert r.status_code == 409 and r.json()["codigo"] == "ASIGNACION_SENSORES_INVALIDA"


def test_start_ignora_sensor_no_en_uso_sin_lectura(entorno):
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_temp["temp_ref"] = None
    assert client.post("/cycle/start").status_code == 200


# ── F0 solo en laboratorio ──────────────────────────────────────────────────

def _f0(client, srv, valor=True):
    return client.patch("/cycle/parameter", headers=cabecera(srv, "ingeniero"),
                        json={"cycle_id": "p", "fase": "globals", "path": ["F0"], "value": valor})


def test_f0_rechazado_en_equipo_no_lab(entorno):
    client, ctx, srv, prog, _ = entorno
    ctx.profile.equipment_class = EquipmentClass.PISO
    r = _f0(client, srv)
    assert r.status_code == 422 and r.json()["codigo"] == "f0_no_disponible"
    assert prog.get_param("globals", "F0") is False
    assert _f0(client, srv, False).status_code == 200      # desactivar siempre se permite


def test_f0_permitido_en_lab(entorno):
    client, ctx, srv, prog, _ = entorno
    assert _f0(client, srv).status_code == 200
    assert prog.get_param("globals", "F0") is True


def test_status_publica_el_principal(entorno):
    client, ctx, srv, prog, _ = entorno
    ctx.programa_para_sensores.return_value = SimpleNamespace(sensores=_CON_REF)
    principal = client.get("/status").json()["sensors"]["principal"]
    assert principal["sensor"] == "temp_camara" and principal["nombre"] == "Cámara 1"
    assert principal["referencias"] == [{"sensor": "temp_ref", "nombre": "Referencia",
                                         "valor": 24.0}]


def test_f0_rechazado_tambien_con_valor_no_booleano(entorno):
    client, ctx, srv, prog, _ = entorno
    ctx.profile.equipment_class = EquipmentClass.PISO
    r = client.patch("/cycle/parameter", headers=cabecera(srv, "ingeniero"),
                     json={"cycle_id": "p", "fase": "globals", "path": ["F0"], "value": 1})
    assert r.status_code == 422


def test_put_tecnico_revierte_si_el_ciclo_arranca_durante_la_escritura(entorno, monkeypatch):
    client, ctx, srv, prog, archivo = entorno
    estados = iter([GlobalState.PREPARADO, GlobalState.CICLO])
    ctx.estado.get_machine_state.side_effect = lambda: next(estados, GlobalState.CICLO)
    r = _put(client, srv, _CON_REF)
    assert r.status_code == 409
    assert prog.sensores == _FABRICA
    assert json.loads(archivo.read_text(encoding="utf-8"))["cycle_temperature_sensors"] == _FABRICA
