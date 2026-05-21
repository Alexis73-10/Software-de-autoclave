# state_machine/cycle_phases/esterilizacion.py
#
# FASE 6 — ESTERILIZACIÓN
#
# Propósito:
#   Mantener las condiciones de temperatura y presión de esterilización
#   durante el tiempo exacto definido en el ciclo (tiempo_esterilizacion).
#   Es la fase crítica del proceso — cualquier desviación reinicia o
#   detiene el temporizador según la configuración.
#
# TODO: implementar lógica real cuando se defina el proceso.

import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class EsterilizacionFase(BaseFase):

    name = "ESTERILIZACION"

    def reset(self):
        pass

    def update(self) -> FaseResult:
        logger.info("Esterilización: fase no implementada — saltando")
        return FaseResult.COMPLETADO
