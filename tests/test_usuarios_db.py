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
    assert rows == 1


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
