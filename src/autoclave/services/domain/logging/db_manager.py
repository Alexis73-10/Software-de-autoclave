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
#   audit_log — bitácora de seguridad y configuración (migración v1,
#               planeacion_backend_autenticacion.md §5.10)

import json
import os
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
    activo   INTEGER DEFAULT 1,
    creado_por      TEXT DEFAULT '',
    creado_en       TEXT DEFAULT '',
    codigo_creacion TEXT DEFAULT '',
    debe_cambiar_clave INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alarmas_historial (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo               TEXT NOT NULL,
    nivel                TEXT NOT NULL,
    titulo               TEXT NOT NULL,
    origen               TEXT DEFAULT '',
    descripcion_inicial  TEXT NOT NULL,
    descripcion_final    TEXT DEFAULT '',
    valores_json         TEXT DEFAULT '{}',
    aparecida            TEXT NOT NULL,
    resuelta             TEXT,
    reconocida_por       TEXT,
    reconocida_en        TEXT,
    ciclo_id             INTEGER REFERENCES ciclos(id)
);

CREATE INDEX IF NOT EXISTS idx_alarmas_aparecida ON alarmas_historial(aparecida);
"""

# Usuarios semilla (planeacion_backend_autenticacion.md, decisión 5), ambos con
# debe_cambiar_clave. El hash PBKDF2 va precalculado con una sal fija: la
# contraseña semilla es pública y se cambia en el primer login, así que la sal
# fija no expone nada y evita 600 000 iteraciones en cada base nueva.
_USUARIOS_SEMILLA = (
    ("Administrador", "admin", "admin",          # contraseña: admin1234
     "pbkdf2$600000$244c45ae5ee701d94ead2bfad6339db3$"
     "5abbc82ab1c70a268623cc8f2c774a1733f3851d9a30f9a3fcd835f3afc5a190"),
    ("Ingeniero", "ingeniero", "ingeniero",      # contraseña: ingeniero1234
     "pbkdf2$600000$dd26db607bc796ade9d097563e47d0e1$"
     "f8fa605e93fc5e4e035c60d0e07b23a96ca6390830855f36c14cb03a2d609019"),
)


# ── Migraciones numeradas (PRAGMA user_version) ─────────────────────────────
# La base anterior a este mecanismo es v0. Cada migración es atómica (una
# transacción) y registra su versión al terminar. v2: sensores del ciclo (tanda
# planeacion_backend_parametros.md (system_params, entradas mostradas, gráfica).

def _migracion_v1(conn: sqlite3.Connection) -> None:
    """Bitácora audit_log (planeacion_backend_parametros.md §7). `ts` es
    reloj de pared: es un sello de registro, no un temporizador."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ts             TEXT NOT NULL,
            usuario        TEXT NOT NULL DEFAULT '',
            rol            TEXT NOT NULL DEFAULT '',
            evento         TEXT NOT NULL,
            entidad        TEXT NOT NULL DEFAULT '',
            valor_anterior TEXT,
            valor_nuevo    TEXT,
            detalle        TEXT
        )""")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_evento ON audit_log(evento, entidad)"
    )


def _migracion_v2(conn: sqlite3.Connection) -> None:
    """Sensores del ciclo (tanda 2026-10-14 §1.1, RS-08): asignación de roles
    vigente al inicio (JSON canónico), F0 final y número de programa en
    `ciclos`; temperatura del Principal en `lecturas`; Cámara 2 en la gráfica.
    Aditiva: las filas anteriores quedan con NULL / ''."""
    for tabla, columna, tipo in (
        ("ciclos", "asignacion_sensores", "TEXT DEFAULT ''"),
        ("ciclos", "f0_final", "REAL"),
        ("ciclos", "numero_programa", "INTEGER"),
        ("lecturas", "temp_principal", "REAL"),
        ("lecturas_grafica", "temp_2_camara", "REAL"),
    ):
        columnas = {f[1] for f in conn.execute(f"PRAGMA table_info({tabla})")}
        if columna not in columnas:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")


def _migracion_v3(conn: sqlite3.Connection) -> None:
    """E4 (tanda 2026-10-14; planeacion_arranque_y_modo_sin_bd §7.5): UUID por
    ciclo (idempotencia de la reimportación del respaldo) e instantánea del
    programa con el que corrió (JSON). Índice UNIQUE sobre numero_ciclo, solo
    si no hay duplicados: con duplicados se registran y NO se crea (migración
    no destructiva)."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(ciclos)")}
    for columna, tipo in (("uuid", "TEXT"), ("programa_json", "TEXT")):
        if columna not in columnas:
            conn.execute(f"ALTER TABLE ciclos ADD COLUMN {columna} {tipo}")
    duplicados = conn.execute(
        "SELECT numero_ciclo, COUNT(*) FROM ciclos GROUP BY numero_ciclo HAVING COUNT(*) > 1"
    ).fetchall()
    if duplicados:
        logger.error("Migración v3: números de ciclo duplicados %s; no se crea el índice UNIQUE",
                     [tuple(d) for d in duplicados])
        return
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ciclos_numero_unico ON ciclos(numero_ciclo)")


# v2 la toma la tanda 2026-10-14 (sensores del ciclo); lo que estaba previsto
# para planeacion_backend_parametros.md pasa a v3 o posterior. Las versiones
# son secuenciales: no se deja ningún hueco.
_MIGRACIONES = (
    (1, _migracion_v1),
    (2, _migracion_v2),
    (3, _migracion_v3),
)

ESQUEMA_VERSION = _MIGRACIONES[-1][0]


class BdBloqueadaError(RuntimeError):
    """Existe la marca BD_BLOQUEADA (T8, §7.7)."""


def marca_bd_bloqueada(db_path: Path = DB_DEFAULT) -> Path:
    return Path(db_path).parent / "BD_BLOQUEADA"


def es_base_corrupta(error: Exception) -> bool:
    """True si el error de SQLite indica un archivo corrupto o que no es una
    base (no un bloqueo ni un error de E/S transitorio)."""
    if not isinstance(error, sqlite3.DatabaseError) or isinstance(error, sqlite3.OperationalError):
        return False
    texto = str(error).lower()
    return "not a database" in texto or "malformed" in texto


def apartar_base_corrupta(db_path: Path = DB_DEFAULT, ahora: datetime | None = None) -> Path:
    """§7.7: la base corrupta no se borra ni se sobrescribe. Se renombra a
    `autoclave.db.corrupta-<fecha>` y se deja la marca BD_BLOQUEADA, que
    impide crear una base nueva y sembrar admin. Devuelve la ruta nueva."""
    db_path = Path(db_path)
    sello = (ahora or datetime.now()).strftime("%Y%m%d-%H%M%S")
    destino = db_path.with_name(f"{db_path.name}.corrupta-{sello}")
    # TMG-06 de T8: la marca va primero; si un archivo no se puede mover, el
    # bloqueo ya rige y no se crea una base nueva junto a restos de la corrupta
    marca = marca_bd_bloqueada(db_path)
    marca.write_text(
        f"Base de datos corrupta apartada en {destino.name} ({sello}).\n"
        "No se crea una base nueva hasta que un técnico revise y borre este archivo.\n",
        encoding="utf-8")
    for sufijo in ("-wal", "-shm", "-journal"):
        extra = db_path.with_name(db_path.name + sufijo)
        if extra.exists():
            os.replace(extra, destino.with_name(destino.name + sufijo))
    os.replace(db_path, destino)
    return destino


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
        # T8 (§7.7, BD-06): tras detectar una base corrupta no se crea otra
        # (ni se siembra admin) hasta que un técnico retire la marca
        marca = marca_bd_bloqueada(self._path)
        if marca.exists():
            raise BdBloqueadaError(
                f"Base de datos bloqueada por {marca.name}: requiere intervención de un técnico")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,   # protegido por Lock manual
            timeout=10.0,              # espera un bloqueo de otro proceso (TMG-03 de T3)
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._apply_schema()
            self.seed_admin_if_empty()
        except Exception:
            # sin conexión abierta: en Windows impediría renombrar la base corrupta
            self._conn.close()
            raise
        logger.info("SQLite iniciado: %s", self._path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _apply_schema(self):
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
            self._migrate()
            self._migrar_versiones()

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
        # Auditoría de creación de usuarios (planeacion_nuevo_usuario.md, D-08/D-12)
        for columna in ("creado_por", "creado_en", "codigo_creacion"):
            try:
                self._conn.execute(
                    f"ALTER TABLE usuarios ADD COLUMN {columna} TEXT DEFAULT ''"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # la columna ya existe
        # Cambio de contraseña obligatorio (planeacion_backend_autenticacion.md, decisión 5)
        try:
            self._conn.execute(
                "ALTER TABLE usuarios ADD COLUMN debe_cambiar_clave INTEGER DEFAULT 0"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # la columna ya existe
        # Código de alarma del fallo del ciclo (alarmas Parte A)
        try:
            self._conn.execute(
                "ALTER TABLE ciclos ADD COLUMN codigo_fallo TEXT DEFAULT ''"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # la columna ya existe

    def _migrar_versiones(self):
        """Aplica en orden las migraciones numeradas pendientes. Si una falla,
        se revierte entera y la versión no avanza."""
        actual = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for version, migracion in _MIGRACIONES:
            if version <= actual:
                continue
            try:
                self._conn.execute("BEGIN IMMEDIATE")   # TMG-03 de T3
                migracion(self._conn)
                self._conn.execute(f"PRAGMA user_version = {int(version)}")
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                logger.exception("Migración v%d fallida", version)
                raise
            logger.info("Base de datos migrada a v%d", version)

    def get_version_esquema(self) -> int:
        with self._lock:
            return self._conn.execute("PRAGMA user_version").fetchone()[0]

    # ------------------------------------------------------------------
    # Bitácora (audit_log)
    # ------------------------------------------------------------------

    def registrar_auditoria(
        self,
        evento: str,
        usuario: str = "",
        rol: str = "",
        entidad: str = "",
        valor_anterior=None,
        valor_nuevo=None,
        detalle: dict | None = None,
    ) -> int:
        """Inserta una fila en audit_log. Los valores anterior y nuevo se
        guardan como texto (JSON si no son str); `detalle`, como JSON."""
        def texto(v):
            if v is None or isinstance(v, str):
                return v
            return json.dumps(v, ensure_ascii=False)

        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO audit_log (ts, usuario, rol, evento, entidad,"
                " valor_anterior, valor_nuevo, detalle) VALUES (?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), usuario or "", rol or "",
                 evento, entidad or "", texto(valor_anterior), texto(valor_nuevo),
                 json.dumps(detalle, ensure_ascii=False) if detalle else None),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_auditoria(self, evento: str | None = None, entidad: str | None = None,
                      limite: int = 100) -> list[dict]:
        """Filas de audit_log, la más reciente primero, con `detalle` ya decodificado."""
        condiciones, params = [], []
        if evento is not None:
            condiciones.append("evento = ?")
            params.append(evento)
        if entidad is not None:
            condiciones.append("entidad = ?")
            params.append(entidad)
        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
        params.append(limite)
        with self._lock:
            filas = self._conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
        resultado = []
        for f in filas:
            d = dict(f)
            d["detalle"] = json.loads(d["detalle"]) if d["detalle"] else None
            resultado.append(d)
        return resultado

    # ------------------------------------------------------------------
    # Ciclos
    # ------------------------------------------------------------------

    def max_numero_ciclo(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(numero_ciclo), 0) FROM ciclos").fetchone()
        return row[0]

    def indice_numero_unico(self) -> bool:
        """True si existe el índice UNIQUE de v3 (no se crea con duplicados)."""
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_ciclos_numero_unico'"
            ).fetchone() is not None

    def cerrar_ciclos_interrumpidos(self, motivo: str) -> list[dict]:
        """D-08 / PF-17: todo ciclo sin fecha_fin quedó interrumpido (corte de
        energía o reinicio). Se cierra como INTERRUMPIDO, nunca se reanuda.
        Devuelve las filas cerradas (la más reciente al final)."""
        with self._lock:
            filas = [dict(f) for f in self._conn.execute(
                "SELECT * FROM ciclos WHERE fecha_fin IS NULL ORDER BY id").fetchall()]
            if filas:
                self._conn.execute(
                    "UPDATE ciclos SET fecha_fin=?, resultado='INTERRUMPIDO', motivo_fallo=? "
                    "WHERE fecha_fin IS NULL",
                    (datetime.now().isoformat(), motivo))
                self._conn.commit()
        return filas

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
        asignacion_sensores: str = "",
        numero_programa: int | None = None,
        uuid: str | None = None,
        programa_json: str | None = None,
    ) -> int:
        """Inserta un nuevo ciclo y retorna su ID."""
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO ciclos
                    (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,
                     temp_esterilizacion, tiempo_esterilizacion,
                     modelo, serie, version_sw, operador,
                     asignacion_sensores, numero_programa, uuid, programa_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    asignacion_sensores or "",
                    numero_programa,
                    uuid,
                    programa_json,
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def cerrar_ciclo(self, ciclo_id: int, resultado: str, motivo_fallo: str | None = None,
                     codigo_fallo: str | None = None, f0_final: float | None = None):
        """Registra la hora de fin, el resultado y (si lo hay) el motivo y código
        del ciclo, y el F0 final si el ciclo tenía F0 activo."""
        with self._lock:
            self._conn.execute(
                "UPDATE ciclos SET fecha_fin=?, resultado=?, motivo_fallo=?, codigo_fallo=?, "
                "f0_final=? WHERE id=?",
                (datetime.now().isoformat(), resultado, motivo_fallo or "",
                 codigo_fallo or "", f0_final, ciclo_id),
            )
            self._conn.commit()

    def importar_ciclo_respaldo(self, encabezado: dict, lecturas: list[dict],
                                cierre: dict | None, motivo_interrumpido: str) -> bool:
        """Reimporta un ciclo del respaldo JSONL (T8, §7.4) en una sola
        transacción. Idempotente por uuid. Devuelve "importado" (no estaba),
        "completado" (estaba incompleto: la base falló a mitad de ciclo; se
        agregan las lecturas que faltan y, si no tenía fin, el cierre del
        respaldo; SAF-02) o "ya_registrado". Sin cierre, un ciclo nuevo queda
        INTERRUMPIDO."""
        uuid_ciclo = encabezado.get("uuid")
        if not uuid_ciclo:
            raise ValueError("respaldo sin uuid")
        with self._lock:
            fila = self._conn.execute("SELECT id, fecha_fin FROM ciclos WHERE uuid=?",
                                      (uuid_ciclo,)).fetchone()
            if fila is not None:
                return self._completar_ciclo_respaldo(fila["id"], fila["fecha_fin"],
                                                      lecturas, cierre)
            try:
                if cierre is not None:
                    fin = (cierre.get("fecha_fin") or datetime.now().isoformat(),
                           cierre.get("resultado") or "DESCONOCIDO",
                           cierre.get("motivo") or "", cierre.get("codigo") or "",
                           cierre.get("f0_final"))
                else:
                    fin = (datetime.now().isoformat(), "INTERRUMPIDO",
                           motivo_interrumpido, "", None)
                cur = self._conn.execute(
                    """
                    INSERT INTO ciclos
                        (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,
                         temp_esterilizacion, tiempo_esterilizacion,
                         modelo, serie, version_sw, operador,
                         asignacion_sensores, numero_programa, uuid, programa_json,
                         fecha_fin, resultado, motivo_fallo, codigo_fallo, f0_final)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        encabezado.get("numero"),
                        encabezado.get("fecha_inicio") or datetime.now().isoformat(),
                        encabezado.get("tipo") or "",
                        encabezado.get("nombre") or "",
                        encabezado.get("temp_ester"),
                        encabezado.get("tiempo_ester"),
                        encabezado.get("modelo") or "",
                        encabezado.get("serie") or "",
                        encabezado.get("version_sw") or "",
                        encabezado.get("operador") or "",
                        encabezado.get("asignacion_sensores") or "",
                        encabezado.get("numero_programa"),
                        uuid_ciclo,
                        encabezado.get("programa_json"),
                    ) + fin,
                )
                ciclo_id = cur.lastrowid
                for l in lecturas:
                    self._insertar_lectura_respaldo(ciclo_id, l)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return "importado"

    def _insertar_lectura_respaldo(self, ciclo_id: int, l: dict) -> None:
        temp, pres, tp = l.get("temp"), l.get("pres"), l.get("temp_principal")
        self._conn.execute(
            """
            INSERT INTO lecturas
                (ciclo_id, timestamp_rel, timestamp_abs, fase_codigo,
                 temp_camara, pres_camara, para_imprimir, temp_principal)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (ciclo_id, l.get("timestamp_rel") or "", l.get("timestamp_abs") or "",
             l.get("fase_codigo") or "",
             round(temp, 2) if isinstance(temp, (int, float)) else None,
             round(pres, 2) if isinstance(pres, (int, float)) else None,
             1 if l.get("para_imprimir") else 0,
             round(tp, 2) if isinstance(tp, (int, float)) else None),
        )

    def _completar_ciclo_respaldo(self, ciclo_id: int, fecha_fin, lecturas: list[dict],
                                  cierre: dict | None) -> str:
        """Con _lock tomado. SAF-02 de T8: agrega las lecturas del respaldo que
        faltan (clave: timestamp_abs, timestamp_rel y fase) y, si la fila no
        tiene fin, aplica el cierre del respaldo. Una fila ya cerrada conserva
        su resultado."""
        existentes = {
            (r["timestamp_abs"], r["timestamp_rel"], r["fase_codigo"])
            for r in self._conn.execute(
                "SELECT timestamp_abs, timestamp_rel, fase_codigo FROM lecturas WHERE ciclo_id=?",
                (ciclo_id,)).fetchall()
        }
        faltan = [l for l in lecturas
                  if (l.get("timestamp_abs") or "", l.get("timestamp_rel") or "",
                      l.get("fase_codigo") or "") not in existentes]
        cerrar = fecha_fin is None and cierre is not None
        if not faltan and not cerrar:
            return "ya_registrado"
        try:
            for l in faltan:
                self._insertar_lectura_respaldo(ciclo_id, l)
            if cerrar:
                self._conn.execute(
                    "UPDATE ciclos SET fecha_fin=?, resultado=?, motivo_fallo=?, codigo_fallo=?, "
                    "f0_final=? WHERE id=?",
                    (cierre.get("fecha_fin") or datetime.now().isoformat(),
                     cierre.get("resultado") or "DESCONOCIDO", cierre.get("motivo") or "",
                     cierre.get("codigo") or "", cierre.get("f0_final"), ciclo_id))
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return "completado"

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

    def get_resumen_ciclos(self, desde: str) -> dict:
        """Resumen de solo lectura para el Menú Principal (GET /cycle/summary).

        total: último numero_ciclo (no un conteo de filas: sobrevive a filas
               faltantes, pero no a vaciar la tabla — TODO(MP-06a)).
        hoy:   ciclos terminados (con fecha_fin, cualquier resultado) desde
               `desde`, medianoche local en el mismo formato ISO sin zona que
               guardan crear_ciclo/cerrar_ciclo (datetime.now().isoformat()).
        ultimo: fila del ciclo de mayor id (puede no estar cerrado), o None.
        """
        with self._lock:
            total = self._conn.execute(
                "SELECT COALESCE(MAX(numero_ciclo), 0) FROM ciclos"
            ).fetchone()[0]
            hoy = self._conn.execute(
                "SELECT COUNT(*) FROM ciclos WHERE fecha_fin IS NOT NULL AND fecha_fin >= ?",
                (desde,),
            ).fetchone()[0]
            ultimo = self._conn.execute(
                "SELECT * FROM ciclos ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {"total": total, "hoy": hoy, "ultimo": ultimo}

    def get_ciclos_desde(self, desde: str, terminados: bool, limite: int,
                         hasta: str | None = None) -> list:
        """Ciclos desde `desde` (ISO local sin zona) y, si se da, antes de `hasta`
        (exclusivo), más recientes primero; solo lectura (Ciclos hoy e Historial
        del Menú Principal).

        terminados=False: por fecha_inicio, incluidos los interrumpidos (sin fecha_fin).
        terminados=True:  por fecha_fin (>= desde), el mismo criterio que el conteo
                          "hoy" de get_resumen_ciclos.
        """
        campo = "fecha_fin" if terminados else "fecha_inicio"
        sql = f"SELECT * FROM ciclos WHERE {campo} IS NOT NULL AND {campo} >= ?"
        params: list = [desde]
        if hasta is not None:
            sql += f" AND {campo} < ?"
            params.append(hasta)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limite)
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def get_conteo_resultados(self, desde: str, hasta: str) -> list:
        """Cantidad de ciclos por (tipo_ciclo, resultado) iniciados en [desde, hasta)
        (ISO local sin zona), con el nombre de programa más reciente; solo lectura
        (resumen por periodo de la pantalla Reportes)."""
        with self._lock:
            return self._conn.execute(
                "SELECT tipo_ciclo, resultado, COUNT(*) AS cantidad,"
                " (SELECT c2.nombre_ciclo FROM ciclos c2 WHERE c2.tipo_ciclo = c.tipo_ciclo"
                "  ORDER BY c2.id DESC LIMIT 1) AS nombre_ciclo"
                " FROM ciclos c WHERE fecha_inicio >= ? AND fecha_inicio < ?"
                " GROUP BY tipo_ciclo, resultado",
                (desde, hasta),
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
        temp_principal=None,
    ):
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO lecturas
                    (ciclo_id, timestamp_rel, timestamp_abs, fase_codigo,
                     temp_camara, pres_camara, para_imprimir, temp_principal)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    ciclo_id,
                    timestamp_rel,
                    timestamp_abs,
                    fase_codigo,
                    round(temp, 2) if temp is not None else None,
                    round(pres, 2) if pres is not None else None,
                    1 if para_imprimir else 0,
                    round(temp_principal, 2) if temp_principal is not None else None,
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
                                 temp_camara, temp_ref, pres_camara, temp_2_camara=None):
        def r(v):
            return round(v, 2) if v is not None else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO lecturas_grafica"
                " (ciclo_id, t_s, fase, temp_camara, temp_ref, pres_camara, temp_2_camara)"
                " VALUES (?,?,?,?,?,?,?)",
                (ciclo_id, round(t_s, 3), fase or "", r(temp_camara), r(temp_ref), r(pres_camara),
                 r(temp_2_camara)),
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
    # Historial de alarmas
    # ------------------------------------------------------------------

    def insertar_alarma(self, codigo, nivel, titulo, origen, descripcion, valores_json,
                        aparecida, resuelta, ciclo_id) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alarmas_historial (codigo, nivel, titulo, origen, "
                "descripcion_inicial, valores_json, aparecida, resuelta, ciclo_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (codigo, nivel, titulo, origen or "", descripcion, valores_json,
                 aparecida, resuelta, ciclo_id),
            )
            self._conn.commit()
            return cur.lastrowid

    def marcar_alarma_resuelta(self, id_, resuelta, descripcion_final, valores_json):
        with self._lock:
            self._conn.execute(
                "UPDATE alarmas_historial SET resuelta=?, descripcion_final=?, valores_json=? "
                "WHERE id=?",
                (resuelta, descripcion_final, valores_json, id_),
            )
            self._conn.commit()

    def marcar_alarma_reconocida(self, id_, usuario, en):
        with self._lock:
            self._conn.execute(
                "UPDATE alarmas_historial SET reconocida_por=?, reconocida_en=? WHERE id=?",
                (usuario, en, id_),
            )
            self._conn.commit()

    def get_alarmas_historial(self, desde: str | None = None, hasta: str | None = None,
                              nivel: str | None = None, limite: int = 200) -> list[dict]:
        condiciones, args = [], []
        if desde:
            condiciones.append("aparecida >= ?")
            args.append(desde)
        if hasta:
            condiciones.append("aparecida <= ?")
            args.append(hasta)
        if nivel:
            condiciones.append("nivel = ?")
            args.append(nivel)
        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        with self._lock:
            filas = self._conn.execute(
                f"SELECT * FROM alarmas_historial {where} ORDER BY aparecida DESC, id DESC "
                "LIMIT ?", (*args, int(limite)),
            ).fetchall()
        return [dict(f) for f in filas]

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
        creado_por: str = "",
        codigo_creacion: str = "",
    ) -> int:
        """Inserta un usuario. Deja propagar sqlite3.IntegrityError si
        `usuario` ya existe (UNIQUE, incluidos inactivos)."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo,"
                " creado_por, creado_en, codigo_creacion)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (nombre, usuario, hash_pw, rol, activo,
                 creado_por, datetime.now().isoformat(), codigo_creacion),
            )
            self._conn.commit()
            return cur.lastrowid

    def existe_usuario(self, usuario: str) -> bool:
        """True si ya hay un usuario con ese nombre, activo o inactivo, sin
        distinguir mayúsculas. Se compara en Python con casefold() porque
        LOWER/NOCASE de SQLite solo pliegan ASCII (no la Ñ ni acentos)."""
        buscado = usuario.casefold()
        with self._lock:
            filas = self._conn.execute("SELECT usuario FROM usuarios").fetchall()
        return any(f["usuario"].casefold() == buscado for f in filas)

    def get_usuario_by_username(self, usuario: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM usuarios WHERE usuario=? AND activo=1",
                (usuario,),
            ).fetchone()
        return dict(row) if row else None

    def actualizar_password(self, usuario: str, hash_pw: str) -> None:
        """Guarda el nuevo hash y baja la bandera debe_cambiar_clave."""
        with self._lock:
            self._conn.execute(
                "UPDATE usuarios SET hash_pw=?, debe_cambiar_clave=0 WHERE usuario=?",
                (hash_pw, usuario),
            )
            self._conn.commit()

    def seed_admin_if_empty(self) -> None:
        """Con la tabla vacía crea los usuarios semilla `admin` e `ingeniero`,
        ambos obligados a cambiar la contraseña en el primer login."""
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM usuarios"
            ).fetchone()[0]
            if count == 0:
                for nombre, usuario, rol, hash_pw in _USUARIOS_SEMILLA:
                    self._conn.execute(
                        "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo,"
                        " creado_por, creado_en, debe_cambiar_clave)"
                        " VALUES (?,?,?,?,1,'semilla',?,1)",
                        (nombre, usuario, hash_pw, rol, datetime.now().isoformat()),
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
