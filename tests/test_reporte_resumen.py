# tests/test_reporte_resumen.py
#
# Resumen de ciclos por periodo (pantalla Reportes): conteo agrupado en
# DbManager, cálculo del resumen (services/domain/reportes/resumen_periodo.py)
# y su ticket para la impresora térmica.

import pytest

from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.reportes import resumen_periodo as rp


def _crear(db, inicio, resultado, tipo="instrumental_134", nombre="Instrumental 134"):
    cid = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo=tipo, nombre=nombre,
                         temp_ester=134, tiempo_ester=4, modelo="", serie="", version_sw="")
    with db._lock:
        db._conn.execute("UPDATE ciclos SET fecha_inicio=?, resultado=? WHERE id=?",
                         (inicio, resultado, cid))
        db._conn.commit()
    return cid


@pytest.fixture
def db(tmp_path):
    d = DbManager(tmp_path / "a.db")
    yield d
    d.close()


# ── conteo en la base ────────────────────────────────────────────────────

def test_conteo_agrupado_por_programa_y_resultado_dentro_del_periodo(db):
    _crear(db, "2026-08-31T23:59:00", "COMPLETADO")                       # fuera (antes)
    _crear(db, "2026-09-01T08:00:00", "COMPLETADO")
    _crear(db, "2026-09-02T08:00:00", "COMPLETADO")
    _crear(db, "2026-09-03T08:00:00", "FALLO_SECADO", "bowe_dick", "Bowie & Dick")
    _crear(db, "2026-09-04T08:00:00", None, "bowe_dick", "Bowie & Dick")  # sin cierre
    _crear(db, "2026-10-01T00:00:00", "COMPLETADO")                       # fuera (tope)
    filas = db.get_conteo_resultados("2026-09-01T00:00:00", "2026-10-01T00:00:00")
    assert sorted((f["tipo_ciclo"], f["resultado"], f["cantidad"]) for f in filas
                  if f["resultado"] is not None) == [
        ("bowe_dick", "FALLO_SECADO", 1), ("instrumental_134", "COMPLETADO", 2)]
    assert [f["cantidad"] for f in filas if f["resultado"] is None] == [1]


# ── cálculo del resumen ──────────────────────────────────────────────────

def _fila(tipo, nombre, resultado, cantidad):
    return {"tipo_ciclo": tipo, "nombre_ciclo": nombre, "resultado": resultado, "cantidad": cantidad}


def test_resumen_totales_por_programa_y_causas():
    r = rp.resumir([
        _fila("instrumental_134", "Instrumental 134", "COMPLETADO", 5),
        _fila("instrumental_134", "Instrumental 134", "FALLO_ESTERILIZACION", 2),
        _fila("instrumental_134", "Instrumental 134", "CANCELADO", 1),
        _fila("bowe_dick", "Bowie & Dick", "COMPLETADO", 1),
        _fila("bowe_dick", "Bowie & Dick", "EMERGENCIA", 2),
        _fila("bowe_dick", "Bowie & Dick", "FALLO_ESTERILIZACION", 1),
        _fila("bowe_dick", "Bowie & Dick", None, 1),
        _fila("bowe_dick", "Bowie & Dick", "SECADO", 1),   # fase en curso: sin cierre
    ], numeros={"instrumental_134": 2, "bowe_dick": 1})
    assert r["totales"] == {"total": 14, "completados": 6, "fallos": 5, "cancelados": 1, "sin_cierre": 2}
    assert r["por_programa"] == [   # de más a menos ciclos
        {"programa_id": "instrumental_134", "programa_nombre": "Instrumental 134", "programa_numero": 2,
         "total": 8, "completados": 5, "fallos": 2, "cancelados": 1, "sin_cierre": 0},
        {"programa_id": "bowe_dick", "programa_nombre": "Bowie & Dick", "programa_numero": 1,
         "total": 6, "completados": 1, "fallos": 3, "cancelados": 0, "sin_cierre": 2},
    ]
    # de la más frecuente a la menos; empate por nombre
    assert r["causas_fallo"] == [{"causa": "FALLO_ESTERILIZACION", "cantidad": 3},
                                 {"causa": "EMERGENCIA", "cantidad": 2}]


def test_resumen_vacio():
    r = rp.resumir([], numeros={})
    assert r["totales"] == {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0, "sin_cierre": 0}
    assert r["por_programa"] == [] and r["causas_fallo"] == []


def test_programa_sin_numero_ni_nombre():
    r = rp.resumir([_fila("borrado", "", "COMPLETADO", 1)], numeros={})
    p = r["por_programa"][0]
    assert p["programa_numero"] is None and p["programa_nombre"] == "borrado"


# ── ticket ───────────────────────────────────────────────────────────────

def test_ticket_del_resumen():
    r = rp.resumir([
        _fila("instrumental_134", "Instrumental 134", "COMPLETADO", 2),
        _fila("instrumental_134", "Instrumental 134", "FALLO_SECADO", 1),
    ], numeros={"instrumental_134": 2})
    texto = rp.format_ticket_resumen(r, desde="2026-09-01", hasta="2026-09-30",
                                     serie="SPK-1", modelo="AVH-450")
    lineas = texto.split("\n")
    assert "RESUMEN DE CICLOS" in lineas
    assert "Desde: 01/09/2026" in lineas and "Hasta: 30/09/2026" in lineas
    assert "Num serie: SPK-1" in lineas
    assert "Total: 3" in lineas
    assert "Completados: 2 (67%)" in lineas
    assert "Fallo: 1 (33%)" in lineas
    assert "Cancelados: 0 (0%)" in lineas
    assert "02 Instrumental 134" in lineas
    assert "FALLO_SECADO: 1" in lineas
    # ancho del papel: ninguna línea pasa de 24 caracteres (como el ticket del ciclo)
    assert max(len(l) for l in lineas) <= 24
    assert texto.endswith("\n" * 5)   # avance de papel para cortar


def test_ticket_sin_ciclos():
    texto = rp.format_ticket_resumen(rp.resumir([], numeros={}), desde="2026-10-06",
                                     hasta="2026-10-06", serie="", modelo="")
    assert "Total: 0" in texto and "Sin ciclos en el periodo" in texto
