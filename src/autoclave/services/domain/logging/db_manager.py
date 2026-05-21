# services/domain/logging/db_manager.py
#
# Capa de acceso a datos — SQLite
#
# Ruta del archivo:
#   db_manager.py → logging/ → domain/ → services/ → autoclave/ → src/ → raíz
#   => DB en  <raíz>/data/autoclave.db
#
# Tablas:
#   ciclos   — un registro por ciclo ejecutado (metadatos + resultado)
#   lecturas — una fila por lectura de sensores durante el ciclo

import sqlite3
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta absoluta de la DB relativa a este archivo
_PROJECT_ROOT = Path(__file__).resolve().parents[5]   # src/ → raíz del proyecto
DB_DEFAULT    = _PROJECT_ROOT / "data" / "autoclave.db"

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ciclos (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_ciclo          INTEGER NOT NULL,
    fecha_inicio          TEXT    NOT NULL,
    fecha_fin             TEXT,
    tipo_ciclo            TEXT    DEFAULT '',
    nombre_ciclo          TEXT    DEFAULT '',
    resultado             TEXT,
    temp_esterilizacion   REAL,
    tiempo_esterilizacion REAL,
    modelo                TEXT    DEFAULT '',
    serie                 TEXT    DEFAULT '',
    version_sw            TEXT    DEFAULT '',
    operador              TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lecturas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo_id        INTEGER NOT NULL REFERENCES ciclos(id),
    timestamp_rel   TEXT    NOT NULL,   -- HH:MM:SS desde inicio de ciclo
    timestamp_abs   TEXT    NOT NULL,   -- ISO-8601 absoluto
    fase_codigo     TEXT    NOT NULL,   -- W / H / S / E
    temp_camara     REAL,
    pres_camara     REAL,
    para_imprimir   INTEGER NOT NULL DEFAULT 0   -- 1 = va al ticket
);

CREATE INDEX IF NOT EXISTS idx_lecturas_ciclo
    ON lecturas(ciclo_id);
"""


class DbManager:
    """
    Singleton de acceso a la base de datos SQLite.

    Thread-safe mediante un Lock interno.
    Usar context manager para operaciones de escritura:

        with db:
            db.insertar_lectura(...)
    """

    def __init__(self, db_path: Path = DB_DEFAULT):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,   # protegido por Lock manual
        )
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()
        logger.info("SQLite iniciado: %s", self._path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _apply_schema(self):
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Ciclos
    # ------------------------------------------------------------------

    def siguiente_numero_ciclo(self) -> int:
        """Retorna MAX(numero_ciclo)+1 ó 1 si la tabla está vacía."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(numero_ciclo), 0) FROM ciclos"
            ).fetchone()
        return row[0] + 1

    def crear_ciclo(
        self,
        numero: int,
        tipo: str,
        nombre: str,
        temp_ester,
        tiempo_ester,
        modelo: str,
        serie: str,
        version_sw: str,
        operador: str = "",
    ) -> int:
        """Inserta un nuevo ciclo y retorna su ID."""
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO ciclos
                    (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,
                     temp_esterilizacion, tiempo_esterilizacion,
                     modelo, serie, version_sw, operador)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    numero,
                    datetime.now().isoformat(),
                    tipo or "",
                    nombre or "",
                    temp_ester,
                    tiempo_ester,
                    modelo or "",
                    serie or "",
                    version_sw or "",
                    operador or "",
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def cerrar_ciclo(self, ciclo_id: int, resultado: str):
        """Registra la hora de fin y el resultado del ciclo."""
        with self._lock:
            self._conn.execute(
                "UPDATE ciclos SET fecha_fin=?, resultado=? WHERE id=?",
                (datetime.now().isoformat(), resultado, ciclo_id),
            )
            self._conn.commit()

    def get_ciclo(self, ciclo_id: int):
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM ciclos WHERE id=?", (ciclo_id,)
            ).fetchone()

    def get_ciclos_recientes(self, limite: int = 50) -> list:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM ciclos ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()

    # ------------------------------------------------------------------
    # Lecturas
    # ------------------------------------------------------------------

    def insertar_lectura(
        self,
        ciclo_id: int,
        timestamp_rel: str,
        timestamp_abs: str,
        fase_codigo: str,
        temp,
        pres,
        para_imprimir: bool = False,
    ):
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO lecturas
                    (ciclo_id, timestamp_rel, timestamp_abs, fase_codigo,
                     temp_camara, pres_camara, para_imprimir)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    ciclo_id,
                    timestamp_rel,
                    timestamp_abs,
                    fase_codigo,
                    round(temp, 2) if temp is not None else None,
                    round(pres, 2) if pres is not None else None,
                    1 if para_imprimir else 0,
                ),
            )
            self._conn.commit()

    def get_lecturas_ciclo(self, ciclo_id: int) -> list:
        """Todas las lecturas de un ciclo (para la gráfica)."""
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM lecturas WHERE ciclo_id=? ORDER BY id",
                (ciclo_id,),
            ).fetchall()

    def get_lecturas_para_imprimir(self, ciclo_id: int) -> list:
        """Sólo las lecturas marcadas para el ticket."""
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM lecturas WHERE ciclo_id=? AND para_imprimir=1 ORDER BY id",
                (ciclo_id,),
            ).fetchall()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def close(self):
        with self._lock:
            try:
                self._conn.close()
                logger.info("SQLite cerrado.")
            except Exception as e:
                logger.warning("Error cerrando SQLite: %s", e)
