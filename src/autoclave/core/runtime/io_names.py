"""Nombres canónicos de Entradas / Salidas (B-ES-2, ES-02).

Una sola fuente: la lista de canales habilitados sale de `io_enabled` del
equipo activo (`config/instances/<activa>.yaml`); este módulo la cruza con las
posiciones de `EstadoAutoclave` para dar id físico, clave i18n y tipo de salida.
"""
import logging
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

# D-ES-09: salidas de movimiento de puerta y bomba de vacío se mantienen pulsadas
SALIDAS_MOMENTANEAS = frozenset({
    "abrir_puerta_1", "abrir_puerta_2", "cerrar_puerta_1", "cerrar_puerta_2",
    "bomba_vacio",
})

_OFFSET_RAW_PRESION = 8      # raw_ai: 0-7 temperatura, 8-15 presión


def _config_dir() -> Path:
    return Path(resource_path("autoclave/config"))


def leer_io_enabled(config_dir: Path | None = None) -> dict[str, list[str]]:
    """`io_enabled` del equipo activo; vacío si falta el archivo."""
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


def clave_estado(nombre: str) -> str:
    """Nombre del YAML (o de /io/channels) -> clave de EstadoAutoclave."""
    return _ALIAS_ESTADO.get(nombre, nombre)


_clave_estado = clave_estado


def canales_digitales(tipo: str, config_dir: Path | None = None) -> list[dict]:
    """Canales DI o DO habilitados, en el orden de `io_enabled`. Los que no
    existen en EstadoAutoclave se omiten (no hay posición que leer)."""
    mapa = EstadoAutoclave.map_di if tipo == "DI" else EstadoAutoclave.map_do
    salida = []
    for nombre in leer_io_enabled(config_dir)[tipo]:
        clave = _clave_estado(nombre)
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
        salida.append(canal)
    return salida


def sensores(tipo: str, config_dir: Path | None = None) -> list[dict]:
    """Sensores analógicos habilitados de `temperature` o `pressure`."""
    es_temp = tipo == "temperature"
    mapa = EstadoAutoclave.map_temp if es_temp else EstadoAutoclave.map_pres
    salida = []
    for nombre in leer_io_enabled(config_dir)["AI"]:
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
