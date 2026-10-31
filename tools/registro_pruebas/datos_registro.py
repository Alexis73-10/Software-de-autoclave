# tools/registro_pruebas/datos_registro.py
#
# Carpeta de datos y configuración de la app de registro de pruebas de banco
# (F1, tanda 3). Los datos NUNCA van dentro del ejecutable ni en git: viven en
# una carpeta persistente. Por defecto C:\ProgramData\Especifika\RegistroPruebas\
# (en otros sistemas ~/.especifika/registro_pruebas); REGISTRO_DATOS la cambia.
#
#   registro.db        base (SQLite WAL)
#   fotos\             fotos de evidencia (un archivo por foto, con el ID de prueba)
#   firmas\            firmas manuscritas en pantalla (PNG pequeño)
#   exportaciones\     JSON / CSV / HTML por registro
#   respaldos\         respaldos de registro.db (API de respaldo de SQLite)
#   config.json        valores de abajo (se crea con los de por defecto)

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFECTO = {
    "host": "0.0.0.0",            # solo red local: el firewall limita a la subred (abrir_firewall.ps1)
    "puerto": 8090,
    "sesion_horas": 10,           # la campaña se hace en una jornada (8-12 h)
    "intentos_max": 5,
    "bloqueo_min": 15,
    "retencion_respaldos": 30,    # días
    "foto_max_mb": 8,
    "firma_max_kb": 200,
    "iteraciones_hash": 0,        # 0 = las del software (solo se cambia en pruebas)
}
SUBCARPETAS = ("fotos", "firmas", "exportaciones", "respaldos")


def carpeta_datos() -> Path:
    propia = os.environ.get("REGISTRO_DATOS")
    if propia:
        return Path(propia)
    if sys.platform == "win32":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "Especifika" / "RegistroPruebas"
    return Path.home() / ".especifika" / "registro_pruebas"


def preparar(datos: Path) -> dict:
    """Crea la carpeta y sus subcarpetas y devuelve la configuración
    (config.json completado con los valores por defecto; un archivo ilegible
    no se pisa: se usan los valores por defecto)."""
    datos.mkdir(parents=True, exist_ok=True)
    for nombre in SUBCARPETAS:
        (datos / nombre).mkdir(exist_ok=True)
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
