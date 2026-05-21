# state_machine/cycle_phases/purga.py
#
# FASE 2 — PURGA
#
# Propósito:
#   Desplazar el aire residual de la cámara mediante ciclos de vapor
#   y descompresión, asegurando una atmósfera de vapor saturado puro
#   antes del vacío.
#
# TODO: implementar lógica real cuando se defina el proceso.

import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PurgaFase(BaseFase):

    name = "PURGA"

    def reset(self):
        pass

    def update(self) -> FaseResult:
        logger.info("Purga: fase no implementada — saltando")
        return FaseResult.COMPLETADO
