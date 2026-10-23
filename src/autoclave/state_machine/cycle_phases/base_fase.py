# state_machine/cycle_phases/base_fase.py
from __future__ import annotations
from enum import Enum, auto
import logging
import math

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.core.runtime.sensores_ciclo import sensor_principal, sensores_referencia

logger = logging.getLogger(__name__)


class FaseResult(Enum):
    EN_CURSO   = auto()
    COMPLETADO = auto()
    FALLO      = auto()


class BaseFase:
    name: str = "BASE"
    # D8-2.12 (tanda 8, Q1-P2): atributos (time.monotonic()) de las ventanas
    # de estabilidad / sostenimiento de la fase. Durante la tolerancia por DI
    # vencida la fase no corre y esos segundos no cuentan: se corren hacia
    # adelante. Los timeouts NO van aquí (siguen corriendo: límites de
    # seguridad).
    _VENTANAS_ESTABILIDAD: tuple[str, ...] = ()

    def __init__(self, estado, set_do, cycle, config, alarm_manager, cap):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager
        self.cap           = cap

    def reset(self):
        pass

    def pausar_ventanas_estabilidad(self, segundos) -> None:
        """D8-2.12: corre `segundos` las ventanas abiertas de
        _VENTANAS_ESTABILIDAD (inicio o fin, da igual: ambos se suman). Una
        ventana sin abrir (None) no se toca; segundos inválidos, nada."""
        if (isinstance(segundos, bool) or not isinstance(segundos, (int, float))
                or not math.isfinite(segundos) or segundos <= 0):
            return
        for atributo in self._VENTANAS_ESTABILIDAD:
            valor = getattr(self, atributo, None)
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                continue
            setattr(self, atributo, valor + segundos)
            # TMG-02 de la revisión S2b: para el motivo de un timeout que
            # vence con la ventana alargada por estas pausas
            self._ventana_pausada_s = self.ventana_pausada_s() + segundos
            logger.warning("%s: ventana %s en pausa %.1f s (sin datos de la tarjeta)",
                           self.name, atributo, segundos)

    def ventana_pausada_s(self) -> float:
        """Segundos que pausar_ventanas_estabilidad corrió las ventanas desde
        el último reset de la fase (las fases lo ponen en 0 en reset())."""
        valor = getattr(self, "_ventana_pausada_s", 0.0)
        return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0.0

    def update(self) -> FaseResult:
        raise NotImplementedError(f"{self.__class__.__name__} debe implementar update()")

    def _temp_camara(self) -> float | None:
        return self.estado.sensores_temp.get("temp_camara")

    def _temp_principal(self) -> float | None:
        """Sensor Principal del programa con el que corre la fase (tanda §1.1):
        control de vapor, fallas, saturación, enfriamiento."""
        return self.estado.sensores_temp.get(sensor_principal(self.cycle))

    def _temps_referencia(self) -> dict:
        """{sensor: lectura} de las Referencias del programa (puede haber None)."""
        return {s: self.estado.sensores_temp.get(s) for s in sensores_referencia(self.cycle)}

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
