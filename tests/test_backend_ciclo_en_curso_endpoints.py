# tests/test_backend_ciclo_en_curso_endpoints.py
#
# GET /cycle/current/progress y GET /cycle/current/graph
# (planeacion_pantalla_ciclo_en_curso.md §6 B1/B2).

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState


class _Ciclo:
    id = "instrumental_134"
    name = "Instrumental 134"

    def get_param(self, seccion, nombre, default=None):
        return {
            ("prevacio", "conteo_pulso_a"): 4,
            ("secado", "tiempo_secado"): 15.0,
        }.get((seccion, nombre), default)


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(tmp_path / "a.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.cap = SimpleNamespace(has_vacuum=True)
    ctx.cycle_manager.get_selected_cycle.return_value = _Ciclo()
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "CALENTAMIENTO"
    ctx.cycle_logger.ciclo_id_pantalla = None
    ctx.cycle_logger.transcurrido_s.return_value = None

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    yield TestClient(srv.app), ctx, db
    db.close()


def _crear_ciclo(db, resultado=None, fases=()):
    cid = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo="instrumental_134",
                         nombre="x", temp_ester=134, tiempo_ester=7,
                         modelo="", serie="", version_sw="")
    t = 0.0
    for fase, d in fases:
        db.abrir_fase(cid, fase, t)
        if d is not None:
            t += d
            db.cerrar_fase_abierta(cid, t)
    if resultado:
        db.cerrar_ciclo(cid, resultado)
    return cid


# ── progreso ────────────────────────────────────────────────────────────

def test_progreso_sin_ciclo(entorno):
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    assert client.get("/cycle/current/progress").json() == {"activo": False}


def test_progreso_en_ciclo_sin_registro_de_logger(entorno):
    client, _, _ = entorno
    assert client.get("/cycle/current/progress").json() == {"activo": False}


def test_progreso_con_ciclo_y_referencia(entorno):
    client, ctx, db = entorno
    _crear_ciclo(db, "COMPLETADO", [("PRE_VACIO", 600.0), ("CALENTAMIENTO", 180.0),
                                    ("ESTERILIZACION", 420.0), ("DESCOMPRESION", 120.0),
                                    ("SECADO", 900.0)])
    cid = _crear_ciclo(db, None, [("PRECALENTAMIENTO", 0.0), ("PRE_VACIO", 650.0),
                                  ("CALENTAMIENTO", None)])
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 710.0

    body = client.get("/cycle/current/progress").json()
    assert body["activo"] is True
    assert body["ciclo_db_id"] == cid
    assert body["fase_ciclo"] == "CALENTAMIENTO"
    assert body["fase_activa"] == "calentamiento"
    assert body["transcurrido_s"] == 710.0
    assert [(f["fase"], f["estado"]) for f in body["fases"]] == [
        ("vacio", "completada"), ("calentamiento", "activa"),
        ("esterilizacion", "pendiente"), ("descompresion", "pendiente"),
        ("secado", "pendiente")]
    assert body["fases"][0]["duracion_s"] == 650.0
    assert body["fases"][1]["duracion_s"] == 60.0
    assert body["restante_s"] == (180.0 - 60.0) + 420.0 + 120.0 + 900.0


def test_progreso_sin_ciclo_de_referencia_restante_nulo(entorno):
    client, ctx, db = entorno
    cid = _crear_ciclo(db, None, [("PRE_VACIO", None)])
    ctx.estado.fase_ciclo = "PRE_VACIO"
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 5.0
    body = client.get("/cycle/current/progress").json()
    assert body["activo"] is True
    assert body["restante_s"] is None


# ── gráfica ─────────────────────────────────────────────────────────────

def test_grafica_sin_ciclo(entorno):
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    assert client.get("/cycle/current/graph").json() == {"ciclo_db_id": None, "lecturas": []}


def test_grafica_completa_e_incremental(entorno):
    client, ctx, db = entorno
    cid = _crear_ciclo(db)
    for t in range(4):
        db.insertar_lectura_grafica(cid, float(t), "PRE_VACIO", 80.0 + t, 79.0, 101.3)
    ctx.cycle_logger.ciclo_id_pantalla = cid

    todo = client.get("/cycle/current/graph").json()
    assert todo["ciclo_db_id"] == cid
    assert [l["t_s"] for l in todo["lecturas"]] == [0.0, 1.0, 2.0, 3.0]
    primera = todo["lecturas"][0]
    assert set(primera) == {"id", "t_s", "fase", "fase_ui", "temp_camara", "temp_ref", "pres_camara"}
    assert primera["fase_ui"] == "vacio"     # la UI no traduce fases (plan §5.3)
    assert primera["temp_ref"] == 79.0

    desde = todo["lecturas"][1]["id"]
    nuevo = client.get(f"/cycle/current/graph?desde_id={desde}").json()
    assert [l["t_s"] for l in nuevo["lecturas"]] == [2.0, 3.0]
