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

import math
import time
import logging
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.core.runtime.sensores_ciclo import NOMBRES
from autoclave.state_machine.alarms.catalogo import CIC_09, CIC_11
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_DEBOUNCE_LECTURAS = 3
_BANDA_PWM_BAJA = 2.0  # kPa por debajo de P_sat(T_actual) -> vapor ON forzado
_BANDA_PWM_ALTA = 1.0  # kPa por encima de P_sat(T_actual) -> vapor OFF forzado
# D8-2.8 (tanda 8): tope de la suma de pausas sin datos de la tarjeta en una
# exposición (parámetro del equipo pausa_max_esterilizacion_s)
_PAUSA_MAX_DEFECTO_S = 30.0
_PAUSA_MAX_RANGO_S = (5.0, 120.0)


class EsterilizacionFase(BaseFase):

    name = "ESTERILIZACION"

    def reset(self):
        self._inicializado = False
        self._timer_fin = None
        self._timer_timeout_max = None
        self._en_recuperacion = True

        # Debounce de las 4 condiciones de falla (referencia fija t_est)
        self._contador_temp_alta = 0
        self._contador_temp_baja = 0
        self._contador_pres_alta = 0
        self._contador_pres_baja = 0
        # Uniformidad térmica de las Referencias (tanda §1.1 b): debounce por
        # sensor y alerta una sola vez por ciclo y sensor.
        self._contador_ref_fuera: dict[str, int] = {}
        self._ref_alertada: set[str] = set()

        # Temporizadores de dos estados (vapor PWM, escape lento, escape rápido)
        self._t_pulso_pwm = None
        self._pwm_abierto = False
        self._t_pulso_lento = None
        self._lento_abierto = False
        self._t_pulso_rapido = None
        self._rapido_abierto = False

        # D8-2.8: segundos de pausa acumulados en esta exposición y alarma
        # propia con que CicloState registra el fallo (None = CIC-04)
        self.pausa_total_s = 0.0
        self.alarma_fallo = None

        self.estado.fase_en_sostenimiento = False

    def _pausa_max_s(self) -> float:
        """pausa_max_esterilizacion_s del equipo, recortado a 5-120 s; sin un
        valor numérico válido, 30 s."""
        try:
            valor = self.config.get("pausa_max_esterilizacion_s")
        except Exception:
            valor = None
        if (isinstance(valor, bool) or not isinstance(valor, (int, float))
                or not math.isfinite(valor)):
            return _PAUSA_MAX_DEFECTO_S
        bajo, alto = _PAUSA_MAX_RANGO_S
        return min(max(float(valor), bajo), alto)

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_rapida_off()
        self.estado.fase_en_sostenimiento = False

    def _vigilar_referencias(self, minimo: float, maximo: float) -> None:
        for sensor, temp in self._temps_referencia().items():
            if temp is None:
                continue        # lo trata la vigilancia SENSOR_AUSENTE de CicloState
            if minimo <= temp <= maximo:
                self._contador_ref_fuera[sensor] = 0
                continue
            n = self._contador_ref_fuera.get(sensor, 0) + 1
            self._contador_ref_fuera[sensor] = n
            if n >= _DEBOUNCE_LECTURAS and sensor not in self._ref_alertada:
                self._ref_alertada.add(sensor)
                logger.warning("Esterilización: referencia %s fuera de rango (%.1f °C)",
                               sensor, temp)
                # SAF-04 de T3: queda en el pie del ticket del ciclo
                try:
                    avisos = getattr(self.estado, "avisos_ciclo", None)
                    if isinstance(avisos, list):
                        avisos.append(f"Uniformidad termica fuera de rango: "
                                      f"{NOMBRES.get(sensor, sensor)} {temp:.1f} C")
                except Exception:
                    logger.exception("Esterilización: no se pudo anotar el aviso de uniformidad")
                try:
                    self.alarm_manager.activar(CIC_09, origen=sensor,
                                               sensor=NOMBRES.get(sensor, sensor),
                                               temp=temp, minimo=minimo, maximo=maximo)
                except Exception:
                    logger.exception("Esterilización: no se pudo registrar CIC-09")

    def pausar_exposicion(self, segundos) -> None:
        """T2-a (tanda 7, decisión 1.3 de Cristian): los segundos de
        tolerancia por DI vencida (la fase no corrió, vapor cortado) no cuentan
        como exposición: el fin del conteo se corre esos segundos. Antes de
        iniciar el conteo no hay nada que correr. El timeout de F0 no cambia."""
        if self._timer_fin is None:
            return
        if (isinstance(segundos, bool) or not isinstance(segundos, (int, float))
                or not math.isfinite(segundos) or segundos <= 0):
            return
        self._timer_fin += segundos
        self.pausa_total_s += segundos
        logger.warning("Esterilización: exposición en pausa %.1f s (sin datos de la tarjeta)",
                       segundos)

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
        # F0 solo en equipos de laboratorio (tanda §1.1); sin capacidades
        # conocidas se respeta el parámetro (comportamiento previo)
        f0_activo    =  bool(self.cycle.get_param("globals", "F0")) and (
            self.cap is None or bool(getattr(self.cap, "has_liquid_sensor", False)))
        f0_objetivo  =  self.cycle.get_param("globals", "F0_objetivo")      or 0.0

        p_sat_est = p_saturacion_kpa(t_est)
        p_control_max = p_sat_est + presion_add

        # ── 1. Inicialización ────────────────────────────────────────────
        # El timer de finalización se fija al entrar a la fase, sin importar
        # la disponibilidad de sensores (plan sección 5).
        if not self._inicializado:
            self._timer_fin = time.monotonic() + tiempo_seg
            if f0_activo:
                self._timer_timeout_max = time.monotonic() + 2 * tiempo_seg
            self._inicializado = True
            self.estado.fase_en_sostenimiento = True
            logger.info(
                "Esterilización: iniciando %.0fs a %.1f°C | P_control_max=%.1f kPa",
                tiempo_seg, t_est, p_control_max,
            )

        # ── 1b. D8-2.8: tope de pausas sin datos en esta exposición ─────────
        # Antes de la lectura de sensores: falla aunque no haya lectura.
        pausa_max = self._pausa_max_s()
        if self.pausa_total_s > pausa_max:
            self.alarma_fallo = (CIC_11, {"segundos": self.pausa_total_s, "maximo": pausa_max})
            return self._fallo(
                f"Comunicación inestable: {self.pausa_total_s:.0f} s de pausa sin datos de la "
                f"tarjeta (máximo {pausa_max:.0f} s)"
            )

        temp = self._temp_principal()
        pres = self._pres_camara()
        if temp is None or pres is None:
            return FaseResult.EN_CURSO

        now = time.monotonic()

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

        # ── 2b. Referencias (tanda §1.1 b): fuera de rango NO falla; alerta
        # de uniformidad térmica no bloqueante. El control y el conteo siguen
        # solo con el Principal (que falla por sí mismo si sale de rango).
        self._vigilar_referencias(t_est - brecha_err_t, t_est + rango_temp)

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
        # Sin F0: única variable de éxito es el conteo de tiempo, sin
        # importar el tramo de control activo (RECUPERACION o PWM_ACTIVO).
        # Con F0: además del tiempo, exige letalidad acumulada suficiente —
        # un timeout de seguridad (2x tiempo_esterilizacion) cubre el caso
        # en que F0 nunca llega (fuga, descalibración de sensor).
        tiempo_cumplido = now >= self._timer_fin

        if not f0_activo:
            if tiempo_cumplido:
                logger.info("Esterilización: COMPLETADO — %.0f seg completados", tiempo_seg)
                self._apagar_salidas()
                return FaseResult.COMPLETADO
            return FaseResult.EN_CURSO

        f0_cumplido = self.estado.f0_acumulado >= f0_objetivo
        if tiempo_cumplido and f0_cumplido:
            logger.info(
                "Esterilización: COMPLETADO — %.0f seg completados, F0=%.2f/%.1f min",
                tiempo_seg, self.estado.f0_acumulado, f0_objetivo,
            )
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        if now >= self._timer_timeout_max:
            return self._fallo(
                f"ESTERILIZACION_TIMEOUT_F0: F0 no alcanzado tras {2 * tiempo_seg / 60:.0f} min "
                f"(F0={self.estado.f0_acumulado:.2f}/{f0_objetivo:.1f} min)"
            )

        return FaseResult.EN_CURSO
