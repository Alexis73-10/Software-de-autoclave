import math
import time
import logging
from datetime import datetime

from autoclave.core.managers.catalogo_parametros import MARGEN_CONTRAPRESION_LIQUIDO
from autoclave.core.managers import limites_equipo
from autoclave.core.runtime import motivos_fase
from autoclave.core.runtime import vigencia_ai
from autoclave.state_machine.alarms.catalogo import CIC_22, CIC_23, CIC_24, CIC_25
from autoclave.state_machine.cycle_phases import enfriamiento_contrapresion as enfr
from autoclave.state_machine.cycle_phases.base_fase import BaseFase, FaseResult
from autoclave.state_machine.cycle_phases.valvula_reposo import abrir_valvula_modo
from autoclave.core.runtime.lectura import carga_enfriada

logger = logging.getLogger(__name__)

# TMG-02 de T11: lecturas consecutivas del Principal en o bajo la temperatura
# de enfriamiento antes de abrir la rápida (modos 4/5), como en el protocolo
# de fallo (SAF-06 de T5)
_DEBOUNCE_LECTURAS = 3

# ── Tanda 32 (LIQ-01 / LIQ-02 / LIQ-03): integración del componente
# EnfriamientoContrapresion. Lo usan esta fase y el protocolo de fallo. ──────

# Defectos seguros si el programa no trae el parámetro o trae un valor no
# válido (los del catálogo de la tanda 32; presion_camara_enfriamiento, el de
# siempre)
_DEFECTOS_ENFRIAMIENTO = {
    "presion_camara_enfriamiento": 200.0,
    "presion_despresurizacion_chaqueta": 20.0,
    "timeout_despresurizacion_chaqueta": 3.0,
    "timeout_presurizacion_enfriamiento": 3.0,
}
# LIQ-03: presión de cambio lenta → rápida del modo 5 (kPa abs) sin un valor válido
PRESION_CAMBIO_DEFECTO = 150.0

# Fallos del componente → alarma bloqueante propia (CicloState la registra
# por `alarma_fallo`, como CIC-20)
CODIGO_ALARMA_ENFRIAMIENTO = {
    enfr.ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA: CIC_22,
    enfr.ENFR_TIMEOUT_PRESURIZACION: CIC_23,
    enfr.ENFR_CONTRAPRESION_BAJA: CIC_24,
}
# Ticket: líneas del pie (estado.avisos_ciclo)
CLAVE_TICKET_AVISO_CONTRAPRESION = "ticket_ciclo.aviso_contrapresion"
CLAVE_TICKET_TOPE = {
    enfr.ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA: "ticket_ciclo.aviso_enfriamiento_detenido_chaqueta",
    enfr.ENFR_TIMEOUT_PRESURIZACION: "ticket_ciclo.aviso_enfriamiento_detenido_presurizacion",
}


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    v = float(valor)
    return v if math.isfinite(v) else None


def parametros_enfriamiento(cycle, modo_key: str) -> dict:
    """Parámetros del componente para `descompresion.<modo_key>`. Un valor
    ausente o no válido toma el defecto seguro (con error en el log si venía
    un valor)."""
    salida = {}
    for nombre, defecto in _DEFECTOS_ENFRIAMIENTO.items():
        try:
            crudo = cycle.get_param("descompresion", modo_key, nombre, default=None)
        except Exception:
            crudo = None
        v = _numero(crudo)
        valido = v is not None and (v >= 0 if nombre == "presion_despresurizacion_chaqueta"
                                    else v > 0)
        if not valido:
            if crudo is not None:
                logger.error("Enfriamiento con contrapresión: %s.%s=%r no válido; se usa %g",
                             modo_key, nombre, crudo, defecto)
            v = defecto
        salida[nombre] = float(v)
    return salida


def presion_atm_configurada(config) -> float | None:
    """Revisión de la tanda 32: presión atmosférica de referencia solo si
    está configurada junto con su brecha (números finitos y positivos, como
    `ProtocoloFallo._referencia_atm_configurada` para el aire atmosférico);
    si no, None y la condición (b) del enfriamiento no se cumple (falla
    cerrada: el defecto 101,3 leería mal la chaqueta en un sitio de altura).
    Nunca lanza."""
    valores = []
    for clave in ("presion_admosferica", "rango_presion_atm"):
        try:
            v = config.get(clave) if config is not None else None
        except Exception:
            return None
        if (isinstance(v, bool) or not isinstance(v, (int, float))
                or not math.isfinite(v) or v <= 0):
            return None
        valores.append(float(v))
    return valores[0]


def presion_max_reposicion(config) -> float | None:
    """Revisión de la tanda 32 (M1): tope de la reposición de aire del
    enfriamiento = alivio de cámara del equipo menos 10 kPa (el mismo margen
    que el corte de chaqueta, `MARGEN_CORTE_BAJO_ALIVIO`). Ante un error,
    None (el componente usa presion_camara_enfriamiento + 30). Nunca lanza."""
    try:
        return (limites_equipo.limites_presion(config).alivio_camara
                - limites_equipo.MARGEN_CORTE_BAJO_ALIVIO)
    except Exception:
        logger.exception("Enfriamiento con contrapresión: alivio de cámara no legible")
        return None


def lenta_rapida_modo_5(cycle) -> tuple[bool, float]:
    """LIQ-03: (descompresion_lenta_rapida activa, presion_cambio) del modo 5.
    Solo True estricto activa la opción; presion_cambio no válida (no numérica
    o no positiva) toma el defecto."""
    try:
        activa = cycle.get_param("descompresion", "modo_5", "descompresion_lenta_rapida",
                                 default=False) is True
    except Exception:
        activa = False
    try:
        cambio = _numero(cycle.get_param("descompresion", "modo_5", "presion_cambio",
                                         default=PRESION_CAMBIO_DEFECTO))
    except Exception:
        cambio = None
    if cambio is None or cambio <= 0:
        cambio = PRESION_CAMBIO_DEFECTO
    return activa, cambio


def valores_alarma_enfriamiento(codigo_enfr: str, params: dict, modo, p_atm: float) -> dict:
    """Valores de la plantilla de CIC-22/23/24."""
    if codigo_enfr == enfr.ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA:
        margen = params["presion_despresurizacion_chaqueta"]
        return {"maximo": float(p_atm) + margen, "margen": f"{margen:g}",
                "minutos": f"{params['timeout_despresurizacion_chaqueta']:g}", "modo": modo}
    if codigo_enfr == enfr.ENFR_TIMEOUT_PRESURIZACION:
        return {"objetivo": params["presion_camara_enfriamiento"],
                "minutos": f"{params['timeout_presurizacion_enfriamiento']:g}", "modo": modo}
    return {"margen": f"{MARGEN_CONTRAPRESION_LIQUIDO:g}",
            "segundos": int(enfr.TIEMPO_FALLO_CONTRAPRESION_S), "modo": modo}


def anotar_ticket(estado, clave: str) -> None:
    """Línea del pie del ticket con la hora de pared (registro). Nunca lanza."""
    try:
        avisos = getattr(estado, "avisos_ciclo", None)
        if isinstance(avisos, list):
            avisos.append({"clave": clave, "hora": datetime.now().strftime("%H:%M")})
    except Exception:
        logger.exception("Enfriamiento con contrapresión: no se pudo anotar %s en el ticket", clave)


class AvisoContrapresion:
    """CIC-25 (LIQ-02): aviso no bloqueante que sigue a `aviso_contrapresion`
    del componente: se activa al aparecer y se resuelve al desaparecer (o al
    salir de la sub-etapa). Cada aparición deja una línea en el ticket, hasta
    _MAX_LINEAS_TICKET por dueño (fase o protocolo). Nunca lanza."""

    _MAX_LINEAS_TICKET = 5

    def __init__(self):
        self.activo = False
        self._lineas = 0

    def actualizar(self, alarm_manager, estado, activo: bool) -> None:
        if activo and not self.activo:
            self.activo = True
            logger.warning("Enfriamiento con contrapresión: presión de cámara bajo el mínimo de "
                           "contrapresión desde hace %.0f s (aviso CIC-25)",
                           enfr.TIEMPO_AVISO_CONTRAPRESION_S)
            if alarm_manager is not None:
                try:
                    alarm_manager.activar(CIC_25, margen=f"{MARGEN_CONTRAPRESION_LIQUIDO:g}",
                                          segundos=int(enfr.TIEMPO_AVISO_CONTRAPRESION_S))
                except Exception:
                    logger.exception("Enfriamiento con contrapresión: no se pudo activar CIC-25")
            if self._lineas < self._MAX_LINEAS_TICKET:
                self._lineas += 1
                anotar_ticket(estado, CLAVE_TICKET_AVISO_CONTRAPRESION)
        elif not activo and self.activo:
            self.despejar(alarm_manager)

    def despejar(self, alarm_manager) -> None:
        if not self.activo:
            return
        self.activo = False
        logger.info("Enfriamiento con contrapresión: fin del aviso de contrapresión baja")
        resolver_aviso_contrapresion(alarm_manager)


def resolver_aviso_contrapresion(alarm_manager) -> None:
    """Resuelve CIC-25 (si no está activa, no hace nada). Nunca lanza."""
    if alarm_manager is None:
        return
    try:
        alarm_manager.resolver(CIC_25)
    except Exception:
        logger.exception("Enfriamiento con contrapresión: no se pudo resolver CIC-25")


class DescompresionFase(BaseFase):
    name = "DESCOMPRESION"

    def reset(self):
        # el modo se lee al iniciar la fase, no al iniciar el ciclo: un cambio
        # con la fase pendiente (T-17, §5.8) debe regir la fase completa
        self._modo             = None
        self._etapa            = None
        self._sub_etapa        = None
        self._t_inicio         = None
        self._t_timeout        = None
        self._lecturas_enfriada = 0
        # Tanda 32: componente de la sub-etapa de enfriamiento (uno por
        # sub-etapa, se crea al entrar), aviso CIC-25 y LIQ-03
        self._enfr = None
        self._enfr_params = None
        self._desc_lenta_primero = False
        self._presion_cambio = PRESION_CAMBIO_DEFECTO
        aviso = getattr(self, "_aviso", None)
        if aviso is not None:
            aviso.despejar(getattr(self, "alarm_manager", None))
        self._aviso = AvisoContrapresion()
        self.alarma_fallo = None
        self.estado.descompresion_enfriando = False   # T30-02: publicación para la pantalla

    @property
    def chaqueta_en_enfriamiento(self) -> bool:
        """Modos 4/5 enfriando o despresurizando: la chaqueta se ventea y se
        enfría con agua; su vapor debe quedar apagado (TMG-01 de T11)."""
        return self._sub_etapa in ("enfriamiento", "descompresion")

    @property
    def en_enfriamiento_con_contrapresion(self) -> bool:
        """D8-2.10 (tanda 8): modos 4/5 en la sub-etapa de enfriamiento (aire
        comprimido de contrapresión y agua de chaqueta). CicloState lo pasa al
        protocolo de fallo si se pierde el Principal."""
        return self._modo in (4, 5) and self._sub_etapa == "enfriamiento"

    def update(self) -> FaseResult:
        if self._etapa is None:
            self._modo = self.cycle.get_param("descompresion", "modo", default=0)
            self._apagar_todo()
            t_pre = self.cycle.get_param("descompresion", "tiempo_pre_despresurizacion", default=0)
            if t_pre and t_pre > 0:
                self._etapa    = "pre_espera"
                self._t_inicio = time.monotonic()
            else:
                self._etapa = "modo"
                self._iniciar_modo()
            return FaseResult.EN_CURSO

        if self._etapa == "pre_espera":
            t_pre = self.cycle.get_param("descompresion", "tiempo_pre_despresurizacion", default=0)
            if time.monotonic() - self._t_inicio >= t_pre:
                self._etapa = "modo"
                self._iniciar_modo()
            return FaseResult.EN_CURSO

        return self._tick_modo()

    def _iniciar_modo(self):
        self._t_inicio = time.monotonic()
        if self._modo > 0:
            timeout_min     = self.cycle.get_param("descompresion", f"modo_{self._modo}", "timeout", default=60)
            self._t_timeout = self._t_inicio + (timeout_min or 60) * 60
        if self._modo == 3:
            self._sub_etapa = "lenta"
        elif self._modo in (4, 5):
            self._sub_etapa = "enfriamiento"
            self._enfr = None       # se crea en el primer tick de la sub-etapa

    def _tick_modo(self) -> FaseResult:
        if self._modo > 0 and self._t_timeout and time.monotonic() > self._t_timeout:
            self._apagar_todo()
            self._cerrar_enfriamiento()
            logger.error("DescompresionFase: timeout en modo %d", self._modo)
            # TMG-06 de T11: motivo específico para el ticket y el registro
            t = self._temp_principal()
            p = self._pres_camara()
            # X9 (D9-13.4): clave + parámetros (sin lectura: "—")
            etapa = (self._sub_etapa
                     if self._sub_etapa in ("enfriamiento", "descompresion", "lenta", "rapida")
                     else "general")
            self.estado.motivo_fallo = motivos_fase.motivo(
                "desc_tiempo_limite", clave_etapa=f"motivos_fase.etapa.{etapa}",
                modo=self._modo, temp=t, pres=p)
            return FaseResult.FALLO

        _dispatch = {
            0: self._tick_modo_0,
            1: self._tick_modo_1,
            2: self._tick_modo_2,
            3: self._tick_modo_3,
            4: self._tick_modo_4,
            5: self._tick_modo_5,
        }
        handler = _dispatch.get(self._modo)
        if handler is None:
            logger.error("DescompresionFase: modo desconocido %d", self._modo)
            return FaseResult.EN_CURSO
        return handler()

    def _en_presion_atm(self) -> bool:
        """Modo 0 (sin cambio): pres <= atm + rango_presion_atm."""
        p = self._pres_camara()
        return p is not None and p <= self._pres_atm() + self._rango_atm()

    def _en_presion_fin(self) -> bool:
        """T29-03 (tanda 29): fin de la despresurización de los modos 1 a 5
        con pres <= atm + descompresion.presion_fin_descompresion. Sin el
        parámetro (o no numérico/no positivo) rige el criterio anterior
        (atm + rango_presion_atm). El modo 0 y el timeout no cambian."""
        p = self._pres_camara()
        if p is None:
            return False
        margen = self.cycle.get_param("descompresion", "presion_fin_descompresion")
        if (isinstance(margen, bool) or not isinstance(margen, (int, float))
                or not math.isfinite(margen) or margen <= 0):
            margen = self._rango_atm()
        return p <= self._pres_atm() + margen

    def _apagar_todo(self):
        self.set_do.descompresion_rapida_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_chaqueta_off()
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()

    def _finalizar(self) -> FaseResult:
        p = self._pres_camara()
        if p is not None and p < self._pres_atm() - self._rango_atm():
            self._apagar_todo()
            self.set_do.aire_admosferico_camara_on()
        else:
            self.set_do.aire_admosferico_camara_off()
            liquido = self.cycle.get_param("globals", "tipo_carga", default="solido") == "liquido"
            temp_obj = self.cycle.get_param("descompresion", f"modo_{self._modo or 2}",
                                            "temperatura_enfriamiento", default=80.0)
            t = self._temp_principal()
            enfriada = carga_enfriada(t, temp_obj)
            abrir_valvula_modo(self.set_do, self._modo, liquido=liquido, enfriada=enfriada)
        return FaseResult.COMPLETADO

    def _tick_modo_0(self) -> FaseResult:
        if self._en_presion_atm():
            return self._finalizar()
        return FaseResult.EN_CURSO

    def _tick_modo_1(self) -> FaseResult:
        self.set_do.descompresion_rapida_on()
        if self._en_presion_fin():
            return self._finalizar()
        return FaseResult.EN_CURSO

    def _tick_modo_2(self) -> FaseResult:
        self.set_do.descompresion_lenta_on()
        if self._en_presion_fin():
            return self._finalizar()
        return FaseResult.EN_CURSO

    def _tick_modo_3(self) -> FaseResult:
        if self._sub_etapa == "lenta":
            presion_cambio = self.cycle.get_param("descompresion", "modo_3", "presion_cambio", default=150)
            self.set_do.descompresion_lenta_on()
            p = self._pres_camara()
            if p is not None and p <= presion_cambio:
                self.set_do.descompresion_lenta_off()
                self._sub_etapa = "rapida"
        else:
            self.set_do.descompresion_rapida_on()
            if self._en_presion_fin():
                return self._finalizar()
        return FaseResult.EN_CURSO

    def _tick_modo_4(self) -> FaseResult:
        return self._tick_enfriamiento(modo_key="modo_4", use_lenta=False)

    def _tick_modo_5(self) -> FaseResult:
        return self._tick_enfriamiento(modo_key="modo_5", use_lenta=True)

    def _tick_enfriamiento(self, modo_key: str, use_lenta: bool) -> FaseResult:
        if self._sub_etapa == "enfriamiento":
            return self._tick_sub_enfriamiento(modo_key, use_lenta)
        return self._tick_sub_descompresion()

    def _cerrar_enfriamiento(self) -> None:
        """Fin de la sub-etapa de enfriamiento (transición, FALLO o timeout):
        el componente se descarta y el aviso CIC-25 se resuelve."""
        self._enfr = None
        aviso = getattr(self, "_aviso", None)
        if aviso is not None:
            aviso.despejar(getattr(self, "alarm_manager", None))

    def _tick_sub_enfriamiento(self, modo_key: str, use_lenta: bool) -> FaseResult:
        """Tanda 32 (LIQ-01/LIQ-02): las salidas de la sub-etapa las decide
        EnfriamientoContrapresion (aire comprimido, lenta en modo 5,
        descompresión de chaqueta abierta fija y agua de chaqueta solo con las
        condiciones (a) y (b)). El vapor de chaqueta sigue apagado por
        `chaqueta_en_enfriamiento` (CicloState) y el corte D-CHQ no cambia.
        Ya no hay pulsos de chaqueta (tiempo_apertura/cierre_chaqueta)."""
        self.estado.descompresion_enfriando = True   # T30-02

        if getattr(self, "_enfr", None) is None:
            self._enfr_params = parametros_enfriamiento(self.cycle, modo_key)
            # reloj por llamada: sigue a time.monotonic (también si se parchea)
            self._enfr = enfr.EnfriamientoContrapresion(
                self._enfr_params, modo_5=use_lenta, solo_aviso=False,
                ahora=lambda: time.monotonic(),
                presion_max_reposicion=presion_max_reposicion(self.config))
            logger.info("DescompresionFase: enfriamiento con contrapresión (%s) %s",
                        modo_key, self._enfr_params)

        # S9 (tanda 9), revisión ★ pasada 2 (R2-A1): con la trama AI vencida
        # la presión puede estar congelada: el componente no da aire
        # comprimido ni cuenta las condiciones (datos no vigentes)
        ai_vigente, _ = vigencia_ai.leer(self.estado)
        # Revisión de la tanda 32: sin presión atmosférica configurada, None
        # (la condición (b) no se cumple)
        res = self._enfr.tick(self._pres_camara(), self._pres_chaqueta(), self._temp_principal(),
                              presion_atm_configurada(self.config), ai_vigente)

        if res.fallo is not None:
            return self._fallo_enfriamiento(res.fallo, modo_key)

        if res.aire_comprimido_on:
            if res.aire_comprimido_pulso:
                self.set_do.aire_comprimido_camara_on()
        else:
            self.set_do.aire_comprimido_camara_off()
        if res.descompresion_chaqueta_on:
            self.set_do.descompresion_chaqueta_on()
        else:
            self.set_do.descompresion_chaqueta_off()
        if use_lenta:
            if res.descompresion_lenta_on:
                self.set_do.descompresion_lenta_on()
            else:
                self.set_do.descompresion_lenta_off()
        if res.agua_chaqueta_on:
            self.set_do.agua_chaqueta_on()
        else:
            self.set_do.agua_chaqueta_off()
        aviso = getattr(self, "_aviso", None)
        if aviso is None:
            aviso = self._aviso = AvisoContrapresion()
        aviso.actualizar(getattr(self, "alarm_manager", None), self.estado,
                         res.aviso_contrapresion)

        temp_obj = self.cycle.get_param("descompresion", modo_key, "temperatura_enfriamiento", default=80.0)
        # Enfriamiento (modos 4/5) medido con el Principal (tanda §1.1)
        t = self._temp_principal()
        # SAF-01 de T11: sin lectura o con 0 (sin señal) no cuenta como enfriada
        self._lecturas_enfriada = self._lecturas_enfriada + 1 if carga_enfriada(t, temp_obj) else 0
        if self._lecturas_enfriada >= _DEBOUNCE_LECTURAS:
            self._cerrar_enfriamiento()
            self.set_do.aire_comprimido_camara_off()
            self.set_do.agua_chaqueta_off()
            self.set_do.descompresion_chaqueta_on()
            # LIQ-03 (tanda 32): modo 5 con descompresion_lenta_rapida: la
            # lenta sigue abierta hasta presion_cambio y la rápida espera
            activa, cambio = lenta_rapida_modo_5(self.cycle) if use_lenta else (False, 0.0)
            self._desc_lenta_primero = activa
            self._presion_cambio = cambio
            if activa:
                self.set_do.descompresion_lenta_on()
                self.set_do.descompresion_rapida_off()
                logger.info("DescompresionFase: modo 5, descompresión por la lenta hasta %.1f kPa "
                            "y luego la rápida (LIQ-03)", cambio)
            else:
                if use_lenta:
                    self.set_do.descompresion_lenta_off()
                self.set_do.descompresion_rapida_on()
            self._sub_etapa = "descompresion"
            self.estado.descompresion_enfriando = False   # T30-02

        return FaseResult.EN_CURSO

    def _fallo_enfriamiento(self, codigo_enfr: str, modo_key: str) -> FaseResult:
        """FALLO propio del componente (CIC-22/23/24): apaga las salidas de la
        sub-etapa; CicloState registra la alarma (`alarma_fallo`) y ejecuta
        el protocolo de fallo (líquidos: sigue con contrapresión)."""
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()
        self.set_do.descompresion_chaqueta_off()
        self.set_do.descompresion_lenta_off()
        params = self._enfr_params or parametros_enfriamiento(self.cycle, modo_key)
        self._cerrar_enfriamiento()
        codigo = CODIGO_ALARMA_ENFRIAMIENTO.get(codigo_enfr)
        logger.error("DescompresionFase: FALLO en el enfriamiento con contrapresión (%s, %s)",
                     codigo_enfr, codigo)
        if codigo is not None:
            self.alarma_fallo = (codigo, valores_alarma_enfriamiento(
                codigo_enfr, params, self._modo, self._pres_atm()))
        # Respaldo: CicloState lo reemplaza con el texto de la alarma propia
        self.estado.motivo_fallo = codigo or codigo_enfr
        return FaseResult.FALLO

    def _tick_sub_descompresion(self) -> FaseResult:
        self.set_do.descompresion_chaqueta_on()
        if getattr(self, "_desc_lenta_primero", False):
            # LIQ-03: lenta abierta y rápida cerrada hasta presion_cambio; sin
            # lectura de presión (o con la trama AI vencida, revisión de la
            # tanda 32) no se cambia a la rápida
            self.set_do.descompresion_lenta_on()
            self.set_do.descompresion_rapida_off()
            ai_vigente, _ = vigencia_ai.leer(self.estado)
            p = _numero(self._pres_camara()) if ai_vigente else None
            if p is not None and 0 < p <= self._presion_cambio:
                logger.info("DescompresionFase: %.1f kPa <= %.1f kPa, de la lenta a la rápida "
                            "(LIQ-03)", p, self._presion_cambio)
                self.set_do.descompresion_lenta_off()
                self.set_do.descompresion_rapida_on()
                self._desc_lenta_primero = False
            elif self._en_presion_fin():
                # DECISIÓN SIN CONFIRMAR: presion_cambio por debajo del fin de
                # la despresurización; el fin de siempre rige también aquí
                return self._finalizar()
            return FaseResult.EN_CURSO
        self.set_do.descompresion_rapida_on()
        if self._en_presion_fin():
            return self._finalizar()
        return FaseResult.EN_CURSO
