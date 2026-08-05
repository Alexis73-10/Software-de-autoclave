# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva la cámara desde la salida de PRE_VACIO hasta el punto de vapor
# saturado del setpoint de esterilización (temperatura_calentamiento +
# presion_add_calentamiento) y sostiene esa condición durante una ventana
# continua de tiempo_estable_preesterilizacion segundos antes de entregar
# control a ESTERILIZACION. Dos tramos internos, sin retroceso entre ellos:
#   RAMPA (control continuo)  vapor_camara con un duty cycle (0 a 1)
#                              recalculado en cada tick — reemplaza los
#                              antiguos tramos discretos APROXIMACION/
#                              PWM_ACTIVO por un único controlador continuo
#                              que combina tres señales independientes
#                              (gana la más restrictiva, min):
#                                duty_tasa           limita la pendiente
#                                  (tasa_calentamiento/tasa_presion; 0 = sin
#                                  límite; solo limita subida)
#                                duty_proximidad      interpola desde 1.0
#                                  lejos del objetivo hasta duty_estable
#                                  (1 - factor_calentamiento/100) cerca de
#                                  él, medido contra los objetivos fijos
#                                  t_obj/p_obj (nunca contra P_sat(temp
#                                  actual), que se mueve mientras sube)
#                                duty_calidad_vapor   corta a 0 si temp ya
#                                  cruzó el tope del 97% de t_obj pero la
#                                  presión no corresponde a vapor saturado
#                                  a esa temperatura real
#                              Un techo independiente (P >= p_obj + presion_
#                              add_calentamiento) fuerza duty=0 sin importar
#                              el resto. El duty resultante se traduce a PWM
#                              sobre intervalo_segmentos_calor. Ver docs/
#                              superpowers/specs/2026-08-05-control-continuo-
#                              rampa-calentamiento-design.md
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
# control (via duty_tasa, en todo momento, no solo en un tramo de
# aproximación) — no producen FALLO; si vapor_camara no responde al comando
# OFF, no hay aborto automático por esta vía (riesgo aceptado, ver
# docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md).

import time
import logging
from collections import deque
from autoclave.core.runtime.steam import p_saturacion_kpa
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

# Ventana mínima (seg) para medir tasa_calentamiento/tasa_presion. El loop de
# control tiquea cada ~0.5s (control_loop.py) y el sensor llega redondeado a
# 0.1°C (converters.py) — una pendiente tick-a-tick queda dominada por ese
# redondeo: la mayoría de los ticks miden delta=0 (vapor_camara ON sin freno)
# y el resto un pico artificial extrapolado x120 (1min/0.5s) cuando el
# redondeo por fin salta. Medir contra una muestra de al menos esta
# antigüedad diluye tanto el ruido de cuantización como el factor de
# extrapolación, dando una tasa que refleja el ritmo real sostenido.
_VENTANA_PENDIENTE_SEG = 10

_FACTOR_TOPE_TEMPERATURA = 0.97


def _duty_por_tasa(tasa_actual, tasa_max):
    """Duty (0 a 1) por limite de pendiente: 1.0 si no hay restriccion
    configurada o la pendiente ya esta dentro del limite; cae
    proporcionalmente (tasa_max / tasa_actual) si lo excede."""
    if tasa_max <= 0 or tasa_actual is None or tasa_actual <= 0:
        return 1.0
    return min(tasa_max / tasa_actual, 1.0)


def _duty_por_proximidad(dist, margen):
    """Fraccion de rampa restante hacia el objetivo: 1.0 a `margen` unidades
    o mas de distancia, 0.0 en o despues del objetivo (dist <= 0), lineal
    en el medio."""
    if margen <= 0:
        return 1.0 if dist > 0 else 0.0
    return max(0.0, min(dist / margen, 1.0))


def _duty_por_calidad_vapor(temp, pres, t_obj, p_add):
    """Corte binario (0 o 1): una vez que temp cruza el 97% de t_obj, exige
    que la presion ya corresponda a la temperatura real (P_sat(temp) +
    p_add) -- evita inyectar cuando el sensor de temperatura corre por
    delante de vapor no saturado."""
    temp_cap = _FACTOR_TOPE_TEMPERATURA * t_obj
    if temp < temp_cap:
        return 1.0
    p_min_para_temp = p_saturacion_kpa(temp) + p_add
    return 1.0 if pres >= p_min_para_temp else 0.0


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"

    def reset(self):
        self._inicializado = False
        self._timer_timeout_fin = None
        self._duty_actual = None

        # Tramo ESTABLE_PREESTERILIZACION: ventana continua dentro de banda
        self._en_sostenimiento = False
        self._timer_sostenido_desde = None
        self._timer_recuperacion_fin = None

        # Pendiente sobre ventana (tasa_calentamiento / tasa_presion) —
        # alimenta duty_tasa en el paso 4 (control continuo de vapor_camara).
        # Historial [(timestamp, temp, pres), ...] de al menos
        # _VENTANA_PENDIENTE_SEG de profundidad; ver constante de módulo.
        self._historial_pendiente = deque()

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
        # tasa_t/tasa_p alimentan duty_tasa en el paso 4 (control continuo de
        # vapor_camara). No disparan FALLO — riesgo aceptado si vapor_camara no
        # responde al comando OFF, ver spec de remoción de FALLO. Se miden
        # contra la muestra más antigua del historial que ya tenga al menos
        # _VENTANA_PENDIENTE_SEG de antigüedad (no contra el tick anterior
        # inmediato — ver constante de módulo).
        self._historial_pendiente.append((now, temp, pres))
        while (
            len(self._historial_pendiente) > 1
            and now - self._historial_pendiente[1][0] >= _VENTANA_PENDIENTE_SEG
        ):
            self._historial_pendiente.popleft()

        tasa_t = None
        tasa_p = None
        t_ref, temp_ref, pres_ref = self._historial_pendiente[0]
        edad = now - t_ref
        if edad >= _VENTANA_PENDIENTE_SEG:
            dt_min = edad / 60
            tasa_t = (temp - temp_ref) / dt_min
            tasa_p = (pres - pres_ref) / dt_min

        # ── 4. Duty cycle continuo de vapor_camara ─────────────────────────
        # Reemplaza los tramos discretos APROXIMACION/PWM_ACTIVO: duty_tasa
        # limita la pendiente (paso 3), duty_proximidad se acerca a
        # duty_estable a medida que temp/pres se acercan a los objetivos
        # fijos t_obj/p_obj (nunca contra P_sat(temp_actual)), y
        # duty_calidad_vapor corta a 0 si la temperatura ya cruzo el tope
        # del 97% pero la presion no corresponde a vapor saturado a esa
        # temperatura -- salvo que la fase ya este en ESTABLE_PREESTERILIZACION
        # (self._en_sostenimiento), donde ese chequeo no aplica: la
        # seguridad de esa banda ya la maneja el paso 7 con su propio
        # timeout de recuperacion, y aplicar duty_calidad_vapor ahi forzaba
        # duty=0 dentro del propio tramo de sostenimiento (confirmado con
        # datos reales del ciclo 72 -- ver spec, seccion 3.3). Gana el mas
        # restrictivo (min); el techo independiente corta a 0 sin importar
        # el resto si la presion ya rebaso lo tolerado.
        duty_tasa = min(
            _duty_por_tasa(tasa_t, tasa_t_max),
            _duty_por_tasa(tasa_p, tasa_p_max),
        )

        duty_estable = 1.0 - factor_pct / 100.0
        cercania = min(
            _duty_por_proximidad(t_obj - temp, rango_cal),
            _duty_por_proximidad(p_obj - pres, rango_cal),
        )
        duty_proximidad = duty_estable + (1.0 - duty_estable) * cercania

        if self._en_sostenimiento:
            duty_calidad_vapor = 1.0
        else:
            duty_calidad_vapor = _duty_por_calidad_vapor(temp, pres, t_obj, p_add)

        duty = min(duty_tasa, duty_proximidad, duty_calidad_vapor)

        p_techo = p_obj + p_add
        if pres >= p_techo:
            duty = 0.0

        duty_anterior = self._duty_actual
        self._duty_actual = duty

        if duty <= 0.0 and (duty_anterior is None or duty_anterior > 0.0):
            razones = []
            if duty_tasa <= 0.0:
                razones.append("tasa")
            if duty_proximidad <= 0.0:
                razones.append("proximidad")
            if duty_calidad_vapor <= 0.0:
                razones.append("calidad_vapor")
            if pres >= p_techo:
                razones.append("techo")
            logger.warning(
                "Calentamiento: vapor_camara a 0 (%s) — T=%.1f°C P=%.1f kPa",
                ",".join(razones) or "?", temp, pres,
            )
        elif duty > 0.0 and duty_anterior == 0.0:
            logger.info(
                "Calentamiento: vapor_camara reanuda (duty=%.2f) — T=%.1f°C P=%.1f kPa",
                duty, temp, pres,
            )

        if intervalo <= 0:
            # intervalo<=0 haria que _tick_dos_estados caiga en su rama
            # "enclavada abierta" (t_off<=0) sin importar duty -- los
            # cuatro mecanismos de arriba quedarian anulados por un solo
            # parametro de ciclo mal configurado (la UI permite
            # intervalo_segmentos_calor=0). Aplicar duty directo.
            if duty > 0.0:
                self.set_do.vapor_camara_on()
                self._pwm_abierto = True
            else:
                self.set_do.vapor_camara_off()
                self._pwm_abierto = False
            self._t_pulso_pwm = None
        else:
            t_on_pwm = intervalo * duty
            t_off_pwm = intervalo - t_on_pwm
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
