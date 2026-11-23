# core/runtime/paquete_liberacion.py
#
# Modo fábrica, Etapa 4: paquete de liberación (D-04, FAB-02, §7 de
# planeacion_modo_fabrica.md; R-06 y «historial.db del paquete» de
# R_revision_plan.md; DF-08 y PA-03 de decisiones.md).
#
# Antes del cierre de fabricación (Etapa 5) se escribe en la USB
#   <USB>/Especifika_liberaciones/liberacion_<serie>_<AAAAMMDD-HHMM>.zip
# con TODO el registro de fábrica del equipo:
#   informe_liberacion.pdf   equipo, versión, fecha, ingeniero, calibración por
#                            sensor, parámetros, programas de fábrica, ciclos de
#                            prueba, contadores, ausentes y firmas (PA-03).
#   ciclos/ciclo_NNNNNN.pdf  cada ciclo con su gráfica, alarmas y ticket.
#   historial.db             copia completa de la base con usuarios.hash_pw y
#                            usuarios.codigo_creacion en NULL (P-09), compactada
#                            (VACUUM) para que no queden restos en páginas libres.
#   bitacora.csv             audit_log completo (UTF-8 con BOM, «;»).
#   calibracion.yaml, parametros.json, programas/* (cycles/user: *.json y
#   *.lst), asignacion_io.json, respaldo_ciclos/** y logs/<carpeta>/*.log.
#   manifiesto.json          tipo «liberacion», formato, versión, serie,
#                            fecha, usuario, SHA-256 de cada archivo, lista de
#                            ausentes y `hash` del manifiesto (mismo cálculo que
#                            los respaldos: respaldo.hash_manifiesto).
#
# Un archivo que falta queda en `ausentes` del manifiesto (con su motivo),
# salvo la base: sin ella se aborta. El ZIP se escribe primero como
# `<nombre>.zip.tmp`, se relee y verifica, y solo entonces se renombra; ante
# cualquier fallo se borra lo escrito y no queda nada en la USB (FAB-02).
#
# El hash global del paquete (lo que el equipo guarda como `hash_paquete`) es
# el SHA-256 del archivo ZIP completo (DECISIÓN SIN CONFIRMAR, E4-D3): se puede
# comprobar con cualquier herramienta (certutil, sha256sum) sin abrir el ZIP.
#
# Nunca toca salidas, el ControlLoop ni la base viva (solo la copia).

import csv
import hashlib
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

from autoclave.core.runtime import respaldo as rp

logger = logging.getLogger(__name__)

CARPETA = "Especifika_liberaciones"
TIPO = rp.TIPO_LIBERACION
FORMATO = 1
MANIFIESTO = "manifiesto.json"
SUFIJO_TEMPORAL = ".tmp"
# Estimación del espacio necesario en la USB: tamaño sin comprimir × 1,5 +
# 20 MB (DECISIÓN SIN CONFIRMAR, E4-D4)
FACTOR_ESPACIO = 1.5
MARGEN_ESPACIO_BYTES = 20 * 1024 * 1024
_BLOQUE = 1024 * 1024
# rango de los programas de fábrica (D-05)
_NUMEROS_FABRICA = range(1, 11)


class ErrorPaquete(Exception):
    """Códigos: usb_ausente, usb_no_escribible, usb_sin_espacio, sin_base,
    error_generacion (al armar), y los de verificar_paquete: ilegible,
    sin_manifiesto, manifiesto_invalido, manifiesto_alterado, tipo_invalido,
    archivo_faltante, archivo_no_declarado, hash_invalido."""

    def __init__(self, codigo: str, detalle: str = ""):
        super().__init__(f"{codigo}: {detalle}" if detalle else codigo)
        self.codigo = codigo
        self.detalle = detalle


@dataclass(frozen=True)
class ResultadoPaquete:
    ruta: Path
    hash_global: str          # SHA-256 del ZIP completo
    tamano: int               # bytes del ZIP
    hash_manifiesto: str      # campo `hash` del manifiesto
    ausentes: tuple = ()      # ({"ruta", "motivo"}, ...)


@dataclass
class FuentesPaquete:
    """Lo que entra al paquete; todo inyectable en las pruebas.

    copiar_base(destino): deja en `destino` una copia consistente de la base
        (copiar_base_desde(db) usa la API de respaldo de SQLite sobre la
        conexión viva). Si lanza, el paquete se aborta (`sin_base`).
    equipo: {serie, modelo, tipo_instalacion, serial_original, modelo_original}.
    parametros: config_manager.describir() (lista de {clave, valor, unidad}).
    mapas_sensores: {"temperature": {sensor: canal}, "pressure": {...}}; None =
        la asignación vigente (EstadoAutoclave).
    carpetas_logs: {subcarpeta dentro de logs/: carpeta con *.log}.
    contadores: {rótulo: valor} para el informe (además de los que se calculan
        de la base)."""
    copiar_base: Callable[[Path], None]
    equipo: dict
    version_sw: str
    parametros: list = field(default_factory=list)
    ruta_calibracion: Path | None = None
    carpeta_programas: Path | None = None
    ruta_asignacion_io: Path | None = None
    carpeta_respaldo_ciclos: Path | None = None
    carpetas_logs: dict = field(default_factory=dict)
    mapas_sensores: dict | None = None
    contadores: dict = field(default_factory=dict)


# ── fuentes ─────────────────────────────────────────────────────────────
def copiar_base_desde(db) -> Callable[[Path], None]:
    """copiar_base para un DbManager vivo: backup de SQLite bajo su lock."""
    def copiar(destino: Path) -> None:
        conn = getattr(db, "_conn", None)
        if conn is None:
            raise RuntimeError("sin conexión a la base")
        dst = sqlite3.connect(str(destino))
        try:
            lock = getattr(db, "_lock", None)
            if lock is not None:
                with lock:
                    conn.backup(dst)
            else:
                conn.backup(dst)
        finally:
            dst.close()
    return copiar


def fuentes_del_equipo(context, contadores: dict | None = None) -> FuentesPaquete:
    """Fuentes reales del equipo para el cierre (Etapa 5), desde el
    BackendContext. Rutas: data/ y logs/ bajo utils/paths.app_root()."""
    from autoclave._version import version_completa
    from autoclave.core.runtime import asignacion_io
    from autoclave.utils.paths import app_root, calibration_path
    raiz = app_root()
    perfil = getattr(context, "profile", None)

    def atributo(nombre):
        v = getattr(perfil, nombre, None)
        return v if isinstance(v, str) else None

    equipo = {"serie": atributo("serial_number") or "", "modelo": atributo("model_id") or "",
              "tipo_instalacion": atributo("tipo_instalacion") or "fabricacion",
              "serial_original": atributo("serial_original"),
              "modelo_original": atributo("modelo_original")}
    # R_revision_plan §1: los *.log están en datos/data y datos/logs
    logs = {"data": raiz / "data", "logs": raiz / "logs"}
    return FuentesPaquete(
        copiar_base=copiar_base_desde(context.db),
        equipo=equipo,
        version_sw=version_completa(),
        parametros=list(context.config_manager.describir()),
        ruta_calibracion=Path(calibration_path()),
        carpeta_programas=Path(context.cycle_manager.carpeta("cycles/user")),
        ruta_asignacion_io=asignacion_io.ruta_por_defecto(),
        carpeta_respaldo_ciclos=raiz / "data" / "respaldo_ciclos",
        carpetas_logs=logs,
        contadores=dict(contadores or {}),
    )


# ── USB ─────────────────────────────────────────────────────────────────
def espacio_requerido(bytes_necesarios: int) -> int:
    """Bytes libres que se exigen en la USB para un paquete estimado en
    `bytes_necesarios` (sin comprimir)."""
    return int(max(0, int(bytes_necesarios)) * FACTOR_ESPACIO) + MARGEN_ESPACIO_BYTES


def _espacio_libre(carpeta: Path) -> int:
    return shutil.disk_usage(str(carpeta)).free


def _probar_escritura(carpeta: Path) -> None:
    prueba = carpeta / f".especifika_prueba_{uuid.uuid4().hex}.tmp"
    try:
        with open(prueba, "wb") as f:
            f.write(b"especifika")
            f.flush()
            os.fsync(f.fileno())
    finally:
        try:
            prueba.unlink()
        except FileNotFoundError:
            pass


def comprobar_usb_para_liberacion(carpeta_usb, bytes_necesarios: int) -> int:
    """6.1 / P-07: la USB existe, se puede escribir (prueba real: crea y borra
    un archivo en su raíz) y tiene espacio para `bytes_necesarios` con margen
    (espacio_requerido). Devuelve los bytes libres. Lanza ErrorPaquete
    `usb_ausente`, `usb_no_escribible` o `usb_sin_espacio`. No deja nada."""
    if not carpeta_usb:
        raise ErrorPaquete("usb_ausente", "sin unidad")
    carpeta = Path(carpeta_usb)
    try:
        existe = carpeta.is_dir()
    except OSError:
        existe = False
    if not existe:
        raise ErrorPaquete("usb_ausente", str(carpeta))
    try:
        _probar_escritura(carpeta)
    except OSError as e:
        raise ErrorPaquete("usb_no_escribible", f"{type(e).__name__}: {e}")
    try:
        libre = _espacio_libre(carpeta)
    except OSError as e:
        raise ErrorPaquete("usb_ausente", f"{type(e).__name__}: {e}")
    requerido = espacio_requerido(bytes_necesarios)
    if libre < requerido:
        raise ErrorPaquete("usb_sin_espacio", f"libre {libre} B, requerido {requerido} B")
    return libre


def nombre_paquete(serie: str, ahora: datetime) -> str:
    limpia = "".join(c if (c.isalnum() and c.isascii()) or c in "_.-" else "_"
                     for c in (serie or "sin_serie"))[:60]
    return f"liberacion_{limpia}_{ahora.strftime('%Y%m%d-%H%M')}.zip"


# ── base: copia, lectura y anonimización ────────────────────────────────
def _tablas(conn) -> set[str]:
    return {f[0] for f in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columnas(conn, tabla: str) -> list[str]:
    return [f[1] for f in conn.execute(f"PRAGMA table_info({tabla})")]


def anonimizar_base(ruta: Path) -> None:
    """P-09: en la COPIA `ruta`, usuarios.hash_pw y usuarios.codigo_creacion
    quedan en NULL. `hash_pw` es NOT NULL en el esquema, así que la tabla se
    reconstruye con las mismas columnas (esas dos sin NOT NULL) y se vuelven a
    crear sus índices y triggers (sin quitar triggers a mano, P-12). Luego VACUUM (no quedan los hashes en
    páginas libres) y modo de diario DELETE (un solo archivo)."""
    conn = sqlite3.connect(str(ruta), isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        if "usuarios" in _tablas(conn):
            info = list(conn.execute("PRAGMA table_info(usuarios)"))
            nulos = {"hash_pw", "codigo_creacion"}
            objetos = [f[0] for f in conn.execute(
                "SELECT sql FROM sqlite_master WHERE tbl_name='usuarios' "
                "AND type IN ('index','trigger') AND sql IS NOT NULL")]
            defs = []
            for _cid, nombre, tipo, notnull, defecto, pk in info:
                d = f'"{nombre}" {tipo or ""}'.rstrip()
                if pk:
                    d += " PRIMARY KEY" + (" AUTOINCREMENT" if nombre == "id" else "")
                if notnull and nombre not in nulos and not pk:
                    d += " NOT NULL"
                if defecto is not None:
                    d += f" DEFAULT {defecto}"
                defs.append(d)
            unicos = [f[1] for f in conn.execute("PRAGMA index_list(usuarios)")
                      if f[2] and f[3] == "u"]
            for indice in unicos:
                cols = [c[2] for c in conn.execute(f'PRAGMA index_info("{indice}")')]
                defs.append("UNIQUE (" + ", ".join(f'"{c}"' for c in cols) + ")")
            columnas = [f[1] for f in info]
            seleccion = ", ".join("NULL" if c in nulos else f'"{c}"' for c in columnas)
            lista = ", ".join(f'"{c}"' for c in columnas)
            conn.execute("BEGIN")
            # P-12: sin quitar triggers a mano; viajan con la tabla renombrada,
            # desaparecen con su DROP TABLE y se recrean con su SQL original
            conn.execute("ALTER TABLE usuarios RENAME TO _usuarios_paquete")
            conn.execute("CREATE TABLE usuarios (" + ", ".join(defs) + ")")
            conn.execute(f"INSERT INTO usuarios ({lista}) SELECT {seleccion} FROM _usuarios_paquete")
            conn.execute("DROP TABLE _usuarios_paquete")
            for sql in objetos:
                conn.execute(sql)
            conn.execute("COMMIT")
        conn.execute("VACUUM")
        conn.execute("PRAGMA journal_mode = DELETE")
    finally:
        conn.close()


def _filas(conn, sql: str, params=()) -> list[dict]:
    try:
        return [dict(f) for f in conn.execute(sql, params)]
    except sqlite3.Error as e:
        logger.warning("Paquete de liberación: consulta fallida (%s): %s", e, sql)
        return []


def bitacora_csv(conn) -> bytes:
    """audit_log completo, en orden de id, como CSV legible para Excel (UTF-8
    con BOM, separador «;», DECISIÓN SIN CONFIRMAR E4-D5)."""
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    columnas = ("id", "ts", "usuario", "rol", "evento", "entidad", "valor_anterior",
                "valor_nuevo", "detalle")
    w.writerow(("id", "fecha", "usuario", "rol", "evento", "entidad", "valor_anterior",
                "valor_nuevo", "detalle"))
    if "audit_log" in _tablas(conn):
        presentes = set(_columnas(conn, "audit_log"))
        for f in conn.execute("SELECT * FROM audit_log ORDER BY id"):
            fila = dict(f)
            w.writerow(["" if fila.get(c) is None else fila.get(c)
                        if c in presentes else "" for c in columnas])
    return salida.getvalue().encode("utf-8-sig")


def _carga(conn, ciclo: dict) -> dict | None:
    if not ciclo.get("lote_carga"):
        return None
    elementos = _filas(conn, "SELECT codigo, nombre, en_catalogo, cantidad, manual FROM "
                             "ciclo_carga WHERE ciclo_id=? ORDER BY orden, id", (ciclo["id"],))
    return {"lote": ciclo["lote_carga"], "impresion": ciclo.get("impresion_carga"),
            "elementos": [{**e, "en_catalogo": bool(e["en_catalogo"]),
                           "manual": bool(e["manual"])} for e in elementos]}


def _ticket(conn, ciclo: dict) -> str:
    try:
        from autoclave.services.domain.logging.ticket_formatter import format_ticket
        lecturas = _filas(conn, "SELECT * FROM lecturas WHERE ciclo_id=? AND para_imprimir=1 "
                                "ORDER BY id", (ciclo["id"],))
        datos = dict(ciclo)
        carga = _carga(conn, ciclo)
        if carga:
            datos["carga"] = carga
        return format_ticket(datos, lecturas)
    except Exception as e:
        logger.exception("Paquete de liberación: ticket del ciclo %s no disponible", ciclo.get("id"))
        return f"(ticket no disponible: {type(e).__name__})"


# ── informe ─────────────────────────────────────────────────────────────
def _calibracion_por_sensor(ruta: Path | None, mapas: dict | None) -> list[dict]:
    if ruta is None or not Path(ruta).is_file():
        return []
    try:
        crudo = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
        user = (crudo.get("calibration") or {}).get("user") or {}
    except Exception as e:
        logger.warning("Paquete de liberación: calibración ilegible (%s)", e)
        return []
    if mapas is None:
        from autoclave.core.runtime.status import EstadoAutoclave
        mapas = {"temperature": dict(EstadoAutoclave.map_temp),
                 "pressure": dict(EstadoAutoclave.map_pres)}
    filas = []
    for tipo, rotulo in (("temperature", "temperatura"), ("pressure", "presión")):
        lista = user.get(tipo) or []
        for sensor, canal in sorted((mapas.get(tipo) or {}).items()):
            if not isinstance(canal, int) or not 0 <= canal < len(lista) \
                    or not isinstance(lista[canal], dict):
                filas.append({"tipo": rotulo, "sensor": sensor, "puerto": None,
                              "gain": None, "offset": None, "poly": None})
                continue
            c = lista[canal]
            filas.append({"tipo": rotulo, "sensor": sensor, "puerto": canal + 1,
                          "gain": c.get("gain"), "offset": c.get("offset"),
                          "poly": c.get("poly") or None})
    return filas


def _programas(carpeta: Path | None) -> tuple[list, list]:
    fabrica, otros = [], []
    if carpeta is None or not Path(carpeta).is_dir():
        return fabrica, otros
    for archivo in sorted(Path(carpeta).glob("*.json")):
        try:
            obj = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            fabrica.append({"numero": None, "nombre": archivo.name, "id": None,
                            "error": type(e).__name__})
            continue
        if not isinstance(obj, dict) or "parameters" not in obj:
            continue        # listas auxiliares (numeros_usados.json...)
        numero = obj.get("cycle_number")
        fila = {"numero": numero, "nombre": obj.get("display_name") or obj.get("nombre")
                or archivo.stem, "id": obj.get("cycle_id") or obj.get("id"),
                "parametros": obj.get("parameters") or {}}
        (fabrica if isinstance(numero, int) and numero in _NUMEROS_FABRICA else otros).append(fila)
    fabrica.sort(key=lambda p: (p["numero"] is None, p["numero"] or 0))
    otros.sort(key=lambda p: (not isinstance(p["numero"], int), p["numero"] or 0))
    return fabrica, otros


def _datos_informe(conn, fuentes: FuentesPaquete, usuario: str, ahora: datetime,
                   ciclos: list, ausentes: list) -> dict:
    nombre = ""
    if "usuarios" in _tablas(conn):
        fila = _filas(conn, "SELECT nombre FROM usuarios WHERE usuario=?", (usuario,))
        nombre = fila[0]["nombre"] if fila else ""
    alarmas_por_ciclo: dict = {}
    if "alarmas_historial" in _tablas(conn):
        for a in _filas(conn, "SELECT ciclo_id, codigo FROM alarmas_historial "
                              "WHERE ciclo_id IS NOT NULL ORDER BY aparecida, id"):
            alarmas_por_ciclo.setdefault(a["ciclo_id"], []).append(a["codigo"])
    resumen = [{"numero": c.get("numero_ciclo"),
                "programa": f"{c.get('numero_programa') or ''} {c.get('nombre_ciclo') or ''}".strip(),
                "inicio": c.get("fecha_inicio"), "resultado": c.get("resultado"),
                "motivo_fallo": c.get("motivo_fallo"), "codigo_fallo": c.get("codigo_fallo"),
                "alarmas": alarmas_por_ciclo.get(c.get("id"), [])} for c in ciclos]
    por_resultado: dict = {}
    for c in ciclos:
        clave = c.get("resultado") or "sin resultado"
        por_resultado[clave] = por_resultado.get(clave, 0) + 1
    contadores = {"Ciclos registrados": len(ciclos),
                  "Último número de ciclo": max((c.get("numero_ciclo") or 0 for c in ciclos),
                                                default=0)}
    for clave, n in sorted(por_resultado.items()):
        contadores[f"Ciclos {clave}"] = n
    for tabla, rotulo in (("alarmas_historial", "Alarmas registradas"),
                          ("audit_log", "Filas de bitácora"),
                          ("mantenimientos", "Mantenimientos registrados")):
        if tabla in _tablas(conn):
            contadores[rotulo] = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    contadores.update(fuentes.contadores or {})
    fabrica, otros = _programas(fuentes.carpeta_programas)
    parametros = fuentes.parametros
    if isinstance(parametros, dict):
        parametros = [{"clave": k, "valor": v} for k, v in parametros.items()]
    return {"equipo": dict(fuentes.equipo), "version_sw": fuentes.version_sw,
            "fecha": ahora.isoformat(sep=" ", timespec="seconds"),
            "ingeniero": {"usuario": usuario, "nombre": nombre},
            "calibracion": _calibracion_por_sensor(fuentes.ruta_calibracion,
                                                   fuentes.mapas_sensores),
            "parametros": sorted(parametros, key=lambda p: str(p.get("clave"))),
            "programas": fabrica, "otros_programas": otros, "ciclos": resumen,
            "contadores": contadores, "ausentes": list(ausentes)}


# ── armado ──────────────────────────────────────────────────────────────
def _copiar_archivo(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, destino)


def _sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(_BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()


def _preparar(fuentes: FuentesPaquete, usuario: str, ahora: datetime,
              staging: Path) -> list:
    """Deja en `staging` todos los archivos del paquete (menos el manifiesto)
    con su ruta dentro del ZIP. Devuelve la lista de ausentes."""
    ausentes: list = []

    def ausente(ruta: str, motivo: str) -> None:
        ausentes.append({"ruta": ruta, "motivo": motivo})
        logger.warning("Paquete de liberación: %s ausente (%s)", ruta, motivo)

    # base (obligatoria)
    base = staging / "historial.db"
    try:
        fuentes.copiar_base(base)
        conn = sqlite3.connect(str(base))
        try:
            conn.execute("PRAGMA journal_mode = DELETE")
            if "ciclos" not in _tablas(conn):
                raise sqlite3.DatabaseError("la copia no tiene la tabla ciclos")
        finally:
            conn.close()
    except Exception as e:
        raise ErrorPaquete("sin_base", f"{type(e).__name__}: {e}")

    conn = sqlite3.connect(str(base))
    conn.row_factory = sqlite3.Row
    try:
        (staging / "bitacora.csv").write_bytes(bitacora_csv(conn))
        ciclos = _filas(conn, "SELECT * FROM ciclos ORDER BY numero_ciclo, id")
        for c in ciclos:
            nombre = f"ciclos/ciclo_{int(c.get('numero_ciclo') or 0):06d}_{c['id']}.pdf"
            try:
                from autoclave.services.domain.exportacion.pdf_liberacion import ciclo_pdf
                grafica = _filas(conn, "SELECT * FROM lecturas_grafica WHERE ciclo_id=? "
                                       "ORDER BY id", (c["id"],))
                alarmas = _filas(conn, "SELECT * FROM alarmas_historial WHERE ciclo_id=? "
                                       "ORDER BY aparecida, id", (c["id"],))
                pdf = ciclo_pdf({"ciclo": c, "grafica": grafica, "alarmas": alarmas,
                                 "ticket": _ticket(conn, c)})
                destino = staging / nombre
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(pdf)
            except Exception as e:
                logger.exception("Paquete de liberación: PDF del ciclo %s", c.get("id"))
                ausente(nombre, f"error_generacion: {type(e).__name__}")

        # archivos de configuración y registro
        if fuentes.ruta_calibracion is not None and Path(fuentes.ruta_calibracion).is_file():
            _copiar_archivo(Path(fuentes.ruta_calibracion), staging / "calibracion.yaml")
        else:
            ausente("calibracion.yaml", "no_existe")
        parametros = fuentes.parametros
        valores = (dict(parametros) if isinstance(parametros, dict)
                   else {p["clave"]: p.get("valor") for p in parametros})
        (staging / "parametros.json").write_text(
            json.dumps(valores, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        carpeta = fuentes.carpeta_programas
        if carpeta is not None and Path(carpeta).is_dir():
            for archivo in sorted(Path(carpeta).iterdir()):
                if archivo.is_file() and archivo.suffix.lower() in (".json", ".lst"):
                    _copiar_archivo(archivo, staging / "programas" / archivo.name)
        else:
            ausente("programas/", "no_existe")
        if fuentes.ruta_asignacion_io is not None and Path(fuentes.ruta_asignacion_io).is_file():
            _copiar_archivo(Path(fuentes.ruta_asignacion_io), staging / "asignacion_io.json")
        else:
            # sin archivo = asignación de fábrica (asignacion_io.ArchivoAsignacion)
            ausente("asignacion_io.json", "no_existe (asignación de fábrica)")
        rc = fuentes.carpeta_respaldo_ciclos
        if rc is not None and Path(rc).is_dir():
            for archivo in sorted(Path(rc).rglob("*")):
                if archivo.is_file():
                    rel = archivo.relative_to(rc).as_posix()
                    _copiar_archivo(archivo, staging / "respaldo_ciclos" / rel)
        else:
            ausente("respaldo_ciclos/", "no_existe")
        for sub, carpeta_logs in sorted((fuentes.carpetas_logs or {}).items()):
            if carpeta_logs is None or not Path(carpeta_logs).is_dir():
                ausente(f"logs/{sub}/", "no_existe")
                continue
            for archivo in sorted(Path(carpeta_logs).glob("*.log")):
                try:
                    _copiar_archivo(archivo, staging / "logs" / sub / archivo.name)
                except OSError as e:
                    ausente(f"logs/{sub}/{archivo.name}", f"ilegible: {type(e).__name__}")

        # informe (al final: lista los ausentes de lo anterior)
        from autoclave.services.domain.exportacion.pdf_liberacion import informe_pdf
        datos = _datos_informe(conn, fuentes, usuario, ahora, ciclos, ausentes)
        (staging / "informe_liberacion.pdf").write_bytes(informe_pdf(datos))
    finally:
        conn.close()
    # P-09: la copia que va al paquete, sin hashes ni códigos de creación
    anonimizar_base(base)
    return ausentes


def _archivos_preparados(staging: Path) -> list[tuple[str, Path]]:
    return sorted((p.relative_to(staging).as_posix(), p)
                  for p in staging.rglob("*") if p.is_file())


def _escribir_zip(destino: Path, manifiesto: dict, archivos: list) -> None:
    with open(destino, "wb") as f:
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.writestr(MANIFIESTO, json.dumps(manifiesto, ensure_ascii=False, indent=2))
            for nombre, ruta in archivos:
                z.write(ruta, nombre)
        f.flush()
        os.fsync(f.fileno())


def generar_paquete_liberacion(fuentes: FuentesPaquete, carpeta_usb, usuario: str,
                               ahora: datetime | None = None) -> ResultadoPaquete:
    """Genera, verifica y deja en la USB el paquete de liberación. Lanza
    ErrorPaquete (usb_ausente, usb_no_escribible, usb_sin_espacio, sin_base,
    error_generacion o un código de verificar_paquete); en ese caso no queda
    nada en la USB."""
    ahora = ahora or datetime.now()
    if not carpeta_usb or not Path(carpeta_usb).is_dir():
        raise ErrorPaquete("usb_ausente", str(carpeta_usb))
    with tempfile.TemporaryDirectory(prefix="liberacion_") as tmp:
        staging = Path(tmp) / "paquete"
        staging.mkdir()
        try:
            ausentes = _preparar(fuentes, usuario, ahora, staging)
        except ErrorPaquete:
            raise
        except Exception as e:
            logger.exception("Paquete de liberación: error al armar el contenido")
            raise ErrorPaquete("error_generacion", f"{type(e).__name__}: {e}")
        archivos = _archivos_preparados(staging)
        hashes = {nombre: _sha256_archivo(ruta) for nombre, ruta in archivos}
        equipo = fuentes.equipo or {}
        m = {"tipo": TIPO, "formato": FORMATO, "version_sw": fuentes.version_sw,
             "serie": equipo.get("serie", ""), "modelo": equipo.get("modelo", ""),
             "tipo_instalacion": equipo.get("tipo_instalacion") or "fabricacion",
             "creado_en": ahora.isoformat(timespec="seconds"), "creado_por": usuario,
             "archivos": hashes, "ausentes": ausentes}
        if equipo.get("tipo_instalacion") == "automatizacion":
            m["serial_original"] = equipo.get("serial_original")
            m["modelo_original"] = equipo.get("modelo_original")
        m["hash"] = rp.hash_manifiesto(m)
        estimado = sum(r.stat().st_size for _, r in archivos) + _BLOQUE
        comprobar_usb_para_liberacion(carpeta_usb, estimado)

        carpeta = Path(carpeta_usb) / CARPETA
        carpeta_creada = not carpeta.exists()
        nombre = nombre_paquete(equipo.get("serie", ""), ahora)
        final = carpeta / nombre
        n = 2
        while final.exists() or Path(str(final) + SUFIJO_TEMPORAL).exists():
            final = carpeta / nombre.replace(".zip", f"_{n}.zip")
            n += 1
        temporal = Path(str(final) + SUFIJO_TEMPORAL)
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            _escribir_zip(temporal, m, archivos)
            hash_global = verificar_paquete(temporal)
            os.replace(temporal, final)
        except Exception as e:
            _limpiar(temporal, final, carpeta if carpeta_creada else None)
            if isinstance(e, ErrorPaquete):
                raise
            if isinstance(e, OSError):
                raise ErrorPaquete("usb_no_escribible", f"{type(e).__name__}: {e}")
            raise ErrorPaquete("error_generacion", f"{type(e).__name__}: {e}")
    tamano = final.stat().st_size
    logger.info("Paquete de liberación escrito: %s (%d B, sha256 %s, %d ausentes)",
                final, tamano, hash_global, len(ausentes))
    return ResultadoPaquete(ruta=final, hash_global=hash_global, tamano=tamano,
                            hash_manifiesto=m["hash"], ausentes=tuple(ausentes))


def _limpiar(temporal: Path, final: Path, carpeta: Path | None) -> None:
    for ruta in (temporal, final):
        try:
            ruta.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Paquete de liberación: no se pudo borrar %s", ruta)
    if carpeta is not None:
        try:
            carpeta.rmdir()          # solo si quedó vacía
        except OSError:
            pass


# ── verificación ────────────────────────────────────────────────────────
def verificar_paquete(ruta) -> str:
    """Relee el ZIP y verifica el manifiesto (tipo «liberacion», `hash`), que
    cada archivo declarado exista con su SHA-256 y que no haya archivos sin
    declarar. Devuelve el hash global (SHA-256 del ZIP). Lanza ErrorPaquete."""
    ruta = Path(ruta)
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = set(z.namelist())
            if MANIFIESTO not in nombres:
                raise ErrorPaquete("sin_manifiesto")
            if z.getinfo(MANIFIESTO).file_size > 16 * 1024 * 1024:
                raise ErrorPaquete("manifiesto_invalido", "demasiado grande")
            m = json.loads(z.read(MANIFIESTO).decode("utf-8"))
            if not isinstance(m, dict) or not isinstance(m.get("archivos"), dict):
                raise ErrorPaquete("manifiesto_invalido")
            if m.get("hash") != rp.hash_manifiesto(m):
                raise ErrorPaquete("manifiesto_alterado")
            if m.get("tipo") != TIPO or m.get("formato") != FORMATO:
                raise ErrorPaquete("tipo_invalido", f"{m.get('tipo')!r}/{m.get('formato')!r}")
            sobrantes = nombres - set(m["archivos"]) - {MANIFIESTO}
            if sobrantes:
                raise ErrorPaquete("archivo_no_declarado", sorted(sobrantes)[0])
            for nombre, esperado in m["archivos"].items():
                if nombre not in nombres:
                    raise ErrorPaquete("archivo_faltante", nombre)
                h = hashlib.sha256()
                with z.open(nombre) as f:
                    for bloque in iter(lambda: f.read(_BLOQUE), b""):
                        h.update(bloque)
                if h.hexdigest() != esperado:
                    raise ErrorPaquete("hash_invalido", nombre)
    except ErrorPaquete:
        raise
    except Exception as e:      # ZIP dañado: BadZipFile, zlib.error, EOFError, OSError...
        raise ErrorPaquete("ilegible", f"{type(e).__name__}: {e}")
    return _sha256_archivo(ruta)
