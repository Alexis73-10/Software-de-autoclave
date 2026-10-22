# Migración v1 con PRAGMA user_version y bitácora audit_log
# (planeacion_backend_autenticacion.md T-21 y §5.10; planeacion_backend_parametros.md
# §7 y §10).

import sqlite3

import pytest

from autoclave.services.domain.logging import db_manager
from autoclave.services.domain.logging.db_manager import DbManager


def _columnas(db, tabla):
    return {r["name"] for r in db._conn.execute(f"PRAGMA table_info({tabla})")}


def test_base_nueva_queda_en_v1_con_audit_log(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION == 9   # v9: O2b (operadores)
    assert _columnas(db, "audit_log") == {
        "id", "ts", "usuario", "rol", "evento", "entidad",
        "valor_anterior", "valor_nuevo", "detalle"}


def test_base_v0_existente_migra_sin_perder_datos(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,"
                " usuario TEXT UNIQUE NOT NULL, hash_pw TEXT NOT NULL, rol TEXT DEFAULT 'operador',"
                " activo INTEGER DEFAULT 1)")
    con.execute("INSERT INTO usuarios (nombre, usuario, hash_pw, rol) VALUES ('V','viejo','x','tecnico')")
    con.commit()
    assert con.execute("PRAGMA user_version").fetchone()[0] == 0
    con.close()

    db = DbManager(db_path=ruta)
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION
    assert db.get_usuario_by_username("viejo")["debe_cambiar_clave"] == 0
    assert db.get_auditoria() == []
    # con usuarios previos no se siembra nada
    assert db.get_usuario_by_username("admin") is None


def test_migracion_idempotente(tmp_path):
    db1 = DbManager(db_path=tmp_path / "t.db")
    db1.registrar_auditoria("login_ok", usuario="ana")
    db2 = DbManager(db_path=tmp_path / "t.db")
    assert db2.get_version_esquema() == db_manager.ESQUEMA_VERSION
    assert len(db2.get_auditoria()) == 1


def test_migracion_fallida_se_revierte_entera(tmp_path, monkeypatch):
    def rota(conn):
        conn.execute("CREATE TABLE a_medias (x INTEGER)")
        raise RuntimeError("falla a mitad")

    monkeypatch.setattr(db_manager, "_MIGRACIONES", ((1, rota),))
    with pytest.raises(RuntimeError):
        DbManager(db_path=tmp_path / "t.db")

    con = sqlite3.connect(tmp_path / "t.db")
    assert con.execute("PRAGMA user_version").fetchone()[0] == 0
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a_medias" not in tablas


def test_registrar_y_leer_auditoria(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    db.registrar_auditoria("param_ciclo_cambio", usuario="ing1", rol="ingeniero",
                           entidad="instrumental_134/secado/tiempo_secado",
                           valor_anterior=10.0, valor_nuevo=20.0,
                           detalle={"ciclo": 12, "fase": "SECADO", "aplica": "siguiente"})
    db.registrar_auditoria("login_fallido", usuario="ana")
    filas = db.get_auditoria()
    assert [f["evento"] for f in filas] == ["login_fallido", "param_ciclo_cambio"]   # reciente primero
    f = db.get_auditoria(evento="param_ciclo_cambio")[0]
    assert (f["usuario"], f["rol"], f["valor_anterior"], f["valor_nuevo"]) == (
        "ing1", "ingeniero", "10.0", "20.0")
    assert f["detalle"] == {"ciclo": 12, "fase": "SECADO", "aplica": "siguiente"}
    assert f["ts"][:4].isdigit() and "T" in f["ts"]
    assert db.get_auditoria(entidad="otra") == []
    assert db.get_auditoria(evento="login_fallido")[0]["detalle"] is None


def test_tablas_historicas_siguen_existiendo(tmp_path):
    # sensor_calibration_audit y cycle_params_audit conservan su creación propia
    from autoclave.services.domain.logging.cycle_params_audit import CycleParamsAuditDB
    from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
    ruta = tmp_path / "t.db"
    DbManager(db_path=ruta)
    SensorCalibrationAuditDB(db_path=ruta)
    CycleParamsAuditDB(db_path=ruta)
    con = sqlite3.connect(ruta)
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"audit_log", "sensor_calibration_audit", "cycle_params_audit"} <= tablas
