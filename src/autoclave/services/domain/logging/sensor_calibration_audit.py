import sqlite3
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DB_DEFAULT   = _PROJECT_ROOT / "data" / "autoclave.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sensor_calibration_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT NOT NULL,
    sensor          TEXT NOT NULL,
    shown_low       REAL NOT NULL,
    real_low        REAL NOT NULL,
    shown_high      REAL NOT NULL,
    real_high       REAL NOT NULL,
    gain_anterior   REAL,
    offset_anterior REAL,
    gain_nuevo      REAL NOT NULL,
    offset_nuevo    REAL NOT NULL,
    usuario         TEXT NOT NULL,
    timestamp       TEXT NOT NULL
);
"""


class SensorCalibrationAuditDB:
    def __init__(self, db_path: Path = _DB_DEFAULT):
        self._db_path = db_path
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)

    def log_change(
        self,
        tipo: str,
        sensor: str,
        shown_low: float,
        real_low: float,
        shown_high: float,
        real_high: float,
        gain_anterior,
        offset_anterior,
        gain_nuevo: float,
        offset_nuevo: float,
        usuario: str,
    ) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO sensor_calibration_audit "
                "(tipo, sensor, shown_low, real_low, shown_high, real_high, "
                " gain_anterior, offset_anterior, gain_nuevo, offset_nuevo, usuario, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (tipo, sensor, shown_low, real_low, shown_high, real_high,
                 gain_anterior, offset_anterior, gain_nuevo, offset_nuevo, usuario, ts),
            )

    def get_last_change(self, tipo: str, sensor: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT usuario, timestamp FROM sensor_calibration_audit "
                "WHERE tipo=? AND sensor=? "
                "ORDER BY timestamp DESC, id DESC LIMIT 1",
                (tipo, sensor),
            ).fetchone()
        return {"usuario": row[0], "timestamp": row[1]} if row else None
