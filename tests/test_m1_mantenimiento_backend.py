"""M1 (tanda 3): servicio y endpoints de mantenimiento (permisos, registro,
alarma no bloqueante, reloj anterior a la instalación)."""

import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.servicio_mantenimiento import (
    ErrorMantenimiento, ServicioMantenimiento)
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.alarms.catalogo import CATALOGO, MANTENIMIENTO_VENCIDO
from tests.helpers.backend_doble import cabecera, cargar_servidor

INST = datetime(2026, 10, 26, 9, 0)


@pytest.fixture
def servicio(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    hoy = {"d": date(2026, 10, 27)}
    alarmas = MagicMock()
    contador = ContadorCiclos(tmp_path / "ciclo_contador.json")
    s = ServicioMantenimiento(tmp_path / "mantenimiento.json", db, INST, contador, alarmas,
                              hoy=lambda: hoy["d"])
    return s, db, hoy, alarmas, contador


def test_valores_por_defecto_definitivos(servicio):
    s, *_ = servicio
    assert s.configuracion() == {"intervalo_dias": 365, "intervalo_ciclos": 1000}
    assert s.estado().proximo_fecha == date(2027, 10, 26)


def test_configuracion_se_guarda_y_valida(servicio):
    s, *_ = servicio
    assert s.guardar_configuracion(90, 500) == {"intervalo_dias": 90, "intervalo_ciclos": 500}
    assert s.configuracion()["intervalo_dias"] == 90
    with pytest.raises(ErrorMantenimiento):
        s.guardar_configuracion(-1, 0)
    with pytest.raises(ErrorMantenimiento):
        s.guardar_configuracion(180, 2_000_000)


def test_configuracion_corrupta_vuelve_a_los_valores_por_defecto(servicio, tmp_path):
    s, *_ = servicio
    (tmp_path / "mantenimiento.json").write_text('{"intervalo_dias": ', encoding="utf-8")
    assert s.configuracion() == {"intervalo_dias": 365, "intervalo_ciclos": 1000}
    (tmp_path / "mantenimiento.json").write_text(
        json.dumps({"intervalo_dias": "x", "intervalo_ciclos": 0}), encoding="utf-8")
    assert s.configuracion()["intervalo_dias"] == 365


def test_registrar_cambia_la_base_del_calculo_y_guarda_los_ciclos(servicio):
    s, db, hoy, alarmas, contador = servicio
    for _ in range(7):
        contador.siguiente()
    hoy["d"] = date(2027, 11, 1)
    assert s.estado().vencido                      # pasó el 26-oct-2027
    r = s.registrar("tec", "preventivo", "cambio de empaques")
    assert r["fecha"] == "2027-11-01" and r["ciclos"] == 7
    e = s.estado()
    assert not e.vencido and e.proximo_fecha == date(2028, 10, 31)
    assert e.ultimo_fecha == date(2027, 11, 1) and e.ultimo_tipo == "preventivo"
    assert db.listar_mantenimientos()[0]["observaciones"] == "cambio de empaques"


def test_ciclos_restantes_desde_el_ultimo_registro(servicio):
    s, db, hoy, alarmas, contador = servicio
    s.guardar_configuracion(180, 100)
    for _ in range(30):
        contador.siguiente()
    s.registrar("tec", "preventivo", "")
    for _ in range(25):
        contador.siguiente()
    assert s.estado().ciclos_restantes == 75


def test_tipo_y_observaciones_validados(servicio):
    s, *_ = servicio
    with pytest.raises(ErrorMantenimiento):
        s.registrar("tec", "inventado", "")
    with pytest.raises(ErrorMantenimiento):
        s.registrar("tec", "correctivo", "x" * 501)


def test_reloj_anterior_a_la_instalacion_no_registra_ni_calcula(servicio):
    s, db, hoy, alarmas, _ = servicio
    hoy["d"] = date(2026, 1, 1)
    assert s.estado().estado == "sin_dato" and s.resumen()["proximo_fecha"] is None
    with pytest.raises(ErrorMantenimiento) as e:
        s.registrar("tec", "correctivo", "")
    assert e.value.codigo == "reloj_invalido"
    assert db.listar_mantenimientos() == []


def test_vencido_activa_el_aviso_y_registrar_lo_resuelve(servicio):
    s, db, hoy, alarmas, _ = servicio
    assert s.evaluar_alarma() is False
    alarmas.activar.assert_not_called()
    hoy["d"] = date(2027, 11, 1)
    assert s.evaluar_alarma() is True
    args = alarmas.activar.call_args
    assert args.args[0] == MANTENIMIENTO_VENCIDO and "vencido" in args.kwargs["motivo"].lower()
    s.registrar("tec", "preventivo", "")
    alarmas.resolver.assert_called_with(MANTENIMIENTO_VENCIDO)


def test_el_aviso_es_no_bloqueante_y_de_baja_prioridad():
    d = CATALOGO[MANTENIMIENTO_VENCIDO]
    assert d.bloquea_inicio is False and d.nivel.nombre_compat == "ALERTA"


def test_sin_base_de_datos_calcula_desde_la_instalacion(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    s = ServicioMantenimiento(tmp_path / "m.json", BdNoDisponible(), INST, None, None,
                              hoy=lambda: date(2026, 10, 27))
    assert s.estado().proximo_fecha == date(2027, 10, 26)


def test_la_tabla_es_de_solo_anexar(servicio):
    import sqlite3
    s, db, *_ = servicio
    s.registrar("tec", "correctivo", "")
    with pytest.raises(sqlite3.DatabaseError):
        db._conn.execute("DELETE FROM mantenimientos")
    with pytest.raises(sqlite3.DatabaseError):
        db._conn.execute("UPDATE mantenimientos SET tipo='x'")


# ── endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def api(servicio):
    s, db, hoy, alarmas, _ = servicio
    ctx = MagicMock()
    ctx.db = db
    ctx.mantenimiento = s
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), srv, ctx, s


def test_get_es_abierto_y_devuelve_el_resumen(api):
    client, srv, ctx, s = api
    r = client.get("/maintenance")
    assert r.status_code == 200
    d = r.json()
    assert d["proximo_fecha"] == "2027-10-26" and d["configuracion"]["intervalo_dias"] == 365


@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("put", "/maintenance/config", {"intervalo_dias": 90, "intervalo_ciclos": 0}),
    ("post", "/maintenance/records", {"tipo": "preventivo"}),
    ("get", "/maintenance/records", None)])
def test_permisos_sin_sesion_y_con_rol_insuficiente(api, metodo, ruta, cuerpo):
    client, srv, *_ = api
    f = getattr(client, metodo)
    kw = {"json": cuerpo} if cuerpo is not None else {}
    assert f(ruta, **kw).status_code == 401
    assert f(ruta, headers=cabecera(srv, "operador"), **kw).status_code == 403
    assert f(ruta, headers=cabecera(srv, "tecnico"), **kw).status_code == 200
    assert f(ruta, headers=cabecera(srv, "ingeniero"), **kw).status_code == 200


def test_registrar_audita_y_se_ve_en_el_historial(api):
    client, srv, ctx, s = api
    r = client.post("/maintenance/records", headers=cabecera(srv, "tecnico"),
                    json={"tipo": "preventivo", "observaciones": "ok"})
    assert r.status_code == 200 and r.json()["registro"]["tipo"] == "preventivo"
    eventos = [c.args[0] for c in ctx.db.registrar_auditoria.call_args_list] \
        if isinstance(ctx.db.registrar_auditoria, MagicMock) else []
    filas = client.get("/maintenance/records", headers=cabecera(srv, "tecnico")).json()["registros"]
    assert filas[0]["usuario"] and filas[0]["observaciones"] == "ok"
    assert any(f["evento"] == "mantenimiento_registrado" for f in ctx.db.get_auditoria(limite=20))


def test_configurar_audita_y_valida(api):
    client, srv, ctx, s = api
    h = cabecera(srv, "ingeniero")
    r = client.put("/maintenance/config", headers=h, json={"intervalo_dias": 90, "intervalo_ciclos": 300})
    assert r.status_code == 200 and s.configuracion()["intervalo_ciclos"] == 300
    assert any(f["evento"] == "mantenimiento_configurado" for f in ctx.db.get_auditoria(limite=20))
    assert client.put("/maintenance/config", headers=h,
                      json={"intervalo_dias": -3, "intervalo_ciclos": 0}).status_code == 422
    assert client.post("/maintenance/records", headers=h, json={"tipo": "zzz"}).status_code == 422


def test_reloj_invalido_devuelve_409(api, servicio):
    client, srv, ctx, s = api
    _, _, hoy, _, _ = servicio
    hoy["d"] = date(2026, 1, 1)
    r = client.post("/maintenance/records", headers=cabecera(srv, "tecnico"), json={"tipo": "correctivo"})
    assert r.status_code == 409 and r.json()["codigo"] == "reloj_invalido"


def test_el_mantenimiento_nunca_bloquea_un_ciclo():
    """El servicio no toca el ControlLoop ni el estado: solo activa un aviso
    no bloqueante (verificado por catálogo y por la ausencia de referencias)."""
    import inspect
    from autoclave.core.runtime import servicio_mantenimiento as mod
    fuente = inspect.getsource(mod)
    assert "control_loop" not in fuente and "GlobalState" not in fuente
    assert CATALOGO[MANTENIMIENTO_VENCIDO].bloquea_inicio is False
