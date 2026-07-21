# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva T de la cámara hasta temperatura_calentamiento siguiendo una rampa
# de tasa_calentamiento °C/min. Pausa en un checkpoint al 97% de T_obj para
# verificar vapor saturado (|P_real - P_sat(T)| <= presion_add_calentamiento).

import time
import logging
from autoclave.core.runtime.steam import p_saturacion_kpa
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"

    def reset(self):
        self._inicializado = False
        self._t_inicio = None
        self._t_inicio_fase = None
        self._timer_timeout_fin = None
        self._checkpoints = None
        self._en_checkpoint = False
        self._t_pulso_vapor_chk = None
        self._vapor_chk_abierto = False
        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.estado.fase_en_sostenimiento = False

    def update(self) -> FaseResult:
        t_obj       = self.cycle.get_param("calentamiento", "temperatura_calentamiento")
        tasa_seg    = (self.cycle.get_param("calentamiento", "tasa_calentamiento")) / 60
        timeout_seg = (self.cycle.get_param("calentamiento", "timeout_calentamiento")) * 60
        tolerancia  = self.cycle.get_param("calentamiento", "rango_presion_calentamiento")

        # ── 1. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            temp = self._temp_camara()
            if temp is None:
                return FaseResult.EN_CURSO
            self._t_inicio          = temp
            self._t_inicio_fase     = time.time()
            self._timer_timeout_fin = time.time() + timeout_seg
            self._checkpoints       = [0.97 * t_obj]
            self.set_do.descompresion_lenta_on()
            self._inicializado = True
            logger.info(
                "Calentamiento: iniciando desde %.1f°C → %.1f°C | tasa %.1f°C/min | timeout %.0fs",
                self._t_inicio, t_obj, tasa_seg * 60, timeout_seg,
            )

        # ── 2. Timeout global ────────────────────────────────────────────
        if time.time() > self._timer_timeout_fin:
            logger.error("Calentamiento: TIMEOUT")
            self._apagar_salidas()
            return FaseResult.FALLO

        temp = self._temp_camara()
        pres = self._pres_camara()

        if temp is None:
            return FaseResult.EN_CURSO

        # ── 3. Entrada a checkpoint ───────────────────────────────────────
        if (not self._en_checkpoint and self._checkpoints
                and temp >= self._checkpoints[0]):
            self._en_checkpoint = True
            self.estado.fase_en_sostenimiento = True
            logger.info(
                "Calentamiento: checkpoint %.1f°C — verificando vapor saturado",
                self._checkpoints[0],
            )

        # ── 4. Lógica de checkpoint — bloquea la finalización mientras esté
        #      pendiente, aunque temp ya haya alcanzado t_obj ─────────────
        if self._en_checkpoint:
            if pres is None:
                return FaseResult.EN_CURSO
            if self._verificar_vapor_saturado(temp, pres, tolerancia):
                logger.info("Calentamiento: checkpoint %.1f°C liberado", self._checkpoints[0])
                self._checkpoints.pop(0)
                self._en_checkpoint = False
                self.estado.fase_en_sostenimiento = False
                self._t_pulso_vapor_chk = None
                self._vapor_chk_abierto = False
            else:
                p_sat = p_saturacion_kpa(temp)
                margen = self.cycle.get_param("calentamiento", "margen_techo_calentamiento")
                techo  = self._checkpoints[0] + margen
                if pres > p_sat + tolerancia:
                    self.set_do.vapor_camara_off()
                    self._t_pulso_vapor_chk = None
                    self._vapor_chk_abierto = False
                elif temp < techo:
                    t_on  = self.cycle.get_param("calentamiento", "tiempo_apertura_vapor_checkpoint")
                    t_off = self.cycle.get_param("calentamiento", "tiempo_cierre_vapor_checkpoint")
                    now = time.time()
                    if self._t_pulso_vapor_chk is None:
                        self._t_pulso_vapor_chk = now
                        self._vapor_chk_abierto = True
                        self.set_do.vapor_camara_on()
                    else:
                        elapsed = now - self._t_pulso_vapor_chk
                        if self._vapor_chk_abierto and elapsed >= t_on:
                            self.set_do.vapor_camara_off()
                            self._vapor_chk_abierto = False
                            self._t_pulso_vapor_chk = now
                        elif not self._vapor_chk_abierto and elapsed >= t_off:
                            self.set_do.vapor_camara_on()
                            self._vapor_chk_abierto = True
                            self._t_pulso_vapor_chk = now
                else:
                    self.set_do.vapor_camara_off()
                    self._t_pulso_vapor_chk = None
                    self._vapor_chk_abierto = False
            return FaseResult.EN_CURSO

        # ── 5. Verificar completación ───────────────────────────────────
        if self.cap.has_liquid_sensor:
            temp2 = self._temp_camara_2()
            if temp2 is None:
                return FaseResult.EN_CURSO
            if temp >= t_obj and temp2 >= t_obj:
                logger.info(
                    "Calentamiento: COMPLETADO — camara=%.1f°C liquido=%.1f°C",
                    temp, temp2,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
        else:
            if temp >= t_obj:
                logger.info("Calentamiento: COMPLETADO — %.1f°C alcanzados", temp)
                self._apagar_salidas()
                return FaseResult.COMPLETADO

        # ── 6. Control de rampa ──────────────────────────────────────────

        elapsed     = time.time() - self._t_inicio_fase
        t_permitida = self._t_inicio + tasa_seg * elapsed

        if temp >= t_permitida:
            self.set_do.vapor_camara_off()
        else:
            self.set_do.vapor_camara_on()

        return FaseResult.EN_CURSO
