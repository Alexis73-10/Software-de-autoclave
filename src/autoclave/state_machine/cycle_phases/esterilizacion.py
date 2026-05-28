# state_machine/cycle_phases/esterilizacion.py
#
# FASE 6 — ESTERILIZACIÓN
#
# Mantiene vapor saturado durante tiempo_esterilizacion.
# Zonas:
#   Temp normal:  [T_est, T_est + add]
#   Temp error:   T > T_est + add + err_T  → FALLO TEMP_ALTA
#                 T < T_est (sin tolerancia) → FALLO TEMP_BAJA
#   Pres normal:  [P_sat(T), P_sat(T) + rango]
#   Pres error:   P > P_sat(T) + rango + err_P → FALLO PRES_ALTA
#                 P < P_sat(T) (sin tolerancia) → FALLO PRES_BAJA

import time
import logging
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class EsterilizacionFase(BaseFase):

    name = "ESTERILIZACION"

    def reset(self):
        self._inicializado = False
        self._timer_fin    = None
        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.estado.fase_en_sostenimiento = False

    def _fallo(self, alarm_id: str, descripcion: str) -> FaseResult:
        logger.error("Esterilización: FALLO — %s", alarm_id)
        self._apagar_salidas()
        self.alarm_manager.report(Alarm(
            alarm_id=alarm_id,
            alarm_type=AlarmType.FALLA,
            source_state="ESTERILIZACION",
            description=descripcion,
            recoverable=False,
        ))
        return FaseResult.FALLO

    def update(self) -> FaseResult:
        t_est      =  self.cycle.get_param("esterilizacion", "temperatura_esterilizacion")      or 134.0
        tiempo_seg = (self.cycle.get_param("esterilizacion", "tiempo_esterilizacion")            or 3.5) * 60
        temp_add   =  self.cycle.get_param("esterilizacion", "temperatura_add_esterilizacion")  or 2.0
        temp_err   =  self.cycle.get_param("esterilizacion", "temperatura_error_esterilizacion") or 5.0
        pres_rango =  self.cycle.get_param("esterilizacion", "rango_presion_esterilizacion")    or 20.0
        pres_err   =  self.cycle.get_param("esterilizacion", "presion_error_esterilizacion")    or 40.0

        # ── 1. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            self._timer_fin = time.time() + tiempo_seg
            self.set_do.descompresion_lenta_on()
            self.estado.fase_en_sostenimiento = True
            self._inicializado = True
            logger.info(
                "Esterilización: iniciando %.0fs | T=%.1f°C add=%.1f err_T=%.1f rango_P=%.1f err_P=%.1f",
                tiempo_seg, t_est, temp_add, temp_err, pres_rango, pres_err,
            )

        temp = self._temp_camara()
        pres = self._pres_camara()

        # ── 2. Verificar temperatura ─────────────────────────────────────
        if temp < t_est:
            return self._fallo(
                "ESTERILIZACION_TEMP_BAJA",
                f"Temperatura baja: {temp:.1f}°C < {t_est:.1f}°C"
            )
        if temp > t_est + temp_add + temp_err:
            return self._fallo(
                "ESTERILIZACION_TEMP_ALTA",
                f"Temperatura alta: {temp:.1f}°C > {t_est + temp_add + temp_err:.1f}°C"
            )

        # ── 3. Verificar presión ─────────────────────────────────────────
        p_sat = p_saturacion_kpa(temp)
        if pres < p_sat:
            return self._fallo(
                "ESTERILIZACION_PRES_BAJA",
                f"Presión baja: {pres:.1f} kPa < P_sat({temp:.1f}°C)={p_sat:.1f} kPa"
            )
        if pres > p_sat + pres_rango + pres_err:
            return self._fallo(
                "ESTERILIZACION_PRES_ALTA",
                f"Presión alta: {pres:.1f} kPa > {p_sat + pres_rango + pres_err:.1f} kPa"
            )

        # ── 4. Control bang-bang (pulsos cortos) ─────────────────────────
        if temp <= t_est:
            self.set_do.vapor_camara_on()
        else:
            self.set_do.vapor_camara_off()

        # ── 5. Condición de finalización ─────────────────────────────────
        if time.time() >= self._timer_fin:
            logger.info("Esterilización: COMPLETADO — %.0f seg completados", tiempo_seg)
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
