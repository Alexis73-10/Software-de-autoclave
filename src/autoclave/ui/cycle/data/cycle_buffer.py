# ui/cycle/data/cycle_buffer.py
#
# Buffer en memoria para la gráfica en vivo.
# Acumula (t_min, temp, pres) desde el inicio del ciclo.
# También rastrea los cambios de fase para las líneas verticales.
#
# NOTA: Es completamente independiente del CycleLogger (que persiste en SQLite).
#       Si la ventana se cierra y reabre, el buffer se reinicia.

import time
import logging

logger = logging.getLogger(__name__)

# Clave del parámetro de duración para cada fase (usada para el timer X/Y Min)
FASE_DURACION_PARAM: dict[str, str] = {
    "PRECALENTAMIENTO": "tiempo_precalentamiento",
    "PURGA":            "tiempo_purga",
    "PRE_VACIO":        "tiempo_prevacio",
    "CALENTAMIENTO":    "tiempo_calentamiento",
    "ESTABILIZACION":   "tiempo_estabilizacion",
    "ESTERILIZACION":   "tiempo_esterilizacion",
}


class CycleBuffer:
    """
    Buffer circular de lecturas en memoria para la gráfica de ciclo.

    - Tamaño máximo: MAX_POINTS (evita consumo de RAM excesivo)
    - Registra límites de fase para las líneas verticales del gráfico
    - Calcula tiempo transcurrido total y por fase
    """

    MAX_POINTS = 3600   # 1 h a 1 punto/seg — ~115 KB RAM

    def __init__(self):
        self._points: list[tuple]           = []   # (t_min, temp, pres)
        self._phase_boundaries: list[tuple] = []   # (t_min, fase_nombre)
        self._start_time: float | None      = None
        self._fase_actual: str              = ""
        self._fase_inicio_t: float          = 0.0  # t_min de inicio de fase actual
        self._fase_durations: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def reset(self, fase_durations: dict | None = None):
        """
        Reinicia el buffer al inicio de un nuevo ciclo.
        fase_durations: {fase_nombre → minutos totales configurados}
        """
        self._points.clear()
        self._phase_boundaries.clear()
        self._start_time    = time.time()
        self._fase_actual   = ""
        self._fase_inicio_t = 0.0
        self._fase_durations = fase_durations or {}
        logger.debug("CycleBuffer reiniciado | duraciones: %s", self._fase_durations)

    def clear(self):
        """Limpia sin reiniciar el temporizador."""
        self._points.clear()
        self._phase_boundaries.clear()
        self._fase_actual   = ""
        self._fase_inicio_t = 0.0

    # ------------------------------------------------------------------
    # Añadir puntos
    # ------------------------------------------------------------------

    def add(self, temp, pres, fase_nombre: str):
        """
        Añade un punto al buffer.
        Si la fase cambió, registra una nueva línea de fase.
        """
        if self._start_time is None:
            return

        t = self._elapsed_min()

        # Detectar cambio de fase
        if fase_nombre and fase_nombre != self._fase_actual:
            self._phase_boundaries.append((t, fase_nombre))
            self._fase_actual   = fase_nombre
            self._fase_inicio_t = t
            logger.debug("CycleBuffer: nueva fase '%s' en t=%.2f min", fase_nombre, t)

        if temp is not None or pres is not None:
            self._points.append((t, temp, pres))
            # Limitar tamaño eliminando los más antiguos
            if len(self._points) > self.MAX_POINTS:
                self._points = self._points[-self.MAX_POINTS:]

    # ------------------------------------------------------------------
    # Consultas de tiempo
    # ------------------------------------------------------------------

    def get_elapsed_min(self) -> float:
        """Minutos desde el inicio del ciclo."""
        if self._start_time is None:
            return 0.0
        return self._elapsed_min()

    def get_fase_elapsed_min(self) -> float:
        """Minutos transcurridos en la fase actual."""
        return max(0.0, self._elapsed_min() - self._fase_inicio_t)

    def get_fase_total_min(self) -> float:
        """Duración total configurada para la fase actual (0 si no definida)."""
        return self._fase_durations.get(self._fase_actual, 0.0)

    # ------------------------------------------------------------------
    # Propiedades de lectura
    # ------------------------------------------------------------------

    @property
    def points(self) -> list:
        return list(self._points)

    @property
    def phase_boundaries(self) -> list:
        return list(self._phase_boundaries)

    @property
    def fase_actual(self) -> str:
        return self._fase_actual

    @property
    def is_active(self) -> bool:
        return self._start_time is not None

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _elapsed_min(self) -> float:
        return (time.time() - (self._start_time or time.time())) / 60.0
