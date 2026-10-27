# autoclave.config.enlace_io
# --------------------------
# Selección del enlace de E/S (tanda 19, MOD-01): módulos Ebyte M31-U por
# Modbus TCP ("modbus") o tarjeta ESP32 por el enlace serial v2 ("serial").
#
# Se lee solo de src/autoclave/config/enlace_io.json, una vez por proceso
# (cambiarlo exige reiniciar el backend). Archivo ausente, JSON inválido o un
# valor no admitido: "modbus" con advertencia en el log (DECISIÓN SIN
# CONFIRMAR: valor por defecto).

from __future__ import annotations

import json
import threading
from typing import Any, Optional

from autoclave.utils.logging import logger
from autoclave.utils.resources import resource_path

CONFIG_RELATIVE_PATH = "autoclave/config/enlace_io.json"

ENLACE_MODBUS = "modbus"
ENLACE_SERIAL = "serial"
ENLACES_ADMITIDOS = (ENLACE_MODBUS, ENLACE_SERIAL)
ENLACE_POR_DEFECTO = ENLACE_MODBUS

_lock = threading.Lock()
_activo: Optional[str] = None


def enlace_desde_dict(datos: Any, origen: str = "<dict>") -> str:
    """Valor de `enlace` en `datos`, o el defecto con advertencia."""
    valor = datos.get("enlace") if isinstance(datos, dict) else None
    if isinstance(valor, str) and valor.strip().lower() in ENLACES_ADMITIDOS:
        return valor.strip().lower()
    logger.warning("enlace_io: valor de enlace inválido en %s (%r); se usa %r",
                   origen, valor, ENLACE_POR_DEFECTO)
    return ENLACE_POR_DEFECTO


def leer_enlace(ruta: Optional[str] = None) -> str:
    """Lee el archivo (sin caché). `ruta` solo la usan las pruebas."""
    ruta = ruta or resource_path(CONFIG_RELATIVE_PATH)
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        logger.warning("enlace_io: no existe %s; se usa %r", ruta, ENLACE_POR_DEFECTO)
        return ENLACE_POR_DEFECTO
    except (OSError, ValueError) as e:
        logger.warning("enlace_io: no se pudo leer %s (%s); se usa %r",
                       ruta, e, ENLACE_POR_DEFECTO)
        return ENLACE_POR_DEFECTO
    return enlace_desde_dict(datos, origen=str(ruta))


def enlace_activo() -> str:
    """Enlace de este proceso: se lee la primera vez y queda fijo."""
    global _activo
    with _lock:
        if _activo is None:
            _activo = leer_enlace()
            logger.info("enlace_io: enlace de E/S activo: %s", _activo)
        return _activo


def es_modbus() -> bool:
    return enlace_activo() == ENLACE_MODBUS


def fijar_enlace(valor: Optional[str]) -> None:
    """Solo pruebas: fija el enlace del proceso (None vuelve a leer el archivo)."""
    global _activo
    if valor is not None and valor not in ENLACES_ADMITIDOS:
        raise ValueError(f"enlace no admitido: {valor!r}")
    with _lock:
        _activo = valor
