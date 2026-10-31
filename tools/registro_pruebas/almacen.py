# tools/registro_pruebas/almacen.py
#
# Base y reglas de integridad de la app de registro de pruebas (F1, tanda 3).
#
# - Cada registro de campaña pertenece a UN usuario. Solo él lo edita; el admin
#   ve todos y consolida.
# - NADA se sobrescribe: cada guardado agrega una versión inmutable (triggers
#   contra UPDATE/DELETE) con usuario, hora del SERVIDOR, hora del teléfono
#   (que no es confiable), motivo y un hash SHA-256 encadenado con la versión
#   anterior del mismo registro. Un resultado firmado solo cambia con una
#   versión nueva con motivo.
# - Fotos y firmas son evidencia inmutable (archivo + sha256) y también entran
#   a la cadena, de modo que una alteración posterior se detecta.
# - Los guardados llevan un `cliente_uuid`: un reintento de la cola del teléfono
#   no duplica nada (idempotencia).

import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import definiciones

BUSY_TIMEOUT_MS = 5000
ROLES = ("admin", "ejecutor")
GRAVEDADES = ("seguridad", "funcional", "cosmetica")
ESTADOS_ANOMALIA = ("abierta", "en_analisis", "corregida", "cerrada")
_UUID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# "id_tarjeta" es el ID del módulo E/S; la clave se conserva porque va guardada
# en las cabeceras de los registros ya hechos (tanda 23, MES-03.2).
CAMPOS_CABECERA = ("equipo", "serial", "version_software", "commit", "firmware", "id_tarjeta",
                   "perfil_instalacion", "programas", "instrumentos", "fecha", "lugar")
CABECERA_MAX = 2000

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    usuario       TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL DEFAULT '',
    hash          TEXT NOT NULL,
    rol           TEXT NOT NULL CHECK(rol IN ('admin', 'ejecutor')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado        TEXT NOT NULL,
    debe_cambiar  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS registros (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario        TEXT NOT NULL REFERENCES usuarios(usuario),
    creado         TEXT NOT NULL,
    snapshot       TEXT NOT NULL,
    snapshot_hash  TEXT NOT NULL,
    estado         TEXT NOT NULL DEFAULT 'abierto' CHECK(estado IN ('abierto', 'cerrado')),
    cerrado_en     TEXT
);
CREATE TABLE IF NOT EXISTS versiones (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id   INTEGER NOT NULL REFERENCES registros(id),
    seq           INTEGER NOT NULL,
    clave         TEXT NOT NULL,          -- cabecera | <id de prueba> | AN-nnn | cierre
    tipo          TEXT NOT NULL,          -- cabecera | prueba | foto | firma | anomalia | cierre
    datos         TEXT NOT NULL,          -- JSON canónico
    usuario       TEXT NOT NULL,
    ts_servidor   TEXT NOT NULL,
    ts_cliente    TEXT,
    motivo        TEXT NOT NULL DEFAULT '',
    cliente_uuid  TEXT,
    hash_prev     TEXT NOT NULL,
    hash          TEXT NOT NULL,
    UNIQUE(registro_id, seq)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_versiones_uuid
    ON versiones(registro_id, cliente_uuid) WHERE cliente_uuid IS NOT NULL;
CREATE TABLE IF NOT EXISTS evidencias (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id   INTEGER NOT NULL REFERENCES registros(id),
    prueba_id     TEXT NOT NULL,
    tipo          TEXT NOT NULL CHECK(tipo IN ('foto', 'firma')),
    cliente_id    TEXT NOT NULL,
    archivo       TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    bytes         INTEGER NOT NULL,
    usuario       TEXT NOT NULL,
    ts_servidor   TEXT NOT NULL,
    ts_cliente    TEXT,
    UNIQUE(registro_id, tipo, cliente_id)
);
"""
_TRIGGERS = [
    f"CREATE TRIGGER IF NOT EXISTS {t}_sin_{a.lower()} BEFORE {a} ON {t} "
    f"BEGIN SELECT RAISE(ABORT, '{t} es de solo anexar'); END"
    for t in ("versiones", "evidencias") for a in ("UPDATE", "DELETE")]


class ErrorRegistro(Exception):
    def __init__(self, codigo: str, motivo: str, estado: int = 409):
        super().__init__(motivo)
        self.codigo, self.motivo, self.estado = codigo, motivo, estado


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_version(registro_id, seq, clave, tipo, datos, usuario, ts_servidor, ts_cliente,
                 motivo, hash_prev) -> str:
    cuerpo = _canon({"registro_id": registro_id, "seq": seq, "clave": clave, "tipo": tipo,
                     "datos": datos, "usuario": usuario, "ts_servidor": ts_servidor,
                     "ts_cliente": ts_cliente, "motivo": motivo, "hash_prev": hash_prev})
    return hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()


GENESIS = "0" * 64


class Almacen:
    def __init__(self, datos: Path, fuente_pruebas: Path | None = None):
        self.datos = Path(datos)
        self.ruta = self.datos / "registro.db"
        self.fuente_pruebas = fuente_pruebas
        self._lock = threading.Lock()
        self.datos.mkdir(parents=True, exist_ok=True)
        for sub in ("fotos", "firmas", "exportaciones", "respaldos"):
            (self.datos / sub).mkdir(exist_ok=True)
        with self.conectar() as con:
            con.execute("PRAGMA journal_mode = WAL")
            con.executescript(_ESQUEMA)
            for sentencia in _TRIGGERS:
                con.execute(sentencia)
        con_cierre = self.conectar()
        con_cierre.close()

    def conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
        con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        con.execute("PRAGMA synchronous = FULL")
        con.row_factory = sqlite3.Row
        return con

    # ── usuarios ─────────────────────────────────────────────────────────
    def hay_usuarios(self) -> bool:
        con = self.conectar()
        try:
            return con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None
        finally:
            con.close()

    def crear_usuario(self, usuario: str, nombre: str, hash_clave: str, rol: str,
                      debe_cambiar: bool = True) -> None:
        if rol not in ROLES:
            raise ErrorRegistro("rol_invalido", "Rol inválido", 422)
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,32}", usuario or ""):
            raise ErrorRegistro("usuario_invalido",
                                "Usuario: 3 a 32 caracteres (letras, números, . _ -)", 422)
        con = self.conectar()
        try:
            con.execute("INSERT INTO usuarios (usuario, nombre, hash, rol, activo, creado, debe_cambiar)"
                        " VALUES (?,?,?,?,1,?,?)",
                        (usuario, (nombre or "")[:80], hash_clave, rol, ahora(), 1 if debe_cambiar else 0))
        except sqlite3.IntegrityError:
            raise ErrorRegistro("usuario_existe", "Ese usuario ya existe", 409)
        finally:
            con.close()

    def usuario(self, usuario: str) -> dict | None:
        con = self.conectar()
        try:
            fila = con.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
            return dict(fila) if fila else None
        finally:
            con.close()

    def listar_usuarios(self) -> list[dict]:
        con = self.conectar()
        try:
            return [dict(f) for f in con.execute(
                "SELECT usuario, nombre, rol, activo, creado, debe_cambiar FROM usuarios ORDER BY usuario")]
        finally:
            con.close()

    def fijar_clave(self, usuario: str, hash_clave: str, debe_cambiar: bool) -> None:
        con = self.conectar()
        try:
            con.execute("UPDATE usuarios SET hash=?, debe_cambiar=? WHERE usuario=?",
                        (hash_clave, 1 if debe_cambiar else 0, usuario))
        finally:
            con.close()

    def fijar_activo(self, usuario: str, activo: bool) -> None:
        con = self.conectar()
        try:
            con.execute("UPDATE usuarios SET activo=? WHERE usuario=?", (1 if activo else 0, usuario))
        finally:
            con.close()

    def admins_activos(self) -> int:
        con = self.conectar()
        try:
            return con.execute("SELECT COUNT(*) FROM usuarios WHERE rol='admin' AND activo=1").fetchone()[0]
        finally:
            con.close()

    # ── cadena de versiones ──────────────────────────────────────────────
    def _agregar(self, con, registro_id: int, clave: str, tipo: str, datos: dict, usuario: str,
                 ts_cliente: str | None, motivo: str = "", cliente_uuid: str | None = None) -> dict:
        """Agrega una versión a la cadena del registro. Llamar dentro de una
        transacción IMMEDIATE. Devuelve la fila; si el `cliente_uuid` ya existe,
        devuelve la ya guardada (reintento de la cola) con `repetida=True`."""
        if cliente_uuid:
            previa = con.execute("SELECT * FROM versiones WHERE registro_id=? AND cliente_uuid=?",
                                 (registro_id, cliente_uuid)).fetchone()
            if previa:
                return {**dict(previa), "repetida": True}
        ultima = con.execute("SELECT seq, hash FROM versiones WHERE registro_id=? ORDER BY seq DESC LIMIT 1",
                             (registro_id,)).fetchone()
        seq = (ultima["seq"] + 1) if ultima else 1
        prev = ultima["hash"] if ultima else GENESIS
        ts = ahora()
        h = hash_version(registro_id, seq, clave, tipo, datos, usuario, ts, ts_cliente, motivo, prev)
        con.execute(
            "INSERT INTO versiones (registro_id, seq, clave, tipo, datos, usuario, ts_servidor, ts_cliente,"
            " motivo, cliente_uuid, hash_prev, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (registro_id, seq, clave, tipo, _canon(datos), usuario, ts, ts_cliente, motivo,
             cliente_uuid, prev, h))
        return {"registro_id": registro_id, "seq": seq, "clave": clave, "tipo": tipo, "datos": _canon(datos),
                "usuario": usuario, "ts_servidor": ts, "ts_cliente": ts_cliente, "motivo": motivo,
                "cliente_uuid": cliente_uuid, "hash_prev": prev, "hash": h, "repetida": False}

    def _transaccion(self):
        con = self.conectar()
        con.execute("BEGIN IMMEDIATE")
        return con

    @staticmethod
    def _validar_ts(valor) -> str | None:
        """REG-08: hora del teléfono; texto corto o nada (no es confiable)."""
        if valor in (None, ""):
            return None
        if not isinstance(valor, str) or len(valor) > 40:
            raise ErrorRegistro("validacion", "ts_cliente inválido", 422)
        return valor

    @staticmethod
    def _validar_uuid(valor, campo="cliente_uuid") -> str | None:
        if valor in (None, ""):
            return None
        if not isinstance(valor, str) or not _UUID.match(valor):
            raise ErrorRegistro("validacion", f"{campo} inválido", 422)
        return valor

    # ── registros ────────────────────────────────────────────────────────
    def _limpiar_cabecera(self, cab) -> dict:
        if not isinstance(cab, dict):
            raise ErrorRegistro("validacion", "La cabecera debe ser un objeto", 422)
        limpia = {}
        for campo in CAMPOS_CABECERA:
            valor = cab.get(campo, "")
            if not isinstance(valor, (str, int, float)) or isinstance(valor, bool):
                raise ErrorRegistro("validacion", f"cabecera.{campo} inválido", 422)
            valor = str(valor).strip()
            if len(valor) > CABECERA_MAX:
                raise ErrorRegistro("validacion", f"cabecera.{campo} demasiado largo", 422)
            limpia[campo] = valor
        return limpia

    def crear_registro(self, usuario: str, cabecera: dict, ts_cliente: str | None = None,
                       cliente_uuid: str | None = None) -> int:
        cabecera = self._limpiar_cabecera(cabecera)
        ts_cliente = self._validar_ts(ts_cliente)
        snapshot = definiciones.construir_snapshot(self.fuente_pruebas)
        cliente_uuid = self._validar_uuid(cliente_uuid)
        con = self._transaccion()
        try:
            if cliente_uuid:    # reintento: el mismo uuid de creación devuelve el registro ya creado
                previa = con.execute(
                    "SELECT registro_id FROM versiones WHERE cliente_uuid=? AND usuario=? AND clave='cabecera'"
                    " AND seq=1", (cliente_uuid, usuario)).fetchone()
                if previa:
                    con.execute("COMMIT")
                    return previa["registro_id"]
            cur = con.execute(
                "INSERT INTO registros (usuario, creado, snapshot, snapshot_hash) VALUES (?,?,?,?)",
                (usuario, ahora(), _canon(snapshot), snapshot["hash"]))
            rid = cur.lastrowid
            self._agregar(con, rid, "cabecera", "cabecera", cabecera, usuario, ts_cliente,
                          cliente_uuid=cliente_uuid)
            con.execute("COMMIT")
            return rid
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def _registro(self, con, registro_id: int) -> sqlite3.Row:
        fila = con.execute("SELECT * FROM registros WHERE id=?", (registro_id,)).fetchone()
        if fila is None:
            raise ErrorRegistro("no_existe", "El registro no existe", 404)
        return fila

    def _exigir_dueno(self, fila, usuario: dict) -> None:
        if fila["usuario"] != usuario["usuario"]:
            raise ErrorRegistro("no_es_suyo", "Solo el dueño del registro puede modificarlo", 403)
        if fila["estado"] != "abierto":
            raise ErrorRegistro("cerrado", "El registro está cerrado: no admite cambios", 409)

    def _comprobar_dueno(self, registro_id: int, usuario: dict) -> None:
        """Permiso antes que validación de datos: un ajeno recibe 403, no 422."""
        con = self.conectar()
        try:
            self._exigir_dueno(self._registro(con, registro_id), usuario)
        finally:
            con.close()

    def acceso(self, registro_id: int, usuario: dict) -> sqlite3.Row:
        """Lectura: el dueño y el admin."""
        con = self.conectar()
        try:
            fila = self._registro(con, registro_id)
        finally:
            con.close()
        if fila["usuario"] != usuario["usuario"] and usuario["rol"] != "admin":
            raise ErrorRegistro("no_es_suyo", "Ese registro es de otro usuario", 403)
        return fila

    def listar_registros(self, usuario: dict) -> list[dict]:
        con = self.conectar()
        try:
            consulta = ("SELECT id, usuario, creado, estado, cerrado_en, snapshot_hash FROM registros"
                        + ("" if usuario["rol"] == "admin" else " WHERE usuario = ?")
                        + " ORDER BY id DESC")
            filas = con.execute(consulta, () if usuario["rol"] == "admin" else (usuario["usuario"],))
            salida = []
            for f in filas:
                d = dict(f)
                cab = con.execute("SELECT datos FROM versiones WHERE registro_id=? AND clave='cabecera'"
                                  " ORDER BY seq DESC LIMIT 1", (f["id"],)).fetchone()
                d["cabecera"] = json.loads(cab["datos"]) if cab else {}
                salida.append(d)
            return salida
        finally:
            con.close()

    def estado_registro(self, registro_id: int) -> dict:
        """Estado vigente: cabecera, pruebas (última versión de cada una),
        anomalías, evidencias, cierre y la cadena completa de versiones."""
        con = self.conectar()
        try:
            fila = self._registro(con, registro_id)
            versiones = [dict(v) for v in con.execute(
                "SELECT * FROM versiones WHERE registro_id=? ORDER BY seq", (registro_id,))]
            evidencias = [dict(e) for e in con.execute(
                "SELECT id, prueba_id, tipo, cliente_id, sha256, bytes, usuario, ts_servidor, ts_cliente "
                "FROM evidencias WHERE registro_id=? ORDER BY id", (registro_id,))]
        finally:
            con.close()
        for v in versiones:
            v["datos"] = json.loads(v["datos"])
        cabecera, pruebas, anomalias, cierre = {}, {}, {}, None
        for v in versiones:
            if v["tipo"] == "cabecera":
                cabecera = v["datos"]
            elif v["tipo"] == "prueba":
                pruebas[v["clave"]] = {**v["datos"], "version": v["seq"], "ts_servidor": v["ts_servidor"],
                                       "usuario": v["usuario"]}
            elif v["tipo"] == "anomalia":
                anomalias[v["clave"]] = {**v["datos"], "version": v["seq"], "ts_servidor": v["ts_servidor"]}
            elif v["tipo"] == "cierre":
                cierre = {**v["datos"], "ts_servidor": v["ts_servidor"], "usuario": v["usuario"]}
        cambios = {}
        for v in versiones:
            if v["tipo"] == "prueba":
                cambios[v["clave"]] = cambios.get(v["clave"], 0) + 1
        for clave, p in pruebas.items():
            p["cambios"] = cambios.get(clave, 0)
        return {"id": fila["id"], "usuario": fila["usuario"], "creado": fila["creado"],
                "estado": fila["estado"], "cerrado_en": fila["cerrado_en"],
                "snapshot": json.loads(fila["snapshot"]), "snapshot_hash": fila["snapshot_hash"],
                "cabecera": cabecera, "pruebas": pruebas, "anomalias": anomalias, "cierre": cierre,
                "evidencias": evidencias, "versiones": versiones}

    # ── guardado de datos ────────────────────────────────────────────────
    def guardar_cabecera(self, registro_id: int, usuario: dict, cabecera: dict,
                         ts_cliente=None, cliente_uuid=None, motivo: str = "") -> dict:
        self._comprobar_dueno(registro_id, usuario)
        ts_cliente = self._validar_ts(ts_cliente)
        cabecera = self._limpiar_cabecera(cabecera)
        cliente_uuid = self._validar_uuid(cliente_uuid)
        con = self._transaccion()
        try:
            self._exigir_dueno(self._registro(con, registro_id), usuario)
            v = self._agregar(con, registro_id, "cabecera", "cabecera", cabecera, usuario["usuario"],
                              ts_cliente, (motivo or "")[:500], cliente_uuid)
            con.execute("COMMIT")
            return v
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def _evidencia(self, con, registro_id: int, tipo: str, cliente_id: str, prueba_id: str | None = None):
        return con.execute("SELECT * FROM evidencias WHERE registro_id=? AND tipo=? AND cliente_id=?",
                           (registro_id, tipo, cliente_id)).fetchone()

    def guardar_prueba(self, registro_id: int, usuario: dict, prueba_id: str, datos: dict,
                       ts_cliente=None, cliente_uuid=None, motivo: str = "") -> dict:
        self._comprobar_dueno(registro_id, usuario)
        cliente_uuid = self._validar_uuid(cliente_uuid)
        ts_cliente = self._validar_ts(ts_cliente)
        if not isinstance(datos, dict):
            raise ErrorRegistro("validacion", "Datos de prueba inválidos", 422)
        pasos = datos.get("pasos", [])
        valores = datos.get("valores", {})
        resultado = datos.get("resultado")
        observaciones = datos.get("observaciones", "")
        firma = datos.get("firma_id")
        if (not isinstance(pasos, list) or len(pasos) > 60 or not all(isinstance(p, bool) for p in pasos)):
            raise ErrorRegistro("validacion", "pasos: lista de casillas (verdadero/falso)", 422)
        if not isinstance(valores, dict) or len(valores) > 40 or not all(
                isinstance(k, str) and len(k) <= 60 and isinstance(v, (str, int, float))
                and not isinstance(v, bool) and len(str(v)) <= 200 for k, v in valores.items()):
            raise ErrorRegistro("validacion", "valores: máximo 40 entradas de texto corto", 422)
        if resultado is not None and resultado not in definiciones.RESULTADOS:
            raise ErrorRegistro("validacion", "resultado: aprobada, fallada o no_aplica", 422)
        if not isinstance(observaciones, str) or len(observaciones) > 2000:
            raise ErrorRegistro("validacion", "observaciones: máximo 2000 caracteres", 422)
        if firma is not None:
            self._validar_uuid(firma, "firma_id")
        limpios = {"pasos": pasos, "valores": {k: str(v) for k, v in valores.items()},
                   "resultado": resultado, "observaciones": observaciones.strip(),
                   "firma_id": firma, "hora_ejecucion": ts_cliente}
        con = self._transaccion()
        try:
            fila = self._registro(con, registro_id)
            self._exigir_dueno(fila, usuario)
            snapshot = json.loads(fila["snapshot"])
            if definiciones.prueba_por_id(snapshot, prueba_id) is None:
                raise ErrorRegistro("prueba_desconocida", "La prueba no existe en este registro", 404)
            if cliente_uuid and con.execute("SELECT 1 FROM versiones WHERE registro_id=? AND cliente_uuid=?",
                                            (registro_id, cliente_uuid)).fetchone():
                v = self._agregar(con, registro_id, prueba_id, "prueba", limpios, usuario["usuario"],
                                  ts_cliente, motivo, cliente_uuid)
                con.execute("COMMIT")
                return v
            if resultado is not None:
                if firma is None:
                    raise ErrorRegistro("falta_firma", "Marcar un resultado exige la firma en pantalla", 422)
                ev = self._evidencia(con, registro_id, "firma", firma, prueba_id)
                if ev is None or ev["prueba_id"] != prueba_id or ev["usuario"] != usuario["usuario"]:
                    raise ErrorRegistro("firma_invalida", "La firma no existe para esta prueba", 422)
            previa = con.execute(
                "SELECT datos FROM versiones WHERE registro_id=? AND clave=? AND tipo='prueba'"
                " ORDER BY seq DESC LIMIT 1", (registro_id, prueba_id)).fetchone()
            if previa:
                anterior = json.loads(previa["datos"])
                # REG-01: la firma no se reutiliza para un resultado distinto
                if (resultado is not None and anterior.get("firma_id") == firma
                        and anterior.get("resultado") != resultado):
                    raise ErrorRegistro("falta_firma_nueva",
                                        "Cambiar el resultado exige una firma nueva", 422)
                cambio = {k: anterior.get(k) for k in ("pasos", "valores", "resultado", "observaciones")} != \
                         {k: limpios[k] for k in ("pasos", "valores", "resultado", "observaciones")}
                if anterior.get("resultado") is not None and anterior.get("firma_id") and cambio \
                        and not (motivo or "").strip():
                    raise ErrorRegistro("falta_motivo",
                                        "Modificar un resultado ya firmado exige indicar el motivo del cambio", 422)
            v = self._agregar(con, registro_id, prueba_id, "prueba", limpios, usuario["usuario"],
                              ts_cliente, (motivo or "").strip()[:500], cliente_uuid)
            con.execute("COMMIT")
            return v
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def guardar_evidencia(self, registro_id: int, usuario: dict, prueba_id: str, tipo: str,
                          cliente_id: str, contenido: bytes, extension: str,
                          ts_cliente: str | None = None) -> dict:
        """Guarda una foto o firma (archivo + sha256) y la agrega a la cadena."""
        self._validar_uuid(cliente_id, "cliente_id")
        ts_cliente = self._validar_ts(ts_cliente)
        if not cliente_id:
            raise ErrorRegistro("validacion", "cliente_id es obligatorio", 422)
        sha = hashlib.sha256(contenido).hexdigest()
        con = self._transaccion()
        try:
            fila = self._registro(con, registro_id)
            self._exigir_dueno(fila, usuario)
            snapshot = json.loads(fila["snapshot"])
            es_cierre = tipo == "firma" and prueba_id == "cierre"      # firma final del registro
            if not es_cierre and definiciones.prueba_por_id(snapshot, prueba_id) is None:
                raise ErrorRegistro("prueba_desconocida", "La prueba no existe en este registro", 404)
            previa = self._evidencia(con, registro_id, tipo, cliente_id, prueba_id)
            if previa:
                con.execute("COMMIT")
                return {**dict(previa), "repetida": True}
            subcarpeta = "fotos" if tipo == "foto" else "firmas"
            nombre = f"R{registro_id}_{prueba_id}_{tipo}_{sha[:12]}{extension}"
            ruta = self.datos / subcarpeta / nombre
            ruta.write_bytes(contenido)
            ts = ahora()
            cur = con.execute(
                "INSERT INTO evidencias (registro_id, prueba_id, tipo, cliente_id, archivo, sha256, bytes,"
                " usuario, ts_servidor, ts_cliente) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (registro_id, prueba_id, tipo, cliente_id, f"{subcarpeta}/{nombre}", sha, len(contenido),
                 usuario["usuario"], ts, ts_cliente))
            self._agregar(con, registro_id, prueba_id, tipo,
                          {"evidencia_id": cur.lastrowid, "cliente_id": cliente_id, "sha256": sha,
                           "archivo": f"{subcarpeta}/{nombre}"}, usuario["usuario"], ts_cliente)
            con.execute("COMMIT")
            return {"id": cur.lastrowid, "registro_id": registro_id, "prueba_id": prueba_id, "tipo": tipo,
                    "cliente_id": cliente_id, "archivo": f"{subcarpeta}/{nombre}", "sha256": sha,
                    "bytes": len(contenido), "repetida": False}
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def evidencia(self, evidencia_id: int):
        con = self.conectar()
        try:
            fila = con.execute("SELECT * FROM evidencias WHERE id=?", (evidencia_id,)).fetchone()
            return dict(fila) if fila else None
        finally:
            con.close()

    # ── anomalías ────────────────────────────────────────────────────────
    def _limpiar_anomalia(self, datos: dict) -> dict:
        if not isinstance(datos, dict):
            raise ErrorRegistro("validacion", "Anomalía inválida", 422)
        limpia = {}
        for campo, maximo in (("prueba_id", 20), ("descripcion", 2000), ("accion", 2000),
                              ("responsable", 80), ("reensayo", 500)):
            valor = datos.get(campo, "")
            if not isinstance(valor, str) or len(valor) > maximo:
                raise ErrorRegistro("validacion", f"anomalía.{campo} inválido", 422)
            limpia[campo] = valor.strip()
        if not limpia["descripcion"]:
            raise ErrorRegistro("validacion", "La anomalía necesita una descripción", 422)
        if datos.get("gravedad") not in GRAVEDADES:
            raise ErrorRegistro("validacion", "gravedad: seguridad, funcional o cosmetica", 422)
        limpia["gravedad"] = datos["gravedad"]
        estado = datos.get("estado", "abierta")
        if estado not in ESTADOS_ANOMALIA:
            raise ErrorRegistro("validacion", "estado de anomalía inválido", 422)
        limpia["estado"] = estado
        return limpia

    def guardar_anomalia(self, registro_id: int, usuario: dict, datos: dict, anomalia_id: str | None = None,
                         ts_cliente=None, cliente_uuid=None, motivo: str = "") -> dict:
        self._comprobar_dueno(registro_id, usuario)
        cliente_uuid = self._validar_uuid(cliente_uuid)
        limpia = self._limpiar_anomalia(datos)
        con = self._transaccion()
        try:
            fila = self._registro(con, registro_id)
            self._exigir_dueno(fila, usuario)
            snapshot = json.loads(fila["snapshot"])
            if limpia["prueba_id"] and definiciones.prueba_por_id(snapshot, limpia["prueba_id"]) is None:
                raise ErrorRegistro("prueba_desconocida", "La prueba de la anomalía no existe", 404)
            if cliente_uuid:
                previa = con.execute("SELECT * FROM versiones WHERE registro_id=? AND cliente_uuid=?",
                                     (registro_id, cliente_uuid)).fetchone()
                if previa:
                    con.execute("COMMIT")
                    return {**dict(previa), "repetida": True}
            if anomalia_id is None:
                n = con.execute("SELECT COUNT(DISTINCT clave) FROM versiones WHERE registro_id=? AND tipo='anomalia'",
                                (registro_id,)).fetchone()[0] + 1
                anomalia_id = f"AN-{n:03d}"
            elif not con.execute("SELECT 1 FROM versiones WHERE registro_id=? AND clave=? AND tipo='anomalia'",
                                 (registro_id, anomalia_id)).fetchone():
                raise ErrorRegistro("anomalia_desconocida", "La anomalía no existe", 404)
            v = self._agregar(con, registro_id, anomalia_id, "anomalia", limpia, usuario["usuario"],
                              ts_cliente, (motivo or "").strip()[:500], cliente_uuid)
            con.execute("COMMIT")
            return {**v, "anomalia_id": anomalia_id}
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    # ── cierre ───────────────────────────────────────────────────────────
    def cerrar_registro(self, registro_id: int, usuario: dict, firma_id: str, confirmar_incompleto: bool,
                        ts_cliente=None, cliente_uuid=None) -> dict:
        self._validar_uuid(firma_id, "firma_id")
        cliente_uuid = self._validar_uuid(cliente_uuid)
        con = self._transaccion()
        try:
            fila = self._registro(con, registro_id)
            self._exigir_dueno(fila, usuario)
            ev = self._evidencia(con, registro_id, "firma", firma_id or "")
            if ev is None or ev["prueba_id"] != "cierre":
                raise ErrorRegistro("firma_invalida", "Falta la firma final del registro", 422)
            snapshot = json.loads(fila["snapshot"])
            hechas = {r["clave"] for r in con.execute(
                "SELECT clave FROM versiones WHERE registro_id=? AND tipo='prueba'", (registro_id,))}
            con_resultado = set()
            for clave in hechas:
                d = json.loads(con.execute(
                    "SELECT datos FROM versiones WHERE registro_id=? AND clave=? AND tipo='prueba'"
                    " ORDER BY seq DESC LIMIT 1", (registro_id, clave)).fetchone()["datos"])
                if d.get("resultado"):
                    con_resultado.add(clave)
            faltan = [p["id"] for p in snapshot["pruebas"] if p["id"] not in con_resultado]
            if faltan and not confirmar_incompleto:
                raise ErrorRegistro("incompleto", "Faltan pruebas sin resultado: " + ", ".join(faltan), 409)
            v = self._agregar(con, registro_id, "cierre", "cierre",
                              {"firma_id": firma_id, "sin_resultado": faltan}, usuario["usuario"],
                              ts_cliente, "", cliente_uuid)
            con.execute("UPDATE registros SET estado='cerrado', cerrado_en=? WHERE id=?", (ahora(), registro_id))
            con.execute("COMMIT")
            return v
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    # ── verificación de la cadena ────────────────────────────────────────
    def verificar(self, registro_id: int) -> dict:
        """Recalcula la cadena de hashes, el hash del snapshot y el sha256 de
        cada foto y firma. Devuelve {ok, errores[]}."""
        con = self.conectar()
        try:
            fila = self._registro(con, registro_id)
            versiones = [dict(v) for v in con.execute(
                "SELECT * FROM versiones WHERE registro_id=? ORDER BY seq", (registro_id,))]
            evidencias = [dict(e) for e in con.execute(
                "SELECT * FROM evidencias WHERE registro_id=?", (registro_id,))]
        finally:
            con.close()
        errores = []
        snapshot = json.loads(fila["snapshot"])
        if not definiciones.verificar_snapshot(snapshot) or snapshot.get("hash") != fila["snapshot_hash"]:
            errores.append("El snapshot de definiciones fue alterado")
        prev = GENESIS
        for esperado, v in enumerate(versiones, start=1):
            if v["seq"] != esperado:
                errores.append(f"Falta la versión {esperado} (hueco en la cadena)")
                break
            h = hash_version(v["registro_id"], v["seq"], v["clave"], v["tipo"], json.loads(v["datos"]),
                             v["usuario"], v["ts_servidor"], v["ts_cliente"], v["motivo"], prev)
            if v["hash_prev"] != prev or v["hash"] != h:
                errores.append(f"Versión {v['seq']} ({v['clave']}): el hash no coincide (alterada)")
                break
            prev = v["hash"]
        for e in evidencias:
            ruta = self.datos / e["archivo"]
            if not ruta.is_file():
                errores.append(f"Falta el archivo de {e['tipo']} {e['archivo']}")
            elif hashlib.sha256(ruta.read_bytes()).hexdigest() != e["sha256"]:
                errores.append(f"El archivo {e['archivo']} fue alterado (sha256 distinto)")
        return {"ok": not errores, "errores": errores, "versiones": len(versiones),
                "ultimo_hash": versiones[-1]["hash"] if versiones else GENESIS}

    # ── consolidación (admin) ────────────────────────────────────────────
    def consolidar(self) -> dict:
        con = self.conectar()
        try:
            registros = [dict(r) for r in con.execute("SELECT id, usuario, estado FROM registros ORDER BY id")]
        finally:
            con.close()
        snapshot = definiciones.construir_snapshot(self.fuente_pruebas)
        estados = {r["id"]: self.estado_registro(r["id"]) for r in registros}
        filas = []
        for p in snapshot["pruebas"]:
            por = []
            for r in registros:
                est = estados[r["id"]]["pruebas"].get(p["id"])
                por.append({"registro_id": r["id"], "usuario": r["usuario"],
                            "resultado": est.get("resultado") if est else None,
                            "valores": est.get("valores") if est else {}})
            resultados = {x["resultado"] for x in por if x["resultado"]}
            filas.append({"prueba_id": p["id"], "titulo": p["titulo"], "bloque": p["bloque"],
                          "ejecutores": por, "discrepancia": len(resultados) > 1})
        return {"registros": registros, "pruebas": filas,
                "discrepancias": [f["prueba_id"] for f in filas if f["discrepancia"]]}
