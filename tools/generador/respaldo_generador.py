# tools/generador/respaldo_generador.py
#
# Respaldo diario de generador.db (G1, tanda 2). Usa la API de respaldo de
# SQLite (nunca copia el archivo abierto: con WAL, la copia del archivo podría
# quedar sin las últimas escrituras). Cada respaldo se verifica con
# PRAGMA integrity_check; uno que no pasa se borra y queda en el log. Retención
# por días (30 por defecto) según la fecha del nombre del archivo.

import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

PREFIJO = "generador_"
_FORMATO = "%Y%m%d_%H%M%S"
INTERVALO_S = 24 * 3600


def respaldar(base: Path, carpeta: Path, ahora: datetime | None = None) -> Path | None:
    """Respalda `base` en `carpeta`; devuelve la ruta, o None si falló."""
    ahora = ahora or datetime.now()
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{PREFIJO}{ahora.strftime(_FORMATO)}.db"
    try:
        origen = sqlite3.connect(base)
        copia = sqlite3.connect(destino)
        with copia:
            origen.backup(copia)
        origen.close()
        estado = copia.execute("PRAGMA integrity_check").fetchone()[0]
        copia.close()
    except sqlite3.Error:
        logger.exception("Respaldo del generador fallido: %s", destino)
        destino.unlink(missing_ok=True)
        return None
    if estado != "ok":
        logger.error("Respaldo del generador corrupto (%s): %s; se descarta", estado, destino)
        destino.unlink(missing_ok=True)
        return None
    logger.info("Respaldo del generador: %s", destino)
    return destino


def podar(carpeta: Path, dias: int, ahora: datetime | None = None) -> list[Path]:
    """Borra los respaldos con más de `dias` días. Solo toca archivos con el
    nombre de este módulo."""
    ahora = ahora or datetime.now()
    borrados = []
    for ruta in carpeta.glob(f"{PREFIJO}*.db"):
        try:
            fecha = datetime.strptime(ruta.stem[len(PREFIJO):], _FORMATO)
        except ValueError:
            continue
        if ahora - fecha > timedelta(days=dias):
            ruta.unlink(missing_ok=True)
            borrados.append(ruta)
    return borrados


def iniciar_periodico(base: Path, carpeta: Path, dias: int,
                      intervalo_s: float = INTERVALO_S) -> threading.Event:
    """Respalda al arrancar y cada `intervalo_s`. Devuelve el Event que lo detiene."""
    detener = threading.Event()

    def ciclo():
        while True:
            respaldar(base, carpeta)
            podar(carpeta, dias)
            if detener.wait(intervalo_s):
                return

    threading.Thread(target=ciclo, name="RespaldoGenerador", daemon=True).start()
    return detener
