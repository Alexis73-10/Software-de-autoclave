# core/runtime/fabrica_equipo.py
#
# Modo fábrica, Etapa 3: base de fábrica del equipo (D-08, FAB-06, FAB-08;
# DF-07 y R-05 de la revisión). Lo ajustado en FÁBRICA reemplaza a los valores
# genéricos, y en campo «restaurar valores de fábrica» vuelve a lo de ese
# equipo.
#
# - Parámetros del equipo: `parametros_fabrica_equipo.json` en la carpeta de
#   datos (`data/`, junto a tema.json y ciclo_contador.json) = {clave: valor}.
#   Lo carga `ConfigManager.load_config` como valor de fábrica.
# - Calibración: `calibracion_fabrica_equipo.yaml` en la misma carpeta, con la
#   sección `user` vigente indexada por FUNCIÓN de sensor (temp_camara,
#   pres_camara...) y el canal que esa función usaba al guardar: tras una
#   reasignación de E/S la entrada no se copia al canal nuevo (como «ultimo»).
#   La usa POST /calibration/{tipo}/{sensor}/restaurar con destino «defecto».
# - Defectos de programas: `consolidar_defectos_programas` reescribe
#   `cycles/defecto/` con los programas que quedan.
#
# FAB-06: en ENTREGADO esa base es de solo lectura. Solo el cierre (Etapa 5)
# llama a las tres funciones de escritura de este módulo; lo vigila
# tests/test_fab_e3_solo_lectura.py. Este módulo es el único que nombra los
# dos archivos.

import json
import logging
import math
import os
from pathlib import Path

import yaml

from autoclave.utils.archivos import escribir_texto_atomico

logger = logging.getLogger(__name__)

NOMBRE_PARAMETROS = "parametros_fabrica_equipo.json"
NOMBRE_CALIBRACION = "calibracion_fabrica_equipo.yaml"
# formato del archivo de calibración del equipo
FORMATO_CALIBRACION = 1
# numeración de puertos de la calibración (tanda 23, AIN-05), como en io.py
_FORMATO_PUERTO = 2
# carpeta de estos archivos dentro del ZIP del respaldo USB (solo copia)
CARPETA_EN_RESPALDO = "fabrica_equipo"
TIPOS_CALIBRACION = ("temperature", "pressure")
SUFIJO_TEMPORAL_DEFECTO = ".fab_nuevo"


# ── rutas ──────────────────────────────────────────────────────────────
def carpeta_datos() -> Path:
    """`data/` del equipo (la de tema.json y ciclo_contador.json)."""
    from autoclave.utils.paths import app_root
    return app_root() / "data"


def ruta_parametros() -> Path:
    return carpeta_datos() / NOMBRE_PARAMETROS


def ruta_calibracion() -> Path:
    return carpeta_datos() / NOMBRE_CALIBRACION


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


# ── 1. parámetros del equipo ───────────────────────────────────────────
def leer_parametros_crudos(ruta) -> dict | None:
    """{clave: valor} del archivo, sin validar (lo valida ConfigManager con
    el catálogo). None si no existe. Lanza si es ilegible o no es un objeto
    (el llamador lo registra y sigue con los genéricos)."""
    ruta = Path(ruta)
    if not ruta.exists():
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name}: se esperaba un objeto JSON")
    return datos


def escribir_parametros_fabrica_equipo(config_manager, destino=None) -> dict:
    """Para el cierre (Etapa 5): escribe {clave: valor vigente} de todos los
    parámetros del equipo en `destino` (por omisión, `ruta_parametros()`), de
    forma atómica. Devuelve lo escrito. Lanza si no puede escribir."""
    destino = ruta_parametros() if destino is None else Path(destino)
    valores = {p["clave"]: p["valor"] for p in config_manager.describir()}
    escribir_texto_atomico(destino, json.dumps(valores, ensure_ascii=False, indent=2,
                                               sort_keys=True))
    return valores


# ── 2. calibración del equipo ──────────────────────────────────────────
def _mapas_vigentes() -> dict:
    from autoclave.core.runtime.status import EstadoAutoclave
    return {"temperature": dict(EstadoAutoclave.map_temp),
            "pressure": dict(EstadoAutoclave.map_pres)}


def escribir_calibracion_fabrica_equipo(destino=None, origen=None,
                                        mapas: dict | None = None) -> dict:
    """Para el cierre (Etapa 5): guarda la sección `user` vigente de la
    calibración por función de sensor, con el canal que usa hoy, en
    `destino` (por omisión, `ruta_calibracion()`), de forma atómica.
    `origen`: archivo de calibración activo (por omisión,
    `utils/paths.calibration_path()`). `mapas`: {tipo: {sensor: canal}} (por
    omisión, la asignación de E/S vigente). Devuelve lo escrito. Lanza si no
    puede leer o escribir."""
    from autoclave.config import load_config
    from autoclave.utils.paths import calibration_path
    destino = ruta_calibracion() if destino is None else Path(destino)
    origen = calibration_path() if origen is None else origen
    mapas = _mapas_vigentes() if mapas is None else mapas
    cfg = load_config(origen)
    listas = {"temperature": cfg.calibration.user.temperature,
              "pressure": cfg.calibration.user.pressure}
    salida: dict = {"formato": FORMATO_CALIBRACION}
    for tipo in TIPOS_CALIBRACION:
        por_sensor = {}
        for sensor, canal in sorted((mapas.get(tipo) or {}).items()):
            lista = listas[tipo]
            if not isinstance(canal, int) or isinstance(canal, bool) or not 0 <= canal < len(lista):
                logger.warning("Calibración del equipo: %s/%s con canal %r fuera de rango: no se guarda",
                               tipo, sensor, canal)
                continue
            c = lista[canal]
            por_sensor[sensor] = {"canal": canal, "puerto": canal + 1, "formato": _FORMATO_PUERTO,
                                  "gain": float(c.gain), "offset": float(c.offset),
                                  "poly": [float(x) for x in c.poly] if c.poly else None}
        salida[tipo] = por_sensor
    escribir_texto_atomico(destino,
                           yaml.safe_dump(salida, allow_unicode=True, sort_keys=True))
    return salida


def entrada_calibracion_equipo(tipo: str, sensor: str, canal: int, ruta=None) -> dict | None:
    """Entrada de la calibración de fábrica del equipo para restaurar
    «defecto»: {"gain", "offset", "poly"} o None (y entonces rige el neutro)
    si el archivo no existe, es ilegible, no trae ese sensor, la entrada no
    es válida (no finita, poly mal formado, calibración no plausible a nivel
    de rechazo) o su canal no es el que la función usa hoy (reasignación de
    E/S). Nunca lanza."""
    ruta = ruta_calibracion() if ruta is None else Path(ruta)
    try:
        if not ruta.exists():
            return None
        with open(ruta, "r", encoding="utf-8") as f:
            datos = yaml.safe_load(f)
        if not isinstance(datos, dict) or datos.get("formato") != FORMATO_CALIBRACION:
            logger.warning("Calibración del equipo %s con formato desconocido: rige el neutro", ruta.name)
            return None
        entrada = (datos.get(tipo) or {}).get(sensor) if isinstance(datos.get(tipo), dict) else None
        if not isinstance(entrada, dict):
            return None
        if entrada.get("canal") != canal or isinstance(entrada.get("canal"), bool):
            logger.warning("Calibración del equipo de %s/%s guardada en el canal %r y hoy en el %r "
                           "(reasignación de E/S): rige el neutro", tipo, sensor,
                           entrada.get("canal"), canal)
            return None
        gain, offset, poly = entrada.get("gain"), entrada.get("offset"), entrada.get("poly")
        if not (_numero(gain) and _numero(offset)):
            raise ValueError("ganancia u offset no numéricos")
        from autoclave.core.managers.catalogo_parametros import (evaluar_desviacion_acumulada,
                                                                  evaluar_desviacion_polinomio)
        if poly is not None:
            if not isinstance(poly, list) or not poly or not all(_numero(x) for x in poly):
                raise ValueError("polinomio mal formado")
            poly = [float(x) for x in poly]
        if poly is not None and len(poly) >= 2:
            # SAF-08: el polinomio rige la lectura (converters._user_calibrate):
            # la misma prueba de plausibilidad, sobre el polinomio
            nivel, motivo = evaluar_desviacion_polinomio(tipo, poly, sensor)
        else:
            nivel, motivo = evaluar_desviacion_acumulada(tipo, float(gain), float(offset), sensor)
        if nivel == "rechazo":
            raise ValueError(f"calibración no plausible: {motivo}")
        return {"gain": float(gain), "offset": float(offset), "poly": poly}
    except Exception as e:
        logger.warning("Calibración del equipo de %s/%s no válida (%s): rige el neutro", tipo, sensor, e)
        return None


# ── 3. defectos de programas ───────────────────────────────────────────
def _numero_programa(c):
    n = getattr(c, "number", None)
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else None


def consolidar_defectos_programas(cycle_manager, carpeta_defecto) -> dict:
    """Para el cierre (Etapa 5): deja en `carpeta_defecto` (cycles/defecto)
    un `<cycle_id>.json` por cada programa con número que queda en
    `cycle_manager.cycles`, con sus valores vigentes y `cycle_number` (el
    índice de los defectos), y borra todo otro `.json` de la carpeta
    (defectos de programas que ya no existen o con otro nombre). Un programa
    dañado no se escribe y su defecto previo, si lo hay, se conserva.
    Escribe primero todos los temporales (`*.fab_nuevo`, con fsync) y luego
    los reemplaza; idempotente. No toca `cycle_manager.defectos` (el cierre
    reinicia). Devuelve {"escritos", "borrados", "omitidos"} (nombres de
    archivo e ids). Lanza si una escritura falla, tras borrar los temporales."""
    carpeta = Path(carpeta_defecto)
    carpeta.mkdir(parents=True, exist_ok=True)
    nuevos: dict[str, dict] = {}
    omitidos, conservar = [], set()
    for cid, c in sorted(cycle_manager.cycles.items()):
        numero = _numero_programa(c)
        if numero is None:
            continue
        nombre = f"{cid}.json"
        if getattr(c, "danado", None):
            omitidos.append(cid)
            conservar.add(nombre)
            continue
        nuevos[nombre] = {"cycle_id": cid, "cycle_number": numero,
                          "display_name": getattr(c, "name", "") or "",
                          "parameters": json.loads(json.dumps(c.parameters))}
    temporales = []
    try:
        for nombre, datos in sorted(nuevos.items()):
            tmp = carpeta / (nombre + SUFIJO_TEMPORAL_DEFECTO)
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(json.dumps(datos, indent=4, ensure_ascii=False))
                f.flush()
                os.fsync(f.fileno())
            temporales.append((tmp, carpeta / nombre))
    except Exception:
        for tmp, _ in temporales:
            tmp.unlink(missing_ok=True)
        for nombre in nuevos:
            (carpeta / (nombre + SUFIJO_TEMPORAL_DEFECTO)).unlink(missing_ok=True)
        raise
    for tmp, final in temporales:
        os.replace(tmp, final)
    borrados = []
    for archivo in sorted(carpeta.iterdir()):
        if archivo.is_file() and archivo.suffix == ".json" \
                and archivo.name not in nuevos and archivo.name not in conservar:
            archivo.unlink()
            borrados.append(archivo.name)
    escritos = sorted(nuevos)
    logger.info("Defectos de programas consolidados: %d escritos, %d borrados, %d omitidos",
                len(escritos), len(borrados), len(omitidos))
    return {"escritos": escritos, "borrados": borrados, "omitidos": omitidos}


# ── respaldo USB (solo copia; la restauración no los toca) ──────────────
def contenido_respaldo(perfil_calibracion: bool, parametros: bool) -> dict:
    """{ruta en el ZIP: bytes} de los archivos de la base de fábrica del
    equipo que existan: la calibración con la parte «perfil y calibración» y
    los parámetros con «parámetros y programas». La restauración no los
    restaura (son la base de fábrica del equipo, FAB-06). Nunca lanza."""
    salida = {}
    for incluir, ruta in ((perfil_calibracion, ruta_calibracion()), (parametros, ruta_parametros())):
        if not incluir:
            continue
        try:
            if ruta.exists():
                salida[f"{CARPETA_EN_RESPALDO}/{ruta.name}"] = ruta.read_bytes()
        except OSError:
            logger.exception("No se pudo leer %s para el respaldo", ruta.name)
    return salida
