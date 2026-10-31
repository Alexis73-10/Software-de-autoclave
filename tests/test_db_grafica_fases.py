# tests/test_db_grafica_fases.py
#
# Tablas de la pantalla de ciclo en curso (planeacion_pantalla_ciclo_en_curso.md
# §6 B2/B3): lecturas_grafica (serie de alta resolución, separada de las
# lecturas del ticket) y ciclo_fases (duración por fase de cada ciclo).

import sqlite3

import pytest

from autoclave.services.domain.logging.db_manager import DbManager


@pytest.fixture
def db(tmp_path):
    d = DbManager(tmp_path / "autoclave.db")
    yield d
    d.close()


def _ciclo(db, tipo="instrumental_134"):
    return db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo=tipo, nombre="x",
                          temp_ester=134, tiempo_ester=7, modelo="", serie="", version_sw="")


def test_lecturas_grafica_guarda_temp_ref_y_tiempo_numerico(db):
    cid = _ciclo(db)
    db.insertar_lectura_grafica(cid, 1.25, "PRE_VACIO", 80.123, 79.5, 101.3)
    filas = db.get_lecturas_grafica(cid)
    assert len(filas) == 1
    f = filas[0]
    assert (f["t_s"], f["fase"], f["temp_camara"], f["temp_ref"], f["pres_camara"]) == (
        1.25, "PRE_VACIO", 80.12, 79.5, 101.3)


def test_lecturas_grafica_admite_sensores_sin_lectura(db):
    cid = _ciclo(db)
    db.insertar_lectura_grafica(cid, 0.0, "PRE_VACIO", None, None, None)
    f = db.get_lecturas_grafica(cid)[0]
    assert (f["temp_camara"], f["temp_ref"], f["pres_camara"]) == (None, None, None)


def test_lecturas_grafica_incremental_por_id(db):
    cid = _ciclo(db)
    otro = _ciclo(db)
    for t in range(5):
        db.insertar_lectura_grafica(cid, float(t), "PRE_VACIO", 1.0, 1.0, 1.0)
    db.insertar_lectura_grafica(otro, 0.0, "PRE_VACIO", 1.0, 1.0, 1.0)
    todas = db.get_lecturas_grafica(cid)
    assert [f["t_s"] for f in todas] == [0.0, 1.0, 2.0, 3.0, 4.0]
    nuevas = db.get_lecturas_grafica(cid, desde_id=todas[2]["id"])
    assert [f["t_s"] for f in nuevas] == [3.0, 4.0]


def test_fases_abrir_y_cerrar(db):
    cid = _ciclo(db)
    db.abrir_fase(cid, "PRE_VACIO", 0.0)
    db.cerrar_fase_abierta(cid, 700.0)
    db.abrir_fase(cid, "CALENTAMIENTO", 700.0)
    filas = [dict(f) for f in db.get_fases_ciclo(cid)]
    assert [(f["fase"], f["inicio_s"], f["fin_s"], f["duracion_s"]) for f in filas] == [
        ("PRE_VACIO", 0.0, 700.0, 700.0),
        ("CALENTAMIENTO", 700.0, None, None),
    ]


def test_cerrar_fase_sin_fase_abierta_no_falla(db):
    cid = _ciclo(db)
    db.cerrar_fase_abierta(cid, 5.0)
    assert db.get_fases_ciclo(cid) == []


def _ciclo_con_fases(db, tipo, resultado, duraciones):
    cid = _ciclo(db, tipo)
    t = 0.0
    for fase, d in duraciones:
        db.abrir_fase(cid, fase, t)
        t += d
        db.cerrar_fase_abierta(cid, t)
    db.cerrar_ciclo(cid, resultado)
    return cid


def test_referencia_es_el_ultimo_completado_del_mismo_programa(db):
    _ciclo_con_fases(db, "instrumental_134", "COMPLETADO", [("PRE_VACIO", 100.0)])
    _ciclo_con_fases(db, "instrumental_134", "COMPLETADO",
                     [("PRE_VACIO", 600.0), ("ESTERILIZACION", 420.0)])
    _ciclo_con_fases(db, "instrumental_134", "CANCELADO", [("PRE_VACIO", 5.0)])
    _ciclo_con_fases(db, "bowe_dick", "COMPLETADO", [("PRE_VACIO", 9.0)])
    assert db.get_duraciones_referencia("instrumental_134") == {
        "PRE_VACIO": 600.0, "ESTERILIZACION": 420.0}


def test_referencia_ignora_completados_sin_registro_de_fases(db):
    _ciclo_con_fases(db, "instrumental_134", "COMPLETADO", [("PRE_VACIO", 600.0)])
    viejo = _ciclo(db, "instrumental_134")   # ciclo de antes de existir ciclo_fases
    db.cerrar_ciclo(viejo, "COMPLETADO")
    assert db.get_duraciones_referencia("instrumental_134") == {"PRE_VACIO": 600.0}


def test_referencia_sin_completados_es_vacia(db):
    _ciclo_con_fases(db, "instrumental_134", "FALLO_CALENTAMIENTO", [("PRE_VACIO", 600.0)])
    assert db.get_duraciones_referencia("instrumental_134") == {}


def test_referencia_suma_fase_repetida(db):
    _ciclo_con_fases(db, "x", "COMPLETADO", [("PRE_VACIO", 10.0), ("PRE_VACIO", 5.0)])
    assert db.get_duraciones_referencia("x") == {"PRE_VACIO": 15.0}


def test_bd_existente_recibe_las_tablas_nuevas(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE ciclos (id INTEGER PRIMARY KEY, numero_ciclo INTEGER NOT NULL,"
                " fecha_inicio TEXT NOT NULL)")
    con.commit()
    con.close()
    d = DbManager(ruta)
    try:
        tablas = {r[0] for r in d._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"lecturas_grafica", "ciclo_fases"} <= tablas
    finally:
        d.close()
