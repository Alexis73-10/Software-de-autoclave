# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva la cámara desde la salida de PRE_VACIO hasta el punto de vapor
# saturado del setpoint de esterilización (temperatura_calentamiento +
# presion_add_calentamiento) y sostiene esa condición durante
# tiempo_estable_preesterilizacion segundos. Tres tramos internos, sin
# retroceso entre ellos:
#   APROXIMACION              vapor_camara ON continuo
#   PWM_ACTIVO                entra al alcanzar |P - P_sat(T)| <= rango_calentamiento;
#                              vapor_camara en PWM (factor_calentamiento / intervalo_segmentos_calor)
#   ESTABLE_PREESTERILIZACION sostenimiento; timer no se reinicia si la
#                              condición sale momentáneamente de rango (riesgo
#                              aceptado, a diferencia de EstabilizacionFase)
#
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase (no sincronizados con los
# tramos anteriores). tasa_calentamiento/tasa_presion vigilan la pendiente
# con debounce de 3 lecturas y pueden producir FALLO desde cualquier tramo.

import time
import logging
from autoclave.core.runtime.steam import p_saturacion_kpa
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_DEBOUNCE_LECTURAS = 3


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"

    def reset(self):
        self._inicializado = False
        self._timer_timeout_fin = None
        self._en_pwm = False
        self._timer_estable_inicio = None

        # Debounce de pendiente (tasa_calentamiento / tasa_presion)
        self._temp_anterior = None
        self._pres_anterior = None
        self._t_tick_anterior = None
        self._contador_exceso_temp = 0
        self._contador_exceso_pres = 0

        # Temporizadores de dos estados (vapor PWM, escape lento, escape rápido)
        self._t_pulso_pwm = None
        self._pwm_abierto = False
        self._t_pulso_lento = None
        self._lento_abierto = False
        self._t_pulso_rapido = None
        self._rapido_abierto = False

        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_rapida_off()
        self.estado.fase_en_sostenimiento = False

    def _fallo(self, mensaje: str) -> FaseResult:
        logger.error("Calentamiento: FALLO — %s", mensaje)
        self._apagar_salidas()
        self.estado.motivo_fallo = mensaje
        return FaseResult.FALLO

    def _tick_dos_estados(self, timer_attr, abierto_attr, t_on, t_off, on_fn, off_fn, now):
        """Temporizador de dos estados: abierto t_on seg, cerrado t_off seg, repite.
        t_off<=0 -> permanece abierto. t_on<=0 -> permanece cerrado."""
        if t_off <= 0:
            setattr(self, timer_attr, None)
            setattr(self, abierto_attr, True)
            on_fn()
            return
        if t_on <= 0:
            setattr(self, timer_attr, None)
            setattr(self, abierto_attr, False)
            off_fn()
            return

        timer = getattr(self, timer_attr)
        if timer is None:
            setattr(self, timer_attr, now)
            setattr(self, abierto_attr, True)
            on_fn()
            return

        abierto = getattr(self, abierto_attr)
        elapsed = now - timer
        if abierto and elapsed >= t_on:
            off_fn()
            setattr(self, abierto_attr, False)
            setattr(self, timer_attr, now)
        elif not abierto and elapsed >= t_off:
            on_fn()
            setattr(self, abierto_attr, True)
            setattr(self, timer_attr, now)

    def update(self) -> FaseResult:
        t_obj       =  self.cycle.get_param("calentamiento", "temperatura_calentamiento")        or 134.0
        p_add       =  self.cycle.get_param("calentamiento", "presion_add_calentamiento")        or 0.0
        timeout_seg = (self.cycle.get_param("calentamiento", "timeout_calentamiento")             or 60) * 60
        factor_pct  =  self.cycle.get_param("calentamiento", "factor_calentamiento")              or 0.0
        rango_cal   =  self.cycle.get_param("calentamiento", "rango_calentamiento")               or 0.0
        tasa_t_max  =  self.cycle.get_param("calentamiento", "tasa_calentamiento")                or 0.0
        tasa_p_max  =  self.cycle.get_param("calentamiento", "tasa_presion")                      or 0.0
        tiempo_est  =  self.cycle.get_param("calentamiento", "tiempo_estable_preesterilizacion")  or 0
        intervalo   =  self.cycle.get_param("calentamiento", "intervalo_segmentos_calor")         or 0
        lento_on    =  self.cycle.get_param("calentamiento", "escape_lento_on")                   or 0
        lento_off   =  self.cycle.get_param("calentamiento", "escape_lento_off")                  or 0
        rapido_on   =  self.cycle.get_param("calentamiento", "escape_rapido_on")                  or 0
        rapido_off  =  self.cycle.get_param("calentamiento", "escape_rapido_off")                 or 0

        p_obj = p_saturacion_kpa(t_obj) + p_add

        # ── 1. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            temp_inicial = self._temp_camara()
            if temp_inicial is None:
                return FaseResult.EN_CURSO
            self._timer_timeout_fin = time.time() + timeout_seg
            self._inicializado = True
            logger.info(
                "Calentamiento: iniciando desde %.1f°C | objetivo %.1f°C / %.1f kPa | timeout %.0fs",
                temp_inicial, t_obj, p_obj, timeout_seg,
            )

        # ── 2. Timeout global ────────────────────────────────────────────
        if time.time() > self._timer_timeout_fin:
            return self._fallo(f"Timeout de calentamiento: no se alcanzó el objetivo en {timeout_seg / 60:.0f} min")

        temp = self._temp_camara()
        pres = self._pres_camara()
        if temp is None or pres is None:
            return FaseResult.EN_CURSO

        now = time.time()

        # ── 3. Debounce de pendiente ──────────────────────────────────────
        # Nota: la rampa de temperatura se vigila en valor absoluto (subida O
        # caída abrupta son ambas anómalas, ver FMEA sección 8); la de presión
        # solo en sentido de subida (sobrepresión por PWM mal calibrado).
        if self._t_tick_anterior is not None:
            dt_min = (now - self._t_tick_anterior) / 60
            if dt_min > 0:
                tasa_t = (temp - self._temp_anterior) / dt_min
                if tasa_t_max > 0 and abs(tasa_t) > tasa_t_max:
                    self._contador_exceso_temp += 1
                else:
                    self._contador_exceso_temp = 0
                if self._contador_exceso_temp >= _DEBOUNCE_LECTURAS:
                    return self._fallo(
                        f"Pendiente de temperatura excesiva: {tasa_t:.1f}°C/min (máx {tasa_t_max:.1f}°C/min)"
                    )

                tasa_p = (pres - self._pres_anterior) / dt_min
                if tasa_p_max > 0 and tasa_p > tasa_p_max:
                    self._contador_exceso_pres += 1
                else:
                    self._contador_exceso_pres = 0
                if self._contador_exceso_pres >= _DEBOUNCE_LECTURAS:
                    return self._fallo(
                        f"Pendiente de presión excesiva: {tasa_p:.1f} kPa/min (máx {tasa_p_max:.1f} kPa/min)"
                    )

        self._temp_anterior = temp
        self._pres_anterior = pres
        self._t_tick_anterior = now

        # ── 4. Entrada a PWM (unidireccional) ─────────────────────────────
        if not self._en_pwm and abs(pres - p_saturacion_kpa(temp)) <= rango_cal:
            self._en_pwm = True
            logger.info("Calentamiento: banda alcanzada (%.1f kPa) — entra a PWM_ACTIVO", rango_cal)

        # ── 5. Control de vapor_camara ─────────────────────────────────────
        if not self._en_pwm:
            self.set_do.vapor_camara_on()
        else:
            t_off_pwm = intervalo * (factor_pct / 100.0)
            t_on_pwm  = intervalo - t_off_pwm
            self._tick_dos_estados(
                "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
                self.set_do.vapor_camara_on, self.set_do.vapor_camara_off, now,
            )

        # ── 6. Control de escapes (paralelo e independiente) ───────────────
        self._tick_dos_estados(
            "_t_pulso_lento", "_lento_abierto", lento_on, lento_off,
            self.set_do.descompresion_lenta_on, self.set_do.descompresion_lenta_off, now,
        )
        self._tick_dos_estados(
            "_t_pulso_rapido", "_rapido_abierto", rapido_on, rapido_off,
            self.set_do.descompresion_rapida_on, self.set_do.descompresion_rapida_off, now,
        )

        # ── 7. Condición de finalización ────────────────────────────────────
        if self._timer_estable_inicio is not None:
            # Ya en ESTABLE_PREESTERILIZACION: el timer no se reinicia aunque
            # la condición salga de rango (riesgo aceptado, ver FMEA sección 8).
            if now - self._timer_estable_inicio >= tiempo_est:
                logger.info(
                    "Calentamiento: COMPLETADO tras sostenimiento de %.0fs — %.1f°C / %.1f kPa",
                    tiempo_est, temp, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
            return FaseResult.EN_CURSO

        if temp >= t_obj and pres >= p_obj:
            if tiempo_est <= 0:
                logger.info("Calentamiento: COMPLETADO — %.1f°C / %.1f kPa alcanzados", temp, pres)
                self._apagar_salidas()
                return FaseResult.COMPLETADO
            self._timer_estable_inicio = now
            self.estado.fase_en_sostenimiento = True
            logger.info("Calentamiento: condición alcanzada — sosteniendo %.0fs", tiempo_est)

        return FaseResult.EN_CURSO
