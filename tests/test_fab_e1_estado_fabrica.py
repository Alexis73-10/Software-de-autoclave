"""Modo fábrica, Etapa 1 (DF-01, DF-02): tabla `estado_fabrica` (migración v16)
y entrada a FÁBRICA al terminar el asistente.

- Sin fila = ENTREGADO; toda lectura que falle da ENTREGADO.
- La fila no se borra y una fila ENTREGADO no cambia (triggers).
- La migración inserta ENTREGADO si la base ya tiene ciclos o `equipo_instalado`.
- FÁBRICA solo con código de primera instalación, tabla sin fila y base sin
  ciclos ni `equipo_instalado` anterior; en la misma transacción que
  `equipo_instalado`.
- Ningún camino de `src/` ejecuta DROP TRIGGER (P-12).
"""
import re
import sqlite3
from pathlib import Path

import pytest

from autoclave.core.runtime import bitacora
from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.db_manager import DbManager

pytestmark = pytest.mark.req("DF-01", "DF-02", "FAB-01", "FAB-03")

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"

DETALLE = {"serie": "SN260099", "modelo": "AE-45", "version": "x", "zona_horaria": "Z"}


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "autoclave.db"


@pytest.fixture
def db(ruta):
    base = DbManager(ruta)
    yield base
    base.close()


def _fila(ruta):
    con = sqlite3.connect(str(ruta))
    try:
        return con.execute("SELECT estado, fecha_liberacion, hash_paquete, creado "
                           "FROM estado_fabrica").fetchall()
    finally:
        con.close()


def _crear_ciclo(db):
    return db.crear_ciclo(1, "PRUEBA", "Prueba", 121.0, 15.0, "AE-45", "SN260099", "x")


def _base_v15(ruta, preparar):
    """Base que llega a v16 desde v15 (sin la tabla): se crea, se prepara con
    `preparar(db)` y se le quita la tabla nueva (DROP TABLE solo en la prueba)."""
    db = DbManager(ruta)
    try:
        preparar(db)
    finally:
        db.close()
    con = sqlite3.connect(str(ruta))
    try:
        con.execute("DROP TABLE estado_fabrica")
        con.execute("PRAGMA user_version = 15")
        con.commit()
    finally:
        con.close()


def _entrar(db, primera=True):
    return db.entrar_modo_fabrica_e_instalar(primera_instalacion=primera, entidad="SN260099",
                                             detalle=DETALLE)


# ── migración v16 ─────────────────────────────────────────────────────────────

def test_esquema_v16(db):
    assert dbm.ESQUEMA_VERSION == 16
    assert db.get_version_esquema() == 16


def test_base_nueva_queda_sin_fila_y_lee_entregado(db, ruta):
    assert _fila(ruta) == []
    assert db.estado_fabrica() == "ENTREGADO"


def test_migracion_con_ciclos_inserta_entregado(ruta):
    _base_v15(ruta, _crear_ciclo)
    db = DbManager(ruta)
    try:
        assert db.estado_fabrica() == "ENTREGADO"
    finally:
        db.close()
    filas = _fila(ruta)
    assert len(filas) == 1 and filas[0][0] == "ENTREGADO" and filas[0][3]


def test_migracion_con_equipo_instalado_inserta_entregado(ruta):
    _base_v15(ruta, lambda db: db.registrar_auditoria("equipo_instalado", usuario="sistema",
                                                       entidad="SN1", detalle=DETALLE))
    db = DbManager(ruta)
    db.close()
    assert [f[0] for f in _fila(ruta)] == ["ENTREGADO"]


def test_migracion_de_base_vacia_no_inserta(ruta):
    _base_v15(ruta, lambda db: None)
    db = DbManager(ruta)
    db.close()
    assert _fila(ruta) == []


def test_trigger_impide_borrar_la_fila(db, ruta):
    assert _entrar(db) == "FABRICA"
    con = sqlite3.connect(str(ruta))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("DELETE FROM estado_fabrica")
    finally:
        con.close()
    assert db.estado_fabrica() == "FABRICA"


def test_trigger_impide_modificar_entregado(ruta):
    _base_v15(ruta, _crear_ciclo)
    DbManager(ruta).close()
    con = sqlite3.connect(str(ruta))
    con.execute("PRAGMA recursive_triggers = ON")
    try:
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("UPDATE estado_fabrica SET estado = 'FABRICA'")
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("UPDATE estado_fabrica SET hash_paquete = 'x'")
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("INSERT OR REPLACE INTO estado_fabrica (id, estado, creado) "
                        "VALUES (1, 'FABRICA', 'x')")
    finally:
        con.close()
    assert [f[0] for f in _fila(ruta)] == ["ENTREGADO"]


def test_fabrica_si_puede_pasar_a_entregado(db, ruta):
    """El sentido único FÁBRICA → ENTREGADO lo usará el cierre (Etapa 5)."""
    assert _entrar(db) == "FABRICA"
    con = sqlite3.connect(str(ruta))
    try:
        con.execute("UPDATE estado_fabrica SET estado = 'ENTREGADO', fecha_liberacion = 'hoy'")
        con.commit()
    finally:
        con.close()
    assert db.estado_fabrica() == "ENTREGADO"


def test_check_rechaza_otro_estado_y_otro_id(db, ruta):
    con = sqlite3.connect(str(ruta))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO estado_fabrica (id, estado, creado) VALUES (1, 'OTRO', 'x')")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO estado_fabrica (id, estado, creado) VALUES (2, 'ENTREGADO', 'x')")
    finally:
        con.close()


def test_trigger_impide_insertar_fabrica_en_base_usada(db, ruta):
    """Defensa en profundidad de DF-02: ni a mano entra FÁBRICA con ciclos."""
    _crear_ciclo(db)
    con = sqlite3.connect(str(ruta))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("INSERT INTO estado_fabrica (id, estado, creado) VALUES (1, 'FABRICA', 'x')")
    finally:
        con.close()


def test_estado_fabrica_nunca_lanza(db):
    db._conn.close()
    assert db.estado_fabrica() == "ENTREGADO"


def test_valor_desconocido_es_entregado(db, monkeypatch):
    class _Con:
        def execute(self, *_a):
            class _C:
                def fetchone(self):
                    return ("RARO",)
            return _C()
    monkeypatch.setattr(db, "_conn", _Con())
    assert db.estado_fabrica() == "ENTREGADO"


def test_src_no_tiene_drop_trigger():
    """P-12: ningún camino del código quita un trigger."""
    patron = re.compile(r"DROP\s+TRIGGER", re.IGNORECASE)
    culpables = [str(p.relative_to(SRC)) for p in SRC.rglob("*.py")
                 if patron.search(p.read_text(encoding="utf-8"))]
    assert culpables == []


# ── entrada (DF-02) ───────────────────────────────────────────────────────────

def _eventos(db):
    return [f["evento"] for f in db.get_auditoria(limite=100)]


def test_primera_instalacion_en_base_nueva_entra_en_fabrica(db, ruta):
    assert _entrar(db) == "FABRICA"
    assert db.estado_fabrica() == "FABRICA"
    assert _eventos(db) == ["equipo_instalado"]
    fila = _fila(ruta)[0]
    assert fila[0] == "FABRICA" and fila[1] is None and fila[2] is None and fila[3]


def test_reinstalacion_no_entra_en_fabrica(db, ruta):
    assert _entrar(db, primera=False) == "ENTREGADO"
    assert _fila(ruta) == []
    assert _eventos(db) == ["equipo_instalado"]


def test_base_con_ciclos_no_entra_en_fabrica(db, ruta):
    _crear_ciclo(db)
    assert _entrar(db) == "ENTREGADO"
    assert _fila(ruta) == []
    assert _eventos(db) == ["equipo_instalado"]


def test_base_con_equipo_instalado_previo_no_entra(db, ruta):
    db.registrar_auditoria("equipo_instalado", usuario="sistema", entidad="SN1", detalle=DETALLE)
    assert _entrar(db) == "ENTREGADO"
    assert _fila(ruta) == []
    assert _eventos(db) == ["equipo_instalado", "equipo_instalado"]


def test_tabla_con_fila_entregado_no_cambia(ruta):
    _base_v15(ruta, _crear_ciclo)
    db = DbManager(ruta)
    try:
        assert _entrar(db) == "ENTREGADO"
    finally:
        db.close()
    assert [f[0] for f in _fila(ruta)] == ["ENTREGADO"]


def test_tabla_con_fila_fabrica_no_cambia_ni_duplica(db, ruta):
    assert _entrar(db) == "FABRICA"
    # segunda llamada: ya hay fila y ya hay equipo_instalado
    assert _entrar(db) == "FABRICA"
    assert len(_fila(ruta)) == 1


def test_un_error_al_insertar_fabrica_deja_solo_equipo_instalado(db, ruta, monkeypatch):
    real = db._conn

    class _Con:
        """Falla en el INSERT de estado_fabrica; lo demás va a la conexión real."""
        def __getattr__(self, nombre):
            return getattr(real, nombre)

        def execute(self, sql, *args):
            if "INSERT INTO estado_fabrica" in sql:
                raise sqlite3.OperationalError("disco lleno")
            return real.execute(sql, *args)

    monkeypatch.setattr(db, "_conn", _Con())
    assert _entrar(db) == "ENTREGADO"
    monkeypatch.setattr(db, "_conn", real)
    assert _fila(ruta) == []
    assert _eventos(db) == ["equipo_instalado"]


def test_con_la_instalacion_suprimida_no_escribe_nada(db, ruta):
    db.instalacion_en_curso = lambda: True
    assert _entrar(db) == "ENTREGADO"
    db.instalacion_en_curso = None
    assert _fila(ruta) == []
    assert _eventos(db) == []


# ── evento de la Etapa 5 ──────────────────────────────────────────────────────

def test_evento_equipo_liberado_fabrica_clasificado():
    assert "equipo_liberado_fabrica" in bitacora.EVENTOS
    assert bitacora.categoria_de("equipo_liberado_fabrica") == "sistema"
    assert bitacora.se_registra("equipo_liberado_fabrica")


def test_evento_equipo_liberado_fabrica_con_textos():
    import json
    for idioma in ("es", "en"):
        datos = json.loads((SRC / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        b = datos["bitacora"]
        assert b["ev"]["equipo_liberado_fabrica"]
        assert b["tipo"]["equipo_liberado_fabrica"]
