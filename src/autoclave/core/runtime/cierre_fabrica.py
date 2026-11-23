# core/runtime/cierre_fabrica.py
#
# Modo fábrica, Etapa 5: cierre de fabricación en dos tiempos (DF-05, R-02 de
# la revisión; FAB-02, FAB-05, FAB-07, FAB-10; D-09..D-12; DF-09, DF-10;
# PA-06 = rige D-11, PA-08, PA-09).
#
# FASE 1, con el equipo en marcha (la orquesta backend/rutas/fabrica.py):
#   1. el paquete de liberación en la USB, generado y verificado (FAB-02; si
#      falla, nada cambia);
#   2. consolidar en TEMPORALES, sin tocar los vigentes: los dos archivos de la
#      base de fábrica del equipo con el sufijo `.fab_nuevo` en data/ y los
#      defectos de programas en `cycles/defecto.fab_nuevo/`;
#   3. construir `autoclave.db.nueva` junto a la base con DbManager (esquema,
#      triggers y semillas D-11 tal cual), las dos tablas de auditoría de sus
#      clases, `system_params` vigentes, estado ENTREGADO con fecha y hash del
#      paquete, la fila `equipo_instalado` original (PA-08) y UNA fila
#      `equipo_liberado_fabrica` (D-12). Nada más. Nunca se quitan triggers
#      ni se borran filas de tablas protegidas (FAB-07): la base vieja no se toca;
#   4. (backend) detener el lazo con todo apagado;
#   5. escribir de forma atómica la marca `cierre_fabrica.json` junto a la
#      base: PUNTO DE NO RETORNO;
#   6. (backend) reiniciar el software.
#
# FASE 2, al arrancar el backend ANTES de abrir cualquier DbManager
# (backend/main.py llama a completar_cierre_si_pendiente):
#   - con marca: PRIMERO se valida (SAF-01 de la revisión de seguridad): marca
#     legible, `formato` 1, `hash_paquete` hex de 64 y `fecha`; con el paso
#     `base` pendiente, `.nueva` íntegra, ENTREGADO con el mismo hash y fecha,
#     y la base vigente (solo lectura) en FÁBRICA; con `base` hecho, la base
#     vigente ENTREGADO con ese hash y fecha, sin ciclos y sin filas de
#     bitácora posteriores a `equipo_liberado_fabrica`. Si algo no valida no
#     se borra nada: la marca se renombra a `cierre_fabrica.json.rechazada-
#     <fecha>` y el arranque sigue normal. Validada, pasos idempotentes, cada
#     uno anotado en la marca al terminar y nunca repetido una vez hecho; si la
#     marca no se puede actualizar tras un paso, la fase 2 se corta (SAF-03).
#     Los críticos (archivos de fábrica, defectos, base, respaldo de ciclos,
#     contadores) se reintentan en el próximo arranque si fallan, y mientras
#     tanto el arranque queda detenido con el fallo bloqueante
#     ARR_CIERRE_FABRICA (SAF-02: sin control ni ciclos; antes BD_BLOQUEADA y
#     modo sin base, que permitía ciclos). Los de mejor esfuerzo (registros,
#     sobrescritura de la base vieja) se dan por hechos con aviso en el log si
#     algo no se pudo borrar. Al final se borra la marca (si no se puede, se
#     renombra a `cierre_fabrica.hecho`).
#   - sin marca: se borran los temporales que hayan quedado (corte antes del
#     punto de no retorno, FAB-05) y, solo con la base vigente ENTREGADO y con
#     fecha de liberación (SAF-06), los restos de un cierre ya terminado.
#
# Se conservan: perfil, licencia, asignacion_io.json (y su .formato1.bak),
# módulo y red, calibración vigente, programas y listas .lst, idioma,
# unidades, tema, impresora, correo, mantenimiento.json y datos\estacion\.
#
# Nunca toca salidas ni el ControlLoop.

import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from autoclave.core.runtime import fabrica_equipo as fe
from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.utils.archivos import escribir_texto_atomico

logger = logging.getLogger(__name__)

NOMBRE_MARCA = "cierre_fabrica.json"
NOMBRE_MARCA_HECHA = "cierre_fabrica.hecho"
SUFIJO_RECHAZADA = ".rechazada-"
FORMATO_MARCA = 1
_HASH_HEX = re.compile(r"^[0-9a-f]{64}$")
SUFIJO_NUEVO = fe.SUFIJO_TEMPORAL_DEFECTO          # ".fab_nuevo"
SUFIJO_BASE_NUEVA = ".nueva"
SUFIJO_BASE_VIEJA = ".vieja"
SUFIJO_DEFECTO_VIEJO = ".fab_viejo"
SUFIJO_BORRAR = ".fab_borrar"
CARPETA_DEFECTO = "defecto"
CARPETA_RESPALDO_CICLOS = "respaldo_ciclos"
SIDECARS_BASE = ("-wal", "-shm", "-journal")
# Texto inicial de la marca BD_BLOQUEADA que dejaba una fase 2 incompleta antes
# de SAF-02 (hoy ya no se escribe; si queda una de antes, el cierre la retira al
# terminar; otra, la de una base corrupta, solo la retira un técnico)
PREFIJO_BLOQUEO = "Cierre de fabricación incompleto"

# Pasos de la fase 2, en orden; los cinco primeros son críticos
PASOS = ("archivos_fabrica", "defectos", "base", "respaldo_ciclos", "contadores",
         "registros", "base_vieja")
PASOS_CRITICOS = frozenset(PASOS[:5])

# Etapas de la fase 1 que publica GET /fabrica/cierre
ETAPAS = ("validando", "paquete", "consolidando", "base_nueva", "marca", "reiniciando")

_BLOQUE_CEROS = 1024 * 1024
_REINTENTOS = 3
_PAUSA_REINTENTO_S = 0.5
NUMEROS_FABRICA = range(1, 11)


# ── rutas ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RutasCierre:
    """Dónde actúa el cierre. En el equipo, rutas_del_equipo(); en las
    pruebas, carpetas temporales."""
    carpeta_datos: Path                 # data/: base, marca, contadores, logs del lanzador
    carpeta_ciclos: Path                # cycles/ (user/, defecto/)
    ruta_base: Path | None = None       # por omisión carpeta_datos/autoclave.db
    carpeta_logs: Path | None = None    # logs/ (autoclave.log)
    ruta_registro_perfil: Path | None = None   # registro de cambios del perfil

    @property
    def base(self) -> Path:
        return Path(self.ruta_base) if self.ruta_base is not None \
            else Path(self.carpeta_datos) / "autoclave.db"

    @property
    def base_nueva(self) -> Path:
        return self.base.with_name(self.base.name + SUFIJO_BASE_NUEVA)

    @property
    def marca(self) -> Path:
        return self.base.with_name(NOMBRE_MARCA)

    @property
    def defecto(self) -> Path:
        return Path(self.carpeta_ciclos) / CARPETA_DEFECTO

    @property
    def defecto_nuevo(self) -> Path:
        return Path(self.carpeta_ciclos) / (CARPETA_DEFECTO + SUFIJO_NUEVO)

    @property
    def defecto_viejo(self) -> Path:
        return Path(self.carpeta_ciclos) / (CARPETA_DEFECTO + SUFIJO_DEFECTO_VIEJO)

    def temporal(self, nombre: str) -> Path:
        return Path(self.carpeta_datos) / (nombre + SUFIJO_NUEVO)

    def final(self, nombre: str) -> Path:
        return Path(self.carpeta_datos) / nombre


def carpeta_ciclos_del_equipo() -> Path:
    """cycles/ como lo resuelve CycleManager.carpeta, sin sembrar nada (en la
    fase 2 todavía no hay CycleManager)."""
    if getattr(sys, "frozen", False):
        from autoclave.utils.resources import _carpeta_persistente
        return Path(_carpeta_persistente()) / "autoclave" / "cycles"
    from autoclave.core.managers.cycle_manager import BASE_DIR
    return Path(BASE_DIR) / "cycles"


def rutas_del_equipo(carpeta_ciclos: Path | None = None) -> RutasCierre:
    from autoclave.installation import cambio_perfil
    from autoclave.installation.storage import INSTALLATION_FILE
    from autoclave.services.domain.logging.db_manager import DB_DEFAULT
    from autoclave.utils.paths import app_root
    return RutasCierre(
        carpeta_datos=fe.carpeta_datos(),
        carpeta_ciclos=Path(carpeta_ciclos) if carpeta_ciclos is not None
        else carpeta_ciclos_del_equipo(),
        ruta_base=Path(DB_DEFAULT),
        carpeta_logs=app_root() / "logs",
        ruta_registro_perfil=cambio_perfil.ruta_registro(Path(INSTALLATION_FILE)))


# ── utilidades de archivos ──────────────────────────────────────────────
def _con_reintentos(accion: Callable[[], None]) -> None:
    for intento in range(_REINTENTOS):
        try:
            accion()
            return
        except OSError:
            if intento == _REINTENTOS - 1:
                raise
            time.sleep(_PAUSA_REINTENTO_S)


def _borrar_archivo(ruta: Path) -> None:
    try:
        Path(ruta).unlink()
    except FileNotFoundError:
        pass


def _borrar_base(ruta: Path) -> None:
    for r in [Path(ruta)] + [Path(str(ruta) + s) for s in SIDECARS_BASE]:
        _borrar_archivo(r)


def _borrar_o_truncar(ruta: Path, fallos: list) -> None:
    """Mejor esfuerzo: borra; si el archivo está abierto (un log del propio
    proceso o de otro), lo deja vacío."""
    ruta = Path(ruta)
    try:
        ruta.unlink()
        return
    except FileNotFoundError:
        return
    except OSError:
        pass
    try:
        with open(ruta, "r+b") as f:
            f.truncate(0)
            f.flush()
            os.fsync(f.fileno())
        logger.warning("Cierre de fabricación: %s en uso; se vació en lugar de borrarlo", ruta.name)
    except FileNotFoundError:
        return
    except OSError as e:
        fallos.append(f"{ruta.name}: {type(e).__name__}")
        logger.error("Cierre de fabricación: no se pudo borrar ni vaciar %s: %s", ruta, e)


def sobrescribir_y_borrar(ruta: Path) -> bool:
    """FAB-07: sobrescribe con ceros (fsync) y borra. Mejor esfuerzo (en un
    SSD la sobrescritura física no está garantizada). True si ya no existe."""
    ruta = Path(ruta)
    if not ruta.exists():
        return True
    try:
        tamano = ruta.stat().st_size
        with open(ruta, "r+b") as f:
            ceros = bytes(_BLOQUE_CEROS)
            restante = tamano
            while restante > 0:
                n = min(restante, _BLOQUE_CEROS)
                f.write(ceros[:n])
                restante -= n
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        logger.error("Cierre de fabricación: no se pudo sobrescribir %s: %s", ruta.name, e)
    try:
        ruta.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.error("Cierre de fabricación: no se pudo borrar %s: %s", ruta.name, e)
        return False
    return True


def _bases_viejas(rutas: RutasCierre) -> list[Path]:
    vieja = rutas.base.with_name(rutas.base.name + SUFIJO_BASE_VIEJA)
    return [vieja] + [Path(str(vieja) + s) for s in SIDECARS_BASE]


# ── resumen para GET /fabrica/cierre ────────────────────────────────────
QUE_SE_BORRA = ("ciclos", "graficas", "alarmas", "bitacora", "mantenimientos", "operadores",
                "usuarios_prueba", "catalogo_carga", "respaldo_ciclos", "logs", "contadores")
QUE_QUEDA = ("perfil", "licencia", "asignacion_io", "modulo_red", "calibracion", "parametros",
             "programas", "preferencias", "mantenimiento_intervalos", "cuentas_sistema",
             "equipo_instalado", "estacion")


def resumen(db) -> dict:
    """{borra: {..conteos}, se_borra: [...], queda: [...]} para la pantalla.
    `conteos` None si la base no responde."""
    try:
        c = db.conteos_cierre_fabrica()
        conteos = {"ciclos": c["ciclos"], "lecturas": c["lecturas"],
                   "alarmas": c["alarmas_historial"], "bitacora": c["audit_log"],
                   "mantenimientos": c["mantenimientos"], "operadores": c["operadores"],
                   "usuarios_prueba": c["usuarios_prueba"], "catalogo_carga": c["catalogo_carga"]}
    except Exception:
        logger.exception("Cierre de fabricación: no se pudieron contar las filas")
        conteos = None
    return {"conteos": conteos, "se_borra": list(QUE_SE_BORRA), "queda": list(QUE_QUEDA)}


def tamano_estimado(rutas: RutasCierre, carpeta_respaldo: Path | None = None) -> int:
    """Bytes aproximados del paquete sin comprimir (base, respaldo de ciclos y
    logs) para el rechazo previo por espacio en la USB."""
    total = 0
    for r in [rutas.base] + [Path(str(rutas.base) + "-wal")]:
        try:
            total += r.stat().st_size
        except OSError:
            pass
    carpetas = [carpeta_respaldo or Path(rutas.carpeta_datos) / CARPETA_RESPALDO_CICLOS]
    for carpeta in carpetas:
        if carpeta.is_dir():
            for archivo in carpeta.rglob("*"):
                try:
                    total += archivo.stat().st_size if archivo.is_file() else 0
                except OSError:
                    pass
    for carpeta in (Path(rutas.carpeta_datos), rutas.carpeta_logs):
        if carpeta is not None and Path(carpeta).is_dir():
            for archivo in Path(carpeta).glob("*.log"):
                try:
                    total += archivo.stat().st_size
                except OSError:
                    pass
    return total


# ── fase 1 ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ResultadoFase1:
    ruta_paquete: Path
    nombre_paquete: str
    hash_paquete: str
    fecha_liberacion: str


class ErrorCierre(Exception):
    def __init__(self, codigo: str, detalle: str = ""):
        super().__init__(f"{codigo}: {detalle}" if detalle else codigo)
        self.codigo = codigo
        self.detalle = detalle


def limpiar_temporales(rutas: RutasCierre) -> None:
    """Borra lo que la fase 1 deja antes del punto de no retorno. Nunca lanza."""
    for nombre in (fe.NOMBRE_PARAMETROS, fe.NOMBRE_CALIBRACION):
        try:
            _borrar_archivo(rutas.temporal(nombre))
        except OSError:
            logger.exception("Cierre de fabricación: no se pudo borrar un temporal")
    try:
        for archivo in Path(rutas.carpeta_datos).glob("*" + SUFIJO_NUEVO):
            _borrar_archivo(archivo)
    except OSError:
        logger.exception("Cierre de fabricación: no se pudieron listar los temporales")
    try:
        shutil.rmtree(rutas.defecto_nuevo)
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("Cierre de fabricación: no se pudo borrar %s", rutas.defecto_nuevo)
    try:
        _borrar_base(rutas.base_nueva)
    except OSError:
        logger.exception("Cierre de fabricación: no se pudo borrar la base nueva temporal")


def consolidar_en_temporales(config_manager, cycle_manager, rutas: RutasCierre, *,
                             mapas: dict | None = None, origen_calibracion=None) -> dict:
    """Paso 3: la base de fábrica del equipo en temporales (los vigentes no
    se tocan). Los defectos: copia de la carpeta de defectos en defecto.fab_nuevo y
    consolidación sobre la copia. Lanza si algo falla."""
    datos_par = fe.escribir_parametros_fabrica_equipo(
        config_manager, destino=rutas.temporal(fe.NOMBRE_PARAMETROS))
    datos_cal = fe.escribir_calibracion_fabrica_equipo(
        destino=rutas.temporal(fe.NOMBRE_CALIBRACION), origen=origen_calibracion, mapas=mapas)
    try:
        shutil.rmtree(rutas.defecto_nuevo)
    except FileNotFoundError:
        pass
    if rutas.defecto.is_dir():
        shutil.copytree(rutas.defecto, rutas.defecto_nuevo)
    else:
        rutas.defecto_nuevo.mkdir(parents=True)
    defectos = fe.consolidar_defectos_programas(cycle_manager, rutas.defecto_nuevo)
    return {"parametros": len(datos_par), "defectos": defectos,
            "calibracion": {t: sorted(datos_cal.get(t) or {}) for t in fe.TIPOS_CALIBRACION}}


def _crear_tablas_auditoria(ruta: Path) -> None:
    """cycle_params_audit y sensor_calibration_audit: las crean sus clases
    (R_revision_plan §1), con su mismo SQL."""
    from autoclave.services.domain.logging import cycle_params_audit, sensor_calibration_audit
    conn = sqlite3.connect(str(ruta))
    try:
        conn.execute(cycle_params_audit._CREATE_TABLE)
        conn.execute(sensor_calibration_audit._CREATE_TABLE)
        conn.commit()
    finally:
        conn.close()


def construir_base_nueva(rutas: RutasCierre, *, parametros: list[dict],
                         equipo_instalado: dict | None, usuario: str, rol: str,
                         detalle_liberacion: dict, fecha_liberacion: str,
                         hash_paquete: str) -> Path:
    """Paso 4 (FAB-07): `autoclave.db.nueva` desde cero con DbManager y la
    siembra de preparar_base_entregada; se deja en diario DELETE (un solo
    archivo, sin -wal) y se verifica. Lanza si algo falla."""
    from autoclave.services.domain.logging.db_manager import ESTADO_ENTREGADO, DbManager
    nueva = rutas.base_nueva
    _borrar_base(nueva)
    db = DbManager(nueva)
    try:
        db.preparar_base_entregada(
            parametros=parametros, equipo_instalado=equipo_instalado, usuario=usuario, rol=rol,
            detalle_liberacion=detalle_liberacion, fecha_liberacion=fecha_liberacion,
            hash_paquete=hash_paquete)
    finally:
        db.close()
    _crear_tablas_auditoria(nueva)
    conn = sqlite3.connect(str(nueva))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        modo = conn.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
        chequeo = conn.execute("PRAGMA integrity_check").fetchone()[0]
        estado = conn.execute("SELECT estado FROM estado_fabrica WHERE id = 1").fetchone()
    finally:
        conn.close()
    if str(modo).lower() != "delete" or chequeo != "ok" or not estado \
            or estado[0] != ESTADO_ENTREGADO:
        raise ErrorCierre("base_nueva_invalida", f"modo={modo} chequeo={chequeo} estado={estado}")
    for s in SIDECARS_BASE:
        if Path(str(nueva) + s).exists():
            raise ErrorCierre("base_nueva_invalida", f"quedó {nueva.name}{s}")
    return nueva


def ejecutar_fase1(*, fuentes: pl.FuentesPaquete, carpeta_usb, usuario: str, rol: str,
                   rutas: RutasCierre, config_manager, cycle_manager,
                   leer_base_vieja: Callable[[], tuple[list[dict], dict | None]],
                   serie: str, progreso: Callable[[str], None] = lambda _e: None,
                   ahora: datetime | None = None, mapas: dict | None = None,
                   origen_calibracion=None) -> ResultadoFase1:
    """Pasos 2 a 4 de la fase 1 (las precondiciones, el paro del lazo, la
    marca y el reinicio los hace el llamador). Ante cualquier fallo borra los
    temporales y lanza ErrorCierre (o pl.ErrorPaquete): la USB y el equipo
    quedan como estaban."""
    ahora = ahora or datetime.now()
    progreso("paquete")
    resultado = pl.generar_paquete_liberacion(fuentes, carpeta_usb, usuario, ahora=ahora)
    hash_paquete = pl.verificar_paquete(resultado.ruta)
    if hash_paquete != resultado.hash_global:
        raise ErrorCierre("paquete_no_verifica", resultado.ruta.name)
    fecha = ahora.isoformat(timespec="seconds")
    try:
        progreso("consolidando")
        consolidar_en_temporales(config_manager, cycle_manager, rutas, mapas=mapas,
                                 origen_calibracion=origen_calibracion)
        progreso("base_nueva")
        parametros, equipo_instalado = leer_base_vieja()
        # D-12: fecha, serie y nombre del ZIP; el hash no va a la bitácora
        detalle = {"fecha": fecha, "serie": serie, "paquete": resultado.ruta.name}
        construir_base_nueva(rutas, parametros=parametros, equipo_instalado=equipo_instalado,
                             usuario=usuario, rol=rol, detalle_liberacion=detalle,
                             fecha_liberacion=fecha, hash_paquete=hash_paquete)
    except BaseException:
        limpiar_temporales(rutas)
        raise
    return ResultadoFase1(ruta_paquete=resultado.ruta, nombre_paquete=resultado.ruta.name,
                          hash_paquete=hash_paquete, fecha_liberacion=fecha)


def escribir_marca(rutas: RutasCierre, resultado: ResultadoFase1, usuario: str) -> Path:
    """Paso 5, PUNTO DE NO RETORNO: la marca, atómica, junto a la base.
    Antes de escribirla comprueba que los temporales estén completos."""
    faltan = [p.name for p in (rutas.base_nueva, rutas.temporal(fe.NOMBRE_PARAMETROS),
                               rutas.temporal(fe.NOMBRE_CALIBRACION), rutas.defecto_nuevo)
              if not p.exists()]
    if faltan:
        raise ErrorCierre("temporales_incompletos", ", ".join(faltan))
    datos = {"formato": FORMATO_MARCA, "fecha": resultado.fecha_liberacion, "usuario": usuario,
             "hash_paquete": resultado.hash_paquete, "ruta_paquete": str(resultado.ruta_paquete),
             "pasos_pendientes": list(PASOS), "pasos_hechos": []}
    escribir_texto_atomico(rutas.marca, json.dumps(datos, ensure_ascii=False, indent=2))
    logger.warning("Cierre de fabricación: marca escrita (punto de no retorno); el cierre se "
                   "completa al reiniciar")
    return rutas.marca


# ── fase 2 ──────────────────────────────────────────────────────────────
class _MarcaRechazada(Exception):
    """La marca no corresponde a un cierre legítimo de este equipo (SAF-01):
    no se borra nada y la marca se aparta."""


class _NoVerificable(Exception):
    """No se pudo leer una base para validar (bloqueada, sin permisos): no se
    borra nada, la marca se conserva y el arranque queda detenido (SAF-02)."""


class _MarcaNoGuardada(Exception):
    """SAF-03: la marca no se pudo actualizar tras un paso."""


# Estado de la fase 2 de este proceso por ruta de la marca: True = cierre
# pendiente que no pudo terminar (el arranque se detiene, SAF-02)
_ESTADO_FASE2: dict[str, bool] = {}
# Contexto de la fase 2 en curso (un solo hilo, al arrancar): la fecha de la
# marca para no borrar respaldos posteriores (SAF-02, defensa en profundidad)
_CONTEXTO: dict = {"fecha": None}


def _leer_marca(ruta: Path) -> dict:
    """La marca como objeto. Lanza _MarcaRechazada si es ilegible o no es un
    objeto (SAF-01: se retiró «marca ilegible = repetir todo»)."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as e:
        raise _MarcaRechazada(f"marca ilegible ({type(e).__name__})") from e
    if not isinstance(datos, dict):
        raise _MarcaRechazada("la marca no es un objeto")
    return datos


def _guardar_marca(ruta: Path, datos: dict) -> None:
    """SAF-03: lanza _MarcaNoGuardada si no se puede escribir (antes se tragaba
    el error y un paso destructivo podía repetirse)."""
    try:
        escribir_texto_atomico(ruta, json.dumps(datos, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.exception("Cierre de fabricación: no se pudo actualizar la marca")
        raise _MarcaNoGuardada(f"{type(e).__name__}: {e}") from e


def _fecha_marca(datos: dict) -> datetime:
    fecha = datos.get("fecha")
    if not isinstance(fecha, str):
        raise _MarcaRechazada("marca sin fecha")
    try:
        return datetime.fromisoformat(fecha)
    except ValueError as e:
        raise _MarcaRechazada(f"fecha ilegible: {fecha!r}") from e


def _abrir_solo_lectura(ruta: Path) -> sqlite3.Connection:
    """URI `mode=ro`: nunca crea la base (si no existe, falla)."""
    return sqlite3.connect(Path(ruta).resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)


def _leer_base(ruta: Path, *, integridad: bool = False, contar: bool = False) -> dict:
    """{estado, fecha, hash[, integridad][, ciclos, liberado, posteriores]} de
    una base, en solo lectura. Lanza _MarcaRechazada si la base no existe, no
    es una base o no tiene las tablas, y _NoVerificable si no se puede abrir o
    está bloqueada."""
    from autoclave.services.domain.logging.db_manager import EVENTO_EQUIPO_LIBERADO
    ruta = Path(ruta)
    if not ruta.is_file():
        raise _MarcaRechazada(f"no existe {ruta.name}")
    try:
        conn = _abrir_solo_lectura(ruta)
    except sqlite3.Error as e:
        raise _NoVerificable(f"{ruta.name}: {e}") from e
    try:
        salida = {}
        if integridad:
            salida["integridad"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fila = conn.execute("SELECT estado, fecha_liberacion, hash_paquete FROM estado_fabrica "
                            "WHERE id = 1").fetchone()
        salida.update(estado=fila[0] if fila else None, fecha=fila[1] if fila else None,
                      hash=fila[2] if fila else None)
        if contar:
            salida["ciclos"] = int(conn.execute("SELECT COUNT(*) FROM ciclos").fetchone()[0])
            ultimo = conn.execute("SELECT MAX(id) FROM audit_log WHERE evento = ?",
                                  (EVENTO_EQUIPO_LIBERADO,)).fetchone()[0]
            salida["liberado"] = ultimo is not None
            salida["posteriores"] = int(conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE id > ?",
                (ultimo if ultimo is not None else -1,)).fetchone()[0])
        return salida
    except sqlite3.OperationalError as e:
        texto = str(e).lower()
        if "no such table" in texto or "no such column" in texto:
            raise _MarcaRechazada(f"{ruta.name}: {e}") from e
        raise _NoVerificable(f"{ruta.name}: {e}") from e
    except sqlite3.DatabaseError as e:
        raise _MarcaRechazada(f"{ruta.name} no es una base válida: {e}") from e
    finally:
        conn.close()


def _validar_entregada(ruta: Path, hash_paquete: str, fecha: str) -> None:
    """La base (ya reemplazada) es la del cierre de la marca y no se usó."""
    from autoclave.services.domain.logging.db_manager import ESTADO_ENTREGADO
    b = _leer_base(ruta, contar=True)
    if b["estado"] != ESTADO_ENTREGADO:
        raise _MarcaRechazada(f"la base vigente no está ENTREGADO ({b['estado']})")
    if b["hash"] != hash_paquete or b["fecha"] != fecha:
        raise _MarcaRechazada("la base vigente es de otro cierre (hash o fecha distintos)")
    if b["ciclos"]:
        raise _MarcaRechazada(f"la base vigente tiene {b['ciclos']} ciclos")
    if not b["liberado"] or b["posteriores"]:
        raise _MarcaRechazada("la base vigente tiene bitácora posterior a la liberación")


def _validar_marca(rutas: RutasCierre, datos: dict, pendientes: list[str]) -> None:
    """SAF-01: lanza _MarcaRechazada (o _NoVerificable) si la fase 2 no debe
    tocar nada."""
    from autoclave.services.domain.logging.db_manager import ESTADO_ENTREGADO, ESTADO_FABRICA
    if datos.get("formato") != FORMATO_MARCA or isinstance(datos.get("formato"), bool):
        raise _MarcaRechazada(f"formato de marca desconocido: {datos.get('formato')!r}")
    hash_paquete = datos.get("hash_paquete")
    if not isinstance(hash_paquete, str) or not _HASH_HEX.match(hash_paquete):
        raise _MarcaRechazada("hash_paquete inválido")
    _fecha_marca(datos)
    fecha = datos["fecha"]
    for clave in ("pasos_hechos", "pasos_pendientes"):
        if clave in datos and not isinstance(datos[clave], list):
            raise _MarcaRechazada(f"{clave} no es una lista")
    if "base" in pendientes and rutas.base_nueva.exists():
        n = _leer_base(rutas.base_nueva, integridad=True)
        if n.get("integridad") != "ok":
            raise _MarcaRechazada(f"{rutas.base_nueva.name} no íntegra: {n.get('integridad')}")
        if n["estado"] != ESTADO_ENTREGADO or n["hash"] != hash_paquete or n["fecha"] != fecha:
            raise _MarcaRechazada(f"{rutas.base_nueva.name} no es la base del cierre de la marca")
        # la vigente (o, cortado a mitad del reemplazo, la ya apartada) en FÁBRICA
        vigente = rutas.base if rutas.base.exists() \
            else rutas.base.with_name(rutas.base.name + SUFIJO_BASE_VIEJA)
        v = _leer_base(vigente)
        if v["estado"] != ESTADO_FABRICA:
            raise _MarcaRechazada(f"la base vigente no está en FÁBRICA ({v['estado']})")
        return
    # base ya reemplazada (también con la marca sin actualizar tras el paso)
    _validar_entregada(rutas.base, hash_paquete, fecha)


def _apartar_marca_rechazada(rutas: RutasCierre, motivo: str) -> Path | None:
    """La marca rechazada se renombra sin sobrescribir una anterior."""
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = rutas.marca.with_name(NOMBRE_MARCA + SUFIJO_RECHAZADA + sello)
    destino, n = base, 1
    while destino.exists():
        destino = base.with_name(f"{base.name}-{n}")
        n += 1
    try:
        os.rename(rutas.marca, destino)
    except OSError:
        logger.exception("Cierre de fabricación: no se pudo apartar la marca rechazada (%s)",
                         motivo)
        return None
    logger.error("Cierre de fabricación: marca RECHAZADA (%s); no se borró nada; apartada en %s",
                 motivo, destino.name)
    return destino


def _paso_archivos_fabrica(rutas: RutasCierre, _fallos: list) -> None:
    for nombre in (fe.NOMBRE_PARAMETROS, fe.NOMBRE_CALIBRACION):
        tmp = rutas.temporal(nombre)
        if tmp.exists():
            _con_reintentos(lambda t=tmp, n=nombre: os.replace(t, rutas.final(n)))


def _paso_defectos(rutas: RutasCierre, fallos: list) -> None:
    if rutas.defecto_nuevo.is_dir():
        if rutas.defecto.exists():
            if rutas.defecto_viejo.exists():
                shutil.rmtree(rutas.defecto_viejo)
            _con_reintentos(lambda: os.replace(rutas.defecto, rutas.defecto_viejo))
        _con_reintentos(lambda: os.replace(rutas.defecto_nuevo, rutas.defecto))
    if rutas.defecto_viejo.exists():
        shutil.rmtree(rutas.defecto_viejo, ignore_errors=True)
        if rutas.defecto_viejo.exists():
            fallos.append(rutas.defecto_viejo.name)


def _paso_base(rutas: RutasCierre, _fallos: list) -> None:
    nueva, base = rutas.base_nueva, rutas.base
    if not nueva.exists():
        return                      # ya reemplazada en un intento anterior
    vieja = base.with_name(base.name + SUFIJO_BASE_VIEJA)
    # primero los -wal/-shm/-journal: un -wal viejo junto a la base nueva la
    # corrompería al abrirla
    for s in SIDECARS_BASE:
        extra = Path(str(base) + s)
        if extra.exists():
            _con_reintentos(lambda e=extra, s=s: os.replace(e, Path(str(vieja) + s)))
    if base.exists():
        _con_reintentos(lambda: os.replace(base, vieja))
    for s in SIDECARS_BASE:
        _borrar_archivo(Path(str(nueva) + s))
    _con_reintentos(lambda: os.replace(nueva, base))


def _posterior(archivo: Path, limite: datetime | None) -> bool:
    """Modificado después de la fecha de la marca (SAF-02). Ante un error al
    leer la fecha, se toma como posterior (se conserva)."""
    if limite is None:
        return False
    try:
        return datetime.fromtimestamp(archivo.stat().st_mtime) > limite
    except (OSError, ValueError, OverflowError):
        return True


def _paso_respaldo_ciclos(rutas: RutasCierre, fallos: list) -> None:
    """FAB-10: todo respaldo_ciclos (pendientes e importados/). Se aparta con
    un renombrado (atómico: nada queda para reimportar) y luego se borra.
    SAF-02 (defensa en profundidad): un archivo modificado después de la
    fecha de la marca no se borra (se conserva en su sitio y va al log)."""
    limite = _CONTEXTO.get("fecha")
    carpeta = Path(rutas.carpeta_datos) / CARPETA_RESPALDO_CICLOS
    apartada = Path(rutas.carpeta_datos) / (CARPETA_RESPALDO_CICLOS + SUFIJO_BORRAR)
    if carpeta.exists():
        recientes = [a for a in carpeta.rglob("*") if a.is_file() and _posterior(a, limite)]
        if recientes:
            logger.error("Cierre de fabricación: %d respaldos de ciclos posteriores a la marca "
                         "se CONSERVAN: %s", len(recientes),
                         ", ".join(sorted(a.name for a in recientes)))
            _borrar_arbol_con_ceros(carpeta, fallos, limite)
        else:
            if apartada.exists():
                shutil.rmtree(apartada, ignore_errors=True)
            try:
                _con_reintentos(lambda: os.replace(carpeta, apartada))
            except OSError:
                # sin renombrar (un archivo abierto): se borra en el sitio; si queda algo, falla
                shutil.rmtree(carpeta, ignore_errors=True)
                if carpeta.exists() and any(carpeta.rglob("*.jsonl")):
                    raise
    if apartada.exists():
        _borrar_arbol_con_ceros(apartada, fallos, limite)


def _borrar_arbol_con_ceros(carpeta: Path, fallos: list, limite: datetime | None = None) -> None:
    """Con `limite`, los archivos posteriores se conservan (y las carpetas que
    los contienen); sin él, se borra todo."""
    conservados = []
    for archivo in sorted(carpeta.rglob("*"), reverse=True):
        if not archivo.is_file():
            continue
        if _posterior(archivo, limite):
            conservados.append(archivo)
            continue
        if not sobrescribir_y_borrar(archivo):
            fallos.append(archivo.name)
    if conservados:
        for sub in sorted((d for d in carpeta.rglob("*") if d.is_dir()), reverse=True):
            try:
                sub.rmdir()
            except OSError:
                pass
        return
    shutil.rmtree(carpeta, ignore_errors=True)
    if carpeta.exists():
        fallos.append(carpeta.name)


def _ciclos_en_base(rutas: RutasCierre) -> int:
    """Ciclos de la base vigente (solo lectura). Lanza si no se puede saber."""
    if not rutas.base.is_file():
        return 0
    conn = _abrir_solo_lectura(rutas.base)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM ciclos").fetchone()[0])
    finally:
        conn.close()


def _paso_contadores(rutas: RutasCierre, _fallos: list) -> None:
    """D-10, DF-09, DF-10: contador de ciclos y base de mantenimiento en 0;
    numeros_usados.json sin los números 1 a 10 (conserva los mayores).
    SAF-02: si la base vigente tiene ciclos, el contador y la base de
    mantenimiento no se tocan (nunca baja la numeración de ciclos reales)."""
    datos = Path(rutas.carpeta_datos)
    ciclos = _ciclos_en_base(rutas)
    if ciclos:
        logger.error("Cierre de fabricación: la base vigente tiene %d ciclos; el contador de "
                     "ciclos y la base de mantenimiento NO se ponen en cero", ciclos)
    else:
        escribir_texto_atomico(datos / "ciclo_contador.json", json.dumps({"ultimo": 0}))
        escribir_texto_atomico(datos / "mantenimiento_base.json",
                               json.dumps({"ciclos_instalacion": 0}))
    from autoclave.core.managers.gestion_programas import NUMEROS_USADOS
    usados = Path(rutas.carpeta_ciclos) / "user" / NUMEROS_USADOS
    if usados.exists():
        try:
            lista = json.loads(usados.read_text(encoding="utf-8"))
        except ValueError:
            logger.error("Cierre de fabricación: %s ilegible; se deja vacío", usados.name)
            lista = []
        if not isinstance(lista, list):
            lista = []
        quedan = sorted({n for n in lista if isinstance(n, int) and not isinstance(n, bool)
                         and n not in NUMEROS_FABRICA})
        escribir_texto_atomico(usados, json.dumps(quedan))


def _archivos_de_registro(rutas: RutasCierre) -> list[Path]:
    datos = Path(rutas.carpeta_datos)
    lista: list[Path] = []
    for carpeta in (datos, rutas.carpeta_logs):
        if carpeta is not None and Path(carpeta).is_dir():
            lista += sorted(Path(carpeta).glob("*.log"))
            lista += sorted(Path(carpeta).glob("*.log.*"))
    if rutas.ruta_registro_perfil is not None:
        lista.append(Path(rutas.ruta_registro_perfil))
    lista += [datos / "login_recordado.json", datos / "last_shutdown.json",
              datos / "asignacion_io.json.bak"]
    lista += sorted(rutas.base.parent.glob(rutas.base.name + ".corrupta-*"))
    usuario = Path(rutas.carpeta_ciclos) / "user"
    if usuario.is_dir():
        lista += sorted(usuario.glob("*.bak"))
    # asignacion_io.json.formato1.bak se conserva (no coincide con ninguno)
    return lista


def _paso_registros(rutas: RutasCierre, fallos: list) -> None:
    """D-09 y §6.4 corregida: logs, registro de cambios del perfil, usuario
    recordado, último apagado, bases corruptas apartadas y .bak de
    configuración de las pruebas. Mejor esfuerzo."""
    for archivo in _archivos_de_registro(rutas):
        _borrar_o_truncar(archivo, fallos)


def _paso_base_vieja(rutas: RutasCierre, fallos: list) -> None:
    for archivo in _bases_viejas(rutas):
        if not sobrescribir_y_borrar(archivo):
            fallos.append(archivo.name)


_FUNCIONES = {"archivos_fabrica": _paso_archivos_fabrica, "defectos": _paso_defectos,
              "base": _paso_base, "respaldo_ciclos": _paso_respaldo_ciclos,
              "contadores": _paso_contadores, "registros": _paso_registros,
              "base_vieja": _paso_base_vieja}


def _marca_bloqueo(rutas: RutasCierre) -> Path:
    from autoclave.services.domain.logging.db_manager import marca_bd_bloqueada
    return marca_bd_bloqueada(rutas.base)


def _desbloquear_base(rutas: RutasCierre) -> None:
    """Retira una BD_BLOQUEADA propia de antes de SAF-02 (hoy no se escribe)."""
    marca = _marca_bloqueo(rutas)
    try:
        if marca.exists() and marca.read_text(encoding="utf-8").startswith(PREFIJO_BLOQUEO):
            marca.unlink()
            logger.info("Cierre de fabricación: marca BD_BLOQUEADA propia retirada")
    except Exception:
        logger.exception("Cierre de fabricación: no se pudo retirar la marca BD_BLOQUEADA")


def _base_entregada_con_fecha(rutas: RutasCierre) -> bool:
    """SAF-06: la base vigente (solo lectura) está ENTREGADO con fecha de
    liberación. Ante cualquier duda, False."""
    from autoclave.services.domain.logging.db_manager import ESTADO_ENTREGADO
    try:
        b = _leer_base(rutas.base)
    except (_MarcaRechazada, _NoVerificable) as e:
        logger.info("Cierre de fabricación: restos sin tocar (%s)", e)
        return False
    except Exception:
        logger.exception("Cierre de fabricación: no se pudo leer la base para los restos")
        return False
    return b["estado"] == ESTADO_ENTREGADO and b["fecha"] is not None


def _limpiar_restos(rutas: RutasCierre) -> list[str]:
    """Sin marca: temporales de una fase 1 cortada (solo archivos que crea el
    cierre) y, solo con la base vigente ENTREGADO y con fecha de liberación
    (SAF-06), los restos de un cierre ya terminado (base vieja, defectos
    viejos, respaldo apartado). Si no, esos restos no se tocan."""
    borrados = []
    hay = [p for p in [rutas.base_nueva, rutas.defecto_nuevo]
           + list(Path(rutas.carpeta_datos).glob("*" + SUFIJO_NUEVO)) if p.exists()]
    if hay:
        limpiar_temporales(rutas)
        borrados += [p.name for p in hay]
    apartada = Path(rutas.carpeta_datos) / (CARPETA_RESPALDO_CICLOS + SUFIJO_BORRAR)
    restos = [a for a in _bases_viejas(rutas) if a.exists()] \
        + [c for c in (rutas.defecto_viejo, apartada) if c.exists()]
    if restos:
        if _base_entregada_con_fecha(rutas):
            for archivo in _bases_viejas(rutas):
                if archivo.exists():
                    sobrescribir_y_borrar(archivo)
                    borrados.append(archivo.name)
            for carpeta in (rutas.defecto_viejo, apartada):
                if carpeta.exists():
                    _borrar_arbol_con_ceros(carpeta, [])
                    borrados.append(carpeta.name)
        else:
            logger.warning("Cierre de fabricación: restos sin tocar (la base vigente no está "
                           "ENTREGADO con fecha de liberación): %s",
                           ", ".join(p.name for p in restos))
    if borrados:
        logger.warning("Cierre de fabricación: sin marca; restos borrados: %s", ", ".join(borrados))
    return borrados


def _quitar_marca(rutas: RutasCierre) -> None:
    """SAF-03: si no se puede borrar, se renombra a cierre_fabrica.hecho; si
    tampoco, queda con todos los pasos hechos (el próximo arranque solo la
    vuelve a quitar) y la validación de SAF-01 impide repetir lo destructivo."""
    try:
        rutas.marca.unlink()
        return
    except FileNotFoundError:
        return
    except OSError:
        logger.exception("Cierre de fabricación: no se pudo borrar la marca")
    try:
        os.replace(rutas.marca, rutas.marca.with_name(NOMBRE_MARCA_HECHA))
        logger.warning("Cierre de fabricación: marca renombrada a %s", NOMBRE_MARCA_HECHA)
    except OSError:
        logger.exception("Cierre de fabricación: tampoco se pudo renombrar la marca")


def cierre_incompleto(rutas: RutasCierre | None = None) -> bool:
    """SAF-02: hay un cierre de fabricación pendiente que no pudo terminar y
    el equipo no debe operar (lo consulta la etapa 1 del arranque, que se
    detiene con ARR_CIERRE_FABRICA). Si la fase 2 corrió en este proceso, su
    resultado; si no, que exista la marca (falla cerrada). Nunca lanza."""
    try:
        if rutas is None:
            from autoclave.services.domain.logging.db_manager import DB_DEFAULT
            marca = Path(DB_DEFAULT).with_name(NOMBRE_MARCA)
        else:
            marca = rutas.marca
        clave = str(marca)
        if clave in _ESTADO_FASE2:
            return _ESTADO_FASE2[clave]
        return marca.exists()
    except Exception:
        logger.exception("Cierre de fabricación: no se pudo comprobar si quedó incompleto")
        return False


def completar_cierre_si_pendiente(rutas: RutasCierre | None = None) -> dict:
    """Fase 2 (DF-05). Llamar al arrancar el backend ANTES de abrir cualquier
    DbManager. Nunca lanza. Devuelve {"marca", "completado", "hechos",
    "pendientes", "fallos", "restos", "rechazada", "motivo", "bloquear"}.
    `bloquear` True = cierre pendiente que no terminó (SAF-02)."""
    salida = {"marca": False, "completado": False, "hechos": [], "pendientes": [],
              "fallos": [], "restos": [], "rechazada": None, "motivo": "", "bloquear": False}
    clave = None
    try:
        rutas = rutas or rutas_del_equipo()
        clave = str(rutas.marca)
        if not rutas.marca.exists():
            salida["restos"] = _limpiar_restos(rutas)
            _ESTADO_FASE2[clave] = False
            return salida
        salida["marca"] = True
        logger.warning("Cierre de fabricación pendiente: se valida antes de abrir la base")
        hechos: list[str] = []
        pendientes: list[str] = list(PASOS)
        try:
            datos = _leer_marca(rutas.marca)
            lista = datos.get("pasos_hechos", [])
            hechos = [p for p in lista if p in PASOS] if isinstance(lista, list) else []
            pendientes = [p for p in PASOS if p not in hechos]
            if pendientes:
                _validar_marca(rutas, datos, pendientes)
        except _MarcaRechazada as e:
            destino = _apartar_marca_rechazada(rutas, str(e))
            salida.update(rechazada=destino.name if destino else None, motivo=str(e))
            _ESTADO_FASE2[clave] = False
            return salida
        except _NoVerificable as e:
            logger.error("Cierre de fabricación: no se pudo validar (%s); no se borra nada y el "
                         "arranque queda detenido", e)
            salida.update(pendientes=pendientes, hechos=hechos, motivo=str(e), bloquear=True)
            _ESTADO_FASE2[clave] = True
            return salida
        _CONTEXTO["fecha"] = _fecha_marca(datos) if pendientes else None
        try:
            for paso in PASOS:
                if paso in hechos:
                    continue
                fallos: list = []
                try:
                    _FUNCIONES[paso](rutas, fallos)
                except Exception as e:
                    logger.exception("Cierre de fabricación: falló el paso '%s'", paso)
                    if paso in PASOS_CRITICOS:
                        salida.update(pendientes=[p for p in PASOS if p not in hechos],
                                      hechos=hechos, bloquear=True,
                                      motivo=f"{paso}: {type(e).__name__}: {e}")
                        _ESTADO_FASE2[clave] = True
                        return salida
                    fallos.append(f"{type(e).__name__}: {e}")
                if fallos:
                    logger.warning("Cierre de fabricación: paso '%s' hecho con avisos: %s",
                                   paso, "; ".join(fallos))
                    salida["fallos"] += fallos
                anotados = hechos + [paso]
                datos["pasos_hechos"] = anotados
                datos["pasos_pendientes"] = [p for p in PASOS if p not in anotados]
                try:
                    _guardar_marca(rutas.marca, datos)
                except _MarcaNoGuardada as e:
                    # SAF-03: el paso se hizo pero la marca no lo dice; se corta
                    # aquí (el próximo arranque lo repite tras validar)
                    salida.update(pendientes=[p for p in PASOS if p not in hechos],
                                  hechos=list(hechos), bloquear=True,
                                  motivo=f"marca no actualizada tras '{paso}': {e}")
                    _ESTADO_FASE2[clave] = True
                    return salida
                hechos = anotados
        finally:
            _CONTEXTO["fecha"] = None
        _quitar_marca(rutas)
        _desbloquear_base(rutas)
        salida.update(completado=True, hechos=hechos)
        _ESTADO_FASE2[clave] = False
        logger.warning("Cierre de fabricación terminado: equipo ENTREGADO")
    except Exception:
        logger.exception("Cierre de fabricación: error inesperado en la fase 2")
        salida["bloquear"] = salida["marca"]
        if clave is not None:
            _ESTADO_FASE2[clave] = salida["marca"]
    return salida
