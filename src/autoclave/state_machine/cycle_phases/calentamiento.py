# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva la cámara desde la salida de PRE_VACIO hasta el punto de vapor
# saturado del setpoint (t_obj = temperatura_calentamiento, p_obj =
# Psat(t_obj); desde la tanda 12, C-01, presion_add_calentamiento ya NO se
# suma al objetivo: es solo el techo, Psat(t_obj) + presion_add_calentamiento)
# y sostiene esa condición durante una ventana
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
#                                  actual), que se mueve mientras sube).
#                                  Una vez superado el objetivo, ese piso
#                                  duty_estable se escala hacia 0 a medida
#                                  que el sobrepaso crece (0 a partir de
#                                  rango_calentamiento_temp °C /
#                                  rango_calentamiento_pres kPa pasado el
#                                  objetivo) — corrige que el controlador
#                                  siguiera inyectando vapor a duty_estable
#                                  de forma indefinida muy por encima del
#                                  objetivo (ciclo 79, 2026-08-06: 136.7°C
#                                  con t_obj=134.0°C)
#                                duty_calidad_vapor   corta a 0 si temp ya
#                                  cruzó t_obj - 3 K (_MARGEN_CALIDAD_VAPOR_K,
#                                  tanda 12 C-09; antes 97 % de t_obj) pero
#                                  P < Psat(temp) - 2 kPa (_TOLERANCIA_PSAT_KPA,
#                                  sin presion_add: C-01.5)
#                              Un techo independiente (P >= Psat(t_obj) +
#                              presion_add_calentamiento; hasta la tanda 11
#                              era 2 x presion_add) fuerza duty=0 sin importar
#                              el resto. El duty resultante se traduce a PWM
#                              sobre intervalo_segmentos_calor. Ver docs/
#                              superpowers/specs/2026-08-05-control-continuo-
#                              rampa-calentamiento-design.md
#   ESTABLE_PREESTERILIZACION entra al cruzar temp>=t_obj y pres>=p_obj-2 kPa
#                              (C-01.2); exige una ventana CONTINUA de
#                              tiempo_estable_preesterilizacion segundos dentro
#                              de banda (C-01.3): t_obj <= T <= t_obj +
#                              rango_temp_estabilizacion Y Psat(t_obj)-2 <= P <=
#                              Psat(t_obj)+presion_add_calentamiento; con carga
#                              sólida además coherencia T-P |Tsat(P)-T| <= 1 K
#                              (C-02, _COHERENCIA_TP_K; no aplica a líquidos);
#                              y cada Referencia CON lectura >= t_obj -
#                              brecha_error_temperatura (de la sección
#                              esterilizacion; P3 / D-14.3, tanda 16: el mismo
#                              límite inferior que la banda de Referencia de
#                              ESTERILIZACION; sin valor numérico válido, 0,
#                              es decir >= t_obj) (una
#                              Referencia sin lectura no bloquea: C-13.7b) — el
#                              conteo se reinicia si sale de banda, así se espera a que
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
#
# Tanda 16, VCH (docs/mis_plans/planeacion_control_vapor_chaqueta.md), solo
# en modo chaqueta (estado.modo_vapor == "chaqueta", lo fija CicloState al
# iniciar el ciclo; el modo se registra en el log al iniciar la fase):
#   - la lógica de decisión de arriba no cambia; el duty se aplica a
#     vapor_chaqueta en vez de a vapor_camara (VCH §4.2);
#   - vapor_camara se abre al inicializar la fase y se ordena ON en cada tick
#     mientras no haya aislamiento (D3, §4.3);
#   - aislamiento VCH-AIS (§4.4, estado.aislamiento_camara, compartido con
#     ESTERILIZACION): P >= p_techo -> vapor_camara y vapor_chaqueta OFF
#     forzadas; sale con P <= p_techo - histeresis_cierre_camara sostenida
#     3 s. Aislamiento más largo que timeout_aislamiento_camara -> FALLO
#     CIC-15; max_aislamientos_camara en la ventana móvil -> FALLO CIC-16;
#   - sin lectura del Principal o de la presión: vapor_chaqueta OFF;
#   - estado.inhibir_vapor_chaqueta (corte D-CHQ de CICLO) True: nunca se
#     enciende vapor_chaqueta;
#   - COMPLETADO no cierra vapor_camara (ESTERILIZACION la mantiene
#     abierta); FALLO cierra las dos.
# En modo cámara (equipos de mesa) el comportamiento es el de antes.

import math
import time
import logging
from collections import deque
from autoclave.core.runtime.steam import p_saturacion_kpa, t_saturacion_c
from autoclave.core.runtime import motivos_fase
from autoclave.core.managers import limites_equipo as le
from autoclave.installation.profile import MODO_CHAQUETA
from autoclave.state_machine.alarms.catalogo import CIC_15, CIC_16, nombre_legible
from .aislamiento_camara import AislamientoCamara
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

# Tanda 12, C-01.6: tolerancia (kPa) bajo Psat para entrar al sostenimiento,
# para la banda de sostenimiento y para duty_calidad_vapor.
_TOLERANCIA_PSAT_KPA = 2.0

# Tanda 12, C-09: el tope de calidad de vapor arranca a esta distancia (K)
# bajo t_obj (antes: 97 % de t_obj, que a 121 °C quedaba en 117.37 °C).
_MARGEN_CALIDAD_VAPOR_K = 3.0

# Tanda 12, C-02: coherencia temperatura-presión exigida en la banda de
# sostenimiento (solo carga sólida): |Tsat(P) - T_principal| <= este valor.
_COHERENCIA_TP_K = 1.0

# Tanda 16, VCH §5: histeresis_cierre_camara (kPa), defecto y rango.
_HISTERESIS_CIERRE_DEFECTO = 3.0
_HISTERESIS_CIERRE_RANGO = (1.0, 10.0)


def _numero_finito(valor) -> bool:
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and math.isfinite(valor))


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


def _duty_por_sobrepaso(dist, margen):
    """Factor (0 a 1) que escala el piso duty_estable hacia abajo a medida
    que ya se superó el objetivo: 1.0 en el objetivo o antes (dist >= 0,
    sin restringir todavía), cae linealmente a 0.0 al superarlo por
    `margen` unidades o más. Sin esto, duty_proximidad se queda clavado en
    duty_estable de forma indefinida sin importar cuánto se haya pasado del
    objetivo -- bug real (ciclo 79, 2026-08-06): con temp a 136.7°C
    (t_obj=134.0) el duty seguía en 0.5, como si 136.7°C fuera un punto
    válido para sostener con PWM en vez de apagar."""
    if margen <= 0:
        return 1.0 if dist >= 0 else 0.0
    return max(0.0, min(1.0 + dist / margen, 1.0))


def _duty_por_calidad_vapor(temp, pres, t_obj):
    """Corte binario (0 o 1): una vez que temp cruza t_obj -
    _MARGEN_CALIDAD_VAPOR_K (C-09), exige que la presion ya corresponda a
    la temperatura real (P_sat(temp) - _TOLERANCIA_PSAT_KPA, sin sumar
    presion_add: C-01.5) -- evita inyectar cuando el sensor de temperatura
    corre por delante de vapor no saturado."""
    if temp < t_obj - _MARGEN_CALIDAD_VAPOR_K:
        return 1.0
    p_min_para_temp = p_saturacion_kpa(temp) - _TOLERANCIA_PSAT_KPA
    return 1.0 if pres >= p_min_para_temp else 0.0


def _diferencia_coherencia_tp(temp, pres):
    """Tsat(pres) - temp en K (C-02); None si la presión no permite
    calcular Tsat (p <= 0 o no finita): se trata como incoherente."""
    try:
        return t_saturacion_c(pres) - temp
    except ValueError:
        return None


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"
    # D8-2.12: ventana continua de ESTABLE_PREESTERILIZACION
    _VENTANAS_ESTABILIDAD = ("_timer_sostenido_desde",)

    def reset(self):
        self._inicializado = False
        self._timer_timeout_fin = None
        self._ventana_pausada_s = 0.0   # TMG-02 de la revisión S2b
        self._duty_actual = None

        # Tramo ESTABLE_PREESTERILIZACION: ventana continua dentro de banda
        self._en_sostenimiento = False
        self._timer_sostenido_desde = None
        self._timer_recuperacion_fin = None
        self._coherente_previo = True   # C-02: log solo al perder coherencia

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

        # Tanda 16, VCH: modo fijado al inicializar (None = aún sin fijar)
        self._modo_chaqueta = None
        self._aislado_previo = False
        # Mecanismo de CIC-11 de ESTERILIZACION: CicloState registra
        # `alarma_fallo` (CIC-15/16 del aislamiento)
        self.alarma_fallo = None

        self.estado.fase_en_sostenimiento = False

    # ------------------------------------------------------------------
    # Tanda 16, VCH: modo de vapor y aislamiento de cámara
    # ------------------------------------------------------------------

    def _modo_chaqueta_estado(self) -> bool:
        return getattr(self.estado, "modo_vapor", None) == MODO_CHAQUETA

    @property
    def controla_vapor_chaqueta(self) -> bool:
        """VCH §4.7: True solo en modo chaqueta (CICLO no toca entonces
        vapor_chaqueta, salvo SUM-06 y el corte D-CHQ)."""
        if self._modo_chaqueta is not None:
            return self._modo_chaqueta
        return self._modo_chaqueta_estado()

    def _chaqueta_inhibida(self) -> bool:
        return getattr(self.estado, "inhibir_vapor_chaqueta", False) is True

    def _aislamiento(self) -> AislamientoCamara:
        ais = getattr(self.estado, "aislamiento_camara", None)
        if not isinstance(ais, AislamientoCamara):
            ais = AislamientoCamara()
            self.estado.aislamiento_camara = ais
        return ais

    def _histeresis_cierre(self) -> float:
        """histeresis_cierre_camara (kPa) recortada a 1-10; sin un valor
        numérico finito, 3."""
        valor = self.cycle.get_param("calentamiento", "histeresis_cierre_camara",
                                     default=_HISTERESIS_CIERRE_DEFECTO)
        if not _numero_finito(valor):
            return _HISTERESIS_CIERRE_DEFECTO
        lo, hi = _HISTERESIS_CIERRE_RANGO
        return min(max(float(valor), lo), hi)

    def _brecha_error_temperatura(self) -> float:
        """P3 / D-14.3: brecha_error_temperatura de la sección esterilizacion,
        límite inferior de las Referencias en la ventana. Sin un valor
        numérico finito >= 0 vale 0 (el criterio anterior, T_ref >= t_obj):
        DECISIÓN SIN CONFIRMAR."""
        valor = self.cycle.get_param("esterilizacion", "brecha_error_temperatura")
        if not _numero_finito(valor) or valor < 0:
            return 0.0
        return float(valor)

    def _vigilar_aislamiento(self, pres, p_techo, now):
        """VCH-AIS (§4.4/§4.5), solo modo chaqueta. Devuelve (aislado,
        FaseResult.FALLO o None)."""
        ais = self._aislamiento()
        histeresis = self._histeresis_cierre()
        aislado = ais.actualizar(pres, p_techo, histeresis, now)
        if aislado and not self._aislado_previo:
            logger.warning(
                "Calentamiento: AISLAMIENTO de cámara por sobrepresión — P=%s kPa >= techo "
                "%.1f kPa (vapor_camara y vapor_chaqueta OFF)",
                "?" if pres is None else f"{pres:.1f}", p_techo)
        elif not aislado and self._aislado_previo:
            logger.info(
                "Calentamiento: fin del aislamiento de cámara — P=%s kPa <= %.1f kPa "
                "sostenida (reabre vapor_camara)",
                "?" if pres is None else f"{pres:.1f}", p_techo - histeresis)
        self._aislado_previo = aislado

        timeout_s = le.timeout_aislamiento_camara_s(self.config)
        if ais.sostenido(now, timeout_s):
            minutos = f"{timeout_s / 60:.0f}"
            return aislado, self._fallo_propio(
                CIC_15, {"minutos": minutos, "fase": nombre_legible(self.name),
                         "maximo": p_techo},
                motivos_fase.motivo("ais_sostenida", minutos=minutos,
                                    pres_techo=f"{p_techo:.1f} kPa"))
        maximo = le.max_aislamientos_camara(self.config)
        ventana_s = le.ventana_aislamientos_camara_s(self.config)
        if ais.recurrente(now, maximo, ventana_s):
            cantidad = ais.entradas_en_ventana(now, ventana_s)
            minutos = f"{ventana_s / 60:.0f}"
            return aislado, self._fallo_propio(
                CIC_16, {"cantidad": cantidad, "minutos": minutos,
                         "fase": nombre_legible(self.name)},
                motivos_fase.motivo("ais_recurrente", cantidad=cantidad, minutos=minutos))
        return aislado, None

    def _apagar_salidas(self, completado: bool = False):
        # VCH §4.3: en modo chaqueta el COMPLETADO no cierra vapor_camara
        # (ESTERILIZACION la mantiene abierta); vapor_chaqueta sí queda OFF
        # (ESTERILIZACION la retoma). En FALLO se cierran las dos. En modo
        # cámara, como antes (vapor_chaqueta la maneja CICLO).
        if self._modo_chaqueta:
            self.set_do.vapor_chaqueta_off()
            if not completado:
                self.set_do.vapor_camara_off()
        else:
            self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_rapida_off()
        self.estado.fase_en_sostenimiento = False

    def _fallo(self, mensaje: str) -> FaseResult:
        logger.error("Calentamiento: FALLO — %s", mensaje)
        self._apagar_salidas()
        self.estado.motivo_fallo = mensaje
        return FaseResult.FALLO

    def _fallo_propio(self, codigo_alarma, valores: dict, motivo) -> FaseResult:
        """Mecanismo de CIC-11 de ESTERILIZACION: CicloState registra
        `alarma_fallo`."""
        self.alarma_fallo = (codigo_alarma, valores)
        return self._fallo(motivo)

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
        # R1-P3 (tanda 7): banda de temperatura (°C) y de presión (kPa) por
        # separado. Sin las claves nuevas (Cycle armado sin migrar), la vieja.
        rango_viejo = self.cycle.get_param("calentamiento", "rango_calentamiento")
        rango_cal_t = self.cycle.get_param("calentamiento", "rango_calentamiento_temp")
        rango_cal_p = self.cycle.get_param("calentamiento", "rango_calentamiento_pres")
        rango_cal_t = (rango_cal_t if rango_cal_t is not None else rango_viejo) or 0.0
        rango_cal_p = (rango_cal_p if rango_cal_p is not None else rango_viejo) or 0.0
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

        # Tanda 12, C-01: presion_add_calentamiento es solo techo. El
        # objetivo de presión es la saturación a t_obj, sin sumarle nada.
        p_obj = p_saturacion_kpa(t_obj)
        p_techo = p_obj + p_add

        # ── 1. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            temp_inicial = self._temp_principal()
            if temp_inicial is None:
                if self._modo_chaqueta_estado():
                    # VCH: CICLO ya no maneja la chaqueta (controla_vapor_chaqueta);
                    # sin lectura del Principal no se inyecta por ella
                    self.set_do.vapor_chaqueta_off()
                return FaseResult.EN_CURSO
            self._timer_timeout_fin = time.monotonic() + timeout_seg
            self._inicializado = True
            # VCH-SEL (§4.1): el modo queda fijo para toda la fase
            self._modo_chaqueta = self._modo_chaqueta_estado()
            logger.info(
                "Calentamiento: iniciando desde %.1f°C | objetivo %.1f°C / %.1f kPa | timeout %.0fs",
                temp_inicial, t_obj, p_obj, timeout_seg,
            )
            logger.info(
                "Calentamiento: modo de vapor %s (válvula actuadora %s)",
                "chaqueta" if self._modo_chaqueta else "cámara",
                "vapor_chaqueta" if self._modo_chaqueta else "vapor_camara",
            )

        # ── 2. Timeout global ────────────────────────────────────────────
        if time.monotonic() > self._timer_timeout_fin:
            # TMG-02 de la revisión S2b: vencido en el sostenimiento con la
            # ventana alargada por tramos sin datos (D8-2.12), el motivo no es
            # "no se alcanzó el objetivo"
            if self._timer_sostenido_desde is not None and self.ventana_pausada_s() > 0:
                # X9 (D9-13.4): motivo con clave + parámetros (idioma vigente)
                return self._fallo(motivos_fase.motivo(
                    "cal_tiempo_limite_sostenimiento", minutos=f"{timeout_seg / 60:.0f}",
                    segundos=f"{self.ventana_pausada_s():.0f}"))
            return self._fallo(motivos_fase.motivo(
                "cal_tiempo_limite", minutos=f"{timeout_seg / 60:.0f}"))

        temp = self._temp_principal()
        pres = self._pres_camara()

        # ── VCH (solo modo chaqueta): aislamiento y válvula de cámara ─────
        aislado = False
        if self._modo_chaqueta:
            aislado, fallo = self._vigilar_aislamiento(pres, p_techo, time.monotonic())
            if fallo is not None:
                return fallo
            if aislado:
                self.set_do.vapor_camara_off()
                self.set_do.vapor_chaqueta_off()
            else:
                # D3 / §4.3: abierta desde el inicio de la fase
                self.set_do.vapor_camara_on()

        if temp is None or pres is None:
            if self._modo_chaqueta:
                # VCH: sin lectura no se inyecta por la chaqueta
                self.set_do.vapor_chaqueta_off()
            return FaseResult.EN_CURSO

        now = time.monotonic()

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
        # (t_obj - 3 K, C-09) pero la presion no corresponde a vapor saturado
        # a esa temperatura (P < Psat(T) - 2 kPa, C-01.5) -- salvo que la fase ya este en ESTABLE_PREESTERILIZACION
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
            _duty_por_proximidad(t_obj - temp, rango_cal_t),
            _duty_por_proximidad(p_obj - pres, rango_cal_p),
        )
        # sobrepaso escala duty_estable hacia 0 a medida que temp/pres ya
        # superaron el objetivo -- sin esto, duty_proximidad se queda en
        # duty_estable indefinidamente sin importar cuánto se haya pasado
        # (ver _duty_por_sobrepaso). No afecta el lado de aproximación
        # (dist >= 0): ahí sobrepaso=1.0 y el comportamiento es idéntico al
        # anterior.
        sobrepaso = min(
            _duty_por_sobrepaso(t_obj - temp, rango_cal_t),
            _duty_por_sobrepaso(p_obj - pres, rango_cal_p),
        )
        duty_proximidad = duty_estable * sobrepaso + (1.0 - duty_estable) * cercania

        if self._en_sostenimiento:
            duty_calidad_vapor = 1.0
        else:
            duty_calidad_vapor = _duty_por_calidad_vapor(temp, pres, t_obj)

        duty = min(duty_tasa, duty_proximidad, duty_calidad_vapor)

        # C-01.4: techo en Psat(t_obj) + presion_add (antes p_obj + p_add con
        # p_obj ya sumado, es decir 2 x presion_add)
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

        # VCH §4.2: en modo chaqueta el mismo PWM se calcula sin actuar
        # (funciones nulas) y su estado se aplica a vapor_chaqueta en cada
        # tick, forzado a OFF con aislamiento o con el corte de CICLO.
        if self._modo_chaqueta:
            on_fn = off_fn = lambda: None
        else:
            on_fn, off_fn = self.set_do.vapor_camara_on, self.set_do.vapor_camara_off

        if intervalo <= 0:
            # intervalo<=0 haria que _tick_dos_estados caiga en su rama
            # "enclavada abierta" (t_off<=0) sin importar duty -- los
            # cuatro mecanismos de arriba quedarian anulados por un solo
            # parametro de ciclo mal configurado (la UI permite
            # intervalo_segmentos_calor=0). Aplicar duty directo.
            if duty > 0.0:
                on_fn()
                self._pwm_abierto = True
            else:
                off_fn()
                self._pwm_abierto = False
            self._t_pulso_pwm = None
        else:
            t_on_pwm = intervalo * duty
            t_off_pwm = intervalo - t_on_pwm
            self._tick_dos_estados(
                "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
                on_fn, off_fn, now,
            )

        if self._modo_chaqueta:
            if self._pwm_abierto and not aislado and not self._chaqueta_inhibida():
                self.set_do.vapor_chaqueta_on()
            else:
                self.set_do.vapor_chaqueta_off()

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
        p_min_banda = p_obj - _TOLERANCIA_PSAT_KPA
        if not self._en_sostenimiento:
            # C-01.2: entra con T >= t_obj y P >= Psat(t_obj) - 2 kPa
            if temp >= t_obj and pres >= p_min_banda:
                self._en_sostenimiento = True
                logger.info("Calentamiento: condición alcanzada — entra a ESTABLE_PREESTERILIZACION")
            else:
                return FaseResult.EN_CURSO

        # C-01.3: t_obj <= T <= t_obj + rango_temp_estabilizacion y
        # Psat(t_obj) - 2 <= P <= Psat(t_obj) + presion_add (el techo)
        dentro_rango = (t_obj <= temp <= t_obj + rango_temp_estab
                        and p_min_banda <= pres <= p_techo)

        # C-02 (solo sólidos): coherencia T-P. Fuera de coherencia = fuera de
        # banda (reinicia la ventana y arma el timeout de recuperación). Con
        # líquidos el Principal es la sonda del líquido, que va minutos
        # detrás del vapor: no se exige (queda para el lazo de presión, C-11).
        # Falla segura: cualquier valor que no sea "liquido" (incluido un
        # tipo_carga ausente o nulo) se trata como sólido y exige coherencia.
        exige_coherencia = self.cycle.get_param(
            "globals", "tipo_carga", default="solido") != "liquido"
        if exige_coherencia:
            dif_tp = _diferencia_coherencia_tp(temp, pres)
            coherente = dif_tp is not None and abs(dif_tp) <= _COHERENCIA_TP_K
            if not coherente and self._coherente_previo:
                logger.warning(
                    "Calentamiento: sin coherencia T-P en sostenimiento — "
                    "Tsat(P)=%s°C T=%.1f°C diferencia=%s K (máx %.1f K)",
                    "?" if dif_tp is None else f"{temp + dif_tp:.2f}", temp,
                    "?" if dif_tp is None else f"{dif_tp:+.2f}", _COHERENCIA_TP_K,
                )
            self._coherente_previo = coherente
            dentro_rango = dentro_rango and coherente

        # Tanda §1.1 (a): las sondas en uso deben estar en la consigna
        # durante la ventana. Las Referencias no se comparan con el Principal
        # ni entre sí: solo contra la consigna (cota inferior; pueden ir más
        # frías que el Principal, nunca se les exige un techo). Tanda 12,
        # C-13.7b (opción B): una Referencia sin lectura NO bloquea la ventana
        # (el ciclo sigue y CicloState la marca NO CONFORME); las que sí leen
        # deben estar en consigna.
        # V12 (SAF-08): "sin lectura" es None, no finito o 0 (sin señal,
        # SEN-01), el mismo criterio de ESTERILIZACION y de CicloState.
        # P3 / D-14.3 (tanda 16): límite inferior t_obj -
        # brecha_error_temperatura (sección esterilizacion), el mismo de la
        # banda de Referencia en ESTERILIZACION.
        t_min_ref = t_obj - self._brecha_error_temperatura()
        refs_en_consigna = all(t >= t_min_ref for t in self._temps_referencia().values()
                               if t is not None and math.isfinite(t) and t != 0)
        dentro_rango = dentro_rango and refs_en_consigna

        if dentro_rango:
            self._timer_recuperacion_fin = None
            if self._timer_sostenido_desde is None:
                self._timer_sostenido_desde = now
                self._ventana_pausada_s = 0.0   # re-revisión S2b: ventana nueva
            self.estado.fase_en_sostenimiento = True
            if now - self._timer_sostenido_desde >= tiempo_est:
                logger.info(
                    "Calentamiento: COMPLETADO tras sostenimiento continuo de %.0fs — %.1f°C / %.1f kPa",
                    tiempo_est, temp, pres,
                )
                self._apagar_salidas(completado=True)
                return FaseResult.COMPLETADO
        else:
            self._timer_sostenido_desde = None
            self.estado.fase_en_sostenimiento = False
            if self._timer_recuperacion_fin is None:
                self._timer_recuperacion_fin = now + timeout_rec_seg
                logger.warning("Calentamiento: condición fuera de rango en sostenimiento — recuperando")
            if now > self._timer_recuperacion_fin:
                return self._fallo(motivos_fase.motivo(
                    "cal_no_sostuvo", minutos=f"{timeout_rec_seg / 60:.0f}"))

        return FaseResult.EN_CURSO
