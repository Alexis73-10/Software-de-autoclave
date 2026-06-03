import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent / "generador.db"


def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS codigos_generados (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                serial  TEXT NOT NULL,
                tipo    TEXT NOT NULL CHECK(tipo IN ('instalacion', 'reinstalacion', 'fabrica')),
                fecha   TEXT NOT NULL,
                usuario TEXT NOT NULL
            )
        """)


def fue_instalado(serial: str) -> bool:
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT 1 FROM codigos_generados "
            "WHERE serial = ? AND tipo IN ('instalacion', 'reinstalacion') LIMIT 1",
            (serial,)
        ).fetchone()
    return row is not None


def log_codigo(serial: str, tipo: str, usuario: str, day: date | None = None):
    fecha = (day or date.today()).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO codigos_generados (serial, tipo, fecha, usuario) VALUES (?, ?, ?, ?)",
            (serial, tipo, fecha, usuario)
        )


def get_history(serial: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT tipo, fecha, usuario FROM codigos_generados "
            "WHERE serial = ? ORDER BY fecha DESC, id DESC",
            (serial,)
        ).fetchall()
    return [{"tipo": r[0], "fecha": r[1], "usuario": r[2]} for r in rows]
