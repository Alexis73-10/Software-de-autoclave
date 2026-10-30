# backend/actividad_ui.py
#
# Última actividad del operador en CUALQUIERA de las pantallas QML (una por
# puerta, que pueden estar en procesos o PCs distintos). Es la referencia común
# del standby simultáneo: cada UI informa sus toques (POST /ui/activity) y lee
# la inactividad compartida en GET /status ("ui_inactividad_s").
#
# Solo estado de presentación: no interviene en el control del equipo.
# Se mide con time.monotonic() (un salto del reloj de pared no altera la
# duración) y en el reloj del backend, el único común a ambas pantallas.

import threading
import time


class ActividadUI:
    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._lock = threading.Lock()
        self._ultima = None   # None = nadie ha tocado ninguna pantalla desde que arrancó el backend

    def registrar(self) -> None:
        with self._lock:
            self._ultima = self._reloj()

    def inactividad_s(self) -> float | None:
        with self._lock:
            if self._ultima is None:
                return None
            return max(0.0, self._reloj() - self._ultima)
