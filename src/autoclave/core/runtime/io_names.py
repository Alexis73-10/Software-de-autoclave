"""Nombres canónicos de Entradas / Salidas (B-ES-2, ES-02).

Una sola fuente: la lista de canales habilitados sale de `io_enabled` del
equipo activo (`config/instances/<activa>.yaml`); este módulo la cruza con las
posiciones de `EstadoAutoclave` para dar id físico, clave i18n y tipo de salida.

D8-3.17 (tanda 8): el YAML es el máximo físico; con el perfil de instalación,
solo quedan los canales que el perfil declara (`filtrar_por_perfil`).
"""
import logging
import re
from pathlib import Path

from ruamel.yaml import YAML

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

# Nombre del YAML -> clave de EstadoAutoclave cuando difieren (errata histórica
# `admosferico`, `temp_ref`). El nombre canónico es siempre el del YAML.
_ALIAS_ESTADO = {
    "aire_atmosferico_camara": "aire_admosferico_camara",
    "temp_referencia": "temp_ref",
}

# D11-2 (tanda 11): salidas retiradas del equipo. Su canal físico queda libre
# (no se corre ninguna otra salida ni cambia el mapa de E/S de los módulos).
SALIDAS_RETIRADAS = frozenset({"aire_comprimido_chaqueta"})

# D-ES-09: salidas de movimiento de puerta y bomba de vacío se mantienen pulsadas
SALIDAS_MOMENTANEAS = frozenset({
    "abrir_puerta_1", "abrir_puerta_2", "cerrar_puerta_1", "cerrar_puerta_2",
    "bomba_vacio",
})

_OFFSET_RAW_PRESION = 8      # raw_ai: 0-7 temperatura, 8-15 presión


def _config_dir() -> Path:
    return Path(resource_path("autoclave/config"))


def leer_io_enabled(config_dir: Path | None = None, profile=None) -> dict[str, list[str]]:
    """`io_enabled` del equipo activo; vacío si falta el archivo. Con un
    perfil de instalación, solo los canales que el perfil declara."""
    io = _leer_yaml(config_dir)
    return filtrar_por_perfil(io, profile)


def _leer_yaml(config_dir: Path | None) -> dict[str, list[str]]:
    base = Path(config_dir) if config_dir is not None else _config_dir()
    vacio = {"DI": [], "DO": [], "AI": []}
    try:
        yaml = YAML(typ="safe")
        activa = yaml.load((base / "active_instances.yaml").read_text(encoding="utf-8"))
        nombre = activa["active_instance"]
        datos = yaml.load((base / "instances" / f"{nombre}.yaml").read_text(encoding="utf-8"))
        io = datos.get("io_enabled") or {}
    except (OSError, KeyError, TypeError, AttributeError):
        logger.warning("No se pudo leer io_enabled del equipo activo")
        return vacio
    return {k: [str(n) for n in (io.get(k) or [])] for k in vacio}


# D9-5 (tanda 9): entradas de contacto normalmente cerrado (NC) si el YAML de
# la instancia no trae la sección `di_contacto`. Coincide con la lógica fija del
# código: paro de emergencia (devices/paro_emergencia) y seguro de
# atrapamiento de cada puerta (AdvancedDoor).
NC_POR_OMISION = frozenset({"paro_emergencia", "atrapamiento_puerta_1", "atrapamiento_puerta_2"})


def leer_nc(config_dir: Path | None = None) -> dict[str, bool]:
    """Entrada digital -> True si su contacto es NC, para cada DI del máximo
    físico (`io_enabled`). Toma `di_contacto.<entrada>.nc` del YAML de la
    instancia; una entrada sin declarar (o sin la sección) usa
    NC_POR_OMISION. Solo presentación (Opciones > Entradas / Salidas)."""
    declarados = {}
    base = Path(config_dir) if config_dir is not None else _config_dir()
    try:
        yaml = YAML(typ="safe")
        activa = yaml.load((base / "active_instances.yaml").read_text(encoding="utf-8"))
        datos = yaml.load((base / "instances" / f"{activa['active_instance']}.yaml")
                          .read_text(encoding="utf-8"))
        seccion = datos.get("di_contacto") or {}
        for nombre, valor in seccion.items():
            nc = valor.get("nc") if isinstance(valor, dict) else None
            if isinstance(nc, bool):
                declarados[str(nombre)] = nc
    except (OSError, KeyError, TypeError, AttributeError):
        logger.warning("No se pudo leer di_contacto del equipo activo: rige la del código")
    return {n: declarados.get(n, n in NC_POR_OMISION) for n in _leer_yaml(config_dir)["DI"]}


# Canales que dependen de la puerta: nombre -> (número de puerta, función).
# La función es la clave de la configuración de la puerta (factory.py).
_RE_PUERTA_DI = re.compile(r"^(?:puerta_(\d)_(abierta|cerrada)|(atrapamiento)_puerta_(\d))$")
_RE_PUERTA_DO = re.compile(r"^(abrir|cerrar|bloqueo|desbloqueo)_puerta_(\d)$")
_FUNCION_DO = {"abrir": "abrir", "cerrar": "cerrar", "bloqueo": "bloquear",
               "desbloqueo": "desbloquear"}
_SALIDAS_FUENTE_VAPOR = frozenset({"vapor_generador", "vapor_caldera"})


def _canales_de_puertas(profile) -> tuple[set[str], set[str]]:
    """(DI, DO) que leen o accionan las puertas del perfil, con la misma
    configuración con la que se construyen (devices/factory)."""
    from autoclave.devices.factory.factory import build_doors_cfg
    di, do = set(), set()
    for n, cfg in enumerate(build_doors_cfg(profile), start=1):
        di.update(str(v) for v in (cfg.get("di") or {}).values())
        for funcion in (cfg.get("do") or {}):
            for prefijo, clave in _FUNCION_DO.items():
                if clave == funcion:
                    do.add(f"{prefijo}_puerta_{n}")
    return di, do


def filtrar_por_perfil(io: dict[str, list[str]], profile) -> dict[str, list[str]]:
    """D8-3.17: deja solo los canales que el perfil declara. Fuentes:
    `temperature_probes` (sondas), `supply_inputs` (entradas de suministro),
    `door_count`/`door_type` (entradas y salidas de puerta, sensores de
    empaque) y `vapor_source` (salidas de la fuente de vapor). Los canales
    que el perfil no gobierna (vapor de cámara, escapes, paro...) quedan.
    Sin un perfil de instalación cargado, el YAML completo (máximo físico)."""
    from autoclave.installation.profile import (
        InstallationProfile, SUPPLY_INPUT_KEYS, TEMPERATURE_PROBE_KEYS, entrada_requerida,
        salidas_vapor_permitidas, sensores_empaque, sonda_instalada)
    if not isinstance(profile, InstallationProfile):
        return {k: list(v) for k, v in io.items()}
    di_puertas, do_puertas = _canales_de_puertas(profile)
    empaques = set(sensores_empaque(profile))
    vapor = salidas_vapor_permitidas(profile)

    def ai_ok(nombre: str) -> bool:
        clave = clave_estado(nombre)
        if clave.startswith("temp_"):
            # una sonda que el perfil no declara (p. ej. temp_drenaje_camara,
            # sin posición en la trama) no aparece
            return clave in TEMPERATURE_PROBE_KEYS and sonda_instalada(profile, clave)
        if clave.startswith("pres_empaque_"):
            return clave in empaques
        return True

    def di_ok(nombre: str) -> bool:
        if nombre in SUPPLY_INPUT_KEYS:
            return entrada_requerida(profile, nombre)
        if _RE_PUERTA_DI.match(nombre):
            return nombre in di_puertas
        return True

    def do_ok(nombre: str) -> bool:
        if nombre in _SALIDAS_FUENTE_VAPOR:
            return nombre in vapor
        if _RE_PUERTA_DO.match(nombre):
            return nombre in do_puertas
        return True

    return {"AI": [n for n in io.get("AI", []) if ai_ok(n)],
            "DI": [n for n in io.get("DI", []) if di_ok(n)],
            "DO": [n for n in io.get("DO", []) if do_ok(n)]}


def clave_estado(nombre: str) -> str:
    """Nombre del YAML (o de /io/channels) -> clave de EstadoAutoclave."""
    return _ALIAS_ESTADO.get(nombre, nombre)


_clave_estado = clave_estado


def canales_digitales(tipo: str, config_dir: Path | None = None, profile=None) -> list[dict]:
    """Canales DI o DO habilitados, en el orden de `io_enabled`. Los que no
    existen en EstadoAutoclave se omiten (no hay posición que leer)."""
    mapa = EstadoAutoclave.map_di if tipo == "DI" else EstadoAutoclave.map_do
    nc = leer_nc(config_dir) if tipo == "DI" else {}
    salida = []
    for nombre in leer_io_enabled(config_dir, profile)[tipo]:
        clave = _clave_estado(nombre)
        if tipo == "DO" and nombre in SALIDAS_RETIRADAS:
            # D11-2: YAML de instancia de antes (un equipo instalado conserva
            # su copia); se acepta y se ignora
            logger.warning("Salida %s retirada del equipo (tanda 11, D11-2): se ignora "
                           "en io_enabled", nombre)
            continue
        if clave not in mapa:
            logger.warning("Canal %s %s sin posición en EstadoAutoclave: se omite", tipo, nombre)
            continue
        canal = {
            "name": nombre,
            "estado_key": clave,
            "i18n": f"io.{tipo.lower()}.{nombre}",
            "id": f"{tipo} {mapa[clave] + 1:02d}",
        }
        if tipo == "DO":
            canal["momentanea"] = nombre in SALIDAS_MOMENTANEAS
        else:
            canal["nc"] = nc.get(nombre, nombre in NC_POR_OMISION)
        salida.append(canal)
    return salida


def sensores(tipo: str, config_dir: Path | None = None, profile=None) -> list[dict]:
    """Sensores analógicos habilitados de `temperature` o `pressure`."""
    es_temp = tipo == "temperature"
    mapa = EstadoAutoclave.map_temp if es_temp else EstadoAutoclave.map_pres
    salida = []
    for nombre in leer_io_enabled(config_dir, profile)["AI"]:
        clave = _clave_estado(nombre)
        if clave not in mapa:
            continue
        raw = mapa[clave] + (0 if es_temp else _OFFSET_RAW_PRESION)
        salida.append({
            "name": nombre,
            "estado_key": clave,
            "i18n": f"io.ai.{nombre}",
            "id": f"AI {raw + 1:02d}",
            "raw_index": raw,
        })
    return salida
