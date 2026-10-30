# tools/generador/datos_generador.py
#
# Carpeta de datos y configuración del generador (G1, tanda 2).
#
# Los datos (generador.db, config.json, Respaldos\, la clave inicial del
# admin) NUNCA van dentro del ejecutable ni en la carpeta temporal de
# PyInstaller: viven en una carpeta persistente. Por defecto
# C:\ProgramData\Especifika\Generador\ (en otros sistemas, ~/.especifika/generador);
# la variable de entorno GENERADOR_DATOS la cambia.
#
# config.json (se crea con los valores por defecto si no existe):
#   host                 "0.0.0.0"  (escucha en la red local)
#   puerto               8080
#   inactividad_min      15         (la sesión vence sin uso)
#   intentos_max         5          (intentos fallidos antes del bloqueo)
#   bloqueo_min          15         (duración del bloqueo temporal)
#   retencion_respaldos  30         (días)

import json
import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFECTO = {
    "host": "0.0.0.0",
    "puerto": 8080,
    "inactividad_min": 15,
    "intentos_max": 5,
    "bloqueo_min": 15,
    "retencion_respaldos": 30,
}


def carpeta_datos() -> Path:
    propia = os.environ.get("GENERADOR_DATOS")
    if propia:
        return Path(propia)
    if sys.platform == "win32":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "Especifika" / "Generador"
    return Path.home() / ".especifika" / "generador"


def cargar(datos: Path) -> dict:
    """config.json de la carpeta de datos, completado con los valores por
    defecto. Un archivo ilegible no se pisa: se usan los valores por defecto."""
    datos.mkdir(parents=True, exist_ok=True)
    ruta = datos / "config.json"
    if not ruta.exists():
        ruta.write_text(json.dumps(DEFECTO, indent=2), encoding="utf-8")
        return dict(DEFECTO)
    try:
        leido = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("config.json ilegible en %s; se usan los valores por defecto", ruta)
        return dict(DEFECTO)
    if not isinstance(leido, dict):
        return dict(DEFECTO)
    return {**DEFECTO, **{k: v for k, v in leido.items() if k in DEFECTO}}


def bases_heredadas() -> list[Path]:
    """Dónde puede estar la generador.db anterior a G1: junto a este script
    (desarrollo) o junto al ejecutable."""
    candidatas = [Path(__file__).resolve().parent / "generador.db"]
    if getattr(sys, "frozen", False):
        candidatas.insert(0, Path(sys.executable).resolve().parent / "generador.db")
    return candidatas


def preparar_base(datos: Path, heredadas: list[Path] | None = None) -> Path:
    """Ruta de la base en la carpeta de datos. La primera vez COPIA (no mueve)
    la base heredada si existe; nunca pisa una base ya presente."""
    destino = datos / "generador.db"
    if destino.exists():
        return destino
    for origen in (heredadas if heredadas is not None else bases_heredadas()):
        if origen.is_file() and origen.resolve() != destino.resolve():
            datos.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
            logger.info("Base del generador copiada de %s a %s", origen, destino)
            break
    return destino
