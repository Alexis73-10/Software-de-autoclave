# tests/test_simulador_reportes.py
#
# Rutas de Reportes del backend SIMULADO (simulador/reportes_sim.py): misma
# lógica que el backend real sobre una base abierta en solo lectura.

import sqlite3
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from autoclave.simulador.repeticion import Repeticion
from autoclave.simulador.servidor import crear_app

_CICLO = {
    "id": 76, "numero_ciclo": 76, "tipo_ciclo": "instrumental_121", "nombre_ciclo": "x",
    "lecturas": [
        {"t_s": 0, "codigo": "PV", "temp_camara": 30.0, "pres_camara": 80.0},
        {"t_s": 600, "codigo": "H", "temp_camara": 100.0, "pres_camara": 140.0},
    ],
}


class _Ciclo:
    id = "instrumental_121"
    name = "Instrumental 121"
    number = 1


class _Gestor:
    cycles = {"instrumental_121": _Ciclo()}

    def get_selected_cycle(self):
        return self.cycles["instrumental_121"]


_ESQUEMA = """
CREATE TABLE ciclos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_ciclo INTEGER NOT NULL,
  fecha_inicio TEXT NOT NULL, fecha_fin TEXT, tipo_ciclo TEXT DEFAULT '', nombre_ciclo TEXT DEFAULT '',
  resultado TEXT, operador TEXT DEFAULT '', numero_programa INTEGER, avisos_ticket TEXT DEFAULT '');
CREATE TABLE alarmas_historial (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL,
  nivel TEXT NOT NULL, titulo TEXT NOT NULL, aparecida TEXT NOT NULL);
"""

_FILAS = [   # (inicio, fin, resultado, operador)
    ("2026-01-10T08:00:00", "2026-01-10T09:00:00", "COMPLETADO", "ana"),
    ("2026-01-10T11:00:00", "2026-01-10T12:00:00", "FALLO", "ana"),
    ("2026-01-20T08:00:00", "2026-01-20T09:00:00", "COMPLETADO", "luis"),
    ("2026-02-03T08:00:00", "2026-02-03T09:00:00", "CANCELADO", "luis"),
]


@pytest.fixture
def bd(tmp_path):
    ruta = tmp_path / "autoclave.db"
    c = sqlite3.connect(ruta)
    c.executescript(_ESQUEMA)
    for n, (ini, fin, res, op) in enumerate(_FILAS, 1):
        c.execute("INSERT INTO ciclos (numero_ciclo, fecha_inicio, fecha_fin, tipo_ciclo,"
                  " nombre_ciclo, resultado, operador, numero_programa)"
                  " VALUES (?,?,?,?,?,?,?,?)",
                  (n, ini, fin, "instrumental_121", "Instrumental 121", res, op, 1))
    c.execute("INSERT INTO alarmas_historial (codigo, nivel, titulo, aparecida)"
              " VALUES ('XX_DESCONOCIDA','alta','Alarma x','2026-01-10T11:30:00')")
    c.commit()
    c.close()
    return ruta


def _cliente(bd_ruta):
    app = crear_app(Repeticion(_CICLO), _Gestor(), {"tiempo_standby": {"value": 5}},
                    ahora=lambda: datetime(2026, 3, 1, 10, 0), bd=bd_ruta)
    return TestClient(app)


def test_dashboard_de_un_mes_con_ciclos(bd):
    r = _cliente(bd).get("/report/dashboard", params={"periodo": "mes", "fecha": "2026-01-15"})
    assert r.status_code == 200
    d = r.json()
    assert (d["desde"], d["hasta"]) == ("2026-01-01", "2026-01-31")
    assert d["indicadores"]["total"] == 3
    assert d["indicadores_anterior"] is None            # diciembre sin ciclos
    assert {o["operador"] for o in d["operadores"]} == {"ana", "luis"}
    assert d["alarmas"]


def test_dashboard_anio_y_mes_vacio(bd):
    c = _cliente(bd)
    assert c.get("/report/dashboard", params={"periodo": "anio", "fecha": "2026-06-01"}
                 ).json()["indicadores"]["total"] == 4
    assert c.get("/report/dashboard").json()["indicadores"]["total"] == 0   # marzo 2026


def test_calendario_y_ciclos_del_dia(bd):
    c = _cliente(bd)
    cal = c.get("/report/calendar", params={"periodo": "mes", "fecha": "2026-01-15"}).json()
    assert cal["programa"] == 1 and len(cal["dias"]) == 31
    dia10 = cal["dias"][9]
    assert dia10["fecha"] == "2026-01-10" and dia10["intentos"] == 2 and dia10["exitos"] == 1
    d = c.get("/report/day-cycles", params={"programa": 1, "fecha": "2026-01-10"}).json()
    assert [x["resultado"] for x in d["ciclos"]] == ["COMPLETADO", "FALLO"]
    assert d["ciclos"][0]["programa_numero"] == 1


def test_failures_pagina(bd):
    r = _cliente(bd).get("/report/failures", params={
        "causa": "FALLO", "periodo": "mes", "fecha": "2026-01-15"}).json()
    assert r["total"] == 1 and len(r["ciclos"]) == 1


def test_periodo_invalido_422(bd):
    c = _cliente(bd)
    assert c.get("/report/dashboard", params={"periodo": "decada"}).status_code == 422
    assert c.get("/report/calendar", params={"periodo": "x"}).status_code == 422
    assert c.get("/report/day-cycles").status_code == 422


def test_periodos_del_simulador_aceptan_anio(bd):
    c = _cliente(bd)
    assert c.get("/cycle/list", params={"periodo": "anio"}).status_code == 200
    assert c.get("/report/summary", params={"periodo": "anio"}).status_code == 200


def test_bd_inexistente_responde_vacio_sin_crearla(tmp_path):
    ruta = tmp_path / "no_existe.db"
    c = _cliente(ruta)
    assert c.get("/report/dashboard", params={"periodo": "mes"}).json()["indicadores"]["total"] == 0
    cal = c.get("/report/calendar").json()
    assert cal["programas"] == [] and cal["programa"] is None
    assert c.get("/report/day-cycles", params={"programa": 1}).json()["ciclos"] == []
    assert c.get("/report/failures", params={"causa": "FALLO"}).json()["total"] == 0
    assert c.get("/maintenance").status_code == 200
    assert c.get("/maintenance/records").json() == {"registros": []}
    assert not ruta.exists()
