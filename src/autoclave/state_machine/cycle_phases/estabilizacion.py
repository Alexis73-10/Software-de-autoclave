# state_machine/cycle_phases/estabilizacion.py
#
# FASE 5 — ESTABILIZACIÓN
#
# Mantiene temperatura_calentamiento durante tiempo_estable_preesterilizacion.
# Si tiempo == 0, la fase se salta. Timer principal corre sin parar;
# si las condiciones salen del rango, un timer de recuperación separado
# dispara FALLO si no se restauran a tiempo.

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class EstabilizacionFase(BaseFase):

    name = "ESTABILIZACION"

    def reset(self):
        self._inicializado        = False
        self._timer_principal_fin = None
        self._timer_recuperacion  = None
        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.estado.fase_en_sostenimiento = False

    def update(self) -> FaseResult:
        tiempo_seg      = (self.cycle.get_param("calentamiento", "tiempo_estable_preesterilizacion") or 0) * 60
        t_obj           =  self.cycle.get_param("calentamiento", "temperatura_calentamiento")         or 134.0
        rango_temp      =  self.cycle.get_param("calentamiento", "rango_temp_estabilizacion")         or 1.0
        rango_pres      =  self.cycle.get_param("calentamiento", "presion_add_calentamiento")         or 9.0
        timeout_rec_seg = (self.cycle.get_param("calentamiento", "timeout_recuperacion_estabilizacion") or 5) * 60

        # ── 1. Skip ──────────────────────────────────────────────────────
        if tiempo_seg == 0:
            return FaseResult.COMPLETADO

        # ── 2. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            self._timer_principal_fin = time.time() + tiempo_seg
            self.set_do.descompresion_lenta_on()
            self._inicializado = True
            logger.info("Estabilización: iniciando %.0fs | T_obj=%.1f°C", tiempo_seg, t_obj)

        temp = self._temp_camara()
        pres = self._pres_camara()

        # ── 3. Verificar condiciones ─────────────────────────────────────
        dentro_rango = (
            abs(temp - t_obj) <= rango_temp
            and self._verificar_vapor_saturado(temp, pres, rango_pres)
        )

        # ── 4. Recuperación ──────────────────────────────────────────────
        if not dentro_rango:
            if self._timer_recuperacion is None:
                self._timer_recuperacion = time.time() + timeout_rec_seg
                logger.warning("Estabilización: condiciones fuera de rango — recuperando")
            if time.time() > self._timer_recuperacion:
                logger.error("Estabilización: FALLO — no se recuperaron las condiciones")
                self._apagar_salidas()
                return FaseResult.FALLO
        else:
            if self._timer_recuperacion is not None:
                logger.info("Estabilización: condiciones recuperadas")
            self._timer_recuperacion = None

        # ── 5. Control bang-bang ─────────────────────────────────────────
        if temp < t_obj:
            self.set_do.vapor_camara_on()
        else:
            self.set_do.vapor_camara_off()

        # ── 6. Condición de finalización ─────────────────────────────────
        if time.time() >= self._timer_principal_fin:
            logger.info("Estabilización: COMPLETADO")
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
