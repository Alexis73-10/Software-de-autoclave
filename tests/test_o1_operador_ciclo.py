"""O1 (tanda 3, MP-14b / D-24): el operador que inició el ciclo se guarda en la
base, el respaldo y el ticket, y llega al historial y al detalle."""

import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.services.domain.logging import db_manager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.ticket_formatter import format_footer, format_ticket
from tests.backend_doble import cabecera, cargar_servidor
from tests.test_t8_modo_sin_bd import _correr_ciclo, _logger


# ── backend: el token identifica al operador ───────────────────────────────

@pytest.fixture
def api(monkeypatch):
    ctx = MagicMock()
    ctx.sin_base_de_datos = False
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.apagando = False
    ctx.control_loop.cycle.danado = []
    ctx.control_loop.cycle.get_param.side_effect = lambda *a, default=None: default
    ctx.estado = SimpleNamespace(
        get_flag=lambda f: True, set_flag=MagicMock(), operador_inicio="",
        # S1 (tanda 8, D8-1.3): sin lectura de presión el inicio se rechaza
        sensores_pres={"pres_camara": 101.0, "pres_chaqueta": 300.0})
    ctx.cap.has_liquids = True
    srv, _ = cargar_servidor(ctx)
    monkeypatch.setattr(srv.sc, "verificar_inicio", lambda *a: None)
    return TestClient(srv.app), ctx, srv


def test_el_inicio_con_sesion_guarda_el_usuario(api):
    client, ctx, srv = api
    r = client.post("/cycle/start", headers=cabecera(srv, "operador", "oper1"))
    assert r.status_code == 200 and ctx.estado.operador_inicio == "oper1"
    ctx.estado.set_flag.assert_called_with("START_CICLO", True)


@pytest.mark.parametrize("cabeceras", [None, {"Authorization": "Bearer inexistente"},
                                       {"Authorization": "basura"}])
def test_sin_sesion_o_con_token_invalido_inicia_sin_operador(api, cabeceras):
    client, ctx, _ = api
    ctx.estado.operador_inicio = "viejo"
    r = client.post("/cycle/start", headers=cabeceras)
    assert r.status_code == 200 and ctx.estado.operador_inicio == ""      # nunca hereda el anterior


def test_un_inicio_rechazado_no_deja_operador(api):
    client, ctx, srv = api
    ctx.estado.get_flag = lambda f: False                                  # no listo
    r = client.post("/cycle/start", headers=cabecera(srv, "operador", "oper1"))
    assert r.status_code == 409 and ctx.estado.operador_inicio == ""


# ── CycleLogger: base, respaldo y ticket ────────────────────────────────────

def test_el_ciclo_guarda_operador_en_base_respaldo_y_ticket(tmp_path):
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    estado.operador_inicio = "oper1"
    _correr_ciclo(cl, estado)
    assert db.crear_ciclo.call_args.kwargs["operador"] == "oper1"
    assert respaldo.leer(respaldo.pendientes()[0])["encabezado"]["operador"] == "oper1"
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "Operador: oper1" in impreso and "Operador: ____" not in impreso
    assert estado.operador_inicio == ""                       # consumido


def test_sin_operador_el_ticket_conserva_la_linea_para_firmar(tmp_path):
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    cl, estado, printer, respaldo = _logger(tmp_path, db, sin_bd=False)
    _correr_ciclo(cl, estado)
    assert db.crear_ciclo.call_args.kwargs["operador"] == ""
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "Operador: ____________" in impreso


def test_sin_bd_sigue_la_leyenda_sin_operador(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    cl, estado, printer, respaldo = _logger(tmp_path, BdNoDisponible(), sin_bd=True)
    estado.operador_inicio = "oper1"
    _correr_ciclo(cl, estado)
    assert respaldo.leer(respaldo.pendientes()[0])["encabezado"]["operador"] == "SIN OPERADOR / SIN BD"
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "SIN OPERADOR / SIN BD" in impreso and "Operador: oper1" not in impreso


def test_footer_y_reimpresion_con_operador():
    assert "Operador: ana" in format_footer("COMPLETADO", "2026-10-20T10:00:00", operador="ana")
    assert "Operador: ____________" in format_footer("COMPLETADO", "2026-10-20T10:00:00")
    ciclo = {"numero_ciclo": 3, "serie": "S", "modelo": "M", "version_sw": "1", "nombre_ciclo": "N",
             "tipo_ciclo": "t", "temp_esterilizacion": 134, "tiempo_esterilizacion": 4,
             "fecha_inicio": "2026-10-20T09:00:00", "fecha_fin": "2026-10-20T10:00:00",
             "resultado": "COMPLETADO", "operador": "ana"}
    assert "Operador: ana" in format_ticket(ciclo, [])
    assert "Operador: ____________" in format_ticket({**ciclo, "operador": ""}, [])   # ciclo antiguo


# ── base de datos: migración y ciclos antiguos ──────────────────────────────

def test_el_operador_llega_a_la_fila_del_ciclo(tmp_path):
    db = DbManager(tmp_path / "t.db")
    i = db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1", operador="oper1")
    assert db.get_ciclo(i)["operador"] == "oper1"
    db.close()


def test_migracion_v6_agrega_la_columna_a_una_base_anterior(tmp_path):
    ruta = tmp_path / "vieja.db"
    conn = sqlite3.connect(ruta)
    conn.executescript("""
        CREATE TABLE ciclos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_ciclo INTEGER NOT NULL,
            fecha_inicio TEXT NOT NULL, fecha_fin TEXT, tipo_ciclo TEXT DEFAULT '', nombre_ciclo TEXT DEFAULT '',
            resultado TEXT, temp_esterilizacion REAL, tiempo_esterilizacion REAL, modelo TEXT DEFAULT '',
            serie TEXT DEFAULT '', version_sw TEXT DEFAULT '', motivo_fallo TEXT DEFAULT '');
        INSERT INTO ciclos (numero_ciclo, fecha_inicio, resultado) VALUES (7, '2026-01-01T10:00:00', 'COMPLETADO');
    """)
    conn.commit()
    conn.close()
    db = DbManager(ruta)
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION == 9   # v9: O2b
    antiguo = db.get_ciclo(1)
    assert antiguo["numero_ciclo"] == 7 and (antiguo["operador"] or "") == ""     # sin operador, sin romperse
    db.close()


def test_ciclo_antiguo_sin_operador_se_muestra_como_sin_dato():
    from autoclave.ui_qml.domain import resumen_sistema as d
    assert d.ciclo_presentable({"id": 1, "numero_ciclo": 1, "operador": ""})["operador"] == "—"
    assert d.ciclo_presentable({"id": 1, "numero_ciclo": 1, "operador": None})["operador"] == "—"
    assert d.ciclo_presentable({"id": 1, "numero_ciclo": 1, "operador": "ana"})["operador"] == "ana"


# ── UI: el inicio de ciclo envía el token de la ventana ─────────────────────

def test_el_cliente_de_la_ui_envia_el_token_al_iniciar_ciclo():
    from autoclave.ui.service_ui.session_manager import SessionManager
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    SessionManager.logout()
    try:
        assert ui.start_cycle() is True
        assert "headers" not in ui.backend.post.call_args.kwargs
        SessionManager.login({"nombre": "A", "usuario": "ana", "rol": "operador"}, "TOK")
        assert ui.start_cycle(confirmar_sin_registro=True) is True
        assert ui.backend.post.call_args.kwargs["headers"] == {"Authorization": "Bearer TOK"}
    finally:
        SessionManager.logout()
