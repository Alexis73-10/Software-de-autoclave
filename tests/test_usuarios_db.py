import pytest
import hashlib
from autoclave.services.domain.logging.db_manager import DbManager


@pytest.fixture
def db(tmp_path):
    return DbManager(db_path=tmp_path / "test.db")


def test_init_crea_tabla_usuarios(db):
    # No lanza excepción — tabla existe
    db._conn.execute("SELECT * FROM usuarios").fetchall()


def test_seed_admin_crea_usuario_por_defecto(db):
    user = db.get_usuario_by_username("admin")
    assert user is not None
    assert user["rol"] == "admin"
    assert user["activo"] == 1


def test_seed_admin_no_duplica_al_reiniciar_db(tmp_path):
    db1 = DbManager(db_path=tmp_path / "test.db")
    db2 = DbManager(db_path=tmp_path / "test.db")
    rows = db2._conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    assert rows == 2   # admin e ingeniero (planeacion_backend_autenticacion.md, decisión 5)


def test_crear_usuario_retorna_id(db):
    h = hashlib.sha256("pass123".encode()).hexdigest()
    uid = db.crear_usuario("Juan Pérez", "juanp", h, "operador")
    assert isinstance(uid, int)
    assert uid >= 1


def test_get_usuario_by_username_existe(db):
    h = hashlib.sha256("pass123".encode()).hexdigest()
    db.crear_usuario("Juan Pérez", "juanp", h, "operador")
    user = db.get_usuario_by_username("juanp")
    assert user["nombre"] == "Juan Pérez"
    assert user["rol"] == "operador"


def test_get_usuario_by_username_no_existe(db):
    assert db.get_usuario_by_username("fantasma") is None


def test_get_usuario_inactivo_no_se_devuelve(db):
    h = hashlib.sha256("pass".encode()).hexdigest()
    db.crear_usuario("Inactivo", "inactivo", h, "operador", activo=0)
    assert db.get_usuario_by_username("inactivo") is None


def test_get_ciclos_rango_sin_registros(db):
    assert db.get_ciclos_rango() == []


def test_get_ciclos_rango_filtra_por_fecha(db):
    db._conn.execute(
        "INSERT INTO ciclos (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,"
        " temp_esterilizacion, tiempo_esterilizacion, modelo, serie, version_sw)"
        " VALUES (1,'2026-06-01T10:00:00','user','Ciclo A',134.0,3.5,'M','S','1.0')"
    )
    db._conn.execute(
        "INSERT INTO ciclos (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,"
        " temp_esterilizacion, tiempo_esterilizacion, modelo, serie, version_sw)"
        " VALUES (2,'2026-06-15T10:00:00','user','Ciclo B',134.0,3.5,'M','S','1.0')"
    )
    db._conn.commit()
    rows = db.get_ciclos_rango(desde="2026-06-10", hasta="2026-06-20")
    assert len(rows) == 1
    assert rows[0]["numero_ciclo"] == 2


def test_init_no_rompe_datos_existentes(tmp_path):
    db1 = DbManager(db_path=tmp_path / "test.db")
    h = hashlib.sha256("pass".encode()).hexdigest()
    db1.crear_usuario("Test", "testuser", h)
    db2 = DbManager(db_path=tmp_path / "test.db")
    assert db2.get_usuario_by_username("testuser") is not None


# ── Nuevo usuario (planeacion_nuevo_usuario.md, F1) ──────────────────────────

import sqlite3
from datetime import datetime


def _h(pw="pass1234"):
    return hashlib.sha256(pw.encode()).hexdigest()


def test_migracion_agrega_columnas_auditoria_sin_perder_filas(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute(
        "CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " nombre TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL, hash_pw TEXT NOT NULL,"
        " rol TEXT DEFAULT 'operador', activo INTEGER DEFAULT 1)"
    )
    con.execute(
        "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo)"
        " VALUES ('Viejo', 'viejo', 'x', 'admin', 1)"
    )
    con.commit()
    con.close()

    db = DbManager(db_path=ruta)
    columnas = {r["name"] for r in db._conn.execute("PRAGMA table_info(usuarios)")}
    assert {"creado_por", "creado_en", "codigo_creacion"} <= columnas
    viejo = db.get_usuario_by_username("viejo")
    assert viejo["nombre"] == "Viejo"
    assert viejo["creado_por"] == ""
    assert viejo["creado_en"] == ""
    assert viejo["codigo_creacion"] == ""


def test_base_nueva_trae_columnas_auditoria(db):
    columnas = {r["name"] for r in db._conn.execute("PRAGMA table_info(usuarios)")}
    assert {"creado_por", "creado_en", "codigo_creacion"} <= columnas


def test_migracion_es_idempotente(tmp_path):
    DbManager(db_path=tmp_path / "t.db")
    DbManager(db_path=tmp_path / "t.db")   # segunda vez: columnas ya existen, no falla


def test_crear_usuario_guarda_auditoria(db):
    antes = datetime.now().isoformat()
    db.crear_usuario("Ana Ruiz", "anar", _h(), "tecnico",
                     creado_por="admin", codigo_creacion="ABC123")
    user = db.get_usuario_by_username("anar")
    assert user["creado_por"] == "admin"
    assert user["codigo_creacion"] == "ABC123"
    assert antes <= user["creado_en"] <= datetime.now().isoformat()
    datetime.fromisoformat(user["creado_en"])   # mismo formato que fecha_inicio


def test_crear_usuario_firma_anterior_sigue_funcionando(db):
    db.crear_usuario("Sin Auditoria", "sinaud", _h(), "operador", 1)
    user = db.get_usuario_by_username("sinaud")
    assert user["creado_por"] == ""
    assert user["codigo_creacion"] == ""


def test_crear_usuario_duplicado_propaga_integrity_error(db):
    db.crear_usuario("Uno", "dup", _h())
    with pytest.raises(sqlite3.IntegrityError):
        db.crear_usuario("Dos", "dup", _h())


def test_existe_usuario_activo(db):
    db.crear_usuario("Juan", "juan", _h())
    assert db.existe_usuario("juan") is True


def test_existe_usuario_inactivo(db):
    db.crear_usuario("Inactivo", "inact", _h(), activo=0)
    assert db.existe_usuario("inact") is True


def test_existe_usuario_sin_distinguir_mayusculas(db):
    db.crear_usuario("Juan", "Juan", _h())
    assert db.existe_usuario("juan") is True
    assert db.existe_usuario("JUAN") is True


def test_existe_usuario_no_existe(db):
    assert db.existe_usuario("fantasma") is False


def test_existe_usuario_mayusculas_no_ascii(db):
    # LOWER/NOCASE de SQLite solo pliegan ASCII; el teclado QML tiene Ñ
    db.crear_usuario("Peña", "PEÑA", _h())
    assert db.existe_usuario("peña") is True
