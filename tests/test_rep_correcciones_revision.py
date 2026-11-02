# tests/test_rep_correcciones_revision.py
#
# Correcciones de la revisión de seguridad de la etapa H (2026-11-02) de
# planeacion_dashboard_reportes.md: ciclo cerrado pendiente de confirmar,
# indicador de éxito sin ciclos, /cycle/list con «anio», umbral del consolidado
# y cota de `fecha`.

import re
from pathlib import Path

import pytest

from autoclave.ui_qml.domain import reporte_dashboard as dom
from tests.test_backend_dashboard_reportes import (  # noqa: F401  (fixtures)
    _ciclo, activo, cliente, datos, db)

RAIZ = Path(__file__).resolve().parents[1]


# ── 1) ciclo cerrado que espera CONFIRMAR no es «activo» ─────────────────

def test_cerrado_en_fallo_pendiente_de_confirmar_es_sin_exito(cliente, db, activo):
    cid = _ciclo(db, "2026-10-14T08:00:00", "2026-10-14T08:10:00", "FALLO_ESTERILIZACION")
    activo["id"] = cid           # la pantalla aún lo muestra (cierre sin confirmar)
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-14"}).json()
    assert r["estado"] == "sin_exito"
    cal = cliente.get("/report/calendar", params={"periodo": "mes", "fecha": "2026-10-14",
                                                  "programa": 1}).json()
    dia = {d["fecha"]: d for d in cal["dias"]}["2026-10-14"]
    assert dia["estado"] == "sin_exito" and dia["intentos"] == 1 and dia["exitos"] == 0


def test_cerrado_de_otro_programa_cuenta_en_n_dia(cliente, db, activo):
    cid = _ciclo(db, "2026-10-13T08:00:00", "2026-10-13T08:40:00", tipo="inst",
                 nombre="Instrumental", numero=2)
    activo["id"] = cid
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-13"}).json()
    assert r["estado"] == "falto"


def test_sin_resultado_sigue_siendo_activo(cliente, datos, activo):
    activo["id"] = datos["activo"]
    r = cliente.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-10-15"}).json()
    assert r["estado"] == "en_curso"


# ── 2) éxito con total == 0 ──────────────────────────────────────────────

def _resp(total, ant_total, serie=None):
    ind = {"total": total, "completados": 0, "fallos": 0, "exito_pct": 0,
           "cancelados": 0, "sin_cierre": 0}
    ant = None if ant_total is None else {"total": ant_total, "completados": ant_total,
                                          "fallos": 0, "exito_pct": 100}
    return {"indicadores": ind, "indicadores_anterior": ant, "serie": serie or []}


def _exito(resp):
    return next(t for t in dom.indicadores(resp, "es") if t["clave"] == "exito")


def test_exito_sin_ciclos_muestra_guion_y_sin_comparacion():
    t = _exito(_resp(0, 5))
    assert t["valor"] == dom.SIN_DATO
    assert "0 de 0" not in t["pie"] and "0%" not in t["valor"]
    assert t["comparacion"]["disponible"] is False


def test_exito_con_anterior_sin_ciclos_no_compara():
    r = _resp(4, 0)
    r["indicadores"].update(completados=4, exito_pct=100)
    t = _exito(r)
    assert t["valor"] == "100%" and t["comparacion"]["disponible"] is False


def test_minigrafica_exito_omite_dias_sin_ciclos():
    serie = [{"total": 2, "completados": 2, "fallos": 0},
             {"total": 0, "completados": 0, "fallos": 0},
             {"total": 2, "completados": 1, "fallos": 1}]
    mini = _exito(_resp(4, 4, serie))["mini"]
    assert len(mini) == 2 and [round(p["y"], 2) for p in mini] == [1.0, 0.5]


# ── 3) «anio» en /cycle/list y umbral del consolidado ────────────────────

def test_cycle_list_acepta_anio(cliente, datos):
    r = cliente.get("/cycle/list", params={"periodo": "anio", "fecha": "2026-10-15",
                                           "terminados": "false"})
    assert r.status_code == 200
    j = r.json()
    assert j["desde"] == "2026-01-01" and j["hasta"] == "2026-12-31"
    assert len(j["ciclos"]) >= 10


@pytest.mark.parametrize("p", ["dia", "semana", "mes"])
def test_cycle_list_otros_periodos_igual(cliente, p):
    assert cliente.get("/cycle/list", params={"periodo": p}).status_code == 200


def test_cycle_list_periodo_invalido_422(cliente):
    assert cliente.get("/cycle/list", params={"periodo": "trimestre"}).status_code == 422


def test_umbral_de_confirmacion_no_supera_el_maximo_del_envio():
    from autoclave.ui_qml.bridge.acciones_ciclos import MAX_CICLOS_CONSOLIDADO
    qml = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/Reportes.qml").read_text(encoding="utf-8")
    umbral = int(re.search(r"property int umbralConsolidado:\s*(\d+)", qml).group(1))
    maximo = int(re.search(r"property int maxConsolidado:\s*(\d+)", qml).group(1))
    assert maximo == MAX_CICLOS_CONSOLIDADO and umbral <= maximo
    assert "totalCiclos > maxConsolidado" in qml


# ── 4) fecha acotada ─────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta,q", [
    ("/report/dashboard", {}), ("/report/calendar", {}), ("/report/day-cycles", {"programa": 1}),
    ("/report/summary", {}), ("/report/failures", {"causa": "x"}), ("/cycle/list", {}),
])
@pytest.mark.parametrize("fecha", ["9999-12-31", "0001-01-01", "1999-12-31", "2101-01-01"])
def test_fecha_fuera_de_rango_422(cliente, ruta, q, fecha):
    assert cliente.get(ruta, params={**q, "fecha": fecha}).status_code == 422


@pytest.mark.parametrize("fecha", ["2000-01-01", "2100-12-31"])
def test_fecha_en_los_extremos_ok(cliente, fecha):
    assert cliente.get("/report/dashboard", params={"fecha": fecha, "periodo": "dia"}).status_code == 200
    assert cliente.get("/report/dashboard", params={"fecha": fecha, "periodo": "anio"}).status_code == 200
