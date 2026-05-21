# state_machine/cycle_phases/estabilizacion.py
#
# FASE 5 — ESTABILIZACIÓN
#
# Propósito:
#   Verificar que las condiciones de temperatura y presión de
#   esterilización se mantienen estables durante el tiempo configurado
#   antes de iniciar la cuenta de esterilización oficial.
#
# TODO: implementar lógica real cuando se defina el proceso.

import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class EstabilizacionFase(BaseFase):

    name = "ESTABILIZACION"

    def reset(self):
        pass

    def update(self) -> FaseResult:
        logger.info("Estabilización: fase no implementada — saltando")
        return FaseResult.COMPLETADO
