# state_machine/cycle_phases/purga.py
#
# FASE 2 — PURGA
#
# Abre vapor_camara y descompresion_rapida simultáneamente durante
# tiempo_purga para crear un flujo de vapor que desplaza el aire
# seco de la cámara antes del prevacío.
#
# Parámetros del ciclo (sección "purga"):
#   tiempo_purga  [min]  → si == 0, fase saltada; duración del flujo
#   presion_purga [kPa]  → presente en JSON, no usado en esta fase

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PurgaFase(BaseFase):

    name = "PURGA"

    def reset(self):
        self._inicializado = False
        self._timer_fin    = None

    def update(self) -> FaseResult:

        # ── 1. Parámetros ────────────────────────────────────────────────────
        tiempo_seg = (self.cycle.get_param("purga", "tiempo_purga") or 0) * 60

        # ── 2. Skip ──────────────────────────────────────────────────────────
        if tiempo_seg == 0:
            logger.info("Purga: tiempo=0, fase saltada")
            return FaseResult.COMPLETADO

        # ── 3. Inicialización (solo en el primer update) ─────────────────────
        if not self._inicializado:
            self.set_do.vapor_camara_on()
            self.set_do.descompresion_rapida_on()
            self._timer_fin = time.time() + tiempo_seg
            self._inicializado = True
            logger.info("Purga: iniciando | %.0f s", tiempo_seg)

        # ── 4. Verificar tiempo ───────────────────────────────────────────────
        if time.time() >= self._timer_fin:
            logger.info("Purga: COMPLETADO")
            self.set_do.vapor_camara_off()
            self.set_do.descompresion_rapida_off()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
