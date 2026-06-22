import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DB_DEFAULT   = _PROJECT_ROOT / "data" / "autoclave.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cycle_params_audit (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id       TEXT NOT NULL,
    fase           TEXT NOT NULL,
    param          TEXT NOT NULL,
    valor_anterior TEXT,
    valor_nuevo    TEXT NOT NULL,
    usuario        TEXT NOT NULL,
    timestamp      TEXT NOT NULL
);
"""


class CycleParamsAuditDB:
    def __init__(self, db_path: Path = _DB_DEFAULT):
        self._db_path = db_path
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)

    def log_change(
        self,
        cycle_id: str,
        fase: str,
        param: str,
        valor_anterior,
        valor_nuevo,
        usuario: str,
    ) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO cycle_params_audit "
                "(cycle_id, fase, param, valor_anterior, valor_nuevo, usuario, timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (cycle_id, fase, param, str(valor_anterior), str(valor_nuevo), usuario, ts),
            )

    def get_last_change(self, cycle_id: str, fase: str, param: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT usuario, timestamp FROM cycle_params_audit "
                "WHERE cycle_id=? AND fase=? AND param=? "
                "ORDER BY timestamp DESC, id DESC LIMIT 1",
                (cycle_id, fase, param),
            ).fetchone()
        return {"usuario": row[0], "timestamp": row[1]} if row else None
