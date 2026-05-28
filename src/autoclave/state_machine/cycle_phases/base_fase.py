# state_machine/cycle_phases/base_fase.py
#
# Clase base para todas las fases del ciclo + enum de resultados.
# Cada fase hereda de BaseFase e implementa update() y reset().

from __future__ import annotations
from enum import Enum, auto
import logging

from autoclave.core.steam import p_saturacion_kpa

logger = logging.getLogger(__name__)


class FaseResult(Enum):
    EN_CURSO   = auto()   # la fase sigue ejecutándose
    COMPLETADO = auto()   # la fase terminó con éxito → avanzar a la siguiente
    FALLO      = auto()   # la fase falló → ejecutar protocolo de fallo


class BaseFase:
    """
    Contrato que deben cumplir todas las fases del ciclo.

    Dependencias (inyectadas por CicloState):
        estado       → EstadoAutoclave  (lectura de sensores y flags)
        set_do       → SetOutput        (escritura de salidas digitales)
        cycle        → Cycle            (parámetros del ciclo seleccionado)
        config       → ConfigManager    (parámetros globales de la máquina)
        alarm_manager→ AlarmManager     (reporte de alarmas)
    """

    name: str = "BASE"      # nombre legible para logs y UI

    def __init__(self, estado, set_do, cycle, config, alarm_manager):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager

    def reset(self):
        """Reinicia el estado interno de la fase (llamado antes de cada ejecución)."""
        pass

    def update(self) -> FaseResult:
        """
        Lógica principal de la fase. Llamada una vez por ciclo del control loop.
        Debe retornar siempre un FaseResult.
        """
        raise NotImplementedError(f"{self.__class__.__name__} debe implementar update()")

    # ------------------------------------------------------------------
    # Helpers comunes disponibles para todas las fases
    # ------------------------------------------------------------------

    def _temp_camara(self) -> float | None:
        return self.estado.sensores_temp.get("temp_camara")

    def _pres_camara(self) -> float | None:
        return self.estado.sensores_pres.get("pres_camara")

    def _pres_atm(self) -> float:
        return self.config.get("presion_admosferica") or 101.3

    def _rango_atm(self) -> float:
        return self.config.get("rango_presion_atm") or 20.0

    def _verificar_vapor_saturado(self, t_celsius: float, p_real_kpa: float, tolerancia_kpa: float) -> bool:
        """True si |P_real - P_sat(T)| <= tolerancia."""
        return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
