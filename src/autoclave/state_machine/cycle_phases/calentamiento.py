# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva la cámara desde la salida de PRE_VACIO hasta el punto de vapor
# saturado del setpoint de esterilización (temperatura_calentamiento +
# presion_add_calentamiento) y sostiene esa condición durante una ventana
# continua de tiempo_estable_preesterilizacion segundos antes de entregar
# control a ESTERILIZACION. Tres tramos internos, sin retroceso entre ellos:
#   APROXIMACION              vapor_camara en bang-bang por tick: ON salvo
#                              que la pendiente ya supere tasa_calentamiento/
#                              tasa_presion (0 = sin límite; solo limita subida)
#   PWM_ACTIVO                entra al alcanzar |P - P_sat(T)| <= rango_calentamiento;
#                              vapor_camara en PWM (factor_calentamiento / intervalo_segmentos_calor)
#   ESTABLE_PREESTERILIZACION entra al cruzar temp>=t_obj y pres>=p_obj; exige
#                              una ventana CONTINUA de tiempo_estable_preesterilizacion
#                              segundos dentro de banda (|T-t_obj|<=rango_temp_estabilizacion
#                              Y |P-p_obj|<=presion_add_calentamiento) — el conteo
#                              se reinicia si sale de banda, así se espera a que
#                              la inercia térmica se disipe antes de completar.
#                              Timeout de recuperación dedicado
#                              (timeout_recuperacion_estabilizacion) si nunca
#                              converge. Ver docs/superpowers/specs/
#                              2026-08-04-fusion-calentamiento-estabilizacion-design.md
#
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase (no sincronizados con los
# tramos anteriores). tasa_calentamiento/tasa_presion son puramente de
# control (bang-bang en APROXIMACION) — no producen FALLO; si vapor_camara
# no responde al comando OFF, no hay aborto automático por esta vía (riesgo
# aceptado, ver docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md).

import time
import logging
from autoclave.core.runtime.steam import p_saturacion_kpa
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"

    def reset(self):
        self._inicializado = False
        self._timer_timeout_fin = None
        self._en_pwm = False

        # Tramo ESTABLE_PREESTERILIZACION: ventana continua dentro de banda
        self._en_sostenimiento = False
        self._timer_sostenido_desde = None
        self._timer_recuperacion_fin = None

        # Pendiente instantánea (tasa_calentamiento / tasa_presion) —
        # alimenta el control de vapor_camara en APROXIMACION, paso 5
        self._temp_anterior = None
        self._pres_anterior = None
        self._t_tick_anterior = None

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
        rango_temp_estab =  self.cycle.get_param("calentamiento", "rango_temp_estabilizacion")           or 1.0
        timeout_rec_seg  = (self.cycle.get_param("calentamiento", "timeout_recuperacion_estabilizacion")  or 5) * 60

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

        # ── 3. Cálculo de pendiente ──────────────────────────────────────
        # tasa_t/tasa_p alimentan el control de vapor_camara en APROXIMACION
        # (paso 5). No disparan FALLO — riesgo aceptado si vapor_camara no
        # responde al comando OFF, ver spec de remoción de FALLO.
        tasa_t = None
        tasa_p = None
        if self._t_tick_anterior is not None:
            dt_min = (now - self._t_tick_anterior) / 60
            if dt_min > 0:
                tasa_t = (temp - self._temp_anterior) / dt_min
                tasa_p = (pres - self._pres_anterior) / dt_min

        self._temp_anterior = temp
        self._pres_anterior = pres
        self._t_tick_anterior = now

        # ── 4. Entrada a PWM (unidireccional) ─────────────────────────────
        if not self._en_pwm and abs(pres - p_saturacion_kpa(temp)) <= rango_cal:
            self._en_pwm = True
            logger.info("Calentamiento: banda alcanzada (%.1f kPa) — entra a PWM_ACTIVO", rango_cal)

        # ── 5. Control de vapor_camara ─────────────────────────────────────
        if not self._en_pwm:
            # Bang-bang directo por tick: ON salvo que la pendiente ya
            # supere el techo de tasa_calentamiento/tasa_presion. Solo se
            # limita la dirección de subida (tasa_t sin abs()) porque la
            # válvula no puede enfriar la cámara. tasa_t/tasa_p en None
            # (sin dato de pendiente aún) o el umbral en 0 (deshabilitado)
            # no pueden forzar OFF.
            dentro_de_tasa = (
                (tasa_t is None or tasa_t_max <= 0 or tasa_t <= tasa_t_max)
                and (tasa_p is None or tasa_p_max <= 0 or tasa_p <= tasa_p_max)
            )
            if dentro_de_tasa:
                self.set_do.vapor_camara_on()
            else:
                self.set_do.vapor_camara_off()
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

        # ── 7. Entrada y control de ESTABLE_PREESTERILIZACION ───────────────
        # Exige una ventana CONTINUA de tiempo_est segundos dentro de banda
        # respecto a los objetivos fijos (t_obj, p_obj) — el conteo se
        # reinicia si sale de banda, así se espera a que la inercia térmica
        # se disipe antes de entregar control a ESTERILIZACION.
        if not self._en_sostenimiento:
            if temp >= t_obj and pres >= p_obj:
                self._en_sostenimiento = True
                logger.info("Calentamiento: condición alcanzada — entra a ESTABLE_PREESTERILIZACION")
            else:
                return FaseResult.EN_CURSO

        dentro_rango = t_obj <= temp <= t_obj + rango_temp_estab and p_obj <= pres <= p_obj + p_add

        if dentro_rango:
            self._timer_recuperacion_fin = None
            if self._timer_sostenido_desde is None:
                self._timer_sostenido_desde = now
            self.estado.fase_en_sostenimiento = True
            if now - self._timer_sostenido_desde >= tiempo_est:
                logger.info(
                    "Calentamiento: COMPLETADO tras sostenimiento continuo de %.0fs — %.1f°C / %.1f kPa",
                    tiempo_est, temp, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
        else:
            self._timer_sostenido_desde = None
            self.estado.fase_en_sostenimiento = False
            if self._timer_recuperacion_fin is None:
                self._timer_recuperacion_fin = now + timeout_rec_seg
                logger.warning("Calentamiento: condición fuera de rango en sostenimiento — recuperando")
            if now > self._timer_recuperacion_fin:
                return self._fallo(
                    f"No se logró sostener condición estable en {timeout_rec_seg / 60:.0f} min"
                )

        return FaseResult.EN_CURSO
