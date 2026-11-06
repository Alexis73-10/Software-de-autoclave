# core/runtime/marca_estado_seguro.py
#
# Tanda 28 (A9-R1, decisión de Cristian del 6-nov): marca persistente de
# "protocolo de fin de ciclo en curso", independiente de la base y del
# contador de ciclos.
#
# El registro del ciclo (CycleLogger) cierra el ciclo y borra la marca del
# contador apenas la fase sale de "en curso", antes de que el protocolo de
# fallo y el de estado seguro terminen. Sin esta marca, un corte de energía o
# un reinicio del backend a mitad del protocolo se tomaba como un encendido
# normal (sin protocolo). Ver hubo_ciclo_interrumpido (backend/context.py) y
# ControlLoop._sincronizar_marca_estado_seguro.
#
# - Archivo `data/estado_seguro_en_curso.json` = {"desde": ISO, "origen": ...}:
#   su sola presencia es la marca. Escritura atómica (temporal + fsync +
#   os.replace, con los reintentos de contador_ciclos).
# - Falla cerrada: un archivo presente pero ilegible o corrupto cuenta como
#   marca presente; solo "no existe" es ausencia.

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

NOMBRE_ARCHIVO = "estado_seguro_en_curso.json"
# Mismo criterio que contador_ciclos (TMG-01 de B9a): en Windows os.replace y
# os.unlink fallan con PermissionError si otro proceso tiene el archivo abierto
REINTENTOS = 3
ESPERA_REINTENTO_S = 0.02


class MarcaEstadoSeguro:

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self._lock = threading.Lock()

    def presente(self) -> bool:
        """True si la marca existe. Falla cerrada: ilegible, corrupta o
        cualquier error al consultarla = True."""
        with self._lock:
            try:
                datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return False
            except Exception:
                logger.exception("MarcaEstadoSeguro: %s ilegible; se toma como presente "
                                 "(falla cerrada)", self.ruta)
                return True
            if not isinstance(datos, dict):
                logger.error("MarcaEstadoSeguro: %s no es un objeto; se toma como presente",
                             self.ruta)
            return True

    def marcar(self, detalle: dict | None = None) -> None:
        """Escribe la marca (atómica). Lanza la excepción si no pudo: quien
        llama reintenta."""
        datos = dict(detalle or {})
        with self._lock:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.ruta.with_suffix(self.ruta.suffix + ".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(datos, f, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                for intento in range(REINTENTOS):
                    try:
                        os.replace(tmp, self.ruta)
                        break
                    except PermissionError:
                        if intento == REINTENTOS - 1:
                            raise
                        time.sleep(ESPERA_REINTENTO_S)
            finally:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)

    def borrar(self) -> None:
        """Borra la marca (sin marca, nada). Lanza la excepción si no pudo:
        quien llama reintenta."""
        with self._lock:
            for intento in range(REINTENTOS):
                try:
                    self.ruta.unlink(missing_ok=True)
                    return
                except PermissionError:
                    if intento == REINTENTOS - 1:
                        raise
                    time.sleep(ESPERA_REINTENTO_S)
