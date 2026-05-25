# state_machine/cycle_phases/precalentamiento.py
#
# FASE 1 — PRECALENTAMIENTO
#
# Calienta la chaqueta con vapor hasta alcanzar presion_precalentamiento,
# luego sostiene esa presión durante tiempo_precalentamiento.
# Control bang-bang durante sostenimiento: válvula abre si presión cae,
# cierra si presión está en objetivo; el timer de sostenimiento no se reinicia.
#
# Parámetros del ciclo (sección "precalentamiento"):
#   presion_precalentamiento  [kPa]  → presión objetivo de la chaqueta
#   tiempo_precalentamiento   [min]  → si == 0, fase saltada; duración del sostenimiento
#   timeout_precalentamiento  [min]  → timeout global; si expira antes → FALLO

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PrecalentamientoFase(BaseFase):

    name = "PRECALENTAMIENTO"

    def reset(self):
        self._inicializado        = False
        self._timer_timeout_fin   = None
        self._timer_sostenimiento = None
        self.estado.fase_en_sostenimiento = False

    def _pres_chaqueta(self):
        return self.estado.sensores_pres.get("pres_chaqueta")

    def update(self) -> FaseResult:

        # ── 1. Parámetros ────────────────────────────────────────────────────
        tiempo_seg  = (self.cycle.get_param("precalentamiento", "tiempo_precalentamiento")  or 0) * 60
        presion_obj =  self.cycle.get_param("precalentamiento", "presion_precalentamiento") or 0
        timeout_seg = (self.cycle.get_param("precalentamiento", "timeout_precalentamiento") or 10) * 60

        # ── 2. Skip ──────────────────────────────────────────────────────────
        if tiempo_seg == 0:
            logger.info("Precalentamiento: tiempo=0, fase saltada")
            return FaseResult.COMPLETADO

        # ── 3. Inicialización ────────────────────────────────────────────────
        if not self._inicializado:
            self._timer_timeout_fin = time.time() + timeout_seg
            self._inicializado = True
            logger.info(
                "Precalentamiento: iniciando | obj %.1f kPa | sostenimiento %.0fs | timeout %.0fs",
                presion_obj, tiempo_seg, timeout_seg
            )

        # ── 4. Timeout global ────────────────────────────────────────────────
        if time.time() > self._timer_timeout_fin:
            logger.error(
                "Precalentamiento: TIMEOUT — no se alcanzó %.1f kPa en %.0f min",
                presion_obj, timeout_seg / 60
            )
            self.set_do.vapor_chaqueta_off()
            self.estado.fase_en_sostenimiento = False
            return FaseResult.FALLO

        # ── 5. Leer sensor ───────────────────────────────────────────────────
        pres = self._pres_chaqueta()
        if pres is None:
            logger.debug("Precalentamiento: pres_chaqueta no disponible, esperando...")
            return FaseResult.EN_CURSO

        # ── 6. Aproximación (aún no alcanzó objetivo) ────────────────────────
        if self._timer_sostenimiento is None:
            self.set_do.vapor_chaqueta_on()
            if pres >= presion_obj:
                self._timer_sostenimiento = time.time()
                self.estado.fase_en_sostenimiento = True
                logger.info(
                    "Precalentamiento: %.1f kPa alcanzados — sosteniendo %.0fs",
                    pres, tiempo_seg
                )
            return FaseResult.EN_CURSO

        # ── 7. Sostenimiento (bang-bang, timer no se reinicia) ───────────────
        if pres >= presion_obj:
            self.set_do.vapor_chaqueta_off()
        else:
            self.set_do.vapor_chaqueta_on()

        transcurrido = time.time() - self._timer_sostenimiento
        logger.debug(
            "Precalentamiento: sosteniendo %.1fs / %.1fs | %.1f kPa",
            transcurrido, tiempo_seg, pres
        )

        if transcurrido >= tiempo_seg:
            logger.info("Precalentamiento: COMPLETADO")
            self.set_do.vapor_chaqueta_off()
            self.estado.fase_en_sostenimiento = False
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
