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
    ctx.control_loop.programa_en_ejecucion.return_value = _Ciclo()   # copia de T-17
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "CALENTAMIENTO"
    ctx.cycle_logger.ciclo_id_pantalla = None
    ctx.cycle_logger.transcurrido_s.return_value = None

    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
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
    assert body["resultado"] is None
    assert body["transcurrido_s"] == 710.0
    assert [(f["fase"], f["estado"]) for f in body["fases"]] == [
        ("vacio", "completada"), ("calentamiento", "activa"),
        ("esterilizacion", "pendiente"), ("descompresion", "pendiente"),
        ("secado", "pendiente")]
    assert body["fases"][0]["duracion_s"] == 650.0
    assert body["fases"][1]["duracion_s"] == 60.0
    assert body["restante_s"] == (180.0 - 60.0) + 420.0 + 120.0 + 900.0
    # LLF A-2: fracción de llenado y referencia por fase
    assert [f["fraccion"] for f in body["fases"]] == [1.0, 0.3333, 0.0, 0.0, 0.0]
    assert [f["referencia_s"] for f in body["fases"]] == [600.0, 180.0, 420.0, 120.0, 900.0]


@pytest.mark.req("REQ-36")
def test_progreso_esterilizacion_usa_el_total_de_exposicion(entorno):
    client, ctx, db = entorno
    _crear_ciclo(db, "COMPLETADO", [("PRE_VACIO", 600.0), ("CALENTAMIENTO", 180.0),
                                    ("ESTERILIZACION", 500.0), ("DESCOMPRESION", 120.0),
                                    ("SECADO", 900.0)])
    cid = _crear_ciclo(db, None, [("PRE_VACIO", 650.0), ("CALENTAMIENTO", 60.0),
                                  ("ESTERILIZACION", None)])
    ctx.estado.fase_ciclo = "ESTERILIZACION"
    ctx.estado.exposicion_total_s = 420.0
    ctx.estado.exposicion_restante_s = 320.0
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 810.0
    body = client.get("/cycle/current/progress").json()
    ester = body["fases"][2]
    assert ester["estado"] == "activa"
    assert ester["fraccion"] == 0.2381          # 1 - 320/420
    assert ester["referencia_s"] == 420.0       # el total de la fase, no el historial (500)
    assert body["restante_s"] == 320.0 + 120.0 + 900.0
    # un total no numérico se descarta: fracción 0 y referencia del historial
    ctx.estado.exposicion_total_s = True
    body = client.get("/cycle/current/progress").json()
    assert body["fases"][2]["fraccion"] == 0.0
    assert body["fases"][2]["referencia_s"] == 500.0
    assert body["restante_s"] == 320.0 + 120.0 + 900.0


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
    # Tanda 17 (SON-01, decisión de Cristian): también temp_2_camara (la sonda instalada)
    assert set(primera) == {"id", "t_s", "fase", "fase_ui", "temp_camara", "temp_ref", "pres_camara",
                            "temp_2_camara"}
    assert primera["fase_ui"] == "vacio"     # la UI no traduce fases (plan §5.3)
    assert primera["temp_ref"] == 79.0

    desde = todo["lecturas"][1]["id"]
    nuevo = client.get(f"/cycle/current/graph?desde_id={desde}").json()
    assert [l["t_s"] for l in nuevo["lecturas"]] == [2.0, 3.0]


@pytest.mark.req("REQ-36")
def test_progreso_estado_mock_sin_total_no_falla_y_fraccion_cero(entorno):
    """context.estado es un MagicMock real: exposicion_total_s/restante_s son MagicMock
    (no numéricos); el endpoint no falla y la esterilización activa queda en 0.0."""
    client, ctx, db = entorno
    _crear_ciclo(db, "COMPLETADO", [("PRE_VACIO", 600.0), ("CALENTAMIENTO", 180.0),
                                    ("ESTERILIZACION", 420.0), ("DESCOMPRESION", 120.0),
                                    ("SECADO", 900.0)])
    cid = _crear_ciclo(db, None, [("PRE_VACIO", 650.0), ("CALENTAMIENTO", 60.0),
                                  ("ESTERILIZACION", None)])
    ctx.estado.fase_ciclo = "ESTERILIZACION"
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 810.0
    assert isinstance(ctx.estado.exposicion_total_s, MagicMock)
    resp = client.get("/cycle/current/progress")
    assert resp.status_code == 200
    ester = next(f for f in resp.json()["fases"] if f["fase"] == "esterilizacion")
    assert ester["estado"] == "activa"
    assert ester["fraccion"] == 0.0
