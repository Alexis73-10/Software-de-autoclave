# core/runtime/coherencia_puerta_presion.py
#
# S9 (tanda 9, D9-1.6): coherencia puerta-presión.
#
# Fuera de ciclo, con una puerta detectada ABIERTA, la cámara está a la
# atmósfera: su presión debe quedar en [atm − brecha, atm + brecha]
# (presion_admosferica ± rango_presion_atm, la misma banda de "cámara
# segura"). Si no, durante 3 lecturas seguidas, algo miente: la calibración
# del sensor de presión de cámara, la presión atmosférica de referencia o el
# sensor de puerta. Alarma SEN-10 (ALARMA, bloquea el inicio de ciclo),
# despeje automático con 3 lecturas coherentes seguidas.
#
# - Solo presión: la temperatura con la puerta abierta no se evalúa.
# - En CICLO no actúa (los contadores vuelven a cero).
# - Sin presión de cámara (la cubre SEN-06), sin configuración o sin datos
#   vigentes de la tarjeta: la lectura no cuenta en ningún sentido.
# - Mientras la incoherencia sigue confirmada se reafirma la alarma en cada
#   lectura: el reconocimiento de una FALLA resuelve todas las alarmas y,
#   si la causa sigue, SEN-10 debe volver a verse.

import logging
import math

from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.state_machine.alarms.catalogo import SEN_10
from autoclave.state_machine.machine.enum_global import GlobalState

logger = logging.getLogger(__name__)

_DEBOUNCE_LECTURAS = 3


def _numero(valor) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


class VigilanciaCoherenciaPuertaPresion:

    def __init__(self, alarm_manager, config):
        self.alarm_manager = alarm_manager
        self.config = config
        self._incoherentes = 0
        self._coherentes = 0
        self.activa = False

    def _reiniciar_conteo(self) -> None:
        self._incoherentes = 0
        self._coherentes = 0

    def _evaluar(self, estado) -> bool | None:
        """True incoherente, False coherente, None no evaluable."""
        puertas = getattr(estado, "estado_puertas", None) or {}
        abierta = any(v == DoorState.ABIERTO for v in puertas.values())
        if not abierta:
            return False
        pres = _numero(estado.sensores_pres.get("pres_camara"))
        atm = _numero(self.config.get("presion_admosferica"))
        brecha = _numero(self.config.get("rango_presion_atm"))
        if pres is None or atm is None or brecha is None:
            return None
        return not (atm - brecha <= pres <= atm + brecha)

    def update(self, estado, vigentes: bool = True) -> None:
        if estado.get_machine_state() == GlobalState.CICLO:
            self._reiniciar_conteo()
            return
        if not vigentes:
            return
        incoherente = self._evaluar(estado)
        if incoherente is None:
            return
        if incoherente:
            self._coherentes = 0
            self._incoherentes += 1
            if self._incoherentes >= _DEBOUNCE_LECTURAS:
                if not self.activa:
                    logger.error("Coherencia puerta-presión: puerta abierta con la presión de "
                                 "cámara en %s kPa, fuera de la banda atmosférica",
                                 estado.sensores_pres.get("pres_camara"))
                self.activa = True
                self.alarm_manager.activar(SEN_10)
            return
        self._incoherentes = 0
        self._coherentes += 1
        if self._coherentes >= _DEBOUNCE_LECTURAS and self.activa:
            self.activa = False
            self.alarm_manager.resolver(SEN_10)
            logger.info("Coherencia puerta-presión: SEN-10 despejada (3 lecturas coherentes)")
