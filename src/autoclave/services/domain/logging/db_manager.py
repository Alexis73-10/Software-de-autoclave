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
# U11 (tanda 11, D11-6): se llaman `Admin` e `Ingeniero` (usuario y nombre) y
# nacen con la marca `cuenta_sistema`. Las contraseñas iniciales no cambian.
_USUARIOS_SEMILLA = (
    ("Admin", "Admin", "admin",                  # contraseña: admin1234
     "pbkdf2$600000$244c45ae5ee701d94ead2bfad6339db3$"
     "5abbc82ab1c70a268623cc8f2c774a1733f3851d9a30f9a3fcd835f3afc5a190"),
    ("Ingeniero", "Ingeniero", "ingeniero",      # contraseña: ingeniero1234
     "pbkdf2$600000$dd26db607bc796ade9d097563e47d0e1$"
     "f8fa605e93fc5e4e035c60d0e07b23a96ca6390830855f36c14cb03a2d609019"),
)

# U11: usuario de la semilla anterior a la tanda 11 -> (usuario, nombre) nuevos.
_RENOMBRES_SEMILLA = (("admin", "Admin", "Admin"), ("ingeniero", "Ingeniero", "Ingeniero"))


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
def _migracion_v4(conn: sqlite3.Connection) -> None:
    """RB-03.7 (T10): audit_log es de solo anexar. UPDATE y DELETE abortan."""
    for accion in ("UPDATE", "DELETE"):
        conn.execute(
            f"CREATE TRIGGER IF NOT EXISTS audit_log_sin_{accion.lower()} "
            f"BEFORE {accion} ON audit_log "
            "BEGIN SELECT RAISE(ABORT, 'audit_log es de solo anexar'); END")


def _migracion_v5(conn: sqlite3.Connection) -> None:
    """M1 (tanda 3): registro de mantenimientos realizados. `fecha` es la fecha
    de calendario (reloj de pared) y `ciclos` el contador persistente de ciclos
    en ese momento. Solo se anexan filas (la corrección es un registro nuevo)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mantenimientos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha         TEXT NOT NULL,
            usuario       TEXT NOT NULL DEFAULT '',
            tipo          TEXT NOT NULL DEFAULT '',
            observaciones TEXT NOT NULL DEFAULT '',
            ciclos        INTEGER
        )""")
    for accion in ("UPDATE", "DELETE"):
        conn.execute(
            f"CREATE TRIGGER IF NOT EXISTS mantenimientos_sin_{accion.lower()} "
            f"BEFORE {accion} ON mantenimientos "
            "BEGIN SELECT RAISE(ABORT, 'mantenimientos es de solo anexar'); END")


def _migracion_v6(conn: sqlite3.Connection) -> None:
    """O1 (tanda 3): operador que inició cada ciclo. La columna `operador`
    existe desde el esquema original, pero nada la llenaba; se garantiza en
    bases creadas antes de ella y se deja la versión. Los ciclos anteriores
    conservan '' (la UI muestra "—": sin operador registrado)."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(ciclos)")}
    if "operador" not in columnas:
        conn.execute("ALTER TABLE ciclos ADD COLUMN operador TEXT DEFAULT ''")


def _migracion_v7(conn: sqlite3.Connection) -> None:
    """I4 (tanda 6; planeacion_i18n.md §3.10): parámetros de la alarma del
    fallo del ciclo, en JSON, para presentar el motivo en cualquier idioma y
    unidad. `motivo_fallo` (texto en español) y `codigo_fallo` no cambian; los
    ciclos anteriores quedan con '' (se muestran como antes)."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(ciclos)")}
    if "valores_fallo" not in columnas:
        conn.execute("ALTER TABLE ciclos ADD COLUMN valores_fallo TEXT DEFAULT ''")


def _migracion_v8(conn: sqlite3.Connection) -> None:
    """O2a (tanda 6; planeacion_opciones.md v4 §3.2): parámetros del equipo.
    `global_params.json` es la fuente de los valores de fábrica; aquí queda el
    valor vigente de cada uno, con el defecto, el mínimo y el máximo con que
    se validó, y quién y cuándo lo cambió por última vez ('' / NULL si nunca).
    El historial completo de cambios está en audit_log (param_sistema_cambio)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_params (
            clave      TEXT PRIMARY KEY,
            valor      TEXT NOT NULL,
            defecto    TEXT,
            minimo     REAL,
            maximo     REAL,
            usuario    TEXT DEFAULT '',
            fecha      TEXT
        )
    """)


def _migracion_v9(conn: sqlite3.Connection) -> None:
    """O2b (tanda 6; planeacion_opciones.md v4 §3.6): operadores, separados de
    `usuarios`, identificados por nombre y sin contraseña. Nunca se borran
    (trazabilidad): se desactivan. El nombre es único sin distinguir
    mayúsculas (se compara con casefold() en Python, como `usuarios`)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operadores (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre     TEXT UNIQUE NOT NULL,
            activo     INTEGER NOT NULL DEFAULT 1,
            creado_por TEXT DEFAULT '',
            creado_en  TEXT DEFAULT ''
        )""")
    conn.execute("CREATE TRIGGER IF NOT EXISTS operadores_sin_delete BEFORE DELETE ON operadores "
                 "BEGIN SELECT RAISE(ABORT, 'operadores no se borran'); END")
    conn.execute("CREATE TRIGGER IF NOT EXISTS usuarios_sin_delete BEFORE DELETE ON usuarios "
                 "BEGIN SELECT RAISE(ABORT, 'usuarios no se borran'); END")


def _migracion_v10(conn: sqlite3.Connection) -> None:
    """D8-2.14 (tanda 8, Q1-P5): líneas de aviso del pie del ticket, en JSON
    ({"sin_datos_s": segundos, "avisos": [texto, ...]}), para que la
    reimpresión sea idéntica al ticket impreso en vivo. Los ciclos anteriores
    quedan con '' (se reimprimen como antes, sin esas líneas)."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(ciclos)")}
    if "avisos_ticket" not in columnas:
        conn.execute("ALTER TABLE ciclos ADD COLUMN avisos_ticket TEXT DEFAULT ''")


def _marcar_cuentas_sistema(conn: sqlite3.Connection) -> None:
    """U11 (D11-6.5): `admin`->`Admin` e `ingeniero`->`Ingeniero` solo en las
    filas semilla (creado_por='semilla'), con la marca `cuenta_sistema`.
    Conserva id, contraseña, debe_cambiar_clave, activo y rol; no toca la
    auditoría ni los ciclos (quedan con el nombre anterior) y agrega una fila
    `usuario_renombrado` por cuenta renombrada. Idempotente: una fila ya
    renombrada y marcada no cambia. Si otro usuario choca sin distinguir
    mayúsculas con el nombre nuevo, la semilla no se renombra (queda en el log
    para decisión de Cristian) pero sí se marca: la protección va por la marca,
    no por el texto."""
    filas = [dict(f) for f in conn.execute(
        "SELECT id, usuario, nombre, creado_por, cuenta_sistema FROM usuarios")]
    for viejo, nuevo, nombre_nuevo in _RENOMBRES_SEMILLA:
        semillas = [f for f in filas if f["creado_por"] == "semilla"
                    and f["usuario"].casefold() == viejo.casefold()]
        if len(semillas) != 1:
            if semillas:
                logger.error("Migración v11: %d filas semilla para '%s' (%s); no se tocan",
                             len(semillas), viejo, [f["usuario"] for f in semillas])
            continue
        semilla = semillas[0]
        choques = [f["usuario"] for f in filas
                   if f["id"] != semilla["id"] and f["usuario"].casefold() == nuevo.casefold()]
        if choques:
            logger.warning("Migración v11: la cuenta semilla '%s' no se renombra a '%s' porque "
                           "choca sin distinguir mayúsculas con %s (pregunta para Cristian)",
                           semilla["usuario"], nuevo, choques)
        elif (semilla["usuario"], semilla["nombre"]) != (nuevo, nombre_nuevo):
            conn.execute("UPDATE usuarios SET usuario=?, nombre=? WHERE id=?",
                         (nuevo, nombre_nuevo, semilla["id"]))
            conn.execute(_SQL_AUDITORIA, _fila_auditoria(
                "usuario_renombrado", usuario="sistema", entidad=nuevo,
                valor_anterior={"usuario": semilla["usuario"], "nombre": semilla["nombre"]},
                valor_nuevo={"usuario": nuevo, "nombre": nombre_nuevo},
                detalle={"origen": "migracion_v11"}))
            logger.info("Migración v11: '%s' renombrada a '%s'", semilla["usuario"], nuevo)
        if not semilla["cuenta_sistema"]:
            conn.execute("UPDATE usuarios SET cuenta_sistema=1 WHERE id=?", (semilla["id"],))


def _migracion_v11(conn: sqlite3.Connection) -> None:
    """U11 (tanda 11, D11-6): cuentas del sistema. Columna `cuenta_sistema`
    (marca persistente), renombre de las semillas y triggers que protegen las
    filas marcadas: no cambian de usuario, nombre ni rol, no se desactivan y
    la marca no se pone ni se quita después (borrar ya lo prohíbe la v9). Sí se
    cambian la contraseña y debe_cambiar_clave. Los triggers se crean después
    del renombre."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(usuarios)")}
    if "cuenta_sistema" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN cuenta_sistema INTEGER NOT NULL DEFAULT 0")
    _marcar_cuentas_sistema(conn)
    conn.execute(
        "CREATE TRIGGER IF NOT EXISTS usuarios_cuenta_sistema_protegida "
        "BEFORE UPDATE ON usuarios WHEN OLD.cuenta_sistema = 1 AND ("
        " NEW.usuario IS NOT OLD.usuario OR NEW.nombre IS NOT OLD.nombre"
        " OR NEW.rol IS NOT OLD.rol OR (OLD.activo = 1 AND NEW.activo IS NOT 1)) "
        "BEGIN SELECT RAISE(ABORT, 'cuenta del sistema protegida'); END")
    conn.execute(
        "CREATE TRIGGER IF NOT EXISTS usuarios_marca_sistema_inmutable "
        "BEFORE UPDATE OF cuenta_sistema ON usuarios "
        "WHEN NEW.cuenta_sistema IS NOT OLD.cuenta_sistema "
        "BEGIN SELECT RAISE(ABORT, 'la marca de cuenta del sistema no cambia'); END")
    conn.execute(
        "CREATE TRIGGER IF NOT EXISTS usuarios_marca_sistema_solo_semilla "
        "BEFORE INSERT ON usuarios "
        "WHEN NEW.cuenta_sistema IS NOT 0 AND NEW.creado_por IS NOT 'semilla' "
        "BEGIN SELECT RAISE(ABORT, 'solo las semillas son cuentas del sistema'); END")


def _valores_fallo_json(valores) -> str:
    """'' sin parámetros; JSON (sin NaN) si los hay. Nunca lanza."""
    if not isinstance(valores, dict) or not valores:
        return ""
    try:
        return json.dumps(valores, ensure_ascii=False, allow_nan=False, default=str)
    except (TypeError, ValueError):
        return ""


_MIGRACIONES = (
    (1, _migracion_v1),
    (2, _migracion_v2),
    (3, _migracion_v3),
    (4, _migracion_v4),
    (5, _migracion_v5),
    (6, _migracion_v6),
    (7, _migracion_v7),
    (8, _migracion_v8),
    (9, _migracion_v9),
    (10, _migracion_v10),
    (11, _migracion_v11),
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


_SQL_AUDITORIA = ("INSERT INTO audit_log (ts, usuario, rol, evento, entidad,"
                  " valor_anterior, valor_nuevo, detalle) VALUES (?,?,?,?,?,?,?,?)")


def _fila_auditoria(evento: str, usuario: str = "", rol: str = "", entidad: str = "",
                    valor_anterior=None, valor_nuevo=None, detalle: dict | None = None) -> tuple:
    """Parámetros de _SQL_AUDITORIA: anterior/nuevo como texto (JSON si no
    son str) y `detalle` como JSON."""
    def texto(v):
        if v is None or isinstance(v, str):
            return v
        return json.dumps(v, ensure_ascii=False)

    return (datetime.now().isoformat(timespec="seconds"), usuario or "", rol or "",
            evento, entidad or "", texto(valor_anterior), texto(valor_nuevo),
            json.dumps(detalle, ensure_ascii=False) if detalle else None)


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
            self._verificar_integridad()
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

    def _verificar_integridad(self):
        """A2 (tanda 3): sin UPS, un corte puede dejar la base dañada. Se fija
        `synchronous = FULL` (cada commit se fuerza a disco, también en WAL) y
        se revisa la integridad al abrir. Si falla se lanza DatabaseError
        "malformed": el arranque aparta la base y opera sin BD con alarma."""
        self._conn.execute("PRAGMA synchronous = FULL")
        resultado = [fila[0] for fila in self._conn.execute("PRAGMA quick_check")]
        if resultado != ["ok"]:
            raise sqlite3.DatabaseError(
                "database disk image is malformed: quick_check: " + "; ".join(map(str, resultado[:3])))

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
        fila = _fila_auditoria(evento, usuario, rol, entidad, valor_anterior, valor_nuevo, detalle)
        with self._lock:
            cur = self._conn.execute(_SQL_AUDITORIA, fila)
            self._conn.commit()
            return cur.lastrowid

    def registrar_auditoria_lote(self, filas: list[dict]) -> list[int]:
        """X9 (tanda 9, D9-13.3 SAF-01): varias filas de audit_log en UNA
        transacción, todas o ninguna (p. ej. el cambio de un parámetro y su
        arrastre automático). Cada fila es un dict con los argumentos de
        `registrar_auditoria`. Si cualquiera falla (valor no serializable,
        error de SQLite), se deshace todo y se relanza la excepción."""
        if not filas:
            return []
        ids: list[int] = []
        with self._lock:
            try:
                # las filas se preparan antes de abrir la transacción: un valor
                # no serializable no llega a tomar el bloqueo de escritura
                preparadas = [_fila_auditoria(**f) for f in filas]
                if self._conn.in_transaction:
                    # revisión X9 (TMG-04/SAF-07): una transacción que otro
                    # método dejó abierta tras una excepción no se mezcla con
                    # el lote (su commit confirmaría trabajo ajeno)
                    logger.warning("audit_log: transacción previa abierta; se deshace antes del lote")
                    self._conn.rollback()
                self._conn.execute("BEGIN IMMEDIATE")
                for fila in preparadas:
                    ids.append(self._conn.execute(_SQL_AUDITORIA, fila).lastrowid)
                self._conn.commit()
            except BaseException:
                try:
                    if self._conn.in_transaction:
                        self._conn.rollback()
                except Exception:
                    logger.exception("audit_log: no se pudo deshacer el lote")
                raise
        return ids

    def registrar_auditoria_tras_cierre(self, evento: str, entidad: str = "",
                                        detalle: dict | None = None) -> None:
        """D8-3.21 (tanda 8): una fila de audit_log después de close() (la
        secuencia de apagado ya cerró la base cuando Windows rechaza el
        apagado). Abre y cierra su propia conexión, sin tomar `self._lock`
        (SAF-05/TMG-03 de la revisión final: un cierre colgado con el lock no
        la bloquea; SQLite serializa las dos conexiones) y sin crear el
        archivo si no existe (`mode=rw`)."""
        uri = Path(self._path).resolve().as_uri() + "?mode=rw"
        con = sqlite3.connect(uri, uri=True, timeout=10.0)
        try:
            con.execute(
                _SQL_AUDITORIA,
                (datetime.now().isoformat(timespec="seconds"), "", "", evento,
                 entidad or "", None, None,
                 json.dumps(detalle, ensure_ascii=False) if detalle else None),
            )
            con.commit()
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Parámetros del equipo (O2a, tanda 6): tabla system_params
    # ------------------------------------------------------------------

    def listar_parametros_sistema(self) -> dict[str, dict]:
        """{clave: fila} con `valor` y `defecto` ya decodificados del JSON."""
        with self._lock:
            filas = self._conn.execute("SELECT * FROM system_params").fetchall()
        resultado = {}
        for f in filas:
            d = dict(f)
            try:
                d["valor"] = json.loads(d["valor"])
                d["defecto"] = json.loads(d["defecto"]) if d["defecto"] is not None else None
            except (TypeError, ValueError):
                continue                       # fila ilegible: se ignora (vale la de fábrica)
            resultado[d["clave"]] = d
        return resultado

    def guardar_parametro_sistema(self, clave: str, valor, defecto, minimo, maximo,
                                  usuario: str = "", fecha: str | None = None) -> None:
        """Inserta o reemplaza la fila. `fecha` None conserva NULL (sembrado
        de fábrica, sin cambio de usuario)."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO system_params (clave, valor, defecto, minimo, maximo, usuario, fecha)"
                " VALUES (?,?,?,?,?,?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor,"
                " defecto=excluded.defecto, minimo=excluded.minimo, maximo=excluded.maximo,"
                " usuario=excluded.usuario, fecha=excluded.fecha",
                (clave, json.dumps(valor), json.dumps(defecto), minimo, maximo,
                 usuario or "", fecha))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Mantenimientos realizados (M1, tanda 3)
    # ------------------------------------------------------------------

    def registrar_mantenimiento(self, fecha: str, usuario: str, tipo: str,
                                observaciones: str, ciclos: int | None) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO mantenimientos (fecha, usuario, tipo, observaciones, ciclos)"
                " VALUES (?,?,?,?,?)", (fecha, usuario or "", tipo or "", observaciones or "", ciclos))
            self._conn.commit()
            return cur.lastrowid

    def ultimo_mantenimiento(self, tipo: str | None = "preventivo") -> dict | None:
        """El más reciente del `tipo` dado por fecha (y por id si coinciden).
        Por defecto solo el preventivo: es el único que reinicia el contador
        (MNT-01, D-2 de planeacion_mantenimiento.md). `tipo=None` = cualquiera."""
        if tipo is None:
            return self.ultimo_registro()
        with self._lock:
            fila = self._conn.execute(
                "SELECT * FROM mantenimientos WHERE tipo = ? ORDER BY fecha DESC, id DESC LIMIT 1",
                (tipo,)).fetchone()
        return dict(fila) if fila else None

    def ultimo_registro(self) -> dict | None:
        """El registro de mantenimiento más reciente de CUALQUIER tipo (fecha,
        luego id). Lo usa la protección del reloj (MNT-01)."""
        with self._lock:
            fila = self._conn.execute(
                "SELECT * FROM mantenimientos ORDER BY fecha DESC, id DESC LIMIT 1").fetchone()
        return dict(fila) if fila else None

    def listar_mantenimientos(self, limite: int = 50) -> list[dict]:
        with self._lock:
            filas = self._conn.execute(
                "SELECT * FROM mantenimientos ORDER BY fecha DESC, id DESC LIMIT ?",
                (int(limite),)).fetchall()
        return [dict(f) for f in filas]

    def conteo_ciclos_por_programa(self) -> dict[int, int]:
        """{numero de programa: ciclos terminados} desde el historial (B6, tanda 4).
        Cuenta todo ciclo cerrado (completo, abortado o con fallo); un ciclo aún en
        curso (sin resultado) o anterior a la columna `numero_programa` no cuenta."""
        with self._lock:
            filas = self._conn.execute(
                "SELECT numero_programa, COUNT(*) FROM ciclos"
                " WHERE numero_programa IS NOT NULL AND resultado IS NOT NULL"
                " GROUP BY numero_programa").fetchall()
        return {int(f[0]): int(f[1]) for f in filas}

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

    def consultar_auditoria(self, desde: str | None = None, hasta: str | None = None,
                            usuario: str | None = None, evento: str | None = None,
                            limite: int = 20, desplazamiento: int = 0) -> tuple[list[dict], int]:
        """O2e: página de audit_log (la más reciente primero) y total con los
        mismos filtros. `desde`/`hasta` comparan contra `ts` (ISO local)."""
        condiciones, params = [], []
        for cond, valor in (("ts >= ?", desde), ("ts < ?", hasta), ("usuario = ?", usuario),
                            ("evento = ?", evento)):
            if valor:
                condiciones.append(cond)
                params.append(valor)
        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
        with self._lock:
            total = self._conn.execute(f"SELECT COUNT(*) FROM audit_log {where}", params).fetchone()[0]
            filas = self._conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, int(limite), int(desplazamiento)]).fetchall()
        resultado = []
        for f in filas:
            d = dict(f)
            try:
                d["detalle"] = json.loads(d["detalle"]) if d["detalle"] else None
            except (TypeError, ValueError):
                pass
            resultado.append(d)
        return resultado, int(total)

    def valores_auditoria(self) -> tuple[list[str], list[str]]:
        """Usuarios y eventos distintos de audit_log (para los filtros)."""
        with self._lock:
            usuarios = [r[0] for r in self._conn.execute(
                "SELECT DISTINCT usuario FROM audit_log WHERE usuario <> '' ORDER BY usuario")]
            eventos = [r[0] for r in self._conn.execute(
                "SELECT DISTINCT evento FROM audit_log ORDER BY evento")]
        return usuarios, eventos

    # ------------------------------------------------------------------
    # Ciclos
    # ------------------------------------------------------------------

    def max_numero_ciclo(self, espera_s: float | None = None) -> int:
        """MAX(numero_ciclo). Con `espera_s` (TMG-02: llamada desde el tick)
        no espera el candado de la base más de ese tiempo: lanza TimeoutError
        y quien llama sigue sin el dato."""
        if espera_s is None:
            self._lock.acquire()
        elif not self._lock.acquire(timeout=espera_s):
            raise TimeoutError("base ocupada")
        try:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(numero_ciclo), 0) FROM ciclos").fetchone()
        finally:
            self._lock.release()
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
                     codigo_fallo: str | None = None, f0_final: float | None = None,
                     valores_fallo: dict | None = None, avisos_ticket: dict | None = None):
        """Registra la hora de fin, el resultado y (si lo hay) el motivo, el
        código y los parámetros del fallo, y el F0 final si el ciclo tenía F0 activo.
        `avisos_ticket` (D8-2.14): líneas de aviso del pie del ticket."""
        with self._lock:
            self._conn.execute(
                "UPDATE ciclos SET fecha_fin=?, resultado=?, motivo_fallo=?, codigo_fallo=?, "
                "f0_final=?, valores_fallo=?, avisos_ticket=? WHERE id=?",
                (datetime.now().isoformat(), resultado, motivo_fallo or "",
                 codigo_fallo or "", f0_final, _valores_fallo_json(valores_fallo),
                 _valores_fallo_json(avisos_ticket), ciclo_id),
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
                           cierre.get("f0_final"),
                           _valores_fallo_json(cierre.get("avisos_ticket")))
                else:
                    fin = (datetime.now().isoformat(), "INTERRUMPIDO",
                           motivo_interrumpido, "", None, "")
                cur = self._conn.execute(
                    """
                    INSERT INTO ciclos
                        (numero_ciclo, fecha_inicio, tipo_ciclo, nombre_ciclo,
                         temp_esterilizacion, tiempo_esterilizacion,
                         modelo, serie, version_sw, operador,
                         asignacion_sensores, numero_programa, uuid, programa_json,
                         fecha_fin, resultado, motivo_fallo, codigo_fallo, f0_final,
                         avisos_ticket)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    "f0_final=?, valores_fallo=?, avisos_ticket=? WHERE id=?",
                    (cierre.get("fecha_fin") or datetime.now().isoformat(),
                     cierre.get("resultado") or "DESCONOCIDO", cierre.get("motivo") or "",
                     cierre.get("codigo") or "", cierre.get("f0_final"),
                     _valores_fallo_json(cierre.get("valores")),
                     _valores_fallo_json(cierre.get("avisos_ticket")), ciclo_id))
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

    def get_ciclos_con_resultado(self, desde: str, hasta: str, resultado: str,
                                 limite: int, desplazamiento: int) -> tuple[list, int]:
        """D8-5.6: ciclos iniciados en [desde, hasta) (mismo criterio que
        get_conteo_resultados) que cerraron con `resultado`, más recientes
        primero, una página (limite / desplazamiento); y cuántos son en total.
        Solo lectura (Reportes: ciclos de un tipo de fallo)."""
        filtro = " FROM ciclos WHERE fecha_inicio >= ? AND fecha_inicio < ? AND resultado = ?"
        params = (desde, hasta, resultado)
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*)" + filtro, params).fetchone()[0]
            filas = self._conn.execute(
                "SELECT *" + filtro + " ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limite, desplazamiento),
            ).fetchall()
        return filas, total

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
        """Inserta un usuario. Lanza sqlite3.IntegrityError si `usuario` ya
        existe sin distinguir mayúsculas (incluidos inactivos; U11, D11-6.4).
        La comprobación va con el candado tomado, en el mismo bloque que el
        INSERT, para que dos altas en paralelo no la pasen ambas."""
        buscado = usuario.casefold()
        with self._lock:
            if any(f[0].casefold() == buscado
                   for f in self._conn.execute("SELECT usuario FROM usuarios")):
                raise sqlite3.IntegrityError(f"usuario ya existe: {usuario!r}")
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
        """Usuario ACTIVO para iniciar sesión, sin distinguir mayúsculas (U11,
        D11-6.4; casefold en Python, como existe_usuario). Si en una base
        antigua dos usuarios difieren solo en mayúsculas, decide la
        coincidencia exacta; sin ella no se elige ninguno (None). Un candidato
        inactivo cuenta para esa decisión pero nunca se devuelve."""
        buscado = usuario.casefold()
        with self._lock:
            filas = [dict(f) for f in self._conn.execute("SELECT * FROM usuarios")]
        candidatos = [f for f in filas if f["usuario"].casefold() == buscado]
        exacto = [f for f in candidatos if f["usuario"] == usuario]
        elegido = exacto[0] if exacto else (candidatos[0] if len(candidatos) == 1 else None)
        return elegido if elegido is not None and elegido["activo"] == 1 else None

    def actualizar_password(self, usuario: str, hash_pw: str) -> None:
        """Guarda el nuevo hash y baja la bandera debe_cambiar_clave."""
        with self._lock:
            self._conn.execute(
                "UPDATE usuarios SET hash_pw=?, debe_cambiar_clave=0 WHERE usuario=?",
                (hash_pw, usuario),
            )
            self._conn.commit()

    # ── Gestión de usuarios y operadores (O2b, tanda 6) ─────────────────

    _CAMPOS_USUARIO = ("id, nombre, usuario, rol, activo, creado_por, creado_en,"
                       " debe_cambiar_clave, cuenta_sistema")

    def listar_usuarios(self) -> list[dict]:
        """Todos los usuarios (activos e inactivos), SIN el hash, con el último
        ingreso (`login_ok` de audit_log; None si nunca)."""
        with self._lock:
            filas = self._conn.execute(
                f"SELECT {self._CAMPOS_USUARIO} FROM usuarios ORDER BY nombre COLLATE NOCASE, id"
            ).fetchall()
            ingresos = dict(self._conn.execute(
                "SELECT usuario, MAX(ts) FROM audit_log WHERE evento='login_ok' GROUP BY usuario"
            ).fetchall())
        resultado = []
        for f in filas:
            d = dict(f)
            d["activo"] = bool(d["activo"])
            d["debe_cambiar_clave"] = bool(d["debe_cambiar_clave"])
            d["cuenta_sistema"] = bool(d["cuenta_sistema"])
            d["ultimo_ingreso"] = ingresos.get(d["usuario"])
            resultado.append(d)
        return resultado

    def get_usuario_cualquiera(self, usuario: str) -> dict | None:
        """El usuario (activo o no), SIN el hash; None si no existe."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {self._CAMPOS_USUARIO} FROM usuarios WHERE usuario=?", (usuario,)
            ).fetchone()
        return dict(row) if row else None

    def fijar_activo_usuario(self, usuario: str, activo: bool, rol_protegido: str) -> str:
        """Activa o desactiva. Comprobación y escritura en el mismo bloque con
        el candado tomado: desactivar el último `rol_protegido` activo se
        rechaza. Una cuenta del sistema (U11) no se desactiva. Devuelve "ok",
        "no_existe", "cuenta_sistema", "sin_cambio" o "ultimo_protegido"."""
        with self._lock:
            row = self._conn.execute(
                "SELECT rol, activo, cuenta_sistema FROM usuarios WHERE usuario=?",
                (usuario,)).fetchone()
            if row is None:
                return "no_existe"
            if not activo and row["cuenta_sistema"]:
                return "cuenta_sistema"
            if bool(row["activo"]) == bool(activo):
                return "sin_cambio"
            if not activo and row["rol"] == rol_protegido:
                otros = self._conn.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE rol=? AND activo=1 AND usuario<>?",
                    (rol_protegido, usuario)).fetchone()[0]
                if otros == 0:
                    return "ultimo_protegido"
            self._conn.execute("UPDATE usuarios SET activo=? WHERE usuario=?",
                               (1 if activo else 0, usuario))
            self._conn.commit()
            return "ok"

    def restablecer_password(self, usuario: str, hash_pw: str) -> bool:
        """Nuevo hash y cambio obligatorio en el siguiente login. False si no existe."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE usuarios SET hash_pw=?, debe_cambiar_clave=1 WHERE usuario=?",
                (hash_pw, usuario))
            self._conn.commit()
            return cur.rowcount > 0

    def listar_operadores(self, solo_activos: bool = False) -> list[dict]:
        where = "WHERE activo=1 " if solo_activos else ""
        with self._lock:
            filas = self._conn.execute(
                f"SELECT * FROM operadores {where}ORDER BY nombre COLLATE NOCASE, id").fetchall()
        return [{**dict(f), "activo": bool(f["activo"])} for f in filas]

    def crear_operador(self, nombre: str, creado_por: str = "") -> int | None:
        """Id del nuevo operador; None si ya existe uno con ese nombre (sin
        distinguir mayúsculas, activo o no)."""
        buscado = nombre.casefold()
        with self._lock:
            nombres = [f[0] for f in self._conn.execute("SELECT nombre FROM operadores")]
            if any(n.casefold() == buscado for n in nombres):
                return None
            cur = self._conn.execute(
                "INSERT INTO operadores (nombre, activo, creado_por, creado_en) VALUES (?,1,?,?)",
                (nombre, creado_por or "", datetime.now().isoformat(timespec="seconds")))
            self._conn.commit()
            return cur.lastrowid

    def fijar_activo_operador(self, id_: int, activo: bool) -> dict | None:
        """Fila anterior del operador (None si no existe) y aplica el cambio."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM operadores WHERE id=?", (id_,)).fetchone()
            if row is None:
                return None
            self._conn.execute("UPDATE operadores SET activo=? WHERE id=?",
                               (1 if activo else 0, id_))
            self._conn.commit()
        return {**dict(row), "activo": bool(row["activo"])}

    def seed_admin_if_empty(self) -> None:
        """Con la tabla vacía crea las cuentas del sistema `Admin` e
        `Ingeniero` (U11), marcadas y obligadas a cambiar la contraseña en el
        primer login."""
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM usuarios"
            ).fetchone()[0]
            if count == 0:
                for nombre, usuario, rol, hash_pw in _USUARIOS_SEMILLA:
                    self._conn.execute(
                        "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo,"
                        " creado_por, creado_en, debe_cambiar_clave, cuenta_sistema)"
                        " VALUES (?,?,?,?,1,'semilla',?,1,1)",
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
