# state_machine/cycle_phases/protocolo_fallo.py
#
# Protocolo universal de aborto/fallo.
# Se ejecuta cuando cualquier fase falla, el usuario cancela,
# o se activa el paro de emergencia.
#
# DISPARO (ejecutar — llamar UNA sola vez):
#   1. Apagar todas las salidas
#   2. Según presión inicial:
#        - Presurizada  → válvula del modo de descompresión del programa
#        - Vacío        → aire atmosférico
#        - Normal       → válvula del modo (presión residual)
#        - Desconocida  → descompresión lenta, sin escalar (fin de ciclo §15)
#
# MANTENIMIENTO CONTINUO (update — llamar cada tick):
#   - Presurizada: sigue el modo; si vence su timeout escala a chaqueta +
#     rápida (solo en carga sólida, D-19).
#   - Vacío: cierra las descompresiones y abre aire atmosférico.
#   - Normal: mantiene la válvula del modo, aire atmosférico cerrado.
#   - Cuando se alcanzan condiciones seguras (presión normal Y temperatura
#     del sensor Principal ≤ temp_max_apertura): emite BEEP_FALLO una vez.
#
# Modos 4/5 (PF-19, tanda 2026-10-14 §1.2): primero ENFRIAMIENTO con
# contrapresión de aire comprimido (igual que la fase DESCOMPRESION) hasta que
# el Principal llegue a temperatura_enfriamiento; solo entonces chaqueta +
# rápida. Carga líquida (globals.tipo_carga = "liquido"): la descompresión
# rápida nunca se usa mientras la carga esté caliente: los modos 1/2/3 se
# tratan como lenta y el timeout no escala a la rápida.
#
# Modo 0 (enfriamiento natural, sin timeout) se trata como modo 2 (lenta), con
# el timeout del modo 2 (fin de ciclo; ver informe T5).
#
# finalizar() cierra toda válvula que el protocolo pudo abrir (PF-10: antes
# descompresion_chaqueta quedaba enclavada en los modos 4/5).
#
# D8-2.10 (tanda 8, Cristian): carga líquida en modos 4/5 y se pierde el
# Principal durante el enfriamiento con contrapresión: NO se ventea de
# inmediato. La cámara queda SELLADA (vapor cortado, sin venteo) mientras
# alguna otra sonda válida (Referencia del programa o drenaje) esté por encima
# de temp_max_apertura; con todas las válidas en o por debajo (3 lecturas) se
# ventea por la lenta. Sin ninguna sonda válida, se espera sellado
# espera_sellado_sin_sonda_min (parámetro del equipo) y luego la lenta.
# DECISIÓN SIN CONFIRMAR: el drenaje solo (sin Referencia válida) no autoriza
# el venteo: su agua de enfriamiento lo mantiene frío (ver _tick_sellado).
# DECISIÓN SIN CONFIRMAR (la decisión lo autoriza si el código no deja claro
# cómo mantener la contrapresión): durante la espera sellada TODAS las salidas
# del protocolo quedan cerradas, sin reponer aire comprimido ni enfriar la
# chaqueta. PREGUNTA PARA CRISTIAN en el informe S2a.

import math

import time
import logging
from autoclave.core.runtime.lectura import carga_enfriada, lectura_valida
from autoclave.core.runtime.sensores_ciclo import sensor_principal, sensores_referencia
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.core.runtime import vigencia_ai

logger = logging.getLogger(__name__)

# Reafirmación del aire comprimido de contrapresión (como DescompresionFase)
_PERIODO_AIRE_COMPRIMIDO_SEG = 3.0
_DEBOUNCE_LECTURAS = 3
# D8-2.10: espera sellada sin ninguna sonda válida (parámetro del equipo
# espera_sellado_sin_sonda_min; defecto y rango de la decisión)
_ESPERA_SELLADO_DEFECTO_MIN = 30.0
_ESPERA_SELLADO_RANGO_MIN = (10.0, 240.0)
_SONDA_DRENAJE = "temp_drenaje"
# SAF-11 (re-revisión S2a): el alivio por sobrepresión cierra bajo tope - 5 kPa
_HISTERESIS_ALIVIO_KPA = 5.0


class ProtocoloFallo:

    def __init__(self, estado, set_do, cycle, config):
        self.estado  = estado
        self.set_do  = set_do
        self.cycle   = cycle
        self.config  = config
        # S9 (tanda 9, revisión ★ TMG-02/TMG-03): callable () -> (trama AI
        # vigente, número de trama) que fija el estado seguro (ControlLoop).
        # None: se usa el proveedor común del estado (estado.lectura_ai, que
        # publica el ControlLoop; revisión ★ pasada 2 R2-A1: así también el
        # protocolo del ciclo en CicloState); sin ninguno, la presión
        # publicada se toma como vigente y cada update() cuenta.
        self.lectura_ai = None
        self.reset()

    def reset(self):
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False
        self._presurizado_al_disparo  = False
        self._modo                    = None
        self._sub_etapa                = None
        self._t_timeout_descompresion  = None
        self._escalado                 = False
        self._sin_escalar              = False
        self._aviso_no_escala          = False
        # enfriamiento con contrapresión (modos 4/5)
        self._t_pulso_chaqueta  = None
        self._chaqueta_abierta  = False
        self._t_aire_comprimido = None
        self._lecturas_enfriada = 0
        # P-2 (tanda 6): Principal perdido en ciclo = solo la lenta, sin
        # escalar ni enfriamiento con contrapresión (no se sigue con la
        # Referencia)
        self._solo_lenta        = False
        # SAF-01 / SEN-02 / TMG-07 (revisión Q1): lecturas inválidas seguidas
        # del Principal con el protocolo en marcha antes de pasar a solo_lenta
        self._lecturas_principal_perdido = 0
        # D8-2.10: espera sellada (líquidos, modos 4/5, Principal perdido en
        # el enfriamiento con contrapresión)
        self._sellado = False
        self._lecturas_sondas_frias = 0
        self._sin_sonda_desde = None
        self._motivo_venteo = None
        # SAF-01 (revisión S2a): alivio por sobrepresión con la cámara sellada
        self._lecturas_sobrepresion = 0
        self._alivio_abierto = False
        # TMG-03 (revisión S2a): lecturas calientes seguidas antes de desarmar
        # la espera sin sonda
        self._lecturas_con_sonda = 0
        # S1 (revisión ★ SAF-03): causa del paso a solo_lenta con el protocolo
        # en marcha, para el registro del estado seguro
        self.motivo_solo_lenta = "sensor Principal sin lectura"
        # S9 (tanda 9, D9-1.4): presión de cámara sin lectura confirmada con
        # 3 lecturas (y de vuelta con 3 válidas): el estado seguro queda
        # detenido (CIC-10) sin abrir nada nuevo
        self._lecturas_presion_perdida = 0
        self._lecturas_presion_vuelta = 0
        self._presion_perdida = False
        # S9, revisión ★ TMG-03: número de la última trama AI contada
        self._seq_presion = None
        # S9, revisión ★ TMG-02: la trama AI de este update() está vigente
        self._ai_vigente_tick = True
        # S9, revisión ★ SAF-03: lecturas de vacío seguidas antes de abrir el
        # aire atmosférico (R2-M2: tramas AI distintas)
        self._lecturas_vacio = 0
        self._seq_vacio = None
        # R2-M1: aviso en el log una vez por tramo con la trama AI vencida
        self._aviso_ai_vencida = False
        # R3-A1 (revisión ★ pasada 3): decisión inicial de ejecutar() que
        # quedó PENDIENTE por la trama AI vencida ("abrir": la del disparo
        # normal; "presurizado": solo marcar la presión al disparo, como con
        # abrir_valvulas=False o la cámara sellada). La toma el primer
        # update() con la AI vigente.
        self._decision_pendiente = None
        # R3-A1: reanudar() ya corrió (el timeout de escalada se arma ahí)
        self._reanudado = False

    @property
    def sellado(self) -> bool:
        """D8-2.10: True mientras la cámara espera sellada (sin venteo y con
        todas las salidas del protocolo cerradas) a que las sondas válidas
        confirmen la temperatura o venza la espera sin sonda."""
        return self._sellado

    @property
    def motivo_venteo(self) -> str | None:
        """D8-2.10: por qué terminó la espera sellada ("sondas_frias" o
        "espera_sin_sonda"), o None si no la hubo o sigue sellada."""
        return self._motivo_venteo

    @property
    def presion_perdida(self) -> bool:
        """Tanda 17 (ESG-01): el protocolo está detenido porque la presión de
        cámara no tiene lectura (confirmado con el debounce de S9, D9-1.4).
        Con esto el estado seguro no activa CIC-10 (solo la alarma del sensor)."""
        return self._presion_perdida is True

    @property
    def solo_lenta(self) -> bool:
        """True si el protocolo se disparó por la pérdida del Principal o si
        el Principal se perdió después, con el protocolo ya en marcha (R1-P4)."""
        return self._solo_lenta

    def _principal_perdido(self) -> bool:
        """Principal sin lectura: None, no finito o 0 (mismo criterio que P-2
        en CicloState y que bloqueado_motivo)."""
        temp = self._temp_principal()
        return not lectura_valida(temp) or temp == 0

    def _leer_ai(self) -> tuple[bool, int | None]:
        """S9 (revisión ★ TMG-02/TMG-03): (trama AI vigente, su número). Usa
        lectura_ai o, sin ella, el proveedor común del estado (R2-A1). Sin
        ninguno: (True, None). Ante un error: (False, None)."""
        return vigencia_ai.leer(self.estado, self.lectura_ai)

    def _pres_camara(self):
        """Presión de cámara publicada; None si la trama AI de este update()
        está vencida (S9, revisión ★ TMG-02: la tarjeta manda DI pero no AI y
        Units conserva la última presión, congelada)."""
        if not self._ai_vigente_tick:
            return None
        return self.estado.sensores_pres.get("pres_camara")

    def _presion_camara_perdida(self) -> bool:
        """S1 (tanda 8, revisión ★ SAF-02): transductor de presión de cámara
        sin lectura (el convertidor ya exigió 3 tramas fuera de rango y
        entrega None, nunca 0). Mismo criterio que el Principal perdido.
        S9, revisión ★ pasada 2 (R2-M1): SOLO con la trama AI vigente (el
        transductor manda tramas sin lectura válida). La AI vencida son datos
        no vigentes, no un transductor perdido: no enclava solo_lenta."""
        if not self._ai_vigente_tick:
            return False
        return not lectura_valida(self.estado.sensores_pres.get("pres_camara"))

    def pasar_a_solo_lenta(self) -> bool:
        """R1-P4 (tanda 7, decisión 1.3 de Cristian): el protocolo ya corría
        por otra causa (fallo de fase, cancelación, puerta, paro...) y después
        se perdió el Principal. Se aplica el criterio de P-2 sin importar el
        orden: solo la lenta, sin escalar ni enfriar con contrapresión. Cierra
        lo que el modo pudo abrir (rápida, chaqueta, contrapresión, agua de
        chaqueta) y abre la lenta en este mismo paso (TMG-06 / SEN-04 de la
        revisión Q1: antes la abría el siguiente update(), que sin presión
        retorna sin abrir nada), salvo vacío confirmado; con la presión
        desconocida la abre igual (mismo criterio que ejecutar()). Es un
        enclavamiento: no se revierte aunque el Principal vuelva a leer.
        Devuelve True si cambió el modo."""
        if self._solo_lenta:
            return False
        logger.error("Protocolo fallo: Principal o presión de cámara sin lectura con el "
                     "protocolo en marcha (modo %s) — se pasa a solo la descompresión lenta",
                     self._modo)
        # D8-2.10: decidir antes de limpiar la sub-etapa. Integración S1+S2a
        # (DECISIÓN SIN CONFIRMAR): se sella solo si la presión de cámara lee;
        # sin presión no habría alivio por sobrepresión posible (SAF-01), así
        # que rige D8-1.2 (venteo solo por la lenta).
        sellar = (self._enfriando_con_contrapresion()
                  and not self._presion_camara_perdida())
        self._solo_lenta = True
        self._sin_escalar = True
        self._escalado = False
        self._sub_etapa = None
        self._t_pulso_chaqueta = None
        self._chaqueta_abierta = False
        self.set_do.descompresion_rapida_off()
        self.set_do.descompresion_chaqueta_off()
        self._fin_enfriamiento(cerrar_lenta=False)
        if sellar:
            self._iniciar_sellado()
            return True
        pres  = self._pres_camara()
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0
        if not lectura_valida(pres) or pres >= atm - rango:
            self.set_do.descompresion_lenta_on()
        return True

    # ------------------------------------------------------------------
    # D8-2.10 — espera sellada (líquidos, modos 4/5)
    # ------------------------------------------------------------------

    def _enfriando_con_contrapresion(self) -> bool:
        """Carga líquida, modo 4/5, sub-etapa de enfriamiento y la cámara
        estaba presurizada al disparo (solo entonces se aplica contrapresión,
        SAF-03 de T5)."""
        return (self._modo_efectivo() in (4, 5) and self._sub_etapa == "enfriamiento"
                and self._presurizado_al_disparo and self.es_liquido())

    def _cerrar_todo_sellado(self, lenta_alivio: bool = False) -> None:
        """Cámara sellada: vapor cortado y ninguna válvula del protocolo
        abierta (ni venteo, ni aire, ni agua de chaqueta). `lenta_alivio`:
        la lenta queda abierta solo como alivio de sobrepresión (SAF-01)."""
        self.set_do.vapor_camara_off()
        self.set_do.vapor_chaqueta_off()
        if lenta_alivio:
            self.set_do.descompresion_lenta_on()
        else:
            self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_rapida_off()
        self.set_do.descompresion_chaqueta_off()
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()
        self.set_do.aire_admosferico_camara_off()
        self._t_aire_comprimido = None
        self._t_pulso_chaqueta = None
        self._chaqueta_abierta = False

    def _iniciar_sellado(self) -> None:
        logger.error("Protocolo fallo: carga líquida sin Principal durante el enfriamiento "
                     "con contrapresión — cámara SELLADA, sin venteo (D8-2.10)")
        self._sellado = True
        self._sin_escalar = True
        self._escalado = False
        self._sub_etapa = None
        self._lecturas_sondas_frias = 0
        self._sin_sonda_desde = None
        self._motivo_venteo = None
        self._lecturas_sobrepresion = 0
        self._alivio_abierto = False
        self._lecturas_con_sonda = 0
        self._cerrar_todo_sellado()

    def _espera_sellado_sin_sonda_s(self) -> float:
        """espera_sellado_sin_sonda_min del equipo en segundos, recortado a
        10-240 min; sin un valor numérico válido, 30 min."""
        try:
            valor = self.config.get("espera_sellado_sin_sonda_min")
        except Exception:
            valor = None
        if (isinstance(valor, bool) or not isinstance(valor, (int, float))
                or not math.isfinite(valor)):
            return _ESPERA_SELLADO_DEFECTO_MIN * 60.0
        bajo, alto = _ESPERA_SELLADO_RANGO_MIN
        return min(max(float(valor), bajo), alto) * 60.0

    def _temp_max_sellado(self) -> float:
        """temp_max_apertura global; con el del programa, rige el menor (como
        camara_segura y la apertura automática)."""
        temp_max = self.config.get("temp_max_apertura") or 120.0
        try:
            del_ciclo = self.cycle.get_param("finalizacion", "temp_max_apertura")
        except Exception:
            del_ciclo = None
        if (not isinstance(del_ciclo, bool) and isinstance(del_ciclo, (int, float))
                and math.isfinite(del_ciclo)):
            temp_max = min(float(temp_max), float(del_ciclo))
        return float(temp_max)

    def _tope_presion_sellado(self) -> float:
        """SAF-01 (revisión S2a): presión máxima con la cámara sellada. Con el
        vapor cortado y sin aire, la presión solo debería bajar; si sube, hay
        aporte (fuga de vapor). Tope = el mayor entre la contrapresión de
        enfriamiento del modo y P_sat(temperatura_esterilizacion), más
        rango_presion_ester (umbral de falla de presión alta de
        ESTERILIZACION). DECISIÓN SIN CONFIRMAR."""
        modo_key = f"modo_{self._modo_efectivo()}"

        def numero(valor, defecto):
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) \
                    or not math.isfinite(valor):
                return defecto
            return float(valor)
        try:
            p_enfr = numero(self.cycle.get_param("descompresion", modo_key,
                                                 "presion_camara_enfriamiento", default=200), 200.0)
            t_est = numero(self.cycle.get_param("esterilizacion", "temperatura_esterilizacion",
                                                default=121.0), 121.0)
            rango = numero(self.cycle.get_param("esterilizacion", "rango_presion_ester",
                                                default=30.0), 30.0)
        except Exception:
            p_enfr, t_est, rango = 200.0, 121.0, 30.0
        return max(p_enfr, p_saturacion_kpa(t_est)) + rango

    def _alivio_sobrepresion(self) -> bool:
        """SAF-01: True si la lenta debe abrirse como alivio. Abre con 3
        lecturas seguidas sobre el tope y cierra con 3 lecturas seguidas bajo
        tope - _HISTERESIS_ALIVIO_KPA (SAF-11). Sin lectura de presión: no se
        abre (no hay evidencia de sobrepresión), pero si ya estaba abierto
        sigue abierto (SAF-08: una lectura perdida en plena sobrepresión no
        cierra el alivio)."""
        pres = self._pres_camara()
        if not lectura_valida(pres):
            self._lecturas_sobrepresion = 0
            return self._alivio_abierto
        tope = self._tope_presion_sellado()
        if not self._alivio_abierto:
            self._lecturas_sobrepresion = self._lecturas_sobrepresion + 1 if pres > tope else 0
            if self._lecturas_sobrepresion >= _DEBOUNCE_LECTURAS:
                logger.error("Protocolo fallo: sobrepresión con la cámara sellada (%.1f kPa > "
                             "%.1f kPa) — alivio por la lenta", pres, tope)
                self._alivio_abierto = True
                self._lecturas_sobrepresion = 0
        else:
            bajo = pres <= tope - _HISTERESIS_ALIVIO_KPA
            self._lecturas_sobrepresion = self._lecturas_sobrepresion + 1 if bajo else 0
            if self._lecturas_sobrepresion >= _DEBOUNCE_LECTURAS:
                logger.warning("Protocolo fallo: presión de nuevo bajo el tope (%.1f kPa) — "
                               "se cierra el alivio", pres)
                self._alivio_abierto = False
                self._lecturas_sobrepresion = 0
        return self._alivio_abierto

    def _sondas_validas(self) -> tuple[list, float | None]:
        """(Referencias, drenaje): lecturas válidas (finitas y distintas de 0)
        de las Referencias del programa y del drenaje (None si no lee). El
        Principal nunca cuenta."""
        principal = sensor_principal(self.cycle)
        refs = []
        for s in sensores_referencia(self.cycle):
            if s == principal or s == _SONDA_DRENAJE:
                continue
            valor = self.estado.sensores_temp.get(s)
            if lectura_valida(valor) and valor != 0:
                refs.append(float(valor))
        drenaje = None
        if principal != _SONDA_DRENAJE:
            valor = self.estado.sensores_temp.get(_SONDA_DRENAJE)
            if lectura_valida(valor) and valor != 0:
                drenaje = float(valor)
        return refs, drenaje

    def _ventear_tras_sellado(self, motivo: str) -> None:
        logger.warning("Protocolo fallo: fin de la espera sellada (%s) — venteo por la lenta",
                       motivo)
        self._sellado = False
        self._motivo_venteo = motivo
        self._sin_sonda_desde = None
        self._lecturas_sondas_frias = 0
        # Abre la lenta en este mismo paso (como pasar_a_solo_lenta), salvo
        # vacío confirmado; con la presión desconocida la abre igual
        pres  = self._pres_camara()
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0
        if not lectura_valida(pres) or pres >= atm - rango:
            self.set_do.descompresion_lenta_on()

    def _tick_sellado(self) -> None:
        """Un tick de la espera sellada: mantiene todo cerrado y decide si ya
        se puede ventear por la lenta."""
        self._cerrar_todo_sellado(lenta_alivio=self._alivio_sobrepresion())
        refs, drenaje = self._sondas_validas()
        temp_max = self._temp_max_sellado()
        validas = refs + ([drenaje] if drenaje is not None else [])
        # SAF-02 (revisión S2a): si el Principal vuelve a leer, también veta
        # el venteo mientras esté caliente (nunca lo autoriza: el
        # enclavamiento de solo_lenta no se revierte)
        principal = self._temp_principal()
        if lectura_valida(principal) and principal != 0:
            validas.append(float(principal))
        if any(t > temp_max for t in validas):
            # alguna sonda válida caliente: sigue sellada. TMG-03 (revisión
            # S2a): la espera sin sonda solo se desarma con 3 lecturas
            # calientes seguidas (una sonda que va y viene no la reinicia)
            self._lecturas_sondas_frias = 0
            self._lecturas_con_sonda += 1
            if self._lecturas_con_sonda >= _DEBOUNCE_LECTURAS:
                self._sin_sonda_desde = None
            return
        self._lecturas_con_sonda = 0
        if refs:
            # todas las válidas en o por debajo de temp_max_apertura
            self._lecturas_sondas_frias += 1
            if self._lecturas_sondas_frias >= _DEBOUNCE_LECTURAS:
                self._ventear_tras_sellado("sondas_frias")
            elif self._sin_sonda_desde is not None:
                self._revisar_espera_sin_sonda()
            return
        # DECISIÓN SIN CONFIRMAR (S2a, ensayo con la planta simulada): el
        # drenaje solo NO autoriza el venteo. Su agua de enfriamiento lo
        # mantiene bajo temp_segura_drenaje (70 °C por defecto, menor que
        # temp_max_apertura, 80 °C) aunque la carga siga caliente, y con la
        # cámara sellada no circula vapor por él. Caliente, sí mantiene el
        # sellado (arriba); frío y sin Referencias válidas, rige la espera
        # sin sonda. PREGUNTA PARA CRISTIAN en el informe S2a.
        self._lecturas_sondas_frias = 0
        if self._sin_sonda_desde is None:
            self._sin_sonda_desde = time.monotonic()
            logger.error("Protocolo fallo: cámara sellada sin ninguna sonda válida — "
                         "espera de %.0f min antes de ventear",
                         self._espera_sellado_sin_sonda_s() / 60)
        self._revisar_espera_sin_sonda()

    def _revisar_espera_sin_sonda(self) -> None:
        if (self._sin_sonda_desde is not None
                and time.monotonic() - self._sin_sonda_desde >= self._espera_sellado_sin_sonda_s()):
            self._ventear_tras_sellado("espera_sin_sonda")

    @property
    def ejecutado(self) -> bool:
        return self._ejecutado

    # ------------------------------------------------------------------
    # Datos del programa
    # ------------------------------------------------------------------

    def es_liquido(self) -> bool:
        try:
            return self.cycle.get_param("globals", "tipo_carga", default="solido") == "liquido"
        except Exception:
            return True     # SAF-12 de T5: ante la duda, sin la rápida

    def _modo_efectivo(self) -> int:
        return 2 if not self._modo else self._modo

    def _temp_principal(self):
        return self.estado.sensores_temp.get(sensor_principal(self.cycle))

    def _temp_enfriamiento(self) -> float:
        valor = self.cycle.get_param("descompresion", f"modo_{self._modo_efectivo()}",
                                     "temperatura_enfriamiento", default=80.0)
        return float(valor) if valor is not None else 80.0

    def _enfriada(self) -> bool:
        # SAF-01 de T11: un 0 (sensor sin señal) no cuenta como enfriada
        return carga_enfriada(self._temp_principal(), self._temp_enfriamiento())

    def _enfriada_confirmada(self) -> bool:
        """3 lecturas seguidas bajo temperatura_enfriamiento (SAF-06 de T5):
        un valor espurio no habilita la rápida."""
        self._lecturas_enfriada = self._lecturas_enfriada + 1 if self._enfriada() else 0
        return self._lecturas_enfriada >= _DEBOUNCE_LECTURAS

    def bloqueado_motivo(self, incluir_presion: bool = True) -> str | None:
        """Motivo por el que el protocolo no puede terminar solo (SAF-04 de
        T5): lo muestra el estado seguro como alarma. None si avanza.

        Tanda 17 (ESG-01, corrección R3 V17-s3-02): con `incluir_presion`
        False se omite la presión de cámara sin lectura y se da el siguiente
        motivo (bloqueado_motivo_sin_presion). Se publica como propiedad más
        abajo; los textos quedan en esta función (los recorre
        tests/test_v8b_textos.py)."""
        if not self._ejecutado:
            return None
        temp = self._temp_principal()
        if incluir_presion and self._presion_perdida:
            # S9 (D9-1.4): sin presión de cámara no se puede confirmar la
            # cámara segura; primero que el Principal (sin presión, nada termina)
            # T10 (tanda 10, D10-3): solo el texto; misma condición y prioridad
            return ("Sensor de presión de cámara sin lectura: sin el sensor de presión de "
                    "cámara no se puede llevar la cámara a estado seguro. Revise la conexión "
                    "del sensor de presión de cámara o llame a servicio técnico")
        if self._sellado:
            return ("Sensor Principal sin lectura con carga líquida: cámara sellada hasta que "
                    "las sondas confirmen la temperatura o venza la espera")
        if self._solo_lenta and (not lectura_valida(temp) or temp == 0):
            return "Sensor Principal sin lectura: el estado seguro no puede confirmar la temperatura"
        if self._modo_efectivo() in (4, 5) and self._sub_etapa == "enfriamiento"                 and not lectura_valida(self._temp_principal()):
            return "Sensor Principal sin lectura: no se puede confirmar el enfriamiento"
        if self._aviso_no_escala:
            return "Tiempo límite de descompresión con carga líquida caliente: no se usa el escape rápido"
        return None

    _motivo_bloqueo = bloqueado_motivo
    bloqueado_motivo = property(bloqueado_motivo)

    @property
    def bloqueado_motivo_sin_presion(self) -> str | None:
        """Tanda 17 (ESG-01, corrección R3 V17-s3-02): el motivo de bloqueo
        sin contar la presión de cámara sin lectura, con la misma prioridad que
        bloqueado_motivo para los demás. Con la presión perdida, el estado
        seguro activa CIC-10 solo con este (sellado, Principal sin lectura,
        líquidos calientes); None si no hay otro motivo."""
        return self._motivo_bloqueo(incluir_presion=False)

    # ------------------------------------------------------------------
    # DISPARO — llamar UNA vez al detectar el fallo
    # ------------------------------------------------------------------

    def ejecutar(self, abrir_valvulas: bool = True, solo_lenta: bool = False,
                 en_enfriamiento_contrapresion: bool = False):
        """`abrir_valvulas` False (paro de emergencia, fin de ciclo §15.1):
        solo apaga todo y registra el modo; las válvulas las abre update()
        cuando el protocolo de estado seguro lo permita.

        `solo_lenta` (P-2, tanda 6): el sensor Principal se perdió en ciclo.
        Se ventea solo por la lenta, sin escalar a la rápida ni enfriar con
        contrapresión (sin Principal no se puede confirmar la temperatura de
        la carga), sea cual sea el modo del programa.

        `en_enfriamiento_contrapresion` (D8-2.10): la fase DESCOMPRESION estaba
        enfriando con contrapresión (modos 4/5). Con `solo_lenta` y carga
        líquida, la cámara queda sellada (ALL_OFF, sin abrir nada) en vez de
        ventear por la lenta."""
        if self._ejecutado:
            return
        if solo_lenta:
            self._solo_lenta = True
            self._sin_escalar = True

        logger.warning("Protocolo de fallo ejecutado — apagando todas las salidas")

        # 1. Todas las salidas a cero (si no hay enlace serial, esto puede no
        # confirmarse — se reintenta en update() hasta que se confirme).
        self._salidas_apagadas = self.set_do.reset_all_outputs()

        # 2. Válvula de seguridad inicial según estado de la cámara. R2-B3
        # (revisión ★ pasada 2): con la presión vigente; con la trama AI
        # vencida no se abre nada (datos no vigentes, R2-M1)
        self._ai_vigente_tick, seq_ai = self._leer_ai()
        pres  = self._pres_camara()
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        self._modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
        modo = self._modo_efectivo()
        self._sub_etapa = ("lenta" if modo == 3
                           else "enfriamiento" if modo in (4, 5) else None)
        if self._solo_lenta:
            self._sub_etapa = None

        if (self._solo_lenta and en_enfriamiento_contrapresion
                and modo in (4, 5) and self.es_liquido()):
            if not self._ai_vigente_tick:
                self._decision_pendiente = "presurizado"      # R3-A1
            elif pres is not None and pres > atm + rango:
                self._presurizado_al_disparo = True
            self._iniciar_sellado()
            self._ejecutado = True
            return

        if not self._ai_vigente_tick:
            # R3-A1 (revisión ★ pasada 3): sin presión vigente la decisión
            # inicial (presurizada al disparo, timeout del modo, válvula del
            # modo, vacío) queda PENDIENTE con todo cerrado; la toma el primer
            # update() con la trama AI vigente
            self._decision_pendiente = "abrir" if abrir_valvulas else "presurizado"
            logger.error("Protocolo fallo: trama AI vencida al disparar — salidas apagadas; "
                         "la decisión inicial espera datos vigentes")
            self._ejecutado = True
            return

        self._decision_inicial(pres, seq_ai, abrir_valvulas)
        self._ejecutado = True

    def _decision_inicial(self, pres, seq_ai, abrir_valvulas: bool) -> None:
        """Válvula de seguridad inicial según el estado de la cámara (paso 2
        de ejecutar(); R3-A1: también, diferida, desde update())."""
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0
        if not abrir_valvulas:
            if pres is not None and pres > atm + rango:
                # el timeout se arma al abrir válvulas (reanudar), no durante
                # el paro ni la espera de confirmación (TMG-02 de T5)
                self._presurizado_al_disparo = True
            logger.warning("Protocolo fallo: paro de emergencia — salidas apagadas, "
                           "sin válvulas")
        elif pres is None:
            # Fin de ciclo §15: presión desconocida → la lenta y sin escalar
            logger.warning("Protocolo fallo: presión desconocida — descompresión lenta sin escalar")
            self._sin_escalar = True
            self.set_do.descompresion_lenta_on()
        elif pres > atm + rango:
            self._presurizado_al_disparo = True
            self._t_timeout_descompresion = self._calcular_timeout()
            logger.warning(
                "Protocolo fallo: cámara presurizada (%.1f kPa) → modo de descompresión %d%s",
                pres, self._modo, " (carga líquida)" if self.es_liquido() else "",
            )
            self._aplicar_paso_modo(pres)
        elif pres < atm - rango:
            # Vacío real → aire atmosférico, ninguna válvula de descompresión.
            # R2-B3: esta es la primera lectura de vacío; update() abre el
            # aire con la tercera (SAF-03)
            logger.warning(
                "Protocolo fallo: cámara en vacío (%.1f kPa) → aire atmosférico tras 3 lecturas",
                pres
            )
            self._lecturas_vacio = 1
            self._seq_vacio = seq_ai
        else:
            # Rango normal, sin presión que evacuar → deja la válvula
            # de descompresión del modo configurado
            logger.warning(
                "Protocolo fallo: presión normal (%.1f kPa) → válvula del modo %d",
                pres, self._modo
            )
            self._aplicar_paso_modo(pres)

    def _tomar_decision_pendiente(self, seq_ai) -> bool:
        """R3-A1: primer update() con la trama AI vigente tras un disparo con
        la AI vencida. Devuelve True si este update() ya actuó (decisión
        "abrir": como el disparo normal, el resto queda para el siguiente)."""
        modo, self._decision_pendiente = self._decision_pendiente, None
        pres = self._pres_camara()
        if not lectura_valida(pres):
            pres = None
        logger.warning("Protocolo fallo: datos vigentes — se toma la decisión inicial "
                       "pendiente (%s, presión %s)", modo, pres)
        if modo == "abrir":
            self._decision_inicial(pres, seq_ai, True)
            return True
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0
        if pres is not None and pres > atm + rango:
            self._presurizado_al_disparo = True
            # si reanudar() ya corrió, el plazo del modo empieza ahora
            if (self._reanudado and not self._escalado and not self._sin_escalar
                    and self._t_timeout_descompresion is None):
                self._t_timeout_descompresion = self._calcular_timeout()
        return False

    # ------------------------------------------------------------------
    # Estrategia de válvulas según el modo de descompresión del ciclo
    # ------------------------------------------------------------------

    def _referencia_atm_configurada(self) -> bool:
        """S9, revisión ★ pasada 3 (b): presión atmosférica de referencia y
        su brecha configuradas (números finitos, positivos). Sin ellas el
        protocolo sigue usando 101,3 / 20 kPa para el resto, pero NO abre el
        aire atmosférico: en un sitio de altura (p. ej. 75 kPa) el defecto
        leería vacío con la cámara a la atmósfera."""
        for clave in ("presion_admosferica", "rango_presion_atm"):
            try:
                v = self.config.get(clave)
            except Exception:
                return False
            if (isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(v) or v <= 0):
                return False
        return True

    def _calcular_timeout(self) -> float:
        timeout_key = f"modo_{self._modo_efectivo()}"
        timeout_min = self.cycle.get_param("descompresion", timeout_key, "timeout", default=60)
        return time.monotonic() + (timeout_min or 60) * 60

    def _aplicar_paso_modo(self, pres: float) -> None:
        if self._solo_lenta:
            # P-2: solo la lenta (la rápida la cerró el ALL_OFF y nadie la abre)
            self.set_do.descompresion_lenta_on()
            return
        if self._escalado:
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
            return

        modo_efectivo = self._modo_efectivo()

        if modo_efectivo in (4, 5):
            if self._sub_etapa == "enfriamiento":
                if self._enfriada_confirmada():
                    logger.info("Protocolo fallo: carga a temperatura de enfriamiento → "
                                "despresurización con chaqueta + rápida")
                    self._fin_enfriamiento()
                    self._sub_etapa = "descompresion"
                elif (self._presurizado_al_disparo and self.es_liquido()
                      and self._principal_perdido()):
                    # D8-2.10: carga líquida con el Principal sin lectura en el
                    # enfriamiento con contrapresión: nunca ventear de
                    # inmediato. Se cierra todo mientras corre el debounce;
                    # con 3 lecturas, pasar_a_solo_lenta() sella del todo.
                    self._cerrar_todo_sellado()
                    return
                elif self._presurizado_al_disparo and lectura_valida(self._temp_principal()):
                    # Contrapresión solo si la cámara estaba presurizada al
                    # disparo (SAF-03 de T5): nunca presurizar una cámara que
                    # estaba a presión atmosférica o en vacío.
                    self.set_do.aire_admosferico_camara_off()
                    self._tick_enfriamiento(pres)
                    return
                else:
                    # Sin contrapresión (no estaba presurizada, o el Principal
                    # no lee: lenta y sin escalar, SAF-04 de T5)
                    if not lectura_valida(self._temp_principal()):
                        self._sin_escalar = True
                    self._fin_enfriamiento(cerrar_lenta=False)
                    atm = self.config.get("presion_admosferica") or 101.3
                    rango = self.config.get("rango_presion_atm") or 20.0
                    if pres < atm - rango:
                        # S9, revisión ★ SAF-03: aire solo con 3 lecturas de
                        # vacío seguidas (contadas en update())
                        self.set_do.descompresion_lenta_off()
                        self.set_do.descompresion_chaqueta_off()
                        if (self._lecturas_vacio >= _DEBOUNCE_LECTURAS
                                and self._referencia_atm_configurada()):
                            self.set_do.aire_admosferico_camara_on()
                    else:
                        self.set_do.aire_admosferico_camara_off()
                        self.set_do.descompresion_lenta_on()
                    return
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
            return

        if self.es_liquido():
            # Líquidos: nunca la rápida con la carga caliente (tanda §1.2)
            self.set_do.descompresion_lenta_on()
            return

        if modo_efectivo == 1:
            self.set_do.descompresion_rapida_on()
        elif modo_efectivo == 2:
            self.set_do.descompresion_lenta_on()
        elif modo_efectivo == 3:
            if self._sub_etapa == "lenta":
                presion_cambio = self.cycle.get_param(
                    "descompresion", "modo_3", "presion_cambio", default=150
                )
                self.set_do.descompresion_lenta_on()
                if pres <= presion_cambio:
                    self.set_do.descompresion_lenta_off()
                    self._sub_etapa = "rapida"
            else:
                self.set_do.descompresion_rapida_on()

    def _tick_enfriamiento(self, pres: float) -> None:
        """Enfriamiento con contrapresión (mismo patrón que la fase
        DESCOMPRESION, modos 4/5): aire comprimido hasta la presión de
        enfriamiento, agua de chaqueta y pulsos de la descompresión de
        chaqueta; en modo 5 además la lenta."""
        now = time.monotonic()
        modo_key = f"modo_{self._modo_efectivo()}"
        presion_obj = self.cycle.get_param("descompresion", modo_key,
                                           "presion_camara_enfriamiento", default=200)
        if pres < presion_obj:
            if self._t_aire_comprimido is None or now >= self._t_aire_comprimido:
                self.set_do.aire_comprimido_camara_on()
                self._t_aire_comprimido = now + _PERIODO_AIRE_COMPRIMIDO_SEG
        else:
            self.set_do.aire_comprimido_camara_off()
            self._t_aire_comprimido = None

        self.set_do.agua_chaqueta_on()
        if self._modo_efectivo() == 5:
            self.set_do.descompresion_lenta_on()

        t_on  = self.cycle.get_param("descompresion", modo_key, "tiempo_apertura_chaqueta", default=5)
        t_off = self.cycle.get_param("descompresion", modo_key, "tiempo_cierre_chaqueta",   default=10)
        if not t_off:
            self.set_do.descompresion_chaqueta_on()
        elif self._t_pulso_chaqueta is None:
            self._t_pulso_chaqueta = now
            self._chaqueta_abierta = True
            self.set_do.descompresion_chaqueta_on()
        else:
            transcurrido = now - self._t_pulso_chaqueta
            if self._chaqueta_abierta and transcurrido >= (t_on or 0):
                self.set_do.descompresion_chaqueta_off()
                self._chaqueta_abierta = False
                self._t_pulso_chaqueta = now
            elif not self._chaqueta_abierta and transcurrido >= t_off:
                self.set_do.descompresion_chaqueta_on()
                self._chaqueta_abierta = True
                self._t_pulso_chaqueta = now

    def _fin_enfriamiento(self, cerrar_lenta: bool = True) -> None:
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()
        if cerrar_lenta:
            self.set_do.descompresion_lenta_off()
        self._t_aire_comprimido = None

    # ------------------------------------------------------------------
    # MANTENIMIENTO — llamar en cada tick mientras se espera confirmación
    # y, después, desde el protocolo de estado seguro (fin de ciclo §15)
    # ------------------------------------------------------------------

    def update(self):
        if not self._ejecutado:
            return

        # Reintentar el apagado si la primera confirmación (ACK de ALL_OFF)
        # no llegó — p.ej. porque el enlace serial cayó justo al fallar.
        if not self._salidas_apagadas:
            self._salidas_apagadas = self.set_do.reset_all_outputs()
            if self._salidas_apagadas:
                logger.info("Protocolo fallo: apagado de salidas confirmado tras reintento")
        else:
            # s3 (tanda 16, V-02): con el ALL_OFF ya confirmado, se reafirma el
            # corte del aporte de vapor en cada llamada (una orden perdida o una
            # salida reencendida no queda así). Solo dos órdenes por tick: el
            # SetOutput no deduplica, pero el protocolo nunca enciende estas
            # salidas, así que no hay conflicto con ninguna rama de abajo.
            self.set_do.vapor_camara_off()
            self.set_do.vapor_chaqueta_off()

        # S9, revisión ★ TMG-02/TMG-03: vigencia y número de la trama AI de
        # este update(); con la AI vencida la presión cuenta como perdida
        self._ai_vigente_tick, seq_ai = self._leer_ai()
        self._seguir_presion_perdida(seq_ai)
        if self._decision_pendiente is not None:
            if not self._ai_vigente_tick:
                # R3-A1: decisión inicial pendiente: todo cerrado (el ALL_OFF
                # del disparo), ninguna válvula nueva
                self.set_do.aire_comprimido_camara_off()
                self._t_aire_comprimido = None
                return
            if self._tomar_decision_pendiente(seq_ai):
                return
        if not self._ai_vigente_tick:
            # R2-M1 (revisión ★ pasada 2, DECISIÓN SIN CONFIRMAR de la sesión
            # principal): trama AI vencida = datos NO vigentes, como la DI
            # vencida. Presión y temperaturas pueden estar congeladas: no se
            # abre nada nuevo (ni aire comprimido ni aire atmosférico), lo ya
            # abierto se mantiene, no cuenta para el Principal perdido ni para
            # pasar a solo_lenta. CIC-10 por bloqueado_motivo (fuera de
            # ciclo); aquí, el log.
            if not self._aviso_ai_vencida:
                self._aviso_ai_vencida = True
                logger.error("Protocolo fallo: trama AI vencida — sin abrir válvulas nuevas "
                             "hasta tener datos vigentes")
        else:
            self._aviso_ai_vencida = False

        # R1-P4: Principal perdido con el protocolo ya en marcha por otra causa.
        # SAF-01 / SEN-02 / TMG-07 (revisión Q1): con _DEBOUNCE_LECTURAS
        # lecturas inválidas seguidas; una válida reinicia el contador.
        # R2-M1: con la trama AI vencida no se cuenta.
        if not self._solo_lenta and self._ai_vigente_tick:
            if self._principal_perdido() or self._presion_camara_perdida():
                self._lecturas_principal_perdido += 1
            else:
                self._lecturas_principal_perdido = 0
            if self._lecturas_principal_perdido >= _DEBOUNCE_LECTURAS:
                if self._presion_camara_perdida() and not self._principal_perdido():
                    self.motivo_solo_lenta = "sensor de presión de cámara sin lectura"
                elif self._presion_camara_perdida():
                    self.motivo_solo_lenta = ("sensor Principal y sensor de presión de "
                                              "cámara sin lectura")
                self.pasar_a_solo_lenta()

        if self._sellado:
            # D8-2.10: espera sellada; nada se abre (ni con la presión
            # desconocida) hasta que las sondas o la espera lo permitan
            if not self._ai_vigente_tick:
                # R2-M1: con temperaturas congeladas no se decide el venteo;
                # todo sigue cerrado (el alivio, como estaba)
                self._cerrar_todo_sellado(lenta_alivio=self._alivio_abierto)
                return
            self._tick_sellado()
            if self._sellado:
                return

        pres     = self._pres_camara()
        # Principal del programa del ciclo (tanda §1.1)
        temp     = self._temp_principal()
        atm      = self.config.get("presion_admosferica") or 101.3
        rango    = self.config.get("rango_presion_atm")   or 20.0
        temp_max = self.config.get("temp_max_apertura")   or 120.0

        enfriando = self._modo_efectivo() in (4, 5) and self._sub_etapa == "enfriamiento"

        if not lectura_valida(pres):
            self._lecturas_vacio = 0
            self._seq_vacio = None
            if enfriando or not self._ai_vigente_tick:
                # SAF-02 de T5: sin presión no se inyecta aire comprimido
                self.set_do.aire_comprimido_camara_off()
                self._t_aire_comprimido = None
            return

        # S9, revisión ★ SAF-03: lecturas de vacío seguidas (3 antes de abrir
        # el aire atmosférico; una fuera del vacío reinicia el conteo).
        # R2-M2: cuenta tramas AI distintas (la misma trama, una vez)
        if seq_ai is None or seq_ai != self._seq_vacio:
            self._seq_vacio = seq_ai
            self._lecturas_vacio = self._lecturas_vacio + 1 if pres < atm - rango else 0

        # ── Gestión dinámica de presión ───────────────────────────────
        if enfriando:
            # Modos 4/5: el enfriamiento manda hasta que la carga llegue a
            # temperatura_enfriamiento (con contrapresión solo si estaba
            # presurizada al disparo)
            self._revisar_escalado()
            self._aplicar_paso_modo(pres)
        elif pres > atm + rango:
            # S9, revisión ★ SAF-03: con presión sobre atm + brecha el aire
            # atmosférico se cierra SIEMPRE (también presurizada al disparo y
            # en solo_lenta: un arranque en vacío con el aire abierto y la
            # presión que sube después sacaría vapor por la toma de aire)
            self.set_do.aire_admosferico_camara_off()
            if self._presurizado_al_disparo:
                self._revisar_escalado()
                self._aplicar_paso_modo(pres)
            else:
                # Nunca estuvo presurizada al disparo pero subió después:
                # comportamiento heredado, sin cambios.
                self.set_do.descompresion_lenta_on()
        elif pres < atm - rango:
            # Vacío real → cerrar válvulas de descompresión, aire atmosférico.
            # S9, revisión ★ SAF-03: cerrar es inmediato (lado seguro); el
            # aire solo se abre con 3 lecturas de vacío seguidas
            self.set_do.descompresion_rapida_off()
            self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_off()
            if (self._lecturas_vacio >= _DEBOUNCE_LECTURAS
                    and self._referencia_atm_configurada()):
                self.set_do.aire_admosferico_camara_on()
        else:
            # Rango normal → mantener la válvula de descompresión del modo,
            # aire atmosférico cerrado (evita cerrar en falso si la cámara
            # todavía tiene algo de presión residual, no vacío)
            self.set_do.aire_admosferico_camara_off()
            self._aplicar_paso_modo(pres)

        # ── Buzzer cuando se alcanzan condiciones seguras ─────────────
        if not self._buzzer_emitido:
            pres_ok = abs(pres - atm) <= rango
            temp_ok = (temp is not None) and (temp <= temp_max)

            if pres_ok and temp_ok:
                logger.info(
                    "Protocolo fallo: condiciones seguras (%.1f kPa / %.1f°C) → buzzer",
                    pres, temp
                )
                self.set_do.buzer_fallo()
                self._buzzer_emitido = True

    def _seguir_presion_perdida(self, seq_ai: int | None = None) -> None:
        """S9 (D9-1.4): debounce de 3 lecturas en los dos sentidos del
        "estado seguro detenido" por la presión de cámara sin lectura. Solo
        informa (bloqueado_motivo → CIC-10 + NO ABRIR); las válvulas siguen
        su regla de siempre (sin presión, update() no abre nada nuevo).

        Revisión ★: TMG-03, cuenta tramas AI distintas (seq_ai; None = cada
        llamada cuenta). TMG-02 / R2-M1, la trama AI vencida (ya es un filtro
        temporal: _VIGENCIA_DI_SEG sin tramas) también deja el motivo de
        inmediato, solo informativo: no enclava solo_lenta."""
        if not self._ai_vigente_tick:
            self._lecturas_presion_vuelta = 0
            self._lecturas_presion_perdida = _DEBOUNCE_LECTURAS
            self._presion_perdida = True
            self._seq_presion = None
            return
        if seq_ai is not None:
            if seq_ai == self._seq_presion:
                return                # misma trama AI: ya contada
            self._seq_presion = seq_ai
        if self._presion_camara_perdida():
            self._lecturas_presion_vuelta = 0
            self._lecturas_presion_perdida += 1
            if self._lecturas_presion_perdida >= _DEBOUNCE_LECTURAS:
                self._presion_perdida = True
        else:
            self._lecturas_presion_perdida = 0
            self._lecturas_presion_vuelta += 1
            if self._lecturas_presion_vuelta >= _DEBOUNCE_LECTURAS:
                self._presion_perdida = False

    def reanudar(self, tras_modo_prueba: bool = False) -> None:
        """El protocolo vuelve a actuar tras una pausa (paro o confirmación
        pendiente): los pulsos de chaqueta y la contrapresión empiezan de
        nuevo (TMG-07 de T5) y, si estaba presurizada, el plazo del modo
        empieza a contar ahora (TMG-02 de T5).

        S9, revisión ★: TMG-05, todos los debounces vuelven a contar desde
        cero. TMG-04, tras_modo_prueba: en el modo prueba se pudo encender
        vapor, así que la espera sellada sin sonda empieza de nuevo (tras un
        paro sigue corriendo: las salidas estuvieron en cero)."""
        self._lecturas_enfriada = 0
        self._lecturas_presion_perdida = 0
        self._lecturas_presion_vuelta = 0
        self._seq_presion = None
        self._lecturas_principal_perdido = 0
        self._lecturas_vacio = 0
        self._seq_vacio = None
        self._reanudado = True
        if tras_modo_prueba:
            self._sin_sonda_desde = None
        self._t_pulso_chaqueta = None
        self._chaqueta_abierta = False
        self._t_aire_comprimido = None
        # TMG-08 (revisión S2a): tras la pausa, las 3 lecturas del sellado
        # vuelven a contarse seguidas. La espera sin sonda sigue corriendo: la
        # cámara estuvo igual de sellada (salidas en cero) durante la pausa.
        self._lecturas_sondas_frias = 0
        self._lecturas_con_sonda = 0
        self._lecturas_sobrepresion = 0
        if (self._presurizado_al_disparo and not self._escalado
                and not self._sin_escalar):
            self._t_timeout_descompresion = self._calcular_timeout()

    def _revisar_escalado(self) -> None:
        if (self._escalado or self._sin_escalar or self._t_timeout_descompresion is None
                or time.monotonic() <= self._t_timeout_descompresion):
            return
        # Con el contador confirmado (3 lecturas, sin incrementarlo aquí):
        # un valor espurio no habilita la rápida con líquido caliente
        if self.es_liquido() and self._lecturas_enfriada < _DEBOUNCE_LECTURAS:
            # Líquidos: la escalada usa la rápida; con la carga caliente no
            if not self._aviso_no_escala:
                logger.error("Protocolo fallo: timeout del modo %d con carga líquida caliente — "
                             "no se escala a la descompresión rápida", self._modo)
                self._aviso_no_escala = True
            return
        logger.error(
            "Protocolo fallo: timeout del modo %d agotado, escalando a chaqueta+rápida",
            self._modo,
        )
        self._escalado = True
        # SAF-02 de T5: la escalada sale del enfriamiento; nada queda enclavado
        self._fin_enfriamiento()

    # ------------------------------------------------------------------
    # FIN — estado seguro alcanzado (fin de ciclo §15.4)
    # ------------------------------------------------------------------

    def finalizar(self) -> None:
        """Cierra toda válvula que el protocolo pudo abrir (PF-10)."""
        self.set_do.descompresion_rapida_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_chaqueta_off()
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()
        self.set_do.aire_admosferico_camara_off()
        logger.info("Protocolo fallo: estado seguro — válvulas del protocolo cerradas")
