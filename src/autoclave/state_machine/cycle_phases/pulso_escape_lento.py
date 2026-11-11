"""Pulsos del escape lento en DESCOMPRESION (ajuste 10-nov).

Mantener `descompresion_lenta` abierta de forma continua carga demasiado el
compresor (que ya alimenta las solenoides y la cámara y sostiene la fuga). La
válvula se pulsa con el mismo temporizador de dos estados de calentamiento y
esterilización: abierta `escape_lento_on` s, cerrada `escape_lento_off` s, y
repite. Parámetros de `descompresion` (seg, enteros):

- off <= 0 -> abierta continua (comportamiento anterior; es el defecto 1/0).
- on  <= 0 -> el catálogo exige on >= 1; si llegara 0 se trata como el defecto
  (continua), porque cerrada siempre impediría despresurizar.

El componente solo decide el estado de la válvula cuando la fase QUIERE la
lenta abierta; si la fase la quiere cerrada, la cierra y reinicia el ciclo
(el siguiente pedido empieza abierto).
"""
from __future__ import annotations

import math
import time
from typing import Callable

ESCAPE_LENTO_ON_DEFECTO = 1
ESCAPE_LENTO_OFF_DEFECTO = 0


def _segundos(valor, defecto: float) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return float(defecto)
    v = float(valor)
    if not math.isfinite(v) or v < 0:
        return float(defecto)
    return v


class PulsoEscapeLento:
    def __init__(self, ahora: Callable[[], float] = time.monotonic):
        self._ahora = ahora
        self._t_ref: float | None = None
        self._abierta = False

    def reiniciar(self) -> None:
        self._t_ref = None
        self._abierta = False

    def decidir(self, quiere_abierta: bool, t_on, t_off) -> bool:
        """True = la válvula debe estar abierta en este tick."""
        if not quiere_abierta:
            self.reiniciar()
            return False
        t_on = _segundos(t_on, ESCAPE_LENTO_ON_DEFECTO)
        t_off = _segundos(t_off, ESCAPE_LENTO_OFF_DEFECTO)
        if t_off <= 0 or t_on <= 0:
            self._t_ref = None
            self._abierta = True
            return True
        now = self._ahora()
        if self._t_ref is None:
            self._t_ref = now
            self._abierta = True
            return True
        transcurrido = now - self._t_ref
        if self._abierta and transcurrido >= t_on:
            self._abierta = False
            self._t_ref = now
        elif not self._abierta and transcurrido >= t_off:
            self._abierta = True
            self._t_ref = now
        return self._abierta
