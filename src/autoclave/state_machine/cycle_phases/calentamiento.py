# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Propósito:
#   Elevar la temperatura y presión de la cámara hasta las condiciones
#   de esterilización, introduciendo vapor saturado.
#
# TODO: implementar lógica real cuando se defina el proceso.

import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"

    def reset(self):
        pass

    def update(self) -> FaseResult:
        logger.info("Calentamiento: fase no implementada — saltando")
        return FaseResult.COMPLETADO
