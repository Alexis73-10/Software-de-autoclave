# state_machine/cycle_phases/aislamiento_camara.py
#
# F3 (tanda 16, VCH §4.4 / §4.5): aislamiento de cámara por sobrepresión
# (VCH-AIS), solo en modo chaqueta, compartido por CALENTAMIENTO y
# ESTERILIZACION. Una instancia por ciclo en estado.aislamiento_camara (la
# crea CicloState.reset()), así el historial de la ventana móvil cubre las
# dos fases.
#
#   Entrada: P_camara >= techo de la fase (inmediata, sin confirmación).
#   Salida:  P_camara <= techo - histeresis_cierre_camara sostenida
#            SALIDA_SOSTENIDA_S (3 s continuos, monotónico). Una lectura por
#            encima reinicia el conteo.
#   Mientras dura, la fase fuerza vapor_camara OFF y vapor_chaqueta OFF.
#
# El componente solo lleva el estado y el historial; las fases deciden las
# salidas y los FALLO (CIC-15 sostenido, CIC-16 recurrente). El reloj lo pasa
# el llamador (time.monotonic()).
# Sin lectura de presión (None / no finita) no cambia de estado y reinicia el
# conteo de salida: no se reabre la cámara a ciegas.

import math
from collections import deque

SALIDA_SOSTENIDA_S = 3.0


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class AislamientoCamara:

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.aislado = False
        self._desde = None            # inicio del aislamiento en curso
        self._bajo_desde = None       # inicio del tramo bajo el umbral de salida
        self._entradas: deque = deque()   # instantes de entrada (historial)

    def actualizar(self, pres, techo: float, histeresis: float, now: float) -> bool:
        """Evalúa entrada/salida y devuelve si la cámara queda aislada."""
        if not _numero(pres):
            self._bajo_desde = None
            return self.aislado
        if not self.aislado:
            if pres >= techo:
                self.aislado = True
                self._desde = now
                self._bajo_desde = None
                self._entradas.append(now)
            return self.aislado
        if pres <= techo - histeresis:
            if self._bajo_desde is None:
                self._bajo_desde = now
            elif now - self._bajo_desde >= SALIDA_SOSTENIDA_S:
                self.aislado = False
                self._desde = None
                self._bajo_desde = None
        else:
            self._bajo_desde = None
        return self.aislado

    def duracion(self, now: float) -> float:
        """Segundos del aislamiento en curso (0 si no hay)."""
        if not self.aislado or self._desde is None:
            return 0.0
        return max(0.0, now - self._desde)

    def sostenido(self, now: float, timeout_s: float) -> bool:
        """VCH §4.5: el aislamiento en curso superó `timeout_s`."""
        return self.aislado and self.duracion(now) > timeout_s

    def entradas_en_ventana(self, now: float, ventana_s: float) -> int:
        """Aislamientos iniciados en (now - ventana_s, now]."""
        while self._entradas and self._entradas[0] <= now - ventana_s:
            self._entradas.popleft()
        return len(self._entradas)

    def recurrente(self, now: float, maximo: int, ventana_s: float) -> bool:
        """VCH §4.5: `maximo` aislamientos o más dentro de la ventana móvil."""
        return self.entradas_en_ventana(now, ventana_s) >= maximo
