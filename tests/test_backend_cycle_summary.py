# tests/test_backend_cycle_summary.py
#
# GET /cycle/summary y DbManager.get_resumen_ciclos (Resumen del Sistema del
# Menú Principal, Fase 2 de planeacion_menu_principal_ui_qml.md). Solo lectura.

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.services.domain.logging.db_manager import DbManager
from tests.backend_doble import modulo_backend, parche_en_backend

_HOY = "2026-10-02T00:00:00"


def _crear(db, tipo="instrumental_134", nombre="Instrumental 134", numero=None):
    return db.crear_ciclo(numero=numero or db.siguiente_numero_ciclo(), tipo=tipo,
                          nombre=nombre, temp_ester=134, tiempo_ester=4,
                          modelo="", serie="", version_sw="")


def _fechas(db, cid, inicio, fin=None, resultado=None):
    """Fija fechas y resultado a mano (cerrar_ciclo usa la hora real)."""
    with db._lock:
        db._conn.execute("UPDATE ciclos SET fecha_inicio=?, fecha_fin=?, resultado=? WHERE id=?",
                         (inicio, fin, resultado, cid))
        db._conn.commit()


@pytest.fixture
def db(tmp_path):
    d = DbManager(tmp_path / "a.db")
    yield d
    d.close()


# ── consulta en DbManager ────────────────────────────────────────────────

def test_resumen_sin_ciclos(db):
    assert db.get_resumen_ciclos(_HOY) == {"total": 0, "hoy": 0, "ultimo": None}


def test_hoy_cuenta_terminados_desde_medianoche_local(db):
    _fechas(db, _crear(db), "2026-10-01T22:00:00", "2026-10-01T23:30:00", "COMPLETADO")
    # empezó ayer y terminó hoy: cuenta (terminado desde las 00:00)
    _fechas(db, _crear(db), "2026-10-01T23:50:00", "2026-10-02T00:20:00", "COMPLETADO")
    _fechas(db, _crear(db), "2026-10-02T08:00:00", "2026-10-02T08:40:00", "FALLO")
    _fechas(db, _crear(db), "2026-10-02T09:00:00", "2026-10-02T09:05:00", "CANCELADO")
    # interrumpido (sin fecha_fin): no está terminado
    _fechas(db, _crear(db), "2026-10-02T10:00:00")
    r = db.get_resumen_ciclos(_HOY)
    assert r["hoy"] == 3
    assert r["total"] == 5


def test_total_es_el_ultimo_numero_de_ciclo_aunque_falten_filas(db):
    _crear(db, numero=1)
    _crear(db, numero=7)   # p. ej. historial depurado entre medias (TODO(MP-06a))
    assert db.get_resumen_ciclos(_HOY)["total"] == 7


def test_ultimo_es_el_de_mayor_id(db):
    _crear(db, nombre="primero")
    cid = _crear(db, nombre="segundo")
    assert db.get_resumen_ciclos(_HOY)["ultimo"]["id"] == cid


# ── endpoint ─────────────────────────────────────────────────────────────

@pytest.fixture
def cliente(db):
    ctx = MagicMock()
    ctx.db = db
    ctx.cycle_manager.cycles = {
        "instrumental_134": SimpleNamespace(number=2),
        "sin_numero": SimpleNamespace(number=None),
    }
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    with parche_en_backend("_inicio_del_dia", MagicMock(return_value=_HOY)):
        yield TestClient(srv.app)


def test_endpoint_sin_ciclos(cliente):
    assert cliente.get("/cycle/summary").json() == {
        "ciclos_totales": 0, "ciclos_hoy": 0, "ultimo_ciclo": None}


def test_endpoint_con_ultimo_ciclo(cliente, db):
    _fechas(db, _crear(db), "2026-10-01T10:00:00", "2026-10-01T10:45:00", "COMPLETADO")
    cid = _crear(db)
    _fechas(db, cid, "2026-10-02T14:25:10.123456", "2026-10-02T15:02:00", "FALLO")
    assert cliente.get("/cycle/summary").json() == {
        "ciclos_totales": 2,
        "ciclos_hoy": 1,
        "ultimo_ciclo": {
            "id": cid,
            "numero_ciclo": 2,
            "fecha_inicio": "2026-10-02T14:25:10.123456",
            "fecha_fin": "2026-10-02T15:02:00",
            "programa_id": "instrumental_134",
            "programa_nombre": "Instrumental 134",
            "programa_numero": 2,
            "resultado": "FALLO",
            "operador": None,
        },
    }


def test_endpoint_resultado_nulo_y_programa_desconocido(cliente, db):
    _fechas(db, _crear(db, tipo="borrado_del_disco"), "2026-10-02T10:00:00")
    u = cliente.get("/cycle/summary").json()["ultimo_ciclo"]
    assert u["resultado"] is None and u["fecha_fin"] is None
    assert u["programa_numero"] is None


def test_endpoint_programa_sin_numero(cliente, db):
    _crear(db, tipo="sin_numero")
    assert cliente.get("/cycle/summary").json()["ultimo_ciclo"]["programa_numero"] is None


def test_inicio_del_dia_es_medianoche_local_en_formato_de_la_tabla():
    with patch("autoclave.backend.context.BackendContext", return_value=MagicMock()):
        for key in list(sys.modules):
            if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
                del sys.modules[key]
        srv = importlib.import_module("autoclave.backend.server")
    valor = modulo_backend("rutas._comun")._inicio_del_dia()
    assert valor.endswith("T00:00:00") and len(valor) == 19


def test_endpoint_operador_si_se_guardo(cliente, db):
    # CycleLogger hoy no lo llena (Paso 1 b); si algún día se guarda, se publica
    db.crear_ciclo(numero=1, tipo="instrumental_134", nombre="x", temp_ester=134,
                   tiempo_ester=4, modelo="", serie="", version_sw="", operador="Ana")
    assert cliente.get("/cycle/summary").json()["ultimo_ciclo"]["operador"] == "Ana"


# ── curva de un ciclo del historial ─────────────────────────────────────

def test_grafica_historica(cliente, db):
    cid = _crear(db)
    db.insertar_lectura_grafica(cid, 0.0, "PRE_VACIO", 40.0, 35.0, 101.3)
    db.insertar_lectura_grafica(cid, 1.0, "CALENTAMIENTO", 41.5, None, 102.0)
    otro = _crear(db)
    db.insertar_lectura_grafica(otro, 0.0, "PRE_VACIO", 99.0, 99.0, 99.0)
    r = cliente.get(f"/cycle/history/{cid}/graph").json()
    assert r["ciclo_db_id"] == cid
    assert [(l["t_s"], l["fase"], l["fase_ui"], l["temp_camara"], l["temp_ref"], l["pres_camara"])
            for l in r["lecturas"]] == [
        (0.0, "PRE_VACIO", "vacio", 40.0, 35.0, 101.3),
        (1.0, "CALENTAMIENTO", "calentamiento", 41.5, None, 102.0),
    ]
    assert all(isinstance(l["id"], int) for l in r["lecturas"])


def test_grafica_historica_sin_lecturas(cliente, db):
    cid = _crear(db)
    assert cliente.get(f"/cycle/history/{cid}/graph").json() == {"ciclo_db_id": cid, "lecturas": []}


def test_grafica_historica_ciclo_inexistente(cliente):
    assert cliente.get("/cycle/history/999/graph").status_code == 404


# ── listado de ciclos por periodo (Ciclos hoy e Historial) ───────────────

def test_ciclos_desde_por_inicio_incluye_interrumpidos(db):
    _fechas(db, _crear(db), "2026-10-01T22:00:00", "2026-10-01T23:00:00", "COMPLETADO")
    a = _crear(db); _fechas(db, a, "2026-10-02T08:00:00", "2026-10-02T08:40:00", "FALLO_SECADO")
    b = _crear(db); _fechas(db, b, "2026-10-02T10:00:00")   # interrumpido
    filas = db.get_ciclos_desde(_HOY, terminados=False, limite=10)
    assert [f["id"] for f in filas] == [b, a]                # más reciente primero


def test_ciclos_desde_terminados_por_fin_como_el_conteo_de_hoy(db):
    a = _crear(db); _fechas(db, a, "2026-10-01T23:50:00", "2026-10-02T00:20:00", "COMPLETADO")
    _fechas(db, _crear(db), "2026-10-02T10:00:00")           # interrumpido: no terminado
    filas = db.get_ciclos_desde(_HOY, terminados=True, limite=10)
    assert [f["id"] for f in filas] == [a]
    assert len(filas) == db.get_resumen_ciclos(_HOY)["hoy"]


def test_ciclos_desde_respeta_el_limite(db):
    for i in range(5):
        _fechas(db, _crear(db), f"2026-10-02T0{i}:00:00", f"2026-10-02T0{i}:30:00", "COMPLETADO")
    assert len(db.get_ciclos_desde(_HOY, terminados=False, limite=3)) == 3


def test_ciclos_desde_con_tope_excluye_el_periodo_siguiente(db):
    a = _crear(db); _fechas(db, a, "2026-10-01T23:59:00", "2026-10-02T00:30:00", "COMPLETADO")
    _fechas(db, _crear(db), "2026-10-02T00:00:00", "2026-10-02T00:40:00", "COMPLETADO")
    filas = db.get_ciclos_desde("2026-10-01T00:00:00", terminados=False, limite=10,
                                hasta="2026-10-02T00:00:00")
    assert [f["id"] for f in filas] == [a]
    # terminados: el tope se aplica a fecha_fin (a terminó el 2: no entra)
    assert db.get_ciclos_desde("2026-10-01T00:00:00", terminados=True, limite=10,
                               hasta="2026-10-02T00:00:00") == []


def _servidor():
    with patch("autoclave.backend.context.BackendContext", return_value=MagicMock()):
        for key in list(sys.modules):
            if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
                del sys.modules[key]
        return importlib.import_module("autoclave.backend.server")


@pytest.mark.parametrize("periodo, fecha, desde, hasta", [
    ("dia",    (2026, 10, 2), "2026-10-02T00:00:00", "2026-10-03T00:00:00"),
    # semana de calendario: lunes a domingo (el 2026-10-02 es viernes)
    ("semana", (2026, 10, 2), "2026-09-28T00:00:00", "2026-10-05T00:00:00"),
    ("semana", (2026, 9, 28), "2026-09-28T00:00:00", "2026-10-05T00:00:00"),
    ("semana", (2026, 10, 4), "2026-09-28T00:00:00", "2026-10-05T00:00:00"),
    # mes de calendario, con cambio de año
    ("mes",    (2026, 10, 2), "2026-10-01T00:00:00", "2026-11-01T00:00:00"),
    ("mes",    (2026, 12, 31), "2026-12-01T00:00:00", "2027-01-01T00:00:00"),
    ("semana", (2026, 12, 31), "2026-12-28T00:00:00", "2027-01-04T00:00:00"),
])
def test_rango_del_periodo_de_calendario(periodo, fecha, desde, hasta):
    from datetime import date
    _servidor()   # ORG-12: carga el backend; la función vive en rutas/_comun.py
    assert modulo_backend("rutas._comun")._rango_del_periodo(periodo, date(*fecha)) == (desde, hasta)


def test_endpoint_lista_dia(cliente, db):
    _fechas(db, _crear(db), "2026-10-01T22:00:00", "2026-10-01T23:00:00", "COMPLETADO")
    cid = _crear(db)
    _fechas(db, cid, "2026-10-02T08:00:00", "2026-10-02T08:40:00", "FALLO_SECADO")
    r = cliente.get("/cycle/list", params={"periodo": "dia"}).json()
    assert r["periodo"] == "dia" and r["truncado"] is False
    assert r["ciclos"] == [{
        "id": cid, "numero_ciclo": 2, "fecha_inicio": "2026-10-02T08:00:00",
        "fecha_fin": "2026-10-02T08:40:00", "programa_id": "instrumental_134",
        "programa_nombre": "Instrumental 134", "programa_numero": 2,
        "resultado": "FALLO_SECADO", "operador": None,
    }]


def test_endpoint_lista_terminados_y_truncado(cliente, db):
    for i in range(3):
        _fechas(db, _crear(db), f"2026-10-02T0{i}:00:00", f"2026-10-02T0{i}:30:00", "COMPLETADO")
    _fechas(db, _crear(db), "2026-10-02T09:00:00")   # interrumpido
    r = cliente.get("/cycle/list", params={"periodo": "dia", "terminados": True, "limite": 2}).json()
    assert len(r["ciclos"]) == 2 and r["truncado"] is True
    assert all(c["fecha_fin"] for c in r["ciclos"])


def test_endpoint_lista_periodo_invalido(cliente):
    assert cliente.get("/cycle/list", params={"periodo": "anio"}).status_code == 422


def test_endpoint_lista_sin_fecha_es_el_periodo_de_hoy(cliente, db):
    r = cliente.get("/cycle/list", params={"periodo": "dia"}).json()
    assert (r["desde"], r["hasta"]) == ("2026-10-02", "2026-10-02")


def test_endpoint_lista_de_un_mes_anterior(cliente, db):
    _fechas(db, _crear(db), "2026-08-31T23:00:00", "2026-08-31T23:40:00", "COMPLETADO")
    sep = _crear(db); _fechas(db, sep, "2026-09-15T08:00:00", "2026-09-15T08:40:00", "COMPLETADO")
    _fechas(db, _crear(db), "2026-10-01T08:00:00", "2026-10-01T08:40:00", "COMPLETADO")
    r = cliente.get("/cycle/list", params={"periodo": "mes", "fecha": "2026-09-20"}).json()
    assert [c["id"] for c in r["ciclos"]] == [sep]
    # último día incluido, para el rótulo del periodo
    assert (r["desde"], r["hasta"]) == ("2026-09-01", "2026-09-30")


def test_endpoint_lista_fecha_invalida(cliente):
    assert cliente.get("/cycle/list", params={"fecha": "2026-13-01"}).status_code == 422


# ── reimpresión de ciclos en la impresora térmica ────────────────────────

@pytest.fixture
def estado_maquina(cliente):
    """Estado global que ve el endpoint de impresión (por defecto, sin ciclo)."""
    from autoclave.backend import server
    from autoclave.state_machine.machine.enum_global import GlobalState
    server.context.estado.get_machine_state.return_value = GlobalState.PREPARADO
    server.context.realtime_printer.estado.return_value = "lista"
    return server.context


def test_imprimir_encola_el_ticket_de_cada_ciclo_en_orden(cliente, db, estado_maquina):
    a = _crear(db); b = _crear(db)
    db.insertar_lectura(a, "00:00:10", "2026-10-02T08:00:10", "CALENTAMIENTO", 120.0, 200.0,
                        para_imprimir=True)
    r = cliente.post("/cycle/history/print", json={"ids": [b, a]})
    assert r.status_code == 200 and r.json() == {"ok": True, "impresos": 2}
    tickets = [c.args[0] for c in estado_maquina.realtime_printer.enqueue.call_args_list]
    # en el orden pedido, uno por ciclo, con el formato de la reimpresión
    assert len(tickets) == 2
    assert f"Ciclo No.: {db.get_ciclo(b)['numero_ciclo']:06d}" in tickets[0]
    assert f"Ciclo No.: {db.get_ciclo(a)['numero_ciclo']:06d}" in tickets[1]
    assert "0120.0 0200.0" in tickets[1]          # la lectura para_imprimir de a


def test_imprimir_rechazado_durante_un_ciclo(cliente, db, estado_maquina):
    from autoclave.state_machine.machine.enum_global import GlobalState
    estado_maquina.estado.get_machine_state.return_value = GlobalState.CICLO
    r = cliente.post("/cycle/history/print", json={"ids": [_crear(db)]})
    assert r.status_code == 409
    estado_maquina.realtime_printer.enqueue.assert_not_called()


def test_imprimir_ciclo_inexistente(cliente, db, estado_maquina):
    cid = _crear(db)
    assert cliente.post("/cycle/history/print", json={"ids": [cid, 999]}).status_code == 404
    estado_maquina.realtime_printer.enqueue.assert_not_called()


@pytest.mark.parametrize("estado", ["desconectada", "sin_papel", "no_instalada", "error"])
def test_imprimir_rechazado_si_la_impresora_no_esta_lista(cliente, db, estado_maquina, estado):
    # Windows acepta el trabajo aunque la impresora esté desconectada: se avisa
    # en vez de dejar los tickets atascados en la cola
    estado_maquina.realtime_printer.estado.return_value = estado
    r = cliente.post("/cycle/history/print", json={"ids": [_crear(db)]})
    assert r.status_code == 503 and r.json()["detail"] == {"impresora": estado}
    estado_maquina.realtime_printer.enqueue.assert_not_called()


def test_imprimir_sin_ciclos(cliente, estado_maquina):
    assert cliente.post("/cycle/history/print", json={"ids": []}).status_code == 422


def test_ticket_txt_eliminado(cliente, db):
    # planeacion_backend_autenticacion.md §4.6: un GET no debe escribir archivos
    assert cliente.get(f"/cycle/history/{_crear(db)}/ticket.txt").status_code == 404


# ── resumen por periodo (pantalla Reportes) ──────────────────────────────

def test_resumen_de_un_mes(cliente, db):
    _fechas(db, _crear(db), "2026-08-31T23:00:00", "2026-08-31T23:40:00", "COMPLETADO")   # fuera
    _fechas(db, _crear(db), "2026-09-02T08:00:00", "2026-09-02T08:40:00", "COMPLETADO")
    _fechas(db, _crear(db), "2026-09-03T08:00:00", "2026-09-03T08:40:00", "FALLO_SECADO")
    _fechas(db, _crear(db), "2026-09-04T08:00:00")                                         # sin cierre
    r = cliente.get("/report/summary", params={"periodo": "mes", "fecha": "2026-09-15"}).json()
    assert (r["periodo"], r["desde"], r["hasta"]) == ("mes", "2026-09-01", "2026-09-30")
    assert r["totales"] == {"total": 3, "completados": 1, "fallos": 1, "cancelados": 0, "sin_cierre": 1}
    assert r["por_programa"] == [{
        "programa_id": "instrumental_134", "programa_nombre": "Instrumental 134", "programa_numero": 2,
        "total": 3, "completados": 1, "fallos": 1, "cancelados": 0, "sin_cierre": 1}]
    assert r["causas_fallo"] == [{"causa": "FALLO_SECADO", "cantidad": 1}]


def test_resumen_sin_fecha_es_el_periodo_de_hoy(cliente):
    r = cliente.get("/report/summary", params={"periodo": "semana"}).json()
    assert (r["desde"], r["hasta"]) == ("2026-09-28", "2026-10-04")   # hoy: viernes 2026-10-02
    assert r["totales"]["total"] == 0


def test_resumen_periodo_invalido(cliente):
    assert cliente.get("/report/summary", params={"periodo": "anio"}).status_code == 422


def test_imprimir_resumen(cliente, db, estado_maquina):
    estado_maquina.profile.serial_number = "SPK-1"
    estado_maquina.profile.model_id = "AVH-450"
    _fechas(db, _crear(db), "2026-10-02T08:00:00", "2026-10-02T08:40:00", "COMPLETADO")
    r = cliente.post("/report/summary/print", json={"periodo": "dia"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    texto = estado_maquina.realtime_printer.enqueue.call_args.args[0]
    assert "RESUMEN DE CICLOS" in texto and "Total: 1" in texto and "Num serie: SPK-1" in texto
    assert "Desde: 02/10/2026" in texto


def test_imprimir_resumen_rechazado_durante_un_ciclo(cliente, estado_maquina):
    from autoclave.state_machine.machine.enum_global import GlobalState
    estado_maquina.estado.get_machine_state.return_value = GlobalState.CICLO
    assert cliente.post("/report/summary/print", json={"periodo": "dia"}).status_code == 409
    estado_maquina.realtime_printer.enqueue.assert_not_called()


def test_imprimir_resumen_con_la_impresora_desconectada(cliente, estado_maquina):
    estado_maquina.realtime_printer.estado.return_value = "desconectada"
    r = cliente.post("/report/summary/print", json={"periodo": "mes", "fecha": "2026-09-01"})
    assert r.status_code == 503 and r.json()["detail"] == {"impresora": "desconectada"}
    estado_maquina.realtime_printer.enqueue.assert_not_called()
