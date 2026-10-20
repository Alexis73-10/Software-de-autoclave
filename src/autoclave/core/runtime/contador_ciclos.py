# core/runtime/contador_ciclos.py
#
# Contador consecutivo persistente de ciclos (planeacion_arranque_y_modo_sin_bd
# §7.5, aprobado; tanda 2026-10-14 E4). Fuente única del número de ciclo con y
# sin base de datos: no se repite si la base se borra o se reemplaza (BD-04).
#
# - Archivo `data/ciclo_contador.json` = {"ultimo": N}, escritura atómica
#   (temporal + fsync + os.replace).
# - Al arrancar se sincroniza con max(contador, MAX(numero) de la base).
# - Se incrementa al iniciar cada ciclo.

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# TMG-01 (revisión de B9a): en Windows os.replace falla con PermissionError si
# otro proceso (antivirus, indexador, OneDrive) tiene abierto el destino un
# instante. Se reintenta pocas veces con una espera corta (corre en el tick).
REINTENTOS_REEMPLAZO = 3
ESPERA_REINTENTO_S = 0.02


class ContadorCiclos:

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self._lock = threading.Lock()

    def _datos(self) -> dict:
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                raise ValueError("no es un objeto")
            return datos
        except FileNotFoundError:
            return {}
        except Exception:
            # Un contador ilegible no puede bajar la numeración: se registra y
            # la sincronización con la base decide el mínimo.
            logger.exception("ContadorCiclos: %s ilegible", self.ruta)
            return {}

    def _leer(self) -> int:
        valor = self._datos().get("ultimo", 0)
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            logger.error("ContadorCiclos: valor inválido %r; se toma 0", valor)
            return 0
        return valor

    def _escribir(self, valor: int, en_curso="__igual__") -> None:
        datos = {"ultimo": valor}
        previo = self._datos().get("en_curso") if en_curso == "__igual__" else en_curso
        if previo:
            datos["en_curso"] = previo
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_suffix(self.ruta.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            for intento in range(REINTENTOS_REEMPLAZO):
                try:
                    os.replace(tmp, self.ruta)
                    break
                except PermissionError:
                    if intento == REINTENTOS_REEMPLAZO - 1:
                        raise
                    time.sleep(ESPERA_REINTENTO_S)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @property
    def ultimo(self) -> int:
        with self._lock:
            return self._leer()

    def sincronizar(self, maximo_bd: int | None) -> int:
        """Al arrancar: contador = max(contador, MAX(numero) de la base)."""
        with self._lock:
            actual = self._leer()
            nuevo = max(actual, int(maximo_bd or 0))
            if nuevo != actual:
                self._escribir(nuevo)
                logger.info("ContadorCiclos: sincronizado %d → %d", actual, nuevo)
            return nuevo

    # ── Marca de ciclo en curso (TMG-03 de T6) ────────────────────────────
    # Sobrevive a un corte de energía aunque la base no esté disponible: al
    # arrancar, una marca presente = ciclo interrumpido, con su programa.

    def marcar_en_curso(self, numero: int, programa: dict | None) -> None:
        with self._lock:
            self._escribir(self._leer(), en_curso={"numero": numero, "programa": programa})

    def limpiar_en_curso(self, solo_numero: int | None = None) -> None:
        """Borra la marca. Con `solo_numero`, solo si la marca es de ese ciclo:
        una limpieza diferida (S3d) no debe borrar la marca de un ciclo que ya
        inició después."""
        with self._lock:
            marca = self._datos().get("en_curso")
            if marca and (solo_numero is None or (isinstance(marca, dict)
                                                  and marca.get("numero") == solo_numero)):
                self._escribir(self._leer(), en_curso=None)

    def en_curso(self) -> dict | None:
        with self._lock:
            marca = self._datos().get("en_curso")
        return marca if isinstance(marca, dict) else None

    def siguiente(self, maximo_bd: int | None = None) -> int:
        """Reserva y devuelve el número del ciclo que inicia. `maximo_bd`
        protege contra un contador atrasado respecto a la base."""
        with self._lock:
            numero = max(self._leer(), int(maximo_bd or 0)) + 1
            self._escribir(numero)
            return numero
