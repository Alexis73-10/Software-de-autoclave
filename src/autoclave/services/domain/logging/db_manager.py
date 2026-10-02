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
#   lecturas — una fila por lectura de sensores durante el ciclo (ticket)
#   lecturas_grafica — serie de ~1 s para la gráfica de la pantalla de ciclo
#                      en curso (separada del ticket; tiempo monotónico)
#   ciclo_fases — inicio/fin/duración de cada fase de cada ciclo (estimador
#                 de tiempo restante y desplegable "Tiempos")

import sqlite3
import logging
import threading
from datetime import datetime
from pathlib import Path
from autoclave.utils.paths import app_root

logger = logging.getLogger(__name__)

DB_DEFAULT = app_root() / "data" / "autoclave.db"

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
    operador              TEXT    DEFAULT '',
    motivo_fallo          TEXT    DEFAULT ''
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

CREATE INDEX IF NOT EXISTS idx_ciclos_fecha
    ON ciclos(fecha_inicio);

CREATE INDEX IF NOT EXISTS idx_ciclos_numero
    ON ciclos(numero_ciclo);

-- Serie de la gráfica de la pantalla de ciclo en curso. t_s: segundos desde
-- el inicio del ciclo medidos con time.monotonic() (C-01); fase: fase_ciclo.
CREATE TABLE IF NOT EXISTS lecturas_grafica (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo_id        INTEGER NOT NULL REFERENCES ciclos(id),
    t_s             REAL    NOT NULL,
    fase            TEXT    NOT NULL,
    temp_camara     REAL,
    temp_ref        REAL,
    pres_camara     REAL
);

CREATE INDEX IF NOT EXISTS idx_lecturas_grafica_ciclo
    ON lecturas_grafica(ciclo_id, id);

-- Una fila por tramo de fase (fase = fase_ciclo del backend). inicio_s/fin_s
-- en segundos monotónicos desde el inicio del ciclo; fin_s NULL = en curso.
CREATE TABLE IF NOT EXISTS ciclo_fases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo_id        INTEGER NOT NULL REFERENCES ciclos(id),
    fase            TEXT    NOT NULL,
    inicio_s        REAL    NOT NULL,
    fin_s           REAL,
    duracion_s      REAL
);

CREATE INDEX IF NOT EXISTS idx_ciclo_fases_ciclo
    ON ciclo_fases(ciclo_id);

CREATE TABLE IF NOT EXISTS usuarios (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    usuario  TEXT UNIQUE NOT NULL,
    hash_pw  TEXT NOT NULL,
    rol      TEXT DEFAULT 'operador',
    activo   INTEGER DEFAULT 1
);
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
        self.seed_admin_if_empty()
        logger.info("SQLite iniciado: %s", self._path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _apply_schema(self):
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
            self._migrate()

    def _migrate(self):
        """Migraciones aditivas para bases de datos creadas antes de que
        existiera esta columna — no toca datos existentes."""
        try:
            self._conn.execute(
                "ALTER TABLE ciclos ADD COLUMN motivo_fallo TEXT DEFAULT ''"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # la columna ya existe

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

    def cerrar_ciclo(self, ciclo_id: int, resultado: str, motivo_fallo: str | None = None):
        """Registra la hora de fin, el resultado y (si lo hay) el motivo del ciclo."""
        with self._lock:
            self._conn.execute(
                "UPDATE ciclos SET fecha_fin=?, resultado=?, motivo_fallo=? WHERE id=?",
                (datetime.now().isoformat(), resultado, motivo_fallo or "", ciclo_id),
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
    # Gráfica de la pantalla de ciclo en curso
    # ------------------------------------------------------------------

    def insertar_lectura_grafica(self, ciclo_id: int, t_s: float, fase: str,
                                 temp_camara, temp_ref, pres_camara):
        def r(v):
            return round(v, 2) if v is not None else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO lecturas_grafica"
                " (ciclo_id, t_s, fase, temp_camara, temp_ref, pres_camara)"
                " VALUES (?,?,?,?,?,?)",
                (ciclo_id, round(t_s, 3), fase or "", r(temp_camara), r(temp_ref), r(pres_camara)),
            )
            self._conn.commit()

    def get_lecturas_grafica(self, ciclo_id: int, desde_id: int | None = None) -> list:
        """Lecturas de la gráfica del ciclo; con desde_id, solo las posteriores a ese id."""
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM lecturas_grafica WHERE ciclo_id=? AND id>? ORDER BY id",
                (ciclo_id, desde_id or 0),
            ).fetchall()

    # ------------------------------------------------------------------
    # Duración por fase
    # ------------------------------------------------------------------

    def abrir_fase(self, ciclo_id: int, fase: str, inicio_s: float):
        with self._lock:
            self._conn.execute(
                "INSERT INTO ciclo_fases (ciclo_id, fase, inicio_s) VALUES (?,?,?)",
                (ciclo_id, fase, inicio_s),
            )
            self._conn.commit()

    def cerrar_fase_abierta(self, ciclo_id: int, fin_s: float):
        """Cierra la fase en curso del ciclo (si la hay) con su duración."""
        with self._lock:
            self._conn.execute(
                "UPDATE ciclo_fases SET fin_s=?, duracion_s=?-inicio_s"
                " WHERE ciclo_id=? AND fin_s IS NULL",
                (fin_s, fin_s, ciclo_id),
            )
            self._conn.commit()

    def get_fases_ciclo(self, ciclo_id: int) -> list:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM ciclo_fases WHERE ciclo_id=? ORDER BY id", (ciclo_id,)
            ).fetchall()

    def get_duraciones_referencia(self, tipo_ciclo: str) -> dict[str, float]:
        """Duración total por fase (fase_ciclo -> s) del último ciclo COMPLETADO
        del mismo programa que tenga registro de fases; {} si no hay ninguno."""
        with self._lock:
            fila = self._conn.execute(
                "SELECT c.id FROM ciclos c"
                " WHERE c.tipo_ciclo=? AND c.resultado='COMPLETADO'"
                " AND EXISTS (SELECT 1 FROM ciclo_fases f WHERE f.ciclo_id=c.id)"
                " ORDER BY c.id DESC LIMIT 1",
                (tipo_ciclo,),
            ).fetchone()
            if fila is None:
                return {}
            filas = self._conn.execute(
                "SELECT fase, SUM(duracion_s) FROM ciclo_fases"
                " WHERE ciclo_id=? AND duracion_s IS NOT NULL GROUP BY fase",
                (fila[0],),
            ).fetchall()
        return {fase: total for fase, total in filas}

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

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    def crear_usuario(
        self,
        nombre: str,
        usuario: str,
        hash_pw: str,
        rol: str = "operador",
        activo: int = 1,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo)"
                " VALUES (?,?,?,?,?)",
                (nombre, usuario, hash_pw, rol, activo),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_usuario_by_username(self, usuario: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM usuarios WHERE usuario=? AND activo=1",
                (usuario,),
            ).fetchone()
        return dict(row) if row else None

    def seed_admin_if_empty(self) -> None:
        import hashlib
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM usuarios"
            ).fetchone()[0]
            if count == 0:
                admin_hash = hashlib.sha256(
                    "admin1234".encode("utf-8")
                ).hexdigest()
                self._conn.execute(
                    "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo)"
                    " VALUES (?,?,?,?,?)",
                    ("Administrador", "admin", admin_hash, "admin", 1),
                )
                self._conn.commit()

    def get_ciclos_rango(
        self,
        desde: str | None = None,
        hasta: str | None = None,
        limite: int = 100,
    ) -> list:
        with self._lock:
            conditions: list[str] = []
            params: list = []
            if desde:
                conditions.append("fecha_inicio >= ?")
                params.append(desde)
            if hasta:
                conditions.append("fecha_inicio <= ?")
                params.append(hasta + "T23:59:59")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params.append(limite)
            return self._conn.execute(
                f"SELECT * FROM ciclos {where} ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
