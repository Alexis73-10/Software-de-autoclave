# state_machine/cycle_phases/esterilizacion.py
#
# FASE 6 — ESTERILIZACIÓN
#
# Sostiene la cámara en vapor saturado a temperatura_esterilizacion durante
# tiempo_esterilizacion minutos. No hay tramo de aproximación (viene ya
# validada de ESTABILIZACION): dos tramos internos, bidireccionales entre sí,
# evaluados en cada tick sin chattering-guard:
#   RECUPERACION   T < T_est + brecha_segura_temperatura
#                  O P < P_sat(T_est) - brecha_segura_presion
#                  -> vapor_camara ON continuo (sin techo de control)
#   PWM_ACTIVO     T >= T_est + brecha_segura_temperatura
#                  Y P >= P_sat(T_est) - brecha_segura_presion
#                  -> vapor_camara en PWM, banda fija [-2,+1] kPa sobre
#                  P_sat(T_actual), techo de control
#                  P_control_max = P_sat(T_est) + presion_add_esterilizacion
#                  (fuerza OFF sin importar la banda local)
#
# El disparador por presión (brecha_segura_presion) cubre el caso en que la
# presión cae de forma sostenida mientras la temperatura se mantiene cerca
# o por encima del setpoint (fuga por descompresion_lenta, que corre
# enclavada abierta durante toda la fase, más rápido de lo que el duty
# cycle de PWM_ACTIVO puede compensar): sin este disparador, RECUPERACION
# nunca se activaba porque solo miraba temperatura, y la presión seguía
# cayendo hasta FALLO sin que el control pasara a modo agresivo.
#
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase, sin depender del tramo
# activo. El timer de tiempo_esterilizacion se fija al entrar a la fase y
# corre sin pausa ni reinicio — no existe timeout de fase; es la única
# condición de finalización exitosa. Las 4 condiciones de falla (temp/pres
# alta/baja) usan temperatura_esterilizacion fija como referencia (nunca
# T_actual), con debounce de 3 lecturas consecutivas — corrige el bug
# ESTERILIZACION_PRES_BAJA de la versión anterior (referencia móvil P_sat(T_actual)).
#
# Riesgo aceptado (ver plan sección 8): si un sensor queda en None, la fase
# no avanza ni falla — puede quedar bloqueada indefinidamente, sin timeout
# que lo capture.

import time
import logging
from autoclave.core.runtime.steam import p_saturacion_kpa
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_DEBOUNCE_LECTURAS = 3
_BANDA_PWM_BAJA = 2.0  # kPa por debajo de P_sat(T_actual) -> vapor ON forzado
_BANDA_PWM_ALTA = 1.0  # kPa por encima de P_sat(T_actual) -> vapor OFF forzado


class EsterilizacionFase(BaseFase):

    name = "ESTERILIZACION"

    def reset(self):
        self._inicializado = False
        self._timer_fin = None
        self._en_recuperacion = True

        # Debounce de las 4 condiciones de falla (referencia fija t_est)
        self._contador_temp_alta = 0
        self._contador_temp_baja = 0
        self._contador_pres_alta = 0
        self._contador_pres_baja = 0

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
        logger.error("Esterilización: FALLO — %s", mensaje)
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

    def _control_vapor_pwm(self, temp, pres, factor_pct, intervalo, p_control_max, now):
        # Techo de control independiente: corta el vapor sin importar la
        # banda local, que sigue a T_actual (no a temperatura_esterilizacion
        # fija) y podría arrastrar la presión hasta el umbral real de falla.
        if pres >= p_control_max:
            self.set_do.vapor_camara_off()
            self._pwm_abierto = False
            self._t_pulso_pwm = None
            return

        p_sat_t = p_saturacion_kpa(temp)
        p_low = p_sat_t - _BANDA_PWM_BAJA
        p_high = p_sat_t + _BANDA_PWM_ALTA

        if pres < p_low:
            self.set_do.vapor_camara_on()
            self._pwm_abierto = True
            self._t_pulso_pwm = None
            return
        if pres > p_high:
            self.set_do.vapor_camara_off()
            self._pwm_abierto = False
            self._t_pulso_pwm = None
            return

        t_off_pwm = intervalo * (factor_pct / 100.0)
        t_on_pwm = intervalo - t_off_pwm
        self._tick_dos_estados(
            "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
            self.set_do.vapor_camara_on, self.set_do.vapor_camara_off, now,
        )

    def update(self) -> FaseResult:
        t_est        =  self.cycle.get_param("esterilizacion", "temperatura_esterilizacion")  or 134.0
        tiempo_seg   = (self.cycle.get_param("esterilizacion", "tiempo_esterilizacion")         or 3.5) * 60
        factor_pct   =  self.cycle.get_param("esterilizacion", "factor_esterilizacion")        or 0.0
        presion_add  =  self.cycle.get_param("esterilizacion", "presion_add_esterilizacion")   or 0.0
        intervalo    =  self.cycle.get_param("esterilizacion", "intervalo_segmentos_ester")    or 0
        rango_temp   =  self.cycle.get_param("esterilizacion", "rango_temperatura_ester")      or 0.0
        rango_pres   =  self.cycle.get_param("esterilizacion", "rango_presion_ester")          or 0.0
        brecha_seg   =  self.cycle.get_param("esterilizacion", "brecha_segura_temperatura")    or 0.0
        brecha_seg_p =  self.cycle.get_param("esterilizacion", "brecha_segura_presion")        or 0.0
        brecha_err_t =  self.cycle.get_param("esterilizacion", "brecha_error_temperatura")     or 0.0
        brecha_err_p =  self.cycle.get_param("esterilizacion", "brecha_error_presion")         or 0.0
        lento_on     =  self.cycle.get_param("esterilizacion", "escape_lento_on_ester")        or 0
        lento_off    =  self.cycle.get_param("esterilizacion", "escape_lento_off_ester")       or 0
        rapido_on    =  self.cycle.get_param("esterilizacion", "escape_rapido_on_ester")       or 0
        rapido_off   =  self.cycle.get_param("esterilizacion", "escape_rapido_off_ester")      or 0

        p_sat_est = p_saturacion_kpa(t_est)
        p_control_max = p_sat_est + presion_add

        # ── 1. Inicialización ────────────────────────────────────────────
        # El timer de finalización se fija al entrar a la fase, sin importar
        # la disponibilidad de sensores (plan sección 5).
        if not self._inicializado:
            self._timer_fin = time.time() + tiempo_seg
            self._inicializado = True
            self.estado.fase_en_sostenimiento = True
            logger.info(
                "Esterilización: iniciando %.0fs a %.1f°C | P_control_max=%.1f kPa",
                tiempo_seg, t_est, p_control_max,
            )

        temp = self._temp_camara()
        pres = self._pres_camara()
        if temp is None or pres is None:
            return FaseResult.EN_CURSO

        now = time.time()

        # ── 2. Chequeo de fallas (debounce 3, referencia fija t_est) ───────
        if temp > t_est + rango_temp:
            self._contador_temp_alta += 1
        else:
            self._contador_temp_alta = 0
        if self._contador_temp_alta >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Temperatura alta: {temp:.1f}°C > {t_est + rango_temp:.1f}°C"
            )

        if temp < t_est - brecha_err_t:
            self._contador_temp_baja += 1
        else:
            self._contador_temp_baja = 0
        if self._contador_temp_baja >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Temperatura baja: {temp:.1f}°C < {t_est - brecha_err_t:.1f}°C"
            )

        if pres > p_sat_est + rango_pres:
            self._contador_pres_alta += 1
        else:
            self._contador_pres_alta = 0
        if self._contador_pres_alta >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Presión alta: {pres:.1f} kPa > {p_sat_est + rango_pres:.1f} kPa"
            )

        if pres < p_sat_est - brecha_err_p:
            self._contador_pres_baja += 1
        else:
            self._contador_pres_baja = 0
        if self._contador_pres_baja >= _DEBOUNCE_LECTURAS:
            return self._fallo(
                f"Presión baja: {pres:.1f} kPa < {p_sat_est - brecha_err_p:.1f} kPa"
            )

        # ── 3. Transición bidireccional RECUPERACION↔PWM_ACTIVO ────────────
        # Sin chattering-guard: reacción inmediata ante pérdida de reserva
        # térmica o de presión es el objetivo de diseño (plan sección 4.1).
        # La presión también dispara RECUPERACION: la temperatura puede
        # mantenerse cerca del setpoint mientras la presión sola cae por la
        # fuga continua de descompresion_lenta, y sin este chequeo el modo
        # agresivo (sin techo de control) nunca se activaba en ese caso.
        self._en_recuperacion = (
            temp < t_est + brecha_seg
            or pres < p_sat_est - brecha_seg_p
        )

        # ── 4. Control de vapor_camara ─────────────────────────────────────
        if self._en_recuperacion:
            self.set_do.vapor_camara_on()
        else:
            self._control_vapor_pwm(temp, pres, factor_pct, intervalo, p_control_max, now)

        # ── 5. Control de escapes (paralelo e independiente) ───────────────
        self._tick_dos_estados(
            "_t_pulso_lento", "_lento_abierto", lento_on, lento_off,
            self.set_do.descompresion_lenta_on, self.set_do.descompresion_lenta_off, now,
        )
        self._tick_dos_estados(
            "_t_pulso_rapido", "_rapido_abierto", rapido_on, rapido_off,
            self.set_do.descompresion_rapida_on, self.set_do.descompresion_rapida_off, now,
        )

        # ── 6. Condición de finalización ─────────────────────────────────
        # Única variable de éxito: el conteo de tiempo, sin importar el tramo
        # de control activo (RECUPERACION o PWM_ACTIVO).
        if now >= self._timer_fin:
            logger.info("Esterilización: COMPLETADO — %.0f seg completados", tiempo_seg)
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
