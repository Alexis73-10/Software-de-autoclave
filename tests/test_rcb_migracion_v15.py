"""RCB-05 / RCB-06.4: migración v15 de la base (catálogo de carga, carga del
ciclo, lote y modo de impresión del ciclo) sobre una base v14 con datos."""

import sqlite3

import pytest

from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.db_manager import DbManager

pytestmark = pytest.mark.req("REQ-111")


def _columnas(ruta, tabla):
    conn = sqlite3.connect(str(ruta))
    try:
        return {f[1] for f in conn.execute(f"PRAGMA table_info({tabla})")}
    finally:
        conn.close()


def _indices(ruta):
    conn = sqlite3.connect(str(ruta))
    try:
        return {f[0] for f in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    finally:
        conn.close()


def test_migracion_v15_sobre_base_v14_con_datos(tmp_path, monkeypatch):
    ruta = tmp_path / "v.db"
    with monkeypatch.context() as m:
        m.setattr(dbm, "_MIGRACIONES", tuple(x for x in dbm._MIGRACIONES if x[0] <= 14))
        db = DbManager(db_path=ruta)
        assert db.get_version_esquema() == 14
        i = db.crear_ciclo(numero=7, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                           modelo="M", serie="S", version_sw="1", operador="Ana")
        db.cerrar_ciclo(i, "COMPLETADO")
        db.close()
    assert "lote_carga" not in _columnas(ruta, "ciclos")

    db = DbManager(db_path=ruta)
    assert db.get_version_esquema() == dbm.ESQUEMA_VERSION == 16   # v16: estado_fabrica (modo fábrica)
    fila = db.get_ciclo(i)
    # los datos anteriores no cambian y el ciclo viejo queda sin carga
    assert fila["numero_ciclo"] == 7 and fila["operador"] == "Ana"
    assert fila["resultado"] == "COMPLETADO"
    assert fila["lote_carga"] is None and fila["impresion_carga"] is None
    db.close()

    assert {"id", "codigo", "nombre", "activo", "creado", "modificado",
            "modificado_por"} <= _columnas(ruta, "catalogo_carga")
    assert {"id", "ciclo_id", "codigo", "nombre", "en_catalogo", "cantidad",
            "manual", "orden"} <= _columnas(ruta, "ciclo_carga")
    assert {"idx_ciclo_carga_ciclo", "idx_ciclo_carga_codigo",
            "idx_ciclos_lote_carga"} <= _indices(ruta)

    # idempotente: reabrir no cambia la versión ni falla
    db = DbManager(db_path=ruta)
    assert db.get_version_esquema() == 16
    db.close()


def test_migracion_v15_repetida_no_falla(tmp_path):
    ruta = tmp_path / "v.db"
    db = DbManager(db_path=ruta)
    db.close()
    conn = sqlite3.connect(str(ruta))
    try:
        dbm._migracion_v15(conn)   # segunda aplicación directa
        conn.commit()
    finally:
        conn.close()


def test_catalogo_codigo_unico_y_sin_borrado(tmp_path):
    db = DbManager(db_path=tmp_path / "v.db")
    db.close()
    conn = sqlite3.connect(str(tmp_path / "v.db"))
    try:
        conn.execute("INSERT INTO catalogo_carga (codigo, nombre) VALUES ('A1', 'Pinza')")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO catalogo_carga (codigo, nombre) VALUES ('A1', 'Otra')")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM catalogo_carga")
    finally:
        conn.close()
