# tools/generador/db.py
#
# Base propia del generador de códigos (`generador.db`, NO la del software del
# autoclave). G1 (tanda 2): SQLite en modo WAL con busy_timeout, porque varios
# usuarios entran a la vez desde la red local; tabla `usuarios` con cuentas
# individuales. `codigos_generados` no cambia: los registros históricos (p. ej.
# con usuario "especifika") se conservan tal cual.

import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "generador.db"
BUSY_TIMEOUT_MS = 5000
ROLES = ("admin", "usuario")


def conectar(ruta: Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(ruta or DB_PATH, timeout=BUSY_TIMEOUT_MS / 1000)
    con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """Crea o migra la base (idempotente). WAL queda persistente en el archivo."""
    with conectar() as con:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("""
            CREATE TABLE IF NOT EXISTS codigos_generados (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                serial  TEXT NOT NULL,
                tipo    TEXT NOT NULL CHECK(tipo IN ('instalacion', 'reinstalacion', 'fabrica')),
                fecha   TEXT NOT NULL,
                usuario TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario       TEXT PRIMARY KEY,
                hash          TEXT NOT NULL,
                rol           TEXT NOT NULL CHECK(rol IN ('admin', 'usuario')),
                activo        INTEGER NOT NULL DEFAULT 1,
                creado        TEXT NOT NULL,
                debe_cambiar  INTEGER NOT NULL DEFAULT 1
            )
        """)
    con.close()


# ── Códigos ─────────────────────────────────────────────────────────────────

def fue_instalado(serial: str) -> bool:
    with conectar() as con:
        row = con.execute(
            "SELECT 1 FROM codigos_generados "
            "WHERE serial = ? AND tipo IN ('instalacion', 'reinstalacion') LIMIT 1",
            (serial,)
        ).fetchone()
    con.close()
    return row is not None


def log_codigo(serial: str, tipo: str, usuario: str, day: date | None = None):
    fecha = (day or date.today()).isoformat()
    with conectar() as con:
        con.execute(
            "INSERT INTO codigos_generados (serial, tipo, fecha, usuario) VALUES (?, ?, ?, ?)",
            (serial, tipo, fecha, usuario)
        )
    con.close()


def get_history(serial: str) -> list[dict]:
    with conectar() as con:
        rows = con.execute(
            "SELECT tipo, fecha, usuario FROM codigos_generados "
            "WHERE serial = ? ORDER BY fecha DESC, id DESC",
            (serial,)
        ).fetchall()
    con.close()
    return [{"tipo": r[0], "fecha": r[1], "usuario": r[2]} for r in rows]


# ── Usuarios ────────────────────────────────────────────────────────────────

def hay_usuarios() -> bool:
    with conectar() as con:
        row = con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone()
    con.close()
    return row is not None


def crear_usuario(usuario: str, hash_clave: str, rol: str, debe_cambiar: bool = True) -> None:
    if rol not in ROLES:
        raise ValueError(f"rol inválido: {rol!r}")
    with conectar() as con:
        con.execute(
            "INSERT INTO usuarios (usuario, hash, rol, activo, creado, debe_cambiar) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (usuario, hash_clave, rol, datetime.now().isoformat(timespec="seconds"),
             1 if debe_cambiar else 0))
    con.close()


def obtener_usuario(usuario: str) -> dict | None:
    with conectar() as con:
        row = con.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
    con.close()
    return dict(row) if row else None


def listar_usuarios() -> list[dict]:
    with conectar() as con:
        rows = con.execute("SELECT usuario, rol, activo, creado, debe_cambiar "
                           "FROM usuarios ORDER BY usuario").fetchall()
    con.close()
    return [dict(r) for r in rows]


def fijar_clave(usuario: str, hash_clave: str, debe_cambiar: bool) -> None:
    with conectar() as con:
        con.execute("UPDATE usuarios SET hash = ?, debe_cambiar = ? WHERE usuario = ?",
                    (hash_clave, 1 if debe_cambiar else 0, usuario))
    con.close()


def fijar_activo(usuario: str, activo: bool) -> None:
    with conectar() as con:
        con.execute("UPDATE usuarios SET activo = ? WHERE usuario = ?",
                    (1 if activo else 0, usuario))
    con.close()


def contar_admins_activos() -> int:
    with conectar() as con:
        n = con.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'admin' AND activo = 1").fetchone()[0]
    con.close()
    return n
