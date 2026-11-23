"""Modo fábrica, Etapa 1 (DF-03, DF-04): el backend lee el estado al abrir la
base, lo publica en `/status.modo_fabrica` y ofrece la dependencia
`requiere_modo_fabrica` (409 `solo_modo_fabrica` en ENTREGADO para todos los
roles; en FÁBRICA, solo ingeniero)."""
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend

pytestmark = pytest.mark.req("DF-03", "DF-04", "FAB-01")


# ── contexto ──────────────────────────────────────────────────────────────────

def _contexto(monkeypatch, base):
    from autoclave.backend import context as ctx_mod
    monkeypatch.setattr(ctx_mod, "DbManager", lambda: base)
    monkeypatch.setattr(ctx_mod, "SensorCalibrationAuditDB", MagicMock())
    return ctx_mod.BackendContext()


def test_el_contexto_lee_fabrica_al_abrir_la_base(monkeypatch):
    base = MagicMock()
    base.estado_fabrica.return_value = "FABRICA"
    ctx = _contexto(monkeypatch, base)
    assert ctx.modo_fabrica() is False          # antes de abrir la base
    assert ctx.abrir_base_datos(1) is None
    assert ctx.modo_fabrica() is True


@pytest.mark.parametrize("valor", ["ENTREGADO", "RARO", None])
def test_el_contexto_sin_fabrica(monkeypatch, valor):
    base = MagicMock()
    base.estado_fabrica.return_value = valor
    ctx = _contexto(monkeypatch, base)
    ctx.abrir_base_datos(1)
    assert ctx.modo_fabrica() is False


def test_el_contexto_con_error_de_lectura_da_entregado(monkeypatch):
    base = MagicMock()
    base.estado_fabrica.side_effect = RuntimeError("bd")
    ctx = _contexto(monkeypatch, base)
    ctx.abrir_base_datos(1)
    assert ctx.modo_fabrica() is False


def test_el_contexto_con_una_base_sin_el_metodo(monkeypatch):
    class Base:
        instalacion_en_curso = None
    ctx = _contexto(monkeypatch, Base())
    assert ctx.abrir_base_datos(1) is None
    assert ctx.modo_fabrica() is False


def test_sin_base_no_hay_modo_fabrica(monkeypatch):
    base = MagicMock()
    base.estado_fabrica.return_value = "FABRICA"
    ctx = _contexto(monkeypatch, base)
    ctx.abrir_base_datos(1)
    ctx.sin_base_de_datos = True                # p. ej. falla en caliente
    assert ctx.modo_fabrica() is False


def test_releer_con_base_real(monkeypatch, tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(tmp_path / "a.db")
    try:
        ctx = _contexto(monkeypatch, db)
        ctx.db = db
        assert ctx.releer_estado_fabrica() == "ENTREGADO"
        db.entrar_modo_fabrica_e_instalar(primera_instalacion=True, entidad="SN1", detalle={})
        assert ctx.releer_estado_fabrica() == "FABRICA" and ctx.modo_fabrica() is True
    finally:
        db.close()


# ── /status ───────────────────────────────────────────────────────────────────

def _stub(ctx):
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}
    ctx.alarm_manager.activas.return_value = []
    ctx.alarm_manager.eventos_recientes.return_value = []


@pytest.mark.parametrize("consulta, esperado", [
    (lambda: True, True),
    (lambda: False, False),
    (lambda: "FABRICA", False),                 # solo True estricto
    (MagicMock(side_effect=RuntimeError("x")), False),
])
def test_status_publica_modo_fabrica(consulta, esperado):
    srv, ctx = cargar_servidor()
    _stub(ctx)
    ctx.modo_fabrica = consulta
    cuerpo = TestClient(srv.app).get("/status").json()
    assert cuerpo["modo_fabrica"] is esperado


def test_status_con_contexto_sin_el_metodo_es_false():
    srv, ctx = cargar_servidor()
    _stub(ctx)
    ctx.modo_fabrica = None
    assert TestClient(srv.app).get("/status").json()["modo_fabrica"] is False


# ── dependencia requiere_modo_fabrica ────────────────────────────────────────

def _app_prueba(srv):
    """Ruta local de la prueba (no se registra en la app real: la base de
    rutas de la tanda 15 no cambia)."""
    dep = modulo_backend("dependencias")
    app = FastAPI()
    app.add_exception_handler(dep.RechazoApi, srv.app.exception_handlers[dep.RechazoApi])

    @app.post("/prueba/fabrica")
    def ruta(sesion=Depends(dep.requiere_modo_fabrica())):
        return {"usuario": sesion.usuario}
    return TestClient(app)


@pytest.mark.parametrize("rol", ["operador", "tecnico", "admin", "ingeniero"])
def test_en_entregado_409_para_todos_los_roles(rol):
    srv, ctx = cargar_servidor()
    ctx.modo_fabrica = lambda: False
    cliente = _app_prueba(srv)
    r = cliente.post("/prueba/fabrica", headers=cabecera(srv, rol))
    assert r.status_code == 409
    assert r.json()["codigo"] == "solo_modo_fabrica"


def test_en_entregado_409_tambien_sin_sesion():
    srv, ctx = cargar_servidor()
    ctx.modo_fabrica = lambda: False
    r = _app_prueba(srv).post("/prueba/fabrica")
    assert r.status_code == 409 and r.json()["codigo"] == "solo_modo_fabrica"


def test_si_no_se_sabe_el_estado_409():
    srv, ctx = cargar_servidor()
    ctx.modo_fabrica = MagicMock(side_effect=RuntimeError("x"))
    r = _app_prueba(srv).post("/prueba/fabrica", headers=cabecera(srv, "ingeniero"))
    assert r.status_code == 409 and r.json()["codigo"] == "solo_modo_fabrica"


def test_en_fabrica_ingeniero_pasa():
    srv, ctx = cargar_servidor()
    ctx.modo_fabrica = lambda: True
    r = _app_prueba(srv).post("/prueba/fabrica", headers=cabecera(srv, "ingeniero", "ing1"))
    assert r.status_code == 200 and r.json() == {"usuario": "ing1"}


@pytest.mark.parametrize("rol", ["operador", "tecnico", "admin"])
def test_en_fabrica_otros_roles_403(rol):
    srv, ctx = cargar_servidor()
    ctx.modo_fabrica = lambda: True
    r = _app_prueba(srv).post("/prueba/fabrica", headers=cabecera(srv, rol))
    assert r.status_code == 403 and r.json()["codigo"] == "rol_sin_permiso"


def test_en_fabrica_sin_sesion_401():
    srv, ctx = cargar_servidor()
    ctx.modo_fabrica = lambda: True
    assert _app_prueba(srv).post("/prueba/fabrica").status_code == 401
