# tests/test_backend_dashboard_reportes.py
#
# Etapa D de planeacion_dashboard_reportes.md: DbManager.get_ciclos_periodo /
# get_alarmas_periodo y GET /report/dashboard, /report/calendar y
# /report/day-cycles (solo lectura, sin token), con una BD temporal.

import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers.backend_doble import parche_en_backend

_HOY = "2026-10-15T00:00:00"          # jueves
_NO_CONFORME = json.dumps({"avisos": [{"clave": "ticket_ciclo.no_conforme_referencia"}]})


def _ciclo(db, inicio, fin=None, resultado="COMPLETADO", tipo="bd", nombre="Bowie & Dick",
           numero=1, operador="", avisos=""):
    cid = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo=tipo, nombre=nombre,
                         temp_ester=134, tiempo_ester=4, modelo="", serie="", version_sw="",
                         operador=operador)
    with db._lock:
        db._conn.execute(
            "UPDATE ciclos SET fecha_inicio=?, fecha_fin=?, resultado=?, numero_programa=?,"
            " avisos_ticket=? WHERE id=?",
            (inicio, fin, resultado, numero, avisos, cid))
        db._conn.commit()
    return cid


def _alarma(db, codigo, nivel, titulo, aparecida):
    with db._lock:
        db._conn.execute(
            "INSERT INTO alarmas_historial (codigo, nivel, titulo, descripcion_inicial, aparecida)"
            " VALUES (?, ?, ?, '', ?)", (codigo, nivel, titulo, aparecida))
        db._conn.commit()


@pytest.fixture
def db(tmp_path):
    d = DbManager(tmp_path / "a.db")
    yield d
    d.close()


@pytest.fixture
def datos(db):
    ids = {}
    ids["d01"] = _ciclo(db, "2026-10-01T08:00:00", "2026-10-01T08:40:00", operador="ana")
    ids["d02_f"] = _ciclo(db, "2026-10-02T08:00:00", "2026-10-02T08:10:00", "FALLO_ESTERILIZACION",
                          operador="ana")
    ids["d02_c"] = _ciclo(db, "2026-10-02T09:00:00", "2026-10-02T09:40:00", operador="ana")
    ids["d03"] = _ciclo(db, "2026-10-03T08:00:00", "2026-10-03T09:00:00", tipo="inst",
                        nombre="Instrumental", numero=2, operador="luis")
    ids["d04"] = _ciclo(db, "2026-10-04T08:00:00", "2026-10-04T08:05:00", "CANCELADO")
    ids["d05"] = _ciclo(db, "2026-10-05T08:00:00", "2026-10-05T08:40:00", avisos=_NO_CONFORME)
    # anterior a la columna numero_programa: se resuelve por el programa actual
    ids["d06"] = _ciclo(db, "2026-10-06T08:00:00", "2026-10-06T08:40:00", numero=None)
    # programa ya inexistente y sin número: cuenta en totales, no en el calendario
    ids["d07"] = _ciclo(db, "2026-10-07T08:00:00", "2026-10-07T08:10:00", "FALLO_CALENTAMIENTO",
                        tipo="huerfano", nombre="Borrado", numero=None)
    ids["d08_c"] = _ciclo(db, "2026-10-08T08:00:00", "2026-10-08T08:40:00")
    ids["d08_f"] = _ciclo(db, "2026-10-08T10:00:00", "2026-10-08T10:10:00", "FALLO_ESTERILIZACION")
    ids["activo"] = _ciclo(db, "2026-10-15T07:00:00", None, None)
    # mes anterior
    ids["sep"] = _ciclo(db, "2026-09-10T08:00:00", "2026-09-10T08:40:00")
    _alarma(db, "SIS-01", "FALLO_CRITICO", "guardado", "2026-10-02T08:05:00")
    _alarma(db, "SIS-01", "FALLO_CRITICO", "guardado", "2026-10-08T10:05:00")
    _alarma(db, "XYZ-9", "ALARMA", "Título guardado", "2026-10-03T08:05:00")
    _alarma(db, "TARJETA_SIN_TRAMA_VALIDA", "ALARMA", "x", "2026-10-04T08:05:00")
    _alarma(db, "SIS-01", "FALLO_CRITICO", "guardado", "2026-09-30T23:59:59")   # fuera del mes
    return ids


@pytest.fixture
def activo():
    return {"id": None}


@pytest.fixture
def cliente(db, datos, activo):
    ctx = MagicMock()
    ctx.db = db
    ctx.cycle_manager.cycles = {
        "bd": SimpleNamespace(number=1, name="Bowie & Dick"),
        "inst": SimpleNamespace(number=2, name="Instrumental"),
        "sin_numero": SimpleNamespace(number=None, name="Sin número"),
    }
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(
                ("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    with parche_en_backend("_inicio_del_dia", MagicMock(return_value=_HOY)), \
            parche_en_backend("_ciclo_de_pantalla", lambda: activo["id"]):
        yield TestClient(srv.app)


def _dashboard(cliente, **q):
    r = cliente.get("/report/dashboard", params=q)
    assert r.status_code == 200, r.text
    return r.json()


def _dias(r):
    return {d["fecha"]: d for d in r["dias"]}


# ── DbManager ────────────────────────────────────────────────────────────

def test_get_ciclos_periodo_rango_orden_y_columnas(db, datos):
    filas = db.get_ciclos_periodo("2026-10-02T00:00:00", "2026-10-04T00:00:00")
    assert [f["id"] for f in filas] == [datos["d02_f"], datos["d02_c"], datos["d03"]]
    assert set(filas[0]) == {"id", "numero_ciclo", "fecha_inicio", "fecha_fin", "tipo_ciclo",
                             "nombre_ciclo", "numero_programa", "resultado", "operador",
                             "avisos_ticket"}
    assert db.get_ciclos_periodo("2027-01-01T00:00:00", "2027-02-01T00:00:00") == []


def test_get_alarmas_periodo_semiabierto(db, datos):
    filas = db.get_alarmas_periodo("2026-10-01T00:00:00", "2026-10-03T00:00:00")
    assert [f["codigo"] for f in filas] == ["SIS-01"]
    todas = db.get_alarmas_periodo("2026-10-01T00:00:00", "2026-11-01T00:00:00")
    assert len(todas) == 4 and set(todas[0]) == {"codigo", "nivel", "titulo"}


# ── /report/dashboard ───────────────────────────────────────────────────

def test_dashboard_mes_indicadores_y_anterior(cliente):
    r = _dashboard(cliente, periodo="mes", fecha="2026-10-20")
    assert (r["periodo"], r["desde"], r["hasta"]) == ("mes", "2026-10-01", "2026-10-31")
    assert r["anterior"] == {"desde": "2026-09-01", "hasta": "2026-09-30"}
    ind = r["indicadores"]
    assert (ind["total"], ind["completados"], ind["fallos"], ind["cancelados"],
            ind["sin_cierre"]) == (11, 6, 3, 1, 1)
    assert ind["exito_pct"] == 55
    assert ind["duracion_media_s"] == pytest.approx(
        (2400 + 2400 + 3600 + 2400 + 2400 + 2400) / 6, abs=0.1)
    assert ind["duraciones_excluidas"] == 0
    assert r["indicadores_anterior"]["total"] == 1
    assert r["indicadores_anterior"]["exito_pct"] == 100
    assert len(r["serie"]) == 31
    assert r["serie"][1]["total"] == 2 and r["serie"][1]["fallos"] == 1
    assert r["serie"][1]["completados"] == 1


def test_dashboard_por_programa_y_causas_con_forma_de_summary(cliente):
    r = _dashboard(cliente, periodo="mes", fecha="2026-10-20")
    resumen = cliente.get("/report/summary", params={"periodo": "mes", "fecha": "2026-10-20"}).json()
    assert r["causas_fallo"] == resumen["causas_fallo"]
    assert [p["programa_id"] for p in r["por_programa"]] == [
        p["programa_id"] for p in resumen["por_programa"]]
    assert set(r["por_programa"][0]) == set(resumen["por_programa"][0])
    assert r["causas_fallo"][0] == {"causa": "FALLO_ESTERILIZACION", "cantidad": 2}


def test_dashboard_dia_por_hora_y_sin_datos_anteriores(cliente):
    r = _dashboard(cliente, periodo="dia", fecha="2026-10-02")
    assert r["indicadores"]["total"] == 2
    assert [p["etiqueta"] for p in r["serie"]] == [f"{h:02d}" for h in range(24)]
    assert r["serie"][8]["fallos"] == 1 and r["serie"][9]["completados"] == 1
    assert r["indicadores_anterior"]["total"] == 1          # 1 de octubre
    r = _dashboard(cliente, periodo="dia", fecha="2026-10-01")
    assert r["anterior"] == {"desde": "2026-09-30", "hasta": "2026-09-30"}
    assert r["indicadores_anterior"] is None                 # 30 de septiembre sin ciclos


def test_dashboard_semana_lunes_a_domingo(cliente):
    r = _dashboard(cliente, periodo="semana", fecha="2026-10-07")
    assert (r["desde"], r["hasta"]) == ("2026-10-05", "2026-10-11")
    assert r["anterior"] == {"desde": "2026-09-28", "hasta": "2026-10-04"}
    assert r["indicadores"]["total"] == 5
    assert r["indicadores_anterior"]["total"] == 5          # 1, 2 (x2), 3 y 4 de octubre
    assert [p["etiqueta"] for p in r["serie"]][0] == "2026-10-05" and len(r["serie"]) == 7


def test_dashboard_anio_serie_por_mes_y_anterior_vacio(cliente):
    r = _dashboard(cliente, periodo="anio", fecha="2026-03-01")
    assert (r["desde"], r["hasta"]) == ("2026-01-01", "2026-12-31")
    assert r["anterior"] == {"desde": "2025-01-01", "hasta": "2025-12-31"}
    assert r["indicadores"]["total"] == 12
    assert r["indicadores_anterior"] is None
    assert [p["etiqueta"] for p in r["serie"]] == [f"2026-{m:02d}" for m in range(1, 13)]
    assert r["serie"][9]["total"] == 11 and r["serie"][8]["total"] == 1


def test_dashboard_periodo_sin_ciclos(cliente):
    r = _dashboard(cliente, periodo="mes", fecha="2026-03-10")
    assert r["indicadores"] == {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0,
                                "sin_cierre": 0, "exito_pct": 0, "duracion_media_s": None,
                                "duraciones_excluidas": 0}
    assert r["indicadores_anterior"] is None
    assert r["por_programa"] == [] and r["causas_fallo"] == [] and r["alarmas"] == []
    assert r["operadores"] == [] and r["operadores_otros"] is None


def test_dashboard_duraciones_absurdas_se_excluyen(db, cliente):
    _ciclo(db, "2026-10-12T10:00:00", "2026-10-12T09:00:00")      # hora cambiada: negativa
    _ciclo(db, "2026-10-12T11:00:00", None)                       # COMPLETADO sin fin
    ind = _dashboard(cliente, periodo="dia", fecha="2026-10-12")["indicadores"]
    assert ind["completados"] == 2 and ind["duracion_media_s"] is None
    assert ind["duraciones_excluidas"] == 2


def test_dashboard_alarmas_agrupadas_con_titulo_de_catalogo(cliente):
    from autoclave import i18n
    r = _dashboard(cliente, periodo="mes", fecha="2026-10-20")
    por_codigo = {a["codigo"]: a for a in r["alarmas"]}
    assert set(por_codigo) == {"SIS-01", "XYZ-9", "TARJETA_SIN_TRAMA_VALIDA"}
    assert por_codigo["SIS-01"]["cantidad"] == 2
    assert por_codigo["SIS-01"]["nivel"] == "FALLO_CRITICO"
    assert por_codigo["SIS-01"]["titulo"] == i18n.t("alarmas.SIS-01.titulo") != "guardado"
    assert por_codigo["XYZ-9"]["titulo"] == "Título guardado"            # código desconocido
    assert por_codigo["TARJETA_SIN_TRAMA_VALIDA"]["codigo_visible"] == "MODULO_ES_SIN_TRAMA_VALIDA"
    assert r["alarmas"][0]["codigo"] == "SIS-01"                         # nivel más grave primero


def test_dashboard_operadores(cliente):
    r = _dashboard(cliente, periodo="mes", fecha="2026-10-20")
    assert r["operadores"][0] == {"operador": "Sin operador", "sin_operador": True, "cantidad": 7}
    assert {"operador": "ana", "sin_operador": False, "cantidad": 3} in r["operadores"]
    assert r["operadores_otros"] is None


def test_dashboard_fecha_por_defecto_es_hoy(cliente):
    r = _dashboard(cliente, periodo="dia")
    assert r["desde"] == "2026-10-15" and r["indicadores"]["total"] == 1


# ── /report/calendar ────────────────────────────────────────────────────

def test_calendario_programa_01_por_defecto(cliente, activo, datos):
    activo["id"] = datos["activo"]
    r = cliente.get("/report/calendar", params={"periodo": "mes", "fecha": "2026-10-20"}).json()
    assert r["programa"] == 1 and (r["desde"], r["hasta"]) == ("2026-10-01", "2026-10-31")
    assert r["programas"] == [
        {"numero": 1, "programa_id": "bd", "nombre": "Bowie & Dick"},
        {"numero": 2, "programa_id": "inst", "nombre": "Instrumental"}]   # sin el huérfano
    d = _dias(r)
    assert len(r["dias"]) == 31
    assert d["2026-10-01"]["estado"] == "exito"
    assert d["2026-10-02"] == {"fecha": "2026-10-02", "estado": "exito_fallo_previo",
                               "intentos": 2, "exitos": 1}
    assert d["2026-10-03"]["estado"] == "falto" and d["2026-10-03"]["intentos"] == 0
    assert d["2026-10-04"]["estado"] == "sin_exito"
    assert d["2026-10-05"]["estado"] == "sin_exito"            # NO CONFORME = intento sin éxito
    assert d["2026-10-05"]["intentos"] == 1 and d["2026-10-05"]["exitos"] == 0
    assert d["2026-10-06"]["estado"] == "exito"                # numero_programa NULL → mapa actual
    assert d["2026-10-07"]["estado"] == "falto"                # solo el programa huérfano
    assert d["2026-10-08"]["estado"] == "exito"                # fallo posterior al éxito (DR-D12)
    assert d["2026-10-08"]["intentos"] == 2
    assert d["2026-10-09"]["estado"] == "sin_operacion"
    assert d["2026-10-15"]["estado"] == "en_curso"
    assert d["2026-10-15"]["intentos"] == 0                    # el activo no es intento
    assert d["2026-10-16"]["estado"] == "futuro"


def test_calendario_sin_activo_registrado_el_ciclo_abierto_cuenta_como_sin_cierre(cliente):
    d = _dias(cliente.get("/report/calendar", params={"fecha": "2026-10-20"}).json())
    assert d["2026-10-15"]["estado"] == "sin_exito" and d["2026-10-15"]["intentos"] == 1


def test_calendario_otro_programa(cliente):
    r = cliente.get("/report/calendar", params={"fecha": "2026-10-20", "programa": 2}).json()
    assert r["programa"] == 2
    d = _dias(r)
    assert d["2026-10-03"]["estado"] == "exito"
    assert d["2026-10-01"]["estado"] == "no_ejecutado"         # distinto del 01: no "faltó"
    assert d["2026-10-09"]["estado"] == "sin_operacion"
    assert d["2026-10-31"]["estado"] == "futuro"


def test_calendario_programa_no_disponible_cae_al_01(cliente):
    assert cliente.get("/report/calendar", params={"fecha": "2026-10-20", "programa": 99}
                       ).json()["programa"] == 1


def test_calendario_selector_sigue_el_periodo_pedido(cliente):
    # día 3: solo corrió "inst", pero el 01 aparece siempre (DR-D06) y es el elegido
    r = cliente.get("/report/calendar", params={"periodo": "dia", "fecha": "2026-10-03"}).json()
    assert [p["numero"] for p in r["programas"]] == [1, 2] and r["programa"] == 1
    assert len(r["dias"]) == 31                                 # los días del mes que lo contiene
    # día sin ciclos: ningún programa, ni siquiera el 01
    r = cliente.get("/report/calendar", params={"periodo": "dia", "fecha": "2026-10-09"}).json()
    assert r["programas"] == [] and r["programa"] is None
    assert _dias(r)["2026-10-03"]["estado"] == "no_ejecutado"   # sin programa elegido
    assert _dias(r)["2026-10-09"]["estado"] == "sin_operacion"


def test_calendario_01_ausente_en_el_equipo_elige_el_primero(db, cliente):
    ctx = sys.modules["autoclave.backend.dependencias"].context
    ctx.cycle_manager.cycles = {"inst": SimpleNamespace(number=2, name="Instrumental")}
    r = cliente.get("/report/calendar", params={"periodo": "dia", "fecha": "2026-10-03"}).json()
    assert [p["numero"] for p in r["programas"]] == [2] and r["programa"] == 2


def test_calendario_anio_y_semana(cliente):
    r = cliente.get("/report/calendar", params={"periodo": "anio", "fecha": "2026-10-20"}).json()
    assert len(r["dias"]) == 365 and (r["desde"], r["hasta"]) == ("2026-01-01", "2026-12-31")
    assert _dias(r)["2026-10-02"]["estado"] == "exito_fallo_previo"
    assert _dias(r)["2026-02-01"]["estado"] == "sin_operacion"
    r = cliente.get("/report/calendar", params={"periodo": "semana", "fecha": "2026-10-07"}).json()
    assert len(r["dias"]) == 31 and r["desde"] == "2026-10-01"


# ── /report/day-cycles ──────────────────────────────────────────────────

def test_dia_con_fallo_previo_en_orden_de_inicio(cliente, datos):
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-02"}).json()
    assert r["fecha"] == "2026-10-02" and r["estado"] == "exito_fallo_previo"
    assert [c["id"] for c in r["ciclos"]] == [datos["d02_f"], datos["d02_c"]]
    c = r["ciclos"][0]
    assert c["resultado"] == "FALLO_ESTERILIZACION" and c["operador"] == "ana"
    assert c["programa_id"] == "bd" and c["programa_numero"] == 1
    assert set(c) >= {"id", "numero_ciclo", "fecha_inicio", "fecha_fin", "programa_nombre"}


def test_dia_no_conforme_y_numero_nulo(cliente, datos):
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-05"}).json()
    assert r["estado"] == "sin_exito" and r["ciclos"][0]["no_conforme"] is True
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-06"}).json()
    assert [c["id"] for c in r["ciclos"]] == [datos["d06"]] and r["ciclos"][0]["programa_numero"] == 1


def test_dia_faltó_sin_operacion_y_futuro(cliente):
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-03"}).json()
    assert r["estado"] == "falto" and r["ciclos"] == []
    r = cliente.get("/report/day-cycles", params={"programa": 2, "fecha": "2026-10-04"}).json()
    assert r["estado"] == "no_ejecutado"
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-09"}).json()
    assert r["estado"] == "sin_operacion"
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-20"}).json()
    assert r["estado"] == "futuro" and r["ciclos"] == []


def test_dia_con_ciclo_activo(cliente, activo, datos):
    activo["id"] = datos["activo"]
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-15"}).json()
    assert r["estado"] == "en_curso"
    assert [c["id"] for c in r["ciclos"]] == [datos["activo"]]     # el panel lo muestra
    assert r["ciclos"][0]["resultado"] is None


# ── validación y solo lectura ───────────────────────────────────────────

@pytest.mark.parametrize("ruta,q", [
    ("/report/dashboard", {"periodo": "trimestre"}),
    ("/report/dashboard", {"fecha": "no-es-fecha"}),
    ("/report/calendar", {"periodo": "trimestre"}),
    ("/report/calendar", {"programa": 0}),
    ("/report/day-cycles", {}),                       # programa obligatorio
    ("/report/day-cycles", {"programa": 0}),
    ("/report/day-cycles", {"programa": 1, "fecha": "2026-13-45"}),
])
def test_validacion_422(cliente, ruta, q):
    assert cliente.get(ruta, params=q).status_code == 422


def test_sin_token_y_ningun_endpoint_escribe(cliente, db, datos, activo):
    activo["id"] = datos["activo"]
    antes = db._conn.total_changes
    with db._lock:
        filas = {t: db._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("ciclos", "alarmas_historial", "audit_log")}
    for periodo in ("dia", "semana", "mes", "anio"):
        assert cliente.get("/report/dashboard", params={"periodo": periodo}).status_code == 200
        assert cliente.get("/report/calendar", params={"periodo": periodo}).status_code == 200
    assert cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-02"}
                       ).status_code == 200
    assert db._conn.total_changes == antes
    with db._lock:
        assert filas == {t: db._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                         for t in filas}


def test_las_consultas_nuevas_son_de_solo_lectura_en_el_codigo():
    import inspect
    for nombre in ("get_ciclos_periodo", "get_alarmas_periodo"):
        fuente = inspect.getsource(getattr(DbManager, nombre)).upper()
        assert "INSERT" not in fuente and "UPDATE" not in fuente and "DELETE" not in fuente
