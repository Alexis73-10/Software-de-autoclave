# state_machine/cycle_phases/base_fase.py
from __future__ import annotations
from enum import Enum, auto
import logging

from autoclave.core.runtime.steam import p_saturacion_kpa

logger = logging.getLogger(__name__)


class FaseResult(Enum):
    EN_CURSO   = auto()
    COMPLETADO = auto()
    FALLO      = auto()


class BaseFase:
    name: str = "BASE"

    def __init__(self, estado, set_do, cycle, config, alarm_manager, cap):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager
        self.cap           = cap

    def reset(self):
        pass

    def update(self) -> FaseResult:
        raise NotImplementedError(f"{self.__class__.__name__} debe implementar update()")

    def _temp_camara(self) -> float | None:
        return self.estado.sensores_temp.get("temp_camara")

    def _temp_camara_2(self) -> float | None:
        return self.estado.sensores_temp.get("temp_2_camara")

    def _pres_camara(self) -> float | None:
        return self.estado.sensores_pres.get("pres_camara")

    def _pres_atm(self) -> float:
        return self.config.get("presion_admosferica") or 101.3

    def _rango_atm(self) -> float:
        return self.config.get("rango_presion_atm") or 20.0

    def _verificar_vapor_saturado(self, t_celsius: float, p_real_kpa: float, tolerancia_kpa: float) -> bool:
        return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
