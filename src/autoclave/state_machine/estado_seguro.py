# state_machine/estado_seguro.py
#
# Protocolo de estado seguro común a todo fallo, cancelación y paro
# (planeacion_fin_de_ciclo_y_puertas.md §15, D-22; tanda 2026-10-14 E3).
#
# Antes (PF-10), al confirmar un FALLO nadie continuaba el protocolo de
# fallo: PREPARACION solo venteaba con la rápida y nunca cerraba la
# descompresión de chaqueta. Ahora, al salir de CICLO con FALLO o CANCELADO,
# la StateMachine entrega aquí el ProtocoloFallo del ciclo y este módulo lo
# sigue ejecutando en el estado siguiente hasta que la cámara sea segura:
#
#  0. S9 (tanda 9, D9-1.1/1.2): al arrancar con la cámara no segura corre
#     solo, sin confirmación; la confirmación se exige SOLO tras un paro real
#     visto en este encendido (paso 1). `causa` distingue paro liberado /
#     arranque / fin de ciclo para la UI.
#  1. Paro activo: no hace nada (los estados mandan ALL_OFF continuo); si
#     es un paro real (PARO_REAL, U4) se marca que hará falta una
#     confirmación nueva. Sin datos del módulo E/S solo se pausa.
#  2. Paro liberado: las salidas siguen en 0, sin avance automático, hasta
#     "Confirmar y llevar a estado seguro" (cualquier operador, sin rol).
#  3. Confirmado: exige datos vigentes; sigue el protocolo de fallo (modo de
#     descompresión del programa; en líquidos nunca la rápida con la carga
#     caliente; modos 4/5 con enfriamiento).
#  4. Estado seguro (cámara segura 3 ticks seguidos): cierra toda válvula del
#     protocolo y termina; FALLA ya puede pasar a PREPARACION.
#
# Cada paso queda en audit_log por el callback `al_evento` (paro activado,
# liberado, confirmado, estado seguro alcanzado con la duración).

import logging
import time

from autoclave.core.runtime import camara_segura
from autoclave.state_machine.alarms.catalogo import CIC_10
from autoclave.state_machine.alarms.instancia import EstadoInstancia

logger = logging.getLogger(__name__)

_TICKS_SEGUROS = 3     # convención de debounce de 3 lecturas
_SIN_CONSULTA = object()


class ProtocoloEstadoSeguro:

    def __init__(self, estado, config, profile=None, programas_seguridad=None,
                 al_evento=None, reloj=time.monotonic, alarm_manager=None):
        self.estado = estado
        self.config = config
        self.profile = profile
        self.programas_seguridad = programas_seguridad
        self.al_evento = al_evento
        self._reloj = reloj
        self._protocolo = None
        self._t_inicio = None
        self._ticks_seguros = 0
        self._paro_visto = False
        self._pausado = False
        self.requiere_confirmacion = False
        # S9 (tanda 9, D9-1.2): por qué corre el protocolo ("arranque",
        # "fallo", "cancelado" o "completado"); la UI lo distingue del paro
        self.origen = None
        self.alarm_manager = alarm_manager
        # Callable que mantiene el enfriamiento del drenaje mientras el
        # protocolo ventea (SAF-07 de T5). Lo fija la StateMachine.
        self.mantener_drenaje = None
        self._alarma_bloqueo = None
        # Tanda 17 (ESG-01): episodio de "detenido por presión de cámara sin
        # lectura" ya escrito en el log de desarrollo (una vez por episodio)
        self._presion_perdida_en_log = False
        # ESS-06: lo mismo para el episodio "detenido solo por el Principal"
        self._principal_perdido_en_log = False
        # S9 (tanda 9, revisión ★ TMG-02/TMG-03): callable () -> (trama AI
        # vigente, número de trama). Lo fija el ControlLoop; se entrega al
        # protocolo. Con la AI vencida no se cuenta ningún tick seguro (la
        # presión publicada puede estar congelada). None: sin información.
        self.lectura_ai = None
        # S9, revisión ★ TMG-04: la pausa actual vino del modo prueba (al
        # reanudar, la espera sellada sin sonda empieza de nuevo)
        self._pausa_por_prueba = False

    @property
    def activo(self) -> bool:
        return self._protocolo is not None

    @property
    def programa(self):
        """Programa (copia del ciclo) con el que corre el protocolo, o None."""
        return getattr(self._protocolo, "cycle", None)

    def reemplazar_programa(self, programa) -> None:
        """S4: el protocolo pasa a usar `programa` (copia con otra asignación
        de sensores) sin mutar la instantánea del ciclo terminado."""
        if self._protocolo is not None and programa is not None:
            self._protocolo.cycle = programa

    @property
    def permite_salir_de_falla(self) -> bool:
        """P-2 (tanda 6): con el protocolo disparado por la pérdida del
        Principal, el operador reconoce y FALLA pasa a PREPARACION sin
        técnico; el protocolo sigue venteando por la lenta allí y el inicio
        de ciclo queda bloqueado mientras siga activo. No aplica si espera la
        confirmación tras un paro.

        D8-2.6 (tanda 8, Cristian): vale igual si se llegó a `solo_lenta` con el
        protocolo ya en marcha por otra causa (R1-P4). "NO ABRIR" no cambia:
        sigue hasta que la cámara sea segura (camara_segura, con el Principal)."""
        return (self.activo and not self.requiere_confirmacion
                and getattr(self._protocolo, "solo_lenta", False) is True)

    @property
    def bloqueado_motivo(self) -> str | None:
        """Motivo vigente por el que el protocolo no puede terminar solo
        (CIC-10), o None. Lo muestra la UI junto al botón de asignar sonda."""
        motivo = getattr(self._protocolo, "bloqueado_motivo", None)
        return motivo if isinstance(motivo, str) else None

    @property
    def bloqueado_motivo_sin_presion(self) -> str | None:
        """ESS-02: bloqueado_motivo sin el texto de presión de cámara sin
        lectura (el siguiente motivo, como CIC-10 en ESG-01), o None."""
        if not self.activo:
            return None
        motivo = getattr(self._protocolo, "bloqueado_motivo_sin_presion", None)
        return motivo if isinstance(motivo, str) else None

    @property
    def bloqueo_no_sensor(self) -> bool:
        """ESS-02/03: el protocolo está detenido por algo que no es un sensor
        sin lectura (cámara sellada con líquidos, tiempo límite con carga
        caliente) o enfriando en modo 4/5, donde puede haber contrapresión de
        aire (revisión ESS, SAF-05). Falla cerrada: inactivo, sin la consulta
        o ante un error, True (SAF-08)."""
        protocolo = self._protocolo
        if protocolo is None:
            return True
        try:
            motivo = getattr(protocolo, "bloqueado_motivo_no_sensor", _SIN_CONSULTA)
            if motivo is _SIN_CONSULTA:
                return True
            modo = protocolo._modo_efectivo()
            enfriando = modo in (4, 5) and getattr(protocolo, "_sub_etapa", None) == "enfriamiento"
        except Exception:
            logger.exception("Estado seguro: no se pudo leer el motivo de bloqueo")
            return True
        return motivo is not None or enfriando is True

    @property
    def detenido_sin_presion(self) -> bool:
        """Tanda 17 (ESG-01): el protocolo activo está detenido porque la
        presión de cámara no tiene lectura (sin CIC-10; la UI puede mostrarlo
        en la sección del estado seguro)."""
        return (self.activo is True
                and getattr(self._protocolo, "presion_perdida", False) is True)

    def _evento(self, evento: str, **detalle) -> None:
        logger.info("Estado seguro: %s %s", evento, detalle or "")
        if self.al_evento is None:
            return
        try:
            self.al_evento(evento, detalle)
        except Exception:
            logger.exception("Estado seguro: no se pudo registrar %s", evento)

    @property
    def causa(self) -> str | None:
        """S9 (D9-1.2): "paro_liberado" mientras espera la confirmación (solo
        tras un paro real visto en este encendido); si no, el origen del
        protocolo ("arranque", "fallo", "cancelado", "completado"). None si
        no está activo. La UI elige el texto con esto: nunca dice "paro
        liberado" si no hubo paro."""
        if not self.activo:
            return None
        if self.requiere_confirmacion:
            return "paro_liberado"
        return self.origen or "fallo"

    def iniciar(self, protocolo, requiere_confirmacion: bool = False,
                origen: str = "fallo") -> None:
        """Toma el ProtocoloFallo ya ejecutado del ciclo terminado (o el del
        arranque con la cámara no segura, origen "arranque")."""
        if protocolo is None or not getattr(protocolo, "ejecutado", False):
            return
        self._protocolo = protocolo
        self._t_inicio = self._reloj()
        self._ticks_seguros = 0
        self._paro_visto = False
        # Tras un paro durante el ciclo el protocolo no abrió válvulas: al
        # empezar a actuar se "reanuda" (pulsos y plazo del modo desde cero)
        self._pausado = True
        self._pausa_por_prueba = False
        self.requiere_confirmacion = requiere_confirmacion
        self.origen = origen
        self._evento("estado_seguro_iniciado", requiere_confirmacion=requiere_confirmacion,
                     origen=origen)

    def pausar(self, motivo: str) -> None:
        """S9 (D9-1.3): el modo prueba pausa el protocolo (la máquina de
        estados no corre y la entrada al modo prueba apaga todo). Al volver a
        actuar se reanuda como tras un paro: pulsos y plazos desde cero y las
        3 lecturas seguras se cuentan de nuevo."""
        if not self.activo:
            return
        self._pausado = True
        self._ticks_seguros = 0
        if motivo == "modo_prueba":
            self._pausa_por_prueba = True
        self._evento("estado_seguro_pausado", motivo=motivo)

    def confirmar(self) -> bool:
        """"Confirmar y llevar a estado seguro". False si no aplica (no hay
        protocolo, no requiere confirmación o el paro sigue activo)."""
        if (not self.activo or not self.requiere_confirmacion
                or self.estado.get_flag("PARO_EMERGENCIA")):
            return False
        self.requiere_confirmacion = False
        self._evento("estado_seguro_confirmado")
        return True

    def terminar(self) -> None:
        """Cierre forzado (p. ej. al entrar a un ciclo nuevo)."""
        if self._protocolo is not None:
            self._protocolo.finalizar()
        self._protocolo = None
        self._resolver_alarma_bloqueo()

    def _actualizar_alarma_bloqueo(self) -> None:
        """SAF-04 de T5: si el protocolo no puede terminar solo, alarma visible
        (CIC-10) con el motivo; se resuelve cuando vuelve a avanzar.

        Tanda 17 (ESG-01, decisión de Cristian): si no avanza porque la
        presión de cámara no tiene lectura, NO se activa CIC-10 (y se resuelve
        si estaba activa): solo se ve la alarma del sensor (SEN-04 y presión
        baja/alta si existe). El motivo va al log de desarrollo una vez por
        episodio. El protocolo sigue detenido sin abrir nada nuevo y "NO
        ABRIR" y el bloqueo del inicio de ciclo se mantienen (camara_segura
        falla cerrada sin presión). CIC-10 se conserva para los demás motivos:
        con la presión perdida se activa con el siguiente motivo que haya
        (bloqueado_motivo_sin_presion: cámara sellada, Principal sin lectura,
        líquidos calientes), corrección R3 V17-s3-02. La trama AI vencida
        cuenta como presión sin lectura (el protocolo la trata así desde S9,
        TMG-02/R2-M1): tampoco da CIC-10 por sí sola (DECISIÓN SIN CONFIRMAR)."""
        presion_perdida = getattr(self._protocolo, "presion_perdida", False) is True
        if presion_perdida and not self._presion_perdida_en_log:
            self._presion_perdida_en_log = True
            logger.warning("Estado seguro detenido: presión de cámara sin lectura; sin el "
                           "sensor de presión no se lleva la cámara a estado seguro "
                           "(ESG-01: sin CIC-10 por este motivo, solo la alarma del sensor)")
        elif not presion_perdida and self._presion_perdida_en_log:
            self._presion_perdida_en_log = False
            logger.info("Estado seguro: la presión de cámara volvió a tener lectura")
        # ESS-03 (28-oct, D-1 de Cristian): tampoco hay CIC-10 si el único
        # motivo es el Principal sin lectura; se conserva para la cámara
        # sellada con líquidos y el tiempo límite con carga caliente
        # (bloqueado_motivo_no_sensor). Un protocolo sin esa consulta (dobles
        # de prueba antiguos) sigue con la regla de ESG-01.
        sin_presion = getattr(self._protocolo,
                              "bloqueado_motivo_sin_presion" if presion_perdida else "bloqueado_motivo",
                              None)
        sin_presion = sin_presion if isinstance(sin_presion, str) else None
        motivo = getattr(self._protocolo, "bloqueado_motivo_no_sensor", _SIN_CONSULTA)
        if motivo is _SIN_CONSULTA:
            motivo = sin_presion
        motivo = motivo if isinstance(motivo, str) else None
        principal_solo = sin_presion is not None and motivo is None
        if principal_solo and not self._alarma_principal_activa():
            # Revisión ESS, SAF-07: sin SEN-02/SEN-03 a la vista (p. ej. tras
            # salir de FALLA por P-2 con un Principal que no es del programa
            # seleccionado) CIC-10 sigue siendo el único aviso: se conserva
            motivo = sin_presion
            principal_solo = False
        if principal_solo and not self._principal_perdido_en_log:
            self._principal_perdido_en_log = True
            logger.warning("Estado seguro detenido: sensor Principal sin lectura (%s); ESS-03: "
                           "sin CIC-10 por este motivo, solo la alarma del sensor", sin_presion)
        elif not principal_solo and self._principal_perdido_en_log:
            self._principal_perdido_en_log = False
            logger.info("Estado seguro: el bloqueo por el sensor Principal terminó")
        if self.alarm_manager is None:
            return
        if motivo == self._alarma_bloqueo and (motivo is None or self._cic10_activa()):
            return
        try:
            if motivo is None:
                self.alarm_manager.resolver(CIC_10)
            else:
                self.alarm_manager.activar(CIC_10, motivo=motivo)
            self._alarma_bloqueo = motivo
        except Exception:
            logger.exception("Estado seguro: no se pudo actualizar la alarma de bloqueo")

    def _alarma_principal_activa(self) -> bool:
        """SAF-07: hay una alarma activa DEL Principal (SEN-03 con su nombre
        como origen o SEN-02 que lo nombre; misma regla que /status, SAF-06).
        La de otra sonda no cuenta. Sin gestor, sin protocolo o ante un
        error, False (se conserva CIC-10)."""
        if self.alarm_manager is None or self._protocolo is None:
            return False
        try:
            from autoclave.core.runtime.sensores_ciclo import sensor_principal
            from autoclave.state_machine.alarms.catalogo import nombre_legible
            ciclo = getattr(self._protocolo, "cycle", None)
            legible = nombre_legible("temp_camara" if ciclo is None else sensor_principal(ciclo))
            for i in self.alarm_manager.activas():
                if getattr(i, "estado", None) is not EstadoInstancia.ACTIVA:
                    continue
                codigo = getattr(i, "codigo", None)
                if codigo == "SEN-03" and getattr(i, "origen", None) == legible:
                    return True
                if codigo == "SEN-02":
                    nombrados = {n.strip() for n in
                                 str((getattr(i, "valores", None) or {}).get("sensores", "")).split(",")}
                    if legible in nombrados:
                        return True
            return False
        except Exception:
            return False

    def _cic10_activa(self) -> bool:
        """SAF-03 (revisión S2a): CIC-10 sigue activa en el gestor. Al salir de
        FALLA sin técnico (P-2 / D8-2.6) el reinicio resuelve todas las alarmas;
        con el protocolo aún bloqueado (p. ej. cámara sellada, D8-2.10) hay que
        volver a mostrarla. Ante la duda (gestor sin activas()), True."""
        try:
            return any(getattr(i, "codigo", None) == CIC_10
                       for i in self.alarm_manager.activas())
        except Exception:
            return True

    def _resolver_alarma_bloqueo(self) -> None:
        if self.alarm_manager is not None and self._alarma_bloqueo is not None:
            try:
                self.alarm_manager.resolver(CIC_10)
            except Exception:
                logger.exception("Estado seguro: no se pudo resolver la alarma de bloqueo")
        self._alarma_bloqueo = None

    def _ai_vigente(self) -> bool:
        """S9 (revisión ★ TMG-02): trama AI vigente según lectura_ai; sin
        lectura_ai, True (comportamiento anterior); ante un error, False."""
        if self.lectura_ai is None:
            return True
        try:
            return self.lectura_ai()[0] is True
        except Exception:
            logger.exception("Estado seguro: no se pudo leer la vigencia de la trama AI")
            return False

    def update(self, datos_vigentes: bool = True) -> None:
        if not self.activo:
            return

        if self.estado.get_flag("PARO_EMERGENCIA"):
            # U4 (D2): solo un paro real exige "Confirmar y llevar a estado
            # seguro". Sin datos del módulo E/S (desconectado o sin tramas) se
            # pausa igual, y al volver los datos sigue sin confirmación.
            if self.estado.get_flag("PARO_REAL"):
                if not self._paro_visto:
                    self._paro_visto = True
                    self._evento("paro_activado")
                self.requiere_confirmacion = True
            self._ticks_seguros = 0
            self._pausado = True
            return
        if self._paro_visto:
            self._paro_visto = False
            self._evento("paro_liberado")

        if self.requiere_confirmacion or not datos_vigentes:
            self._ticks_seguros = 0
            self._pausado = True
            return

        if self._pausado:
            self._pausado = False
            reanudar = getattr(self._protocolo, "reanudar", None)
            if callable(reanudar):
                if self._pausa_por_prueba:
                    reanudar(tras_modo_prueba=True)
                else:
                    reanudar()
            self._pausa_por_prueba = False
        # S9, revisión ★ TMG-02: el protocolo lee la vigencia de la trama AI
        if self.lectura_ai is not None:
            self._protocolo.lectura_ai = self.lectura_ai
        solo_lenta_antes = getattr(self._protocolo, "solo_lenta", False) is True
        sellado_antes = getattr(self._protocolo, "sellado", False) is True
        self._protocolo.update()
        if not solo_lenta_antes and getattr(self._protocolo, "solo_lenta", False) is True:
            # R1-P4: el Principal se perdió con el protocolo en marcha
            motivo = getattr(self._protocolo, "motivo_solo_lenta", None)
            self._evento("estado_seguro_solo_lenta",
                         motivo=motivo if isinstance(motivo, str) else "sensor Principal sin lectura")
        sellado = getattr(self._protocolo, "sellado", False) is True
        if not sellado_antes and sellado:
            # D8-2.10: líquidos en modos 4/5, cámara sellada sin venteo
            self._evento("estado_seguro_sellado", motivo="sensor Principal sin lectura")
        elif sellado_antes and not sellado:
            self._evento("estado_seguro_venteo_tras_sellado",
                         motivo=getattr(self._protocolo, "motivo_venteo", None))
        if self.mantener_drenaje is not None:
            try:
                self.mantener_drenaje()
            except Exception:
                logger.exception("Estado seguro: no se pudo mantener el drenaje")
        self._actualizar_alarma_bloqueo()

        programas = None
        if self.programas_seguridad is not None:
            try:
                programas = self.programas_seguridad()
            except Exception:
                logger.exception("Estado seguro: no se pudieron obtener los programas")
                self._ticks_seguros = 0
                return
        propio = getattr(self._protocolo, "cycle", None)
        if programas is None:
            programas = [propio]
        elif propio is not None and not any(p is propio for p in programas):
            # S9 (D9-1.3): con el programa cambiado durante el protocolo, su
            # Principal sigue contando (nunca solo el seleccionado)
            programas = list(programas) + [propio]
        temp_max_ciclo = None
        try:
            temp_max_ciclo = self._protocolo.cycle.get_param("finalizacion", "temp_max_apertura")
        except Exception:
            pass
        segura, _ = camara_segura.evaluar(self.estado, self.config, programas, self.profile,
                                          temp_max_ciclo=temp_max_ciclo)
        if segura and not self._ai_vigente():
            # S9, revisión ★ TMG-02: presión posiblemente congelada
            segura = False
        self._ticks_seguros = self._ticks_seguros + 1 if segura else 0
        if self._ticks_seguros >= _TICKS_SEGUROS:
            duracion = self._reloj() - self._t_inicio if self._t_inicio is not None else None
            self._protocolo.finalizar()
            self._protocolo = None
            self._resolver_alarma_bloqueo()
            self._evento("estado_seguro_alcanzado",
                         duracion_s=round(duracion, 1) if duracion is not None else None)
