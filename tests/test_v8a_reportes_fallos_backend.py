# tests/test_v8a_reportes_fallos_backend.py
#
# D8-5.6 (tanda 8): en Reportes, tocar un tipo de fallo del resumen despliega
# los ciclos del periodo con ese fallo, paginados. Backend: GET /report/failures
# y DbManager.get_ciclos_con_resultado. Solo lectura.

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers.backend_doble import parche_en_backend

_HOY = "2026-10-02T00:00:00"


def _crear(db, tipo="instrumental_134", nombre="Instrumental 134"):
    return db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo=tipo, nombre=nombre,
                          temp_ester=134, tiempo_ester=4, modelo="", serie="", version_sw="")


def _fechas(db, cid, inicio, fin=None, resultado=None, operador=None):
    with db._lock:
        db._conn.execute("UPDATE ciclos SET fecha_inicio=?, fecha_fin=?, resultado=?, operador=?"
                         " WHERE id=?", (inicio, fin, resultado, operador or "", cid))
        db._conn.commit()


@pytest.fixture
def db(tmp_path):
    d = DbManager(tmp_path / "a.db")
    yield d
    d.close()


@pytest.fixture
def cliente(db):
    ctx = MagicMock()
    ctx.db = db
    ctx.cycle_manager.cycles = {"instrumental_134": SimpleNamespace(number=2)}
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    with parche_en_backend("_inicio_del_dia", MagicMock(return_value=_HOY)):
        yield TestClient(srv.app)


# ── consulta en DbManager ────────────────────────────────────────────────

def test_db_filtra_por_resultado_y_periodo_por_fecha_de_inicio(db):
    a = _crear(db); _fechas(db, a, "2026-09-02T08:00:00", "2026-09-02T08:40:00", "FALLO_SECADO")
    b = _crear(db); _fechas(db, b, "2026-09-03T08:00:00", "2026-09-03T08:40:00", "FALLO_PRES_BAJA")
    c = _crear(db); _fechas(db, c, "2026-09-04T08:00:00", "2026-09-04T08:40:00", "FALLO_SECADO")
    d = _crear(db); _fechas(db, d, "2026-10-01T08:00:00", "2026-10-01T08:40:00", "FALLO_SECADO")  # fuera
    filas, total = db.get_ciclos_con_resultado("2026-09-01T00:00:00", "2026-10-01T00:00:00",
                                               "FALLO_SECADO", limite=10, desplazamiento=0)
    assert total == 2
    assert [f["id"] for f in filas] == [c, a]          # más recientes primero


def test_db_pagina_con_limite_y_desplazamiento(db):
    ids = []
    for i in range(5):
        cid = _crear(db)
        _fechas(db, cid, f"2026-09-0{i + 1}T08:00:00", None, "FALLO_SECADO")
        ids.append(cid)
    filas, total = db.get_ciclos_con_resultado("2026-09-01T00:00:00", "2026-10-01T00:00:00",
                                               "FALLO_SECADO", limite=2, desplazamiento=2)
    assert total == 5
    assert [f["id"] for f in filas] == [ids[2], ids[1]]


# ── GET /report/failures ─────────────────────────────────────────────────

def test_endpoint_ciclos_de_un_fallo(cliente, db):
    a = _crear(db)
    _fechas(db, a, "2026-09-02T08:00:00", "2026-09-02T08:40:00", "FALLO_SECADO", "Ana Pérez")
    _fechas(db, _crear(db), "2026-09-03T08:00:00", "2026-09-03T08:40:00", "COMPLETADO")
    r = cliente.get("/report/failures", params={"periodo": "mes", "fecha": "2026-09-15",
                                                "causa": "FALLO_SECADO"})
    assert r.status_code == 200
    j = r.json()
    assert (j["periodo"], j["desde"], j["hasta"], j["causa"]) == ("mes", "2026-09-01", "2026-09-30",
                                                                  "FALLO_SECADO")
    assert (j["total"], j["pagina"], j["paginas"]) == (1, 1, 1)
    assert len(j["ciclos"]) == 1
    c = j["ciclos"][0]
    assert c["id"] == a and c["numero_ciclo"] == 1 and c["programa_numero"] == 2
    assert c["programa_nombre"] == "Instrumental 134" and c["operador"] == "Ana Pérez"
    assert c["fecha_inicio"] == "2026-09-02T08:00:00" and c["resultado"] == "FALLO_SECADO"


def test_endpoint_paginado(cliente, db):
    for i in range(25):
        _fechas(db, _crear(db), f"2026-09-{i + 1:02d}T08:00:00", None, "FALLO_SECADO")
    p1 = cliente.get("/report/failures", params={"periodo": "mes", "fecha": "2026-09-15",
                                                 "causa": "FALLO_SECADO", "por_pagina": 10}).json()
    assert (p1["total"], p1["pagina"], p1["paginas"], p1["por_pagina"]) == (25, 1, 3, 10)
    assert [c["numero_ciclo"] for c in p1["ciclos"]] == list(range(25, 15, -1))
    p3 = cliente.get("/report/failures", params={"periodo": "mes", "fecha": "2026-09-15",
                                                 "causa": "FALLO_SECADO", "por_pagina": 10,
                                                 "pagina": 3}).json()
    assert [c["numero_ciclo"] for c in p3["ciclos"]] == [5, 4, 3, 2, 1]


def test_endpoint_pagina_fuera_de_rango_va_a_la_ultima(cliente, db):
    for i in range(3):
        _fechas(db, _crear(db), f"2026-09-0{i + 1}T08:00:00", None, "FALLO_SECADO")
    j = cliente.get("/report/failures", params={"periodo": "mes", "fecha": "2026-09-15",
                                                "causa": "FALLO_SECADO", "por_pagina": 2,
                                                "pagina": 9}).json()
    assert (j["pagina"], j["paginas"]) == (2, 2) and len(j["ciclos"]) == 1


def test_endpoint_sin_ciclos(cliente):
    j = cliente.get("/report/failures", params={"periodo": "dia", "causa": "FALLO_SECADO"}).json()
    assert (j["total"], j["pagina"], j["paginas"], j["ciclos"]) == (0, 1, 1, [])
    assert j["desde"] == "2026-10-02"


def test_endpoint_valida_parametros(cliente):
    assert cliente.get("/report/failures", params={"periodo": "mes"}).status_code == 422   # sin causa
    assert cliente.get("/report/failures", params={"periodo": "anio", "causa": "X"}).status_code == 422
    assert cliente.get("/report/failures", params={"causa": "X", "pagina": 0}).status_code == 422
    assert cliente.get("/report/failures", params={"causa": "X", "por_pagina": 500}).status_code == 422
