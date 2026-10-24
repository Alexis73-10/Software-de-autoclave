# state_machine/cycle_phases/esterilizacion.py
#
# FASE 6 — ESTERILIZACIÓN
#
# Sostiene la cámara en vapor saturado a temperatura_esterilizacion durante
# tiempo_esterilizacion minutos. No hay tramo de aproximación (viene ya
# validada de CALENTAMIENTO): dos tramos internos, bidireccionales entre sí,
# evaluados en cada tick:
#   RECUPERACION   entra si T < T_est + brecha_segura_temperatura
#                  O P < P_sat(T_est) - brecha_segura_presion (reacción inmediata)
#                  -> vapor_camara ON continuo, salvo el techo de control
#                  P >= P_control_max -> OFF hasta P < P_control_max - 2 kPa
#                  (C-08.3, tanda 12; histéresis: DECISIÓN SIN CONFIRMAR)
#   PWM_ACTIVO     sale de RECUPERACION solo si (C-08.2, histéresis de salida)
#                  T >= T_est + brecha_segura_temperatura + _HIST_RECUP_TEMP_K
#                  Y P >= P_sat(T_est) - brecha_segura_presion + _HIST_RECUP_PRES_KPA
#                  -> vapor_camara en PWM, banda fija [-2,+1] kPa sobre
#                  P_sat(T_actual), techo de control
#                  P_control_max = P_sat(T_est) + presion_add_esterilizacion
#                  (fuerza OFF sin importar la banda local)
#
# El disparador por presión (brecha_segura_presion) cubre el caso en que la
# presión cae de forma sostenida mientras la temperatura se mantiene cerca
# o por encima del setpoint (fuga por descompresion_lenta, que corre
# enclavada abierta durante toda la fase, más rápido de lo que el duty
# cycle de PWM_ACTIVO puede compensar).
#
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase, sin depender del tramo
# activo.
#
# Conteo de exposición: se fija al entrar a la fase (t_inicio +
# tiempo_esterilizacion). Se corre hacia adelante el tiempo sin datos de la
# tarjeta (pausar_exposicion, con tope CIC-11) y el tiempo sin lectura del
# Principal o de la presión (C-10.2, tanda 12; sin tope propio: CicloState ya
# falla con SEN-02/SEN-04 en ese caso). Una excursión confirmada de una
# Referencia lo DETIENE y, al volver a la banda, lo REINICIA desde cero
# (C-13, tanda 12). F0 no se reinicia; su timeout (2 x tiempo) no cambia.
#
# Fallas (todas con debounce por TIEMPO, _DEBOUNCE_FALLA_S = 5 s continuos en
# monotonic, C-07.2 tanda 12; una lectura dentro de rango reinicia el conteo):
#   - temp/pres alta/baja del Principal, siempre contra temperatura_esterilizacion
#     fija (nunca T_actual);
#   - saturación (C-03, solo carga sólida): dT = Tsat(P) - T_principal;
#     dT > +2 K -> CIC-12 (aire / no condensables); dT < -2 K -> CIC-13
#     (vapor sobrecalentado o falla de la sonda);
#   - Referencia fuera de banda sin volver en timeout_excursion_referencia
#     -> CIC-14 (C-13.4).
# Una Referencia sin lectura no participa en C-13 (C-13.7b): la vigila
# CicloState (SEN-11, ciclo NO CONFORME, sin abortar).

import math
import time
import logging
from autoclave.core.runtime.steam import p_saturacion_kpa, t_saturacion_c
from autoclave.core.runtime.sensores_ciclo import NOMBRES
from autoclave.state_machine.alarms.catalogo import CIC_09, CIC_11, CIC_12, CIC_13, CIC_14
from autoclave.core.runtime import motivos_fase
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

# C-07.2 (tanda 12): segundos continuos fuera de rango antes de FALLO (antes
# 3 lecturas). También rige C-03 y la confirmación de excursión de C-13.
_DEBOUNCE_FALLA_S = 5.0
# C-03: umbral de |Tsat(P) - T_principal| (K)
_UMBRAL_SATURACION_K = 2.0
# C-08.2: histéresis de salida de RECUPERACION
_HIST_RECUP_TEMP_K = 0.3
_HIST_RECUP_PRES_KPA = 1.0
# C-08.3 (DECISIÓN SIN CONFIRMAR, tanda 12): histéresis del techo de control
# en RECUPERACION: OFF en P >= P_control_max, ON de nuevo bajo P_control_max - 2
_HIST_TECHO_KPA = 2.0
_BANDA_PWM_BAJA = 2.0  # kPa por debajo de P_sat(T_actual) -> vapor ON forzado
_BANDA_PWM_ALTA = 1.0  # kPa por encima de P_sat(T_actual) -> vapor OFF forzado
# D8-2.8 (tanda 8): tope de la suma de pausas sin datos de la tarjeta en una
# exposición (parámetro del equipo pausa_max_esterilizacion_s)
_PAUSA_MAX_DEFECTO_S = 30.0
_PAUSA_MAX_RANGO_S = (5.0, 120.0)
# C-13.4: esterilizacion.timeout_excursion_referencia (min); el JSON lo pone
# J12, aquí el defecto y el rango por si falta o es inválido
_TIMEOUT_EXCURSION_DEFECTO_MIN = 5
_TIMEOUT_EXCURSION_RANGO_MIN = (1, 30)


def _numero(valor) -> bool:
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and math.isfinite(valor))


class EsterilizacionFase(BaseFase):

    name = "ESTERILIZACION"

    def reset(self):
        self._inicializado = False
        self._timer_fin = None
        self._timer_timeout_max = None
        self._tiempo_seg = None
        self._en_recuperacion = True
        self._techo_recup_off = False

        # C-07.2: inicio (monotonic) de cada condición de falla sostenida
        self._falla_desde: dict[str, float] = {}
        # C-13: por Referencia fuera de banda {"desde", "tmin", "tmax",
        # "confirmada"}; CIC-09 una sola vez por ciclo y sensor
        self._ref_fuera: dict[str, dict] = {}
        self._ref_alertada: set[str] = set()
        # C-10.2: inicio del tramo en curso sin lectura del Principal o la presión
        self._sin_lectura_desde = None
        self.sin_lectura_s = 0.0

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
        # C-13.7: restante de exposición para la pantalla (None fuera de la fase)
        self.estado.exposicion_restante_s = None

    # ------------------------------------------------------------------
    # Parámetros
    # ------------------------------------------------------------------

    def _pausa_max_s(self) -> float:
        """pausa_max_esterilizacion_s del equipo, recortado a 5-120 s; sin un
        valor numérico válido, 30 s."""
        try:
            valor = self.config.get("pausa_max_esterilizacion_s")
        except Exception:
            valor = None
        if not _numero(valor):
            return _PAUSA_MAX_DEFECTO_S
        bajo, alto = _PAUSA_MAX_RANGO_S
        return min(max(float(valor), bajo), alto)

    def _timeout_excursion_min(self) -> float:
        """C-13.4: timeout_excursion_referencia (min), recortado a 1-30; sin
        un valor numérico válido, 5 min."""
        try:
            valor = self.cycle.get_param("esterilizacion", "timeout_excursion_referencia",
                                         default=_TIMEOUT_EXCURSION_DEFECTO_MIN)
        except Exception:
            valor = None
        if not _numero(valor):
            return float(_TIMEOUT_EXCURSION_DEFECTO_MIN)
        bajo, alto = _TIMEOUT_EXCURSION_RANGO_MIN
        return float(min(max(valor, bajo), alto))

    def _carga_solida(self) -> bool:
        """C-03 solo con globals.tipo_carga = "solido" (defecto). Un valor
        desconocido se trata como sólido (se vigila: falla segura)."""
        try:
            tipo = self.cycle.get_param("globals", "tipo_carga", default="solido")
        except Exception:
            tipo = "solido"
        return tipo != "liquido"

    # ------------------------------------------------------------------
    # Estado expuesto
    # ------------------------------------------------------------------

    @property
    def exposicion_detenida(self) -> bool:
        """C-13.2: hay una excursión de Referencia confirmada en curso."""
        return any(r["confirmada"] for r in self._ref_fuera.values())

    def _publicar_restante(self, now) -> None:
        """C-13.7: segundos de exposición que faltan (para la pantalla).
        Detenida: el conteo volverá a empezar completo al retornar."""
        try:
            if self._timer_fin is None or self._tiempo_seg is None:
                restante = None
            elif self.exposicion_detenida:
                restante = float(self._tiempo_seg)
            else:
                restante = max(0.0, self._timer_fin - now)
            self.estado.exposicion_restante_s = restante
        except Exception:
            logger.debug("Esterilización: no se pudo publicar el restante", exc_info=True)

    # ------------------------------------------------------------------
    # Salidas y resultados
    # ------------------------------------------------------------------

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_rapida_off()
        self.estado.fase_en_sostenimiento = False

    def _fallo(self, mensaje: str) -> FaseResult:
        logger.error("Esterilización: FALLO — %s", mensaje)
        self._apagar_salidas()
        # C-13.5: una excursión en curso también queda en el ticket
        try:
            ahora = time.monotonic()
            for sensor, registro in list(self._ref_fuera.items()):
                if registro["confirmada"]:
                    self._anotar_excursion(sensor, registro, ahora)
            self._ref_fuera.clear()
        except Exception:
            logger.exception("Esterilización: no se pudieron anotar las excursiones abiertas")
        self.estado.motivo_fallo = mensaje
        self.estado.exposicion_restante_s = None
        return FaseResult.FALLO

    def _fallo_propio(self, codigo_alarma, valores: dict, motivo) -> FaseResult:
        """Mecanismo de CIC-11: CicloState registra `alarma_fallo`."""
        self.alarma_fallo = (codigo_alarma, valores)
        return self._fallo(motivo)

    def _sostenida(self, clave: str, condicion: bool, now: float) -> bool:
        """C-07.2: True si `condicion` se mantiene sin interrupción desde hace
        _DEBOUNCE_FALLA_S. Una lectura dentro de rango reinicia el conteo."""
        if not condicion:
            self._falla_desde.pop(clave, None)
            return False
        desde = self._falla_desde.setdefault(clave, now)
        return now - desde >= _DEBOUNCE_FALLA_S

    # ------------------------------------------------------------------
    # Pausas de la exposición
    # ------------------------------------------------------------------

    def pausar_exposicion(self, segundos) -> None:
        """T2-a (tanda 7, decisión 1.3 de Cristian): los segundos de
        tolerancia por DI vencida (la fase no corrió, vapor cortado) no cuentan
        como exposición: el fin del conteo se corre esos segundos. Antes de
        iniciar el conteo no hay nada que correr. El timeout de F0 no cambia."""
        if self._timer_fin is None:
            return
        if not _numero(segundos) or segundos <= 0:
            return
        self._timer_fin += segundos
        self.pausa_total_s += segundos
        logger.warning("Esterilización: exposición en pausa %.1f s (sin datos de la tarjeta)",
                       segundos)

    def _correr_por_sin_lectura(self, now) -> None:
        """C-10.2: volvió la lectura del Principal y de la presión; el fin de
        la exposición se corre el tramo sin datos (no suma a pausa_total_s)."""
        desde = self._sin_lectura_desde
        if desde is None:
            return
        self._sin_lectura_desde = None
        hueco = max(0.0, now - desde)
        if self._timer_fin is not None:
            self._timer_fin += hueco
        self.sin_lectura_s += hueco
        logger.warning("Esterilización: %.1f s sin lectura del Principal o de la presión; "
                       "el fin de la exposición se corre ese tiempo", hueco)

    # ------------------------------------------------------------------
    # C-13: Referencias
    # ------------------------------------------------------------------

    def _anotar_excursion(self, sensor, registro, now) -> None:
        """C-13.5: línea del ticket con sensor, duración y mínima (y máxima
        si salió por arriba)."""
        try:
            avisos = getattr(self.estado, "avisos_ciclo", None)
            if not isinstance(avisos, list):
                return
            aviso = {"clave": "ticket_ciclo.aviso_excursion",
                     "sensor": NOMBRES.get(sensor, sensor),
                     "duracion": int(round(max(0.0, now - registro["desde"]))),
                     "temp_min": round(float(registro["tmin"]), 1)}
            if registro.get("salio_arriba"):
                aviso["clave"] = "ticket_ciclo.aviso_excursion_alta"
                aviso["temp_max"] = round(float(registro["tmax"]), 1)
            avisos.append(aviso)
        except Exception:
            logger.exception("Esterilización: no se pudo anotar la excursión de %s", sensor)

    def _vigilar_referencias(self, minimo, maximo, now, tiempo_seg) -> FaseResult | None:
        """C-13. Banda [T_est - brecha_error_temperatura, T_est +
        rango_temperatura_ester] para cada Referencia con lectura. Devuelve
        FALLO (CIC-14) si una excursión no vuelve en el timeout; si no, None."""
        timeout_min = self._timeout_excursion_min()
        for sensor, temp in self._temps_referencia().items():
            nombre = NOMBRES.get(sensor, sensor)
            # C-13.7b: sin lectura no participa (no detiene ni reinicia la
            # exposición); lo vigila CicloState (SEN-11, NO CONFORME). Una
            # excursión aún sin confirmar se descarta; una ya confirmada solo
            # la cierra una lectura dentro de la banda, y su timeout sigue
            # corriendo (si no, la fase quedaría detenida sin límite).
            if not _numero(temp) or temp == 0:
                registro = self._ref_fuera.get(sensor)
                if registro is None:
                    continue
                if not registro["confirmada"]:
                    del self._ref_fuera[sensor]
                    continue
                if now - registro["desde"] >= timeout_min * 60:
                    minutos = f"{timeout_min:.0f}"
                    return self._fallo_propio(
                        CIC_14, {"sensor": nombre, "minutos": minutos},
                        motivos_fase.motivo("est_excursion_referencia", sensor=nombre,
                                            minutos=minutos))
                continue
            if minimo <= temp <= maximo:
                registro = self._ref_fuera.pop(sensor, None)
                if registro is not None and registro["confirmada"]:
                    self._anotar_excursion(sensor, registro, now)
                    logger.warning("Esterilización: %s volvió a la banda tras %.0f s",
                                   nombre, now - registro["desde"])
                    if not self.exposicion_detenida:
                        # C-13.3: el conteo se reinicia desde cero
                        self._timer_fin = now + tiempo_seg
                        logger.warning("Esterilización: conteo de exposición reiniciado "
                                       "(%.0f s)", tiempo_seg)
                continue

            registro = self._ref_fuera.get(sensor)
            if registro is None:
                registro = {"desde": now, "tmin": temp, "tmax": temp,
                            "confirmada": False, "salio_arriba": False}
                self._ref_fuera[sensor] = registro
            registro["tmin"] = min(registro["tmin"], temp)
            registro["tmax"] = max(registro["tmax"], temp)
            if temp > maximo:
                registro["salio_arriba"] = True
            transcurrido = now - registro["desde"]

            if not registro["confirmada"] and transcurrido >= _DEBOUNCE_FALLA_S:
                registro["confirmada"] = True
                logger.warning("Esterilización: excursión de %s (%.1f °C, banda %.1f–%.1f °C); "
                               "conteo de exposición detenido", nombre, temp, minimo, maximo)
                if sensor not in self._ref_alertada:
                    self._ref_alertada.add(sensor)
                    try:
                        self.alarm_manager.activar(CIC_09, origen=sensor, sensor=nombre,
                                                   temp=temp, minimo=minimo, maximo=maximo)
                    except Exception:
                        logger.exception("Esterilización: no se pudo registrar CIC-09")

            if registro["confirmada"] and transcurrido >= timeout_min * 60:
                minutos = f"{timeout_min:.0f}"
                return self._fallo_propio(
                    CIC_14, {"sensor": nombre, "minutos": minutos},
                    motivos_fase.motivo("est_excursion_referencia", sensor=nombre,
                                        minutos=minutos))
        return None

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

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
            self._tiempo_seg = tiempo_seg
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
            return self._fallo_propio(
                CIC_11, {"segundos": self.pausa_total_s, "maximo": pausa_max},
                motivos_fase.motivo("est_comunicacion", segundos=f"{self.pausa_total_s:.0f}",
                                    maximo=f"{pausa_max:.0f}"))

        temp = self._temp_principal()
        pres = self._pres_camara()
        now = time.monotonic()

        # ── 1c. C-10.2: sin medición válida no hay exposición ───────────────
        # CicloState falla antes (SEN-02 / SEN-04); esta es la defensa propia.
        if temp is None or pres is None:
            if self._sin_lectura_desde is None:
                self._sin_lectura_desde = now
                logger.warning("Esterilización: sin lectura del Principal o de la presión; "
                               "el conteo de exposición no avanza")
            return FaseResult.EN_CURSO
        self._correr_por_sin_lectura(now)

        # ── 2. Fallas del Principal (5 s continuos, referencia fija t_est) ───
        if self._sostenida("temp_alta", temp > t_est + rango_temp, now):
            return self._fallo(motivos_fase.motivo(
                "est_temp_alta", temp=temp, temp_limite=t_est + rango_temp))
        if self._sostenida("temp_baja", temp < t_est - brecha_err_t, now):
            return self._fallo(motivos_fase.motivo(
                "est_temp_baja", temp=temp, temp_limite=t_est - brecha_err_t))
        if self._sostenida("pres_alta", pres > p_sat_est + rango_pres, now):
            return self._fallo(motivos_fase.motivo(
                "est_pres_alta", pres=pres, pres_limite=p_sat_est + rango_pres))
        if self._sostenida("pres_baja", pres < p_sat_est - brecha_err_p, now):
            return self._fallo(motivos_fase.motivo(
                "est_pres_baja", pres=pres, pres_limite=p_sat_est - brecha_err_p))

        # ── 2a. C-03: saturación (solo carga sólida) ────────────────────────
        if self._carga_solida():
            try:
                t_sat = t_saturacion_c(pres)
            except (ValueError, TypeError):
                t_sat = None        # P <= 0: la presión baja ya lo vigila
            dt = (t_sat - temp) if t_sat is not None else 0.0
            if self._sostenida("aire", dt > _UMBRAL_SATURACION_K, now):
                return self._fallo_propio(
                    CIC_12, {"tsat": t_sat, "temp": temp, "dt": dt},
                    motivos_fase.motivo("est_aire", temp=temp, temp_sat=t_sat,
                                        dt=f"{dt:.1f}"))
            if self._sostenida("sobrecalentado", dt < -_UMBRAL_SATURACION_K, now):
                return self._fallo_propio(
                    CIC_13, {"tsat": t_sat, "temp": temp, "dt": -dt},
                    motivos_fase.motivo("est_sobrecalentado", temp=temp, temp_sat=t_sat,
                                        dt=f"{-dt:.1f}"))

        # ── 2b. C-13: Referencias fuera de banda ───────────────────────────
        # No fallan por sí mismas: detienen el conteo y lo reinician al
        # volver; solo el timeout de la excursión falla (CIC-14).
        resultado_refs = self._vigilar_referencias(t_est - brecha_err_t, t_est + rango_temp,
                                                   now, tiempo_seg)
        if resultado_refs is not None:
            return resultado_refs

        # ── 3. Transición RECUPERACION↔PWM_ACTIVO (C-08) ───────────────────
        # Entrada inmediata (reacción ante pérdida de reserva térmica o de
        # presión); salida con histéresis para no conmutar en cada tick.
        if self._en_recuperacion:
            self._en_recuperacion = not (
                temp >= t_est + brecha_seg + _HIST_RECUP_TEMP_K
                and pres >= p_sat_est - brecha_seg_p + _HIST_RECUP_PRES_KPA
            )
        else:
            self._en_recuperacion = (
                temp < t_est + brecha_seg
                or pres < p_sat_est - brecha_seg_p
            )

        # ── 4. Control de vapor_camara ─────────────────────────────────────
        if self._en_recuperacion:
            # C-08.3: el techo de control también rige en RECUPERACION, con
            # histéresis (DECISIÓN SIN CONFIRMAR de la sesión principal): OFF
            # al llegar a P_control_max y OFF hasta bajar de
            # P_control_max - _HIST_TECHO_KPA. Sin ella, con vapor saturado la
            # salida de C-08.2 (T_est + brecha + 0.3) queda por encima de
            # Tsat(P_control_max) (≈135.0 °C a 134/9) y la válvula conmutaría
            # en cada tick en el techo.
            if pres >= p_control_max:
                self._techo_recup_off = True
            elif pres < p_control_max - _HIST_TECHO_KPA:
                self._techo_recup_off = False
            if self._techo_recup_off:
                self.set_do.vapor_camara_off()
            else:
                self.set_do.vapor_camara_on()
        else:
            self._techo_recup_off = False
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

        self._publicar_restante(now)

        # ── 6. Condición de finalización ─────────────────────────────────
        # Sin F0: el conteo de tiempo, sin importar el tramo de control. Con
        # F0: además, letalidad acumulada suficiente — un timeout de
        # seguridad (2x tiempo_esterilizacion, sin cambios por los reinicios
        # de C-13) cubre el caso en que F0 nunca llega. Con una Referencia
        # fuera de banda (aunque la excursión no esté confirmada todavía) no
        # se termina: se espera a confirmarla o a que vuelva.
        tiempo_cumplido = now >= self._timer_fin and not self._ref_fuera

        if not f0_activo:
            if tiempo_cumplido:
                logger.info("Esterilización: COMPLETADO — %.0f seg completados", tiempo_seg)
                self._apagar_salidas()
                self.estado.exposicion_restante_s = None
                return FaseResult.COMPLETADO
            return FaseResult.EN_CURSO

        f0_cumplido = self.estado.f0_acumulado >= f0_objetivo
        if tiempo_cumplido and f0_cumplido:
            logger.info(
                "Esterilización: COMPLETADO — %.0f seg completados, F0=%.2f/%.1f min",
                tiempo_seg, self.estado.f0_acumulado, f0_objetivo,
            )
            self._apagar_salidas()
            self.estado.exposicion_restante_s = None
            return FaseResult.COMPLETADO

        if now >= self._timer_timeout_max:
            return self._fallo(motivos_fase.motivo(
                "est_timeout_f0", minutos=f"{2 * tiempo_seg / 60:.0f}",
                f0=f"{self.estado.f0_acumulado:.2f}", f0_objetivo=f"{f0_objetivo:.1f}"))

        return FaseResult.EN_CURSO
