# state_machine/cycle_phases/prevacio.py
#
# FASE 3 — PRE-VACÍO
#
# Propósito:
#   Extraer el aire residual de la cámara mediante la bomba de vacío
#   hasta alcanzar el nivel de vacío configurado, mejorando la
#   penetración del vapor en la carga.
#
# TODO: implementar lógica real cuando se defina el proceso.

import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PrevacioFase(BaseFase):

    name = "PRE_VACIO"

    def reset(self):
        pass

    def update(self) -> FaseResult:
        logger.info("Pre-vacío: fase no implementada — saltando")
        return FaseResult.COMPLETADO
