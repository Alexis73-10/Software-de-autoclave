# state_machine/cycle_phases/precalentamiento.py
#
# FASE 1 — PRECALENTAMIENTO
#
# Propósito:
#   Introducir vapor a la cámara (VAPOR_CAMARA) hasta alcanzar la
#   temperatura y presión de precalentamiento, y mantenerlas durante
#   el tiempo configurado.
#
# Parámetros del ciclo (sección "precalentamiento"):
#   tiempo_precalentamiento   [min]  → si == 0, la fase se salta
#   temperatura_precalentamiento [°C]
#   presion_precalentamiento  [kPa]
#   timeout_precalentamiento  [min]  → si se supera sin cumplir → FALLO
#
# Lógica:
#   1. tiempo == 0 → COMPLETADO inmediato (skip)
#   2. Activar VAPOR_CAMARA
#   3. Esperar a que temp_camara >= temp_obj  AND  pres_camara >= pres_obj
#   4. Una vez alcanzadas, sostener durante tiempo_precalentamiento
#   5. Si el timeout se supera antes → FALLO

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PrecalentamientoFase(BaseFase):

    name = "PRECALENTAMIENTO"

    def reset(self):
        self._inicializado        = False
        self._timer_timeout_fin   = None   # time.time() al que expira el timeout
        self._timer_sostenimiento = None   # time.time() en que empezó el sostenimiento

    def update(self) -> FaseResult:

        # ── 1. Parámetros del ciclo ───────────────────────────────────────
        tiempo_seg   = (self.cycle.get_param("precalentamiento", "tiempo_precalentamiento")   or 0) * 60
        temp_obj     =  self.cycle.get_param("precalentamiento", "temperatura_precalentamiento") or 0
        pres_obj     =  self.cycle.get_param("precalentamiento", "presion_precalentamiento")    or 0
        timeout_seg  = (self.cycle.get_param("precalentamiento", "timeout_precalentamiento")   or 10) * 60

        # ── 2. Skip si tiempo == 0 ────────────────────────────────────────
        if tiempo_seg == 0:
            logger.info("Precalentamiento: tiempo=0, fase saltada")
            return FaseResult.COMPLETADO

        # ── 3. Inicialización (solo el primer ciclo) ──────────────────────
        if not self._inicializado:
            self._timer_timeout_fin = time.time() + timeout_seg
            self._inicializado = True
            logger.info(
                "Precalentamiento: iniciando | obj %.1f°C / %.1f kPa | sostenimiento %.0fs | timeout %.0fs",
                temp_obj, pres_obj, tiempo_seg, timeout_seg
            )

        # ── 4. Activar salida ─────────────────────────────────────────────
        self.set_do.vapor_camara_on()

        # ── 5. Verificar timeout global ───────────────────────────────────
        if time.time() > self._timer_timeout_fin:
            logger.error(
                "Precalentamiento: TIMEOUT — no se alcanzaron las condiciones en %.0f min",
                timeout_seg / 60
            )
            self.set_do.vapor_camara_off()
            return FaseResult.FALLO

        # ── 6. Leer sensores ──────────────────────────────────────────────
        temp = self._temp_camara()
        pres = self._pres_camara()

        if temp is None or pres is None:
            logger.debug("Precalentamiento: sensores no disponibles, esperando...")
            return FaseResult.EN_CURSO

        # ── 7. Evaluar condiciones ────────────────────────────────────────
        condiciones_ok = (temp >= temp_obj) and (pres >= pres_obj)

        if condiciones_ok:
            # Arrancar o continuar el timer de sostenimiento
            if self._timer_sostenimiento is None:
                self._timer_sostenimiento = time.time()
                logger.info(
                    "Precalentamiento: condiciones alcanzadas (%.1f°C / %.1f kPa) — sosteniendo %.0fs",
                    temp, pres, tiempo_seg
                )

            transcurrido = time.time() - self._timer_sostenimiento

            logger.debug(
                "Precalentamiento: sosteniendo %.1fs / %.1fs | %.1f°C / %.1f kPa",
                transcurrido, tiempo_seg, temp, pres
            )

            if transcurrido >= tiempo_seg:
                logger.info("Precalentamiento: COMPLETADO")
                self.set_do.vapor_camara_off()
                return FaseResult.COMPLETADO

        else:
            # Si las condiciones se pierden, reiniciar el timer de sostenimiento
            if self._timer_sostenimiento is not None:
                logger.debug(
                    "Precalentamiento: condiciones perdidas (%.1f°C / %.1f kPa) — reiniciando sostenimiento",
                    temp, pres
                )
                self._timer_sostenimiento = None

        return FaseResult.EN_CURSO
