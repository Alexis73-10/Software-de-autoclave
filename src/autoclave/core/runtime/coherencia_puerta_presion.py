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
# Revisión ★ (SAF-02 / TMG-01): con todas las puertas cerradas la coherencia
# NO es evaluable (no hay referencia atmosférica): no cuenta en ningún
# sentido. Antes contaba como coherente y SEN-10 se despejaba sola al cerrar
# la puerta, sin bloquear nunca un inicio. Ahora solo se despeja con 3
# lecturas coherentes con una puerta ABIERTA.
# Revisión ★ (TMG-03): las 3 lecturas son 3 tramas AI distintas (seq_ai,
# precedente D8-2.9); un tick no evaluable, sin datos vigentes o en pausa
# (modo prueba) pone los contadores a cero.
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
        self._ultima_seq = None

    def reiniciar_conteo(self) -> None:
        self._incoherentes = 0
        self._coherentes = 0
        self._ultima_seq = None

    def _evaluar(self, estado) -> bool | None:
        """True incoherente, False coherente, None no evaluable."""
        puertas = getattr(estado, "estado_puertas", None) or {}
        abierta = any(v == DoorState.ABIERTO for v in puertas.values())
        if not abierta:
            return None          # SAF-02: puerta cerrada = no evaluable
        pres = _numero(estado.sensores_pres.get("pres_camara"))
        atm = _numero(self.config.get("presion_admosferica"))
        brecha = _numero(self.config.get("rango_presion_atm"))
        if pres is None or atm is None or brecha is None:
            return None
        return not (atm - brecha <= pres <= atm + brecha)

    def update(self, estado, vigentes: bool = True, seq_ai: int | None = None) -> None:
        """`seq_ai`: número de la trama AI de esta lectura; la misma trama
        cuenta una sola vez. None (enlace que no lo informa): cada llamada
        cuenta."""
        if estado.get_machine_state() == GlobalState.CICLO:
            self.reiniciar_conteo()
            return
        incoherente = self._evaluar(estado) if vigentes else None
        if incoherente is None:
            # no evaluable (puerta cerrada, sin presión, sin configuración o
            # sin datos vigentes): el conteo vuelve a cero y una SEN-10 ya
            # confirmada se mantiene (y se reafirma si un reconocimiento la
            # resolvió): solo la despejan 3 lecturas coherentes con la puerta
            # abierta (SAF-02)
            self.reiniciar_conteo()
            if self.activa:
                self.alarm_manager.activar(SEN_10)
            return
        if seq_ai is not None:
            if seq_ai == self._ultima_seq:
                return               # misma trama AI: ya contada
            self._ultima_seq = seq_ai
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
