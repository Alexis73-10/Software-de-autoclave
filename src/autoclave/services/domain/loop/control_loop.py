# autoclave/services/control_loop.py

import copy
import time
import threading
from autoclave.state_machine.alarms.catalogo import COM_01, COM_04, TARJETA_SIN_TRAMA_VALIDA
from autoclave.state_machine.state_machine import StateMachine
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.devices.paro_emergencia.paro_emergencia import EmergencyStop
from autoclave.devices.suministro_electrico.suministro_electrico import SuministroElectrico
from datetime import datetime
from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket
from autoclave.core.runtime.letalidad import calcular_incremento_f0
from autoclave.core.runtime.lectura import lectura_valida
from autoclave.core.runtime.sensores_ciclo import sensor_principal
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime import aire_atmosferico_prueba
from autoclave.core.runtime import salidas_prueba_seguridad
from autoclave.core.runtime.coherencia_puerta_presion import VigilanciaCoherenciaPuertaPresion
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.installation.profile import entrada_requerida, numero_puertas

import logging

logger = logging.getLogger(__name__)

# T2-b (tanda 7): tramas vigentes seguidas para dar el enlace por recuperado
_TICKS_ENLACE_OK = 3

# Fases del ciclo donde hay letalidad real y corresponde acumular F0.
# ESTABILIZACION ya no existe como fase.name propia (fusionada dentro de
# CALENTAMIENTO, ver CLAUDE.md) — se conserva en el conjunto por si una
# futura reversión de esa fusión la reintroduce; hoy nunca hace match.
_F0_FASES_ACUMULAN = {"CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION"}

# TMG-03 (E3): ticks fallidos seguidos antes de apagar todo (≈1,5 s con el
# periodo de 0,5 s) y frecuencia del log con traza
_EXCEPCIONES_PARA_APAGAR = 3
_LOG_CADA_EXCEPCIONES = 20

# TMG-01 de T4: ticks consecutivos de cámara segura para dejar de considerar
# el Principal del último ciclo (convención de debounce de 3 lecturas).
_TICKS_SEGUROS_OLVIDAR_CICLO = 3

# Fallas del enlace de E/S que, fuera de ciclo, piden repetir la conexión
# verificada (handshake). Desde la tanda 20 (T20-03) solo las emite
# ModbusLink; se conserva el conjunto completo (segunda barrera de MOD-12).
_ALARMAS_PIDEN_HANDSHAKE = {"TARJETA_EXPANSOR_FUERA_DE_LINEA", "DISCREPANCIA_SALIDAS",
                            # Tanda 19 (MOD-12, DECISIÓN SIN CONFIRMAR): las del
                            # enlace Modbus, si llegan en operación fuera de
                            # ciclo, piden también una nueva conexión verificada
                            # (que reescribe y comprueba la configuración de
                            # seguridad y el orden de módulos). El enlace ya
                            # invalida la conexión por sí mismo; esto es una
                            # segunda barrera, igual que con el expansor.
                            "TARJETA_MODULOS_ORDEN", "TARJETA_CONFIG_SEGURIDAD"}
# U4: lecturas seguidas con la DI vencida antes de TARJETA_SIN_TRAMA_VALIDA
_DEBOUNCE_DI_VENCIDA = 3
# D8-2.11 (tanda 8, Q1-P1): reintentos del ALL_OFF sin confirmar al salir del
# modo prueba (uno por tick) antes de la alarma COM-04
_REINTENTOS_ALL_OFF_SALIDA_PRUEBA = 3
# TMG-03 de la revisión S2b: espera máxima del ACK de cada reintento (bajo
# _sm_lock); el ALL_OFF normal espera 1 s
_TIMEOUT_ACK_REINTENTO_ALL_OFF_S = 0.3


class ControlLoop:

    # Loop central del sistema.
    # - Recibe datos del enlace de E/S
    # - Ejecuta servicios (reglas)
    # - Actualiza dispositivos
    # - Publica estado global

    # Tolerancia a caídas breves del link durante un ciclo: una desconexión
    # de menos de este umbral no lo aborta (ruido momentáneo en el enlace).
    # Si se supera, se aborta — ver abortar_por_desconexion().
    _TOLERANCIA_DESCONEXION_SEG = 5.0

    # Vigencia de la trama DI: tres periodos de 500 ms del módulo E/S. Si la
    # última DI es más vieja (o no hay), el paro se publica activo: "sin datos
    # de las entradas = paro" (adenda E0/E1, A-3, TMG-01).
    _VIGENCIA_DI_SEG = 1.5

    def __init__(self, units, door_service, doors, estado, link, set_do,
                 alarm_manager, cycle_manager, config_manager,
                 cycle_logger=None, interval=0.5, cap=None, realtime_printer=None,
                 profile=None):
        self.units          = units
        self.door_service   = door_service
        self.doors          = doors
        self.estado         = estado
        self.interval       = interval
        self.link           = link
        self.set_do         = set_do
        self._running       = threading.Event()
        # "Apagar equipo" aceptado (TMG-01 de T7): desde aquí ningún tick toca
        # la máquina de estados, aunque estuviera esperando el lock
        self._apagando      = False
        # Reentrante: el backend lo toma en su guard de estado
        # (bloqueo_maquina) y dentro llama a enter/exit_test_mode, que también
        # lo toman (planeacion_backend_autenticacion.md, revisión de la etapa 1).
        self._sm_lock       = threading.RLock()
        # Avisos de "modo prueba cancelado por paro de emergencia" (el backend
        # limpia la sesión dueña y lo registra en audit_log).
        self._al_cancelar_prueba = []
        # Configuración inválida al arrancar (CONFIGURACION_INVALIDA): motivo
        # del bloqueo, o None. _bloqueo_apagado indica si ya se mandó ALL_OFF
        # en la conexión actual con el módulo E/S.
        self._bloqueo_config: str | None = None
        self._bloqueo_apagado = False
        self.cycle          = cycle_manager.get_selected_cycle()
        self.config_manager = config_manager
        self.alarm_manager  = alarm_manager
        self.cycle_manager  = cycle_manager
        self.cycle_logger   = cycle_logger
        self.realtime_printer = realtime_printer
        self.cap             = cap
        # Perfil de instalación (E1): entradas de suministro y puertas.
        self.profile         = profile
        # TMG-03 (E3): ticks fallidos seguidos
        self._excepciones_seguidas = 0
        self._apagado_por_excepcion = False
        # SAF-01 de T3 (se usan desde el primer StateMachine)
        self._programa_ultimo_ciclo = None
        self._ticks_seguros_tras_ciclo = 0
        # E4 (D-08): programa del ciclo interrumpido por un reinicio, a
        # recuperar con el primer dato vigente
        self._recuperacion_pendiente = None
        self._ticks_seguros_recuperacion = 0

        # Protocolo de estado seguro (fin de ciclo §15): una sola instancia que
        # sobrevive a set_active_cycle. `al_evento_seguridad(evento, detalle)`
        # lo fija el backend para el audit_log.
        self.al_evento_seguridad = None
        self.estado_seguro = ProtocoloEstadoSeguro(
            estado, config_manager, profile=profile,
            programas_seguridad=self.programas_para_seguridad,
            al_evento=self._evento_seguridad, alarm_manager=alarm_manager)
        # S9, revisión ★ TMG-02/TMG-03: vigencia y número de la trama AI, para
        # que el protocolo no tome una presión congelada por una vigente
        self.estado_seguro.lectura_ai = self._lectura_ai
        # R2-A1 (revisión ★ pasada 2): proveedor común en el estado, para el
        # protocolo de fallo del ciclo (CicloState) y la fase DESCOMPRESION
        # (core/runtime/vigencia_ai.py)
        self.estado.lectura_ai = self._lectura_ai
        # R2-B2: instante (monotónico) de la primera DI vigente de la conexión
        self._primera_di_mono: float | None = None

        self.state_machine     = StateMachine(
            io=self.link, estado=self.estado, set_do=set_do,
            cycle=self.cycle, config=self.config_manager, cap=cap,
            door_service=door_service, profile=profile,
            alarm_manager=self.alarm_manager,
            programas_seguridad=self.programas_para_seguridad,
            temp_max_ciclo=self.temp_max_tras_ciclo,
            estado_seguro=self.estado_seguro,
        )
        # el registro del ciclo (ticket, F0 del pie) lee el programa con el
        # que corre el ciclo, no el almacenado (T-17)
        if self.cycle_logger is not None:
            self.cycle_logger.programa_en_ejecucion = self.programa_en_ejecucion
        self.link_was_connected = True
        self._link_ever_connected = False
        self._desconectado_desde: float | None = None
        # U4 (tanda 2): estado del módulo E/S publicado en /status
        # ("desconectada", "sin_tramas_validas" u "ok"); falla cerrada hasta
        # el primer tick. COM-01 sigue solo a "desconectada" (desde cuándo y
        # si está activa); TARJETA_SIN_TRAMA_VALIDA propia por DI vencida con
        # el enlace hecho (la del handshake la reporta el enlace como evento).
        self.estado_modulo_es = "desconectada"
        self._desconectada_desde: float | None = None
        # T2-b (tanda 7): ticks seguidos con el módulo E/S en "ok" (enlace hecho y
        # trama DI vigente); DESPEJAR de COM-02/03 exige _TICKS_ENLACE_OK
        self._ticks_modulo_es_ok = 0
        # D8-2.9 (tanda 8, TMG-04): número de secuencia de la última trama DI
        # contada; solo una trama DISTINTA y nueva suma a _ticks_modulo_es_ok
        self._ultima_seq_di_contada = None
        # TMG-01 (revisión S2a): incrementos de F0 recientes (instante, valor)
        # para descontar los acreditados después de la última DI válida
        # cuando se abre un tramo sin datos
        self._f0_recientes = []
        self._f0_tramo_descontado = None
        self._com01_activa = False
        self._sin_di_activa = False
        # Ticks seguidos con la DI vencida y el enlace hecho (debounce de 3
        # lecturas antes de la alarma propia; TMG-03 de U4)
        self._ticks_di_vencida = 0
        # Desde cuándo (monotonic) el puerto está presente sin conexión
        self._sin_conexion_desde: float | None = None
        # Ya hubo un tick con DI vigente en esta conexión (TMG-04 de U4)
        self._di_vista_en_conexion = False
        self.paro_emergencia    = EmergencyStop(estado)
        # S9 (tanda 9, D9-1.6): puerta abierta con la presión de cámara fuera
        # de la banda atmosférica, fuera de ciclo (SEN-10)
        self.coherencia_puerta_presion = VigilanciaCoherenciaPuertaPresion(
            alarm_manager, config_manager)
        # D9-9 (tanda 9): PARO_REAL del tick anterior, para el ALL_OFF inmediato
        self._paro_real_previo = False
        self.suministro_electrico = SuministroElectrico(estado, set_do)

        self.thread: threading.Thread | None = None

        # Modo prueba (bench validation): pausa state_machine.update() sin
        # detener el resto del loop (sensores, puertas, enlace de E/S).
        self._test_mode = threading.Event()
        # D8-2.11 (tanda 8): reintentos pendientes del ALL_OFF de la salida
        # del modo prueba (la máquina sigue pausada mientras queden) y
        # número del próximo; COM-04 activa hasta una confirmación.
        self._reintentos_all_off = 0
        self._reintento_all_off_n = 0
        self._com04_activa = False
        # D8-3.19: el lazo ya cerró el aire atmosférico en este modo prueba y
        # registró el evento; se rearma cuando el módulo E/S lo reporta cerrado
        self._aire_prueba_cortado = False
        # S9, revisión ★ SAF-01: salidas de puerta/vapor cortadas por el lazo
        # en modo prueba (registro una vez por salida mientras siga reportada)
        self._salidas_prueba_cortadas: set[str] = set()
        # Tanda 17 (ESG-02): avisos de salidas apagadas por el lazo en este
        # modo prueba, para la pantalla de Entradas / Salidas (los últimos
        # _MAX_AVISOS_CORTE, con número creciente `n`); se vacía al entrar
        self._avisos_corte_prueba: list[dict] = []
        self._n_aviso_corte_prueba = 0
        # D8-3.19 (SAF-01/TMG-01 de la 2.ª revisión): último paso 1 completo
        # (time.monotonic); presion_vigente exige que el estado esté al día
        self._estado_publicado_mono: float | None = None
        # D8-3.19 (SAF-01/TMG-02, re-revisión E1): instante tomado ANTES de
        # leer Units en el paso 1; la compuerta del aire atmosférico exige que
        # sea posterior a la confirmación de la señal de presión
        self.estado_leido_mono: float | None = None

        # Acumulación de F0 (letalidad): timestamp del último tick que
        # acumuló, para calcular dt_min real (no el interval nominal).
        self._f0_ultimo_tick: float | None = None

        # Último valor visto de puerta_2_cerrada con door_count=1, para
        # avisar solo en el flanco (A-6, SAF-07).
        self._puerta_2_no_declarada_cerrada = False

        # Instante (monotonic) desde el que el enlace está conectado en la
        # conexión actual, o None si está caído. Hasta la primera trama DI de
        # esa conexión (como máximo _VIGENCIA_DI_SEG) la máquina de estados no
        # corre: una línea AI: llegada antes que la DI no debe abortar el
        # ciclo por un paro que solo es falta de datos (decisión P3).
        self._conectado_desde: float | None = None

        # Alarmas del módulo E/S reportadas fuera de ciclo, que se despejan al
        # completar el siguiente handshake. Las del fallo de un ciclo no: esas
        # se liberan con el reconocimiento del operador.
        self._alarmas_modulo_es: set[str] = set()

        # SAF-01 de T3: copia del programa del último ciclo ejecutado. Fuera de
        # CICLO su Principal sigue contando para la seguridad de apertura hasta
        # que la cámara sea segura (sobrevive a set_active_cycle).
        self._programa_ultimo_ciclo = None
        self._ticks_seguros_tras_ciclo = 0


    # =========================================================================
    # LOOP DE ACTUALIZACIÓN
    # =========================================================================

    def run(self):
        while self._running.is_set():
            try:
                self._tick()
            except Exception:
                self._tick_fallido()
            else:
                self._excepciones_seguidas = 0
                self._apagado_por_excepcion = False
                # FW-D6 (TMG-01): solo un tick COMPLETADO renueva el latido.
                # Un lazo vivo que falla en cada tick deja de marcar el tick y
                # ModbusLink corta el tráfico (MOD-08): el corte del módulo
                # apaga todo.
                self.link.marcar_tick_control()
            time.sleep(self.interval)


    def _tick_fallido(self) -> None:
        """TMG-03 (E3): un tick que lanza no renueva el latido (TMG-01 de E6)
        y, tras _EXCEPCIONES_PARA_APAGAR seguidos, se apagan todas las salidas
        desde aquí, sin esperar al watchdog del módulo E/S. Log con traza, pero
        limitado (el primero y uno cada _LOG_CADA_EXCEPCIONES)."""
        # SAF-03 (revisión Q1): un tick que no se completa no cuenta como
        # enlace "ok" (enlace_confirmado_ok no queda en True con el lazo caído)
        self._ticks_modulo_es_ok = 0
        # TMG-05 (revisión S2a): se conserva el número de la última trama
        # contada (la misma trama tras el fallo no cuenta como nueva)
        try:
            self.estado.trama_di_nueva = False
        except Exception:
            pass
        self._excepciones_seguidas += 1
        if self._excepciones_seguidas == 1 or self._excepciones_seguidas % _LOG_CADA_EXCEPCIONES == 0:
            logger.exception("ControlLoop: error inesperado en el tick (%d seguidos)",
                             self._excepciones_seguidas)
        if self._excepciones_seguidas >= _EXCEPCIONES_PARA_APAGAR and not self._apagado_por_excepcion:
            self._apagado_por_excepcion = True
            logger.critical("ControlLoop: %d ticks fallidos seguidos — apagando todas las salidas",
                            self._excepciones_seguidas)
            try:
                self.set_do.reset_all_outputs()
            except Exception:
                logger.exception("ControlLoop: no se pudieron apagar las salidas")

    def programa_en_ejecucion(self):
        """Copia del programa con la que corre (o corrió) el último ciclo
        (T-17); sin ciclo iniciado desde la última selección, el programa
        seleccionado."""
        copia = getattr(self.state_machine.ciclo, "programa_en_curso", None)
        return copia if copia is not None else self.cycle

    def programa_para_sensores(self):
        """Programa cuyo sensor Principal decide temperatura de apertura,
        cámara segura y "NO ABRIR" (tanda §1.1): en CICLO, la copia del ciclo
        en curso; fuera de CICLO, el seleccionado y, sin selección, el del
        último ciclo ejecutado. None = temp_camara."""
        if self.estado.get_machine_state() == GlobalState.CICLO:
            return self.programa_en_ejecucion()
        return self.cycle or getattr(self.state_machine.ciclo, "programa_en_curso", None)

    def programas_para_seguridad(self) -> list:
        """Programas cuyos sensores Principales deciden la seguridad de
        apertura (SAF-01 de T3): en CICLO, la copia del ciclo en curso; fuera,
        el seleccionado y, mientras la cámara no haya sido segura desde el
        último ciclo, también el de ese ciclo (se toma el máximo)."""
        if self.estado.get_machine_state() == GlobalState.CICLO:
            return [self.programa_en_ejecucion()]
        # S9 (tanda 9, D9-1.3): con el programa cambiado durante el estado
        # seguro o la recuperación de arranque, sus copias siguen contando
        # aunque ya no sean el seleccionado ni el último ciclo
        programas = []
        for p in (self.cycle, self._programa_ultimo_ciclo, self.estado_seguro.programa,
                  self._recuperacion_pendiente):
            if p is not None and not any(p is q for q in programas):
                programas.append(p)
        return programas

    def recuperar_ciclo_interrumpido(self, programa) -> None:
        """E4 (D-08, SAF-08 de T5): tras un reinicio con un ciclo sin cerrar,
        su sensor Principal cuenta para la seguridad hasta que la cámara sea
        segura y, si no lo es, arranca el protocolo de estado seguro con ese
        programa (modo de descompresión, carga líquida) y con confirmación."""
        with self._sm_lock:
            self._recuperacion_pendiente = programa
            self._ticks_seguros_recuperacion = 0
            self._programa_ultimo_ciclo = programa

    # S4: tolerancia con que un nuevo Principal puede leer menos que otra sonda
    _TOLERANCIA_NUEVO_PRINCIPAL_C = 2.0

    def aplicar_roles_sensores(self, programa_id, asignacion: dict) -> tuple[bool, str]:
        """S4 (tanda 3): el técnico reasignó los roles de sensor de un programa
        (put_sensor_roles ya verificó que el nuevo Principal tiene lectura).
        Las copias del programa que siguen rigiendo la seguridad fuera de
        CICLO (protocolo de estado seguro, último ciclo, recuperación de
        arranque) conservaban la asignación vieja y un estado seguro detenido
        por "Principal sin lectura" no se liberaba.

        Seguridad (revisión SAF-01): una sonda nueva más fría que la carga
        liberaría la cámara con el producto caliente. Por eso solo se acepta si
        su lectura es válida y no es menor que ninguna otra sonda con lectura
        menos la tolerancia; si no, las copias conservan la asignación vieja
        (el estado seguro sigue detenido, NO ABRIR). Las copias se REEMPLAZAN
        por una copia superficial: la instantánea del ciclo terminado (ticket,
        reportes) no se muta (SAF-02). Nunca durante CICLO. Devuelve
        (aplicado, motivo)."""
        with self._sm_lock:
            if self.estado.get_machine_state() == GlobalState.CICLO:
                return False, "ciclo_en_curso"
            copias = (self.estado_seguro.programa, self._programa_ultimo_ciclo,
                      self._recuperacion_pendiente)
            if not any(p is not None and p is not self.cycle
                       and getattr(p, "id", None) == programa_id for p in copias):
                return False, "sin_copias"
            principal = next((k for k, v in asignacion.items() if v == "principal"), None)
            lecturas = getattr(self.estado, "sensores_temp", {}) or {}
            nueva = lecturas.get(principal)
            if not lectura_valida(nueva) or float(nueva) == 0:
                return False, "principal_sin_lectura"
            # Tanda 17 (corrección R3 V17-s3-06): se compara contra todas las
            # sondas del ciclo con lectura, también las No en uso (monitoreo,
            # SON-01) y las de otros programas. Se deja así a propósito: esta
            # comparación solo puede NEGAR la liberación del estado seguro
            # (lado seguro: sigue detenido y con NO ABRIR); nunca la concede.
            # Filtrar por sensores_en_uso podría liberar con una sonda fría
            # mientras otra, sin rol, mide la carga caliente.
            otras = [float(v) for k, v in lecturas.items()
                     if k != principal and k in ("temp_camara", "temp_2_camara", "temp_ref")
                     and lectura_valida(v) and float(v) != 0]
            if otras and float(nueva) < max(otras) - self._TOLERANCIA_NUEVO_PRINCIPAL_C:
                return False, "principal_mas_frio_que_otra_sonda"

            def reemplazo(programa):
                if (programa is None or programa is self.cycle
                        or getattr(programa, "id", None) != programa_id):
                    return programa
                nuevo = copy.copy(programa)
                nuevo.sensores = dict(asignacion)
                nuevo.sensores_formato_antiguo = False
                return nuevo

            if self.estado_seguro.programa is not None:
                self.estado_seguro.reemplazar_programa(reemplazo(self.estado_seguro.programa))
            self._programa_ultimo_ciclo = reemplazo(self._programa_ultimo_ciclo)
            self._recuperacion_pendiente = reemplazo(self._recuperacion_pendiente)
            return True, "aplicado"

    def _procesar_recuperacion(self) -> None:
        programa = self._recuperacion_pendiente
        if programa is None:
            return
        if self.estado.get_machine_state() == GlobalState.CICLO:
            logger.warning("ControlLoop: recuperación de arranque descartada (CICLO)")
            self._recuperacion_pendiente = None
            return
        ai_vigente = self._ai_vigente()
        if not ai_vigente and self._esperando_primera_ai():
            # S9, revisión ★ (pregunta 7): la primera DI puede llegar antes
            # que la primera AI (pres_camara todavía None). No se decide con
            # eso: se espera la AI hasta _VIGENCIA_DI_SEG desde la conexión.
            self._ticks_seguros_recuperacion = 0
            return
        segura, motivo = camara_segura.evaluar(self.estado, self.config_manager,
                                               self.programas_para_seguridad(), self.profile,
                                               temp_max_ciclo=self.temp_max_tras_ciclo())
        if segura and not ai_vigente:
            # S9, revisión ★ TMG-02: con la trama AI vencida la presión
            # publicada puede estar congelada: nunca cuenta como segura
            segura, motivo = False, "Sin lectura válida de presión de cámara (trama AI vencida)"
        if segura:
            # SAF-02 de T6: 3 ticks seguros seguidos antes de descartar
            self._ticks_seguros_recuperacion += 1
            if self._ticks_seguros_recuperacion >= _TICKS_SEGUROS_OLVIDAR_CICLO:
                logger.info("ControlLoop: arranque con la cámara segura")
                self._recuperacion_pendiente = None
            return
        self._ticks_seguros_recuperacion = 0
        logger.error("ControlLoop: arranque con la cámara no segura (%s) — "
                     "estado seguro automático, solo la lenta", motivo)
        # S9 (tanda 9, D9-1.1, revierte en parte E4/D-08): corre SOLO, sin
        # confirmación (D9-1.2: solo tras un paro real de este encendido) y
        # solo con la lenta (con vacío, aire atmosférico; sin presión no abre
        # nada y queda detenido con CIC-10, D9-1.4)
        protocolo = ProtocoloFallo(self.estado, self.set_do, programa, self.config_manager)
        protocolo.ejecutar(abrir_valvulas=False, solo_lenta=True)
        protocolo.motivo_solo_lenta = "arranque con la cámara no segura"
        self.estado_seguro.iniciar(protocolo, origen="arranque")
        if self.estado_seguro.activo:
            self._recuperacion_pendiente = None     # entregada (si no, se reintenta)
        self._evento_seguridad("arranque_camara_no_segura",
                               {"programa": getattr(programa, "id", None), "motivo": motivo})

    def _evento_seguridad(self, evento: str, detalle: dict) -> None:
        if self.al_evento_seguridad is not None:
            self.al_evento_seguridad(evento, detalle)

    def confirmar_estado_seguro(self) -> bool:
        """"Confirmar y llevar a estado seguro" (cualquier operador). Bajo
        _sm_lock para no intercalarse con el tick."""
        with self._sm_lock:
            return self.estado_seguro.confirmar()

    def temp_max_tras_ciclo(self):
        """`finalizacion.temp_max_apertura` del último ciclo mientras su
        Principal siga contando para la seguridad (SAF-04 de T4); si no, None.
        S9 (D9-1.3): también la del programa del protocolo de estado seguro y
        la de la recuperación de arranque; rige la menor."""
        if self.estado.get_machine_state() == GlobalState.CICLO:
            return None
        valores = []
        for programa in (self._programa_ultimo_ciclo, self.estado_seguro.programa,
                         self._recuperacion_pendiente):
            if programa is None:
                continue
            try:
                v = programa.get_param("finalizacion", "temp_max_apertura")
            except Exception:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                valores.append(v)
        return min(valores) if valores else None

    def _seguir_programa_ultimo_ciclo(self, vigentes: bool = True) -> None:
        if self.estado.get_machine_state() == GlobalState.CICLO:
            copia = getattr(self.state_machine.ciclo, "programa_en_curso", None)
            if copia is not None:
                self._programa_ultimo_ciclo = copia
            self._ticks_seguros_tras_ciclo = 0
            return
        if self._programa_ultimo_ciclo is None:
            return
        # TMG-04 de T6: con datos no vigentes o una recuperación pendiente no
        # se cuenta ningún tick como seguro
        if not vigentes or self._recuperacion_pendiente is not None:
            self._ticks_seguros_tras_ciclo = 0
            return
        segura, _ = camara_segura.evaluar(self.estado, self.config_manager,
                                          self.programas_para_seguridad(), self.profile,
                                          temp_max_ciclo=self.temp_max_tras_ciclo())
        # TMG-01 de T4: 3 ticks seguros consecutivos (un tick ruidoso no basta)
        self._ticks_seguros_tras_ciclo = self._ticks_seguros_tras_ciclo + 1 if segura else 0
        if self._ticks_seguros_tras_ciclo >= _TICKS_SEGUROS_OLVIDAR_CICLO:
            self._programa_ultimo_ciclo = None
            self._ticks_seguros_tras_ciclo = 0

    def aplicar_a_ciclo_en_curso(self, seccion: str, path: list[str], valor,
                                 copia_esperada=None) -> bool:
        """§5.8: aplica al ciclo en curso un cambio ya guardado en el programa
        almacenado, solo si su fase no ha iniciado. Bajo _sm_lock (RLock: el
        guard del backend ya lo tiene). `copia_esperada` (X9, D9-13.3): la
        copia consultada antes de registrar la bitácora; si el ciclo en curso
        ya corre con otra (terminó y arrancó otro), no se aplica."""
        with self._sm_lock:
            if self.estado.get_machine_state() != GlobalState.CICLO:
                return False
            if (copia_esperada is not None
                    and getattr(self.state_machine.ciclo, "programa_en_curso", None)
                    is not copia_esperada):
                return False
            return self.state_machine.ciclo.aplicar_si_fase_pendiente(seccion, path, valor)

    def fase_pendiente_en_curso(self, seccion: str, path: list[str]) -> bool:
        """X9 (D9-13.3, TMG-01): True si un cambio de `seccion`/`path` aún
        podría aplicarse al ciclo en curso. Solo consulta (no aplica), bajo
        _sm_lock; el backend aplica después de registrar la bitácora."""
        with self._sm_lock:
            if self.estado.get_machine_state() != GlobalState.CICLO:
                return False
            return self.state_machine.ciclo.fase_pendiente(seccion, path) is True

    @property
    def desconectado(self) -> bool:
        """True mientras el enlace con el módulo E/S está caído (incluida la
        tolerancia): las lecturas no son vigentes. Solo lectura, para el
        backend (órdenes de puerta, revisión de seguridad de la etapa 2)."""
        return self._desconectado_desde is not None

    @property
    def desconexion_en_tolerancia(self) -> bool:
        """D8-2.13 (tanda 8, Q1-P4): el enlace está caído y todavía no venció
        la tolerancia de COM-02 (_TOLERANCIA_DESCONEXION_SEG). /cycle/abort
        acepta entonces la cancelación en espera, como en R1-P5. Lectura de
        un float desde el hilo HTTP (bajo _sm_lock en el backend)."""
        desde = self._desconectado_desde
        return (desde is not None
                and time.monotonic() - desde < self._TOLERANCIA_DESCONEXION_SEG)

    def _di_vigente(self) -> bool:
        """True si la última trama DI del enlace tiene a lo sumo
        _VIGENCIA_DI_SEG segundos. Un enlace que no informa la edad (o la
        informa con un valor no numérico) no se da por vigente."""
        edad = self.link.edad_ultima_di()
        if isinstance(edad, bool) or not isinstance(edad, (int, float)):
            return False
        return edad <= self._VIGENCIA_DI_SEG

    def _ai_vigente(self) -> bool:
        """True si la última trama AI (presiones y temperaturas) tiene a lo
        sumo _VIGENCIA_DI_SEG segundos. Mismo criterio de falla cerrada que
        _di_vigente. Lo usan el aire atmosférico en modo prueba (D8-3.19) y la
        coherencia puerta-presión (S9, D9-1.6)."""
        edad = getattr(self.link, "edad_ultima_ai", lambda: None)()
        if isinstance(edad, bool) or not isinstance(edad, (int, float)):
            return False
        return edad <= self._VIGENCIA_DI_SEG

    def _esperando_primera_ai(self) -> bool:
        """S9 (revisión ★, pregunta 7): en esta conexión todavía no llegó
        ninguna trama AI y no pasó _VIGENCIA_DI_SEG desde la primera DI
        vigente (R2-B2: no desde la conexión; el handshake puede tardar)."""
        try:
            edad = self.link.edad_ultima_ai()
        except Exception:
            return False
        desde = getattr(self, "_primera_di_mono", None)
        return (edad is None and desde is not None
                and time.monotonic() - desde < self._VIGENCIA_DI_SEG)

    def _secuencia_ai(self):
        """S9 (revisión ★ TMG-03): número de la última trama AI según el
        enlace, o None si no lo informa como entero (dobles de prueba: cada
        tick cuenta, como en D8-2.9)."""
        try:
            seq = self.link.secuencia_ultima_ai()
        except Exception:
            return None
        if isinstance(seq, bool) or not isinstance(seq, int):
            return None
        return seq

    def _lectura_ai(self) -> tuple[bool, int | None]:
        """S9 (revisión ★ TMG-02/TMG-03): (trama AI vigente, su número). Lo
        usan el estado seguro y su protocolo. Falla cerrada: ante un error,
        (False, None)."""
        try:
            # R2-B4: edad y número en una sola toma del enlace
            par = self.link.estado_ultima_ai()
            if isinstance(par, tuple) and len(par) == 2:
                edad, seq = par
                vigente = (not isinstance(edad, bool) and isinstance(edad, (int, float))
                           and edad <= self._VIGENCIA_DI_SEG)
                if isinstance(seq, bool) or not isinstance(seq, int):
                    seq = None
                return vigente, seq if vigente else None
            # enlace que no la implementa (dobles de prueba): dos tomas
            return self._ai_vigente() is True, self._secuencia_ai()
        except Exception:
            logger.exception("ControlLoop: no se pudo leer la vigencia de la trama AI")
            return False, None

    def puertas_confirmadas_cerradas(self) -> bool:
        """Tanda 17 (ESG-02, protección 3): todas las puertas instaladas
        (numero_puertas del perfil) con su entrada puerta_N_cerrada en 1 y la
        trama DI vigente. Falla cerrada: falso, sin lectura, datos no
        vigentes o un error, False."""
        try:
            if self.datos_vigentes is not True:
                return False
            di = self.estado.sensores_di
            for num in range(1, numero_puertas(self.profile) + 1):
                valor = di.get(f"puerta_{num}_cerrada")
                if not (valor is True or (type(valor) is int and valor == 1)):
                    return False
            return True
        except Exception:
            logger.exception("Modo prueba: no se pudo leer si las puertas están cerradas")
            return False

    def salidas_prueba_bloqueadas(self) -> dict[str, str]:
        """{salida: código} de las salidas que el modo prueba no puede encender
        ahora (ver core/runtime/salidas_prueba_seguridad.py). S9 (revisión ★
        SAF-01) reemplazado por la tanda 17 (ESG-02, decisión de Cristian): con
        lectura vigente de presión de cámara se retiran los bloqueos propios
        del estado seguro; rigen siempre la presión de cámara para abrir o
        desbloquear puertas y las puertas cerradas para el vapor de cámara.
        La cámara se evalúa con los programas de seguridad, el menor
        temp_max_apertura y la presión al día (presion_vigente); sin eso, no
        segura. Cualquier error: todas. Bajo _sm_lock (reentrante: el backend
        ya lo tiene en guard_estado)."""
        try:
            with self._sm_lock:
                es_activo = self.estado_seguro.activo is True
                recuperacion = self._recuperacion_pendiente is not None
                vigente = self.presion_vigente is True
                segura, _ = camara_segura.evaluar(
                    self.estado, self.config_manager, self.programas_para_seguridad(),
                    self.profile, datos_vigentes=vigente,
                    temp_max_ciclo=self.temp_max_tras_ciclo())
                presion_segura, _ = camara_segura.evaluar_presion(
                    self.estado, self.config_manager, datos_vigentes=vigente)
                lectura_vigente = vigente and camara_segura.lectura_presion(self.estado) is not None
                return salidas_prueba_seguridad.bloqueadas(
                    es_activo, recuperacion, segura is True,
                    presion_vigente=lectura_vigente,
                    presion_segura=presion_segura is True,
                    puertas_cerradas=self.puertas_confirmadas_cerradas())
        except Exception:
            logger.exception("Modo prueba: no se pudo evaluar las salidas bloqueadas; "
                             "se bloquean todas")
            return salidas_prueba_seguridad.todas()

    def _vigilar_salidas_prueba_seguridad(self) -> list[tuple[str, str]]:
        """S9 (revisión ★ SAF-01): en modo prueba, cada tick se ordena apagar
        las salidas bloqueadas (como el aire atmosférico, D8-3.19: la trama DO
        puede llegar tarde). Devuelve las (salida, código) que el módulo E/S
        reportaba encendidas, una vez por salida, para la bitácora."""
        bloqueadas = self.salidas_prueba_bloqueadas()
        salidas = getattr(self.estado, "salidas_do", None) or {}
        nuevas = []
        for clave, codigo in bloqueadas.items():
            try:
                self.set_do.set_output(EstadoAutoclave.map_do[clave] + 1, False)
            except Exception:
                logger.exception("Modo prueba: no se pudo apagar %s", clave)
            if not salidas.get(clave):
                self._salidas_prueba_cortadas.discard(clave)
            elif clave not in self._salidas_prueba_cortadas:
                self._salidas_prueba_cortadas.add(clave)
                logger.warning("Modo prueba: %s apagada por el lazo (%s)", clave, codigo)
                nuevas.append((clave, codigo))
                self._anotar_aviso_corte(clave, codigo)
        self._salidas_prueba_cortadas &= set(bloqueadas)
        return nuevas

    _MAX_AVISOS_CORTE = 10

    def _anotar_aviso_corte(self, clave: str, codigo: str) -> None:
        """Tanda 17 (ESG-02): aviso para la pantalla de Entradas / Salidas de
        una salida que el lazo apagó con la orden ya dada (vapor de cámara con
        una puerta que dejó de estar cerrada; puerta o desbloqueo con la
        cámara que dejó de estar a presión atmosférica)."""
        self._n_aviso_corte_prueba += 1
        self._avisos_corte_prueba.append({
            "n": self._n_aviso_corte_prueba, "salida": clave, "codigo": codigo,
            "aviso": salidas_prueba_seguridad.AVISOS_CORTE.get(codigo, "")})
        del self._avisos_corte_prueba[:-self._MAX_AVISOS_CORTE]

    @property
    def avisos_corte_prueba(self) -> list[dict]:
        """Tanda 17 (ESG-02): copia de los avisos de salidas apagadas por el
        lazo en el modo prueba en curso (cada uno {n, salida, codigo, aviso};
        `aviso` es la clave i18n o "")."""
        return [dict(a) for a in list(self._avisos_corte_prueba)]

    @property
    def presion_vigente(self) -> bool:
        """D8-3.19: datos vigentes (enlace + DI), trama AI al día y estado
        publicado por el paso 1 hace a lo sumo _VIGENCIA_DI_SEG; sin eso,
        pres_camara puede ser una lectura congelada."""
        publicado = getattr(self, "_estado_publicado_mono", None)
        if publicado is None or time.monotonic() - publicado > self._VIGENCIA_DI_SEG:
            return False      # el tick no publica estado: pres_camara congelada
        return self.datos_vigentes and self._ai_vigente()

    @property
    def datos_vigentes(self) -> bool:
        """True si hay enlace y la trama DI está vigente (A-8: el modo prueba
        no acepta órdenes con datos viejos)."""
        return not self.desconectado and self.link.is_connected() and self._di_vigente()

    def _avisar_puerta_2_no_declarada(self) -> None:
        """Aviso (solo log, en el flanco) si la entrada de la puerta 2 lee
        cerrada en un perfil de una puerta: una puerta 2 real quedaría sin
        interlock por software (A-6, SAF-07)."""
        cerrada = (numero_puertas(self.profile) == 1
                   and bool(self.estado.sensores_di.get("puerta_2_cerrada", 0)))
        if cerrada and not self._puerta_2_no_declarada_cerrada:
            logger.warning(
                "La entrada puerta_2_cerrada lee 1 pero el perfil declara door_count=1: "
                "si el equipo tiene segunda puerta, queda sin interlock por software. "
                "Revisar el perfil de instalación."
            )
        self._puerta_2_no_declarada_cerrada = cerrada

    def _secuencia_di(self):
        """D8-2.9: número de secuencia de la trama DI vigente según el enlace,
        o None si el enlace no lo informa como entero (dobles de prueba que no
        lo implementan)."""
        try:
            seq = self.link.secuencia_ultima_di()
        except Exception:
            return None
        if isinstance(seq, bool) or not isinstance(seq, int):
            return None
        return seq

    def _contar_enlace_ok(self) -> None:
        """T2-b: cuenta las tramas DI vigentes seguidas con estado_modulo_es
        "ok". D8-2.9 (tanda 8, TMG-04): solo cuenta una trama DISTINTA y nueva
        (por su número de secuencia); varios ticks que leen la misma trama
        cuentan una vez. Publica en `estado.trama_di_nueva` si en este tick
        llegó una trama nueva y vigente, para la salida de la tolerancia por
        DI vencida de CicloState.

        DECISIÓN SIN CONFIRMAR: un enlace que no informa la secuencia (solo los
        dobles de prueba; ModbusLink siempre la informa) cuenta cada tick "ok"
        como trama nueva, igual que antes de D8-2.9."""
        nueva = False
        self._publicar_ultima_di_valida()
        if self.estado_modulo_es == "ok":
            seq = self._secuencia_di()
            if seq is None or seq != self._ultima_seq_di_contada:
                nueva = True
                self._ticks_modulo_es_ok += 1
            if seq is not None:
                self._ultima_seq_di_contada = seq
        else:
            # La trama vigente antes de la caída no cuenta como nueva al volver
            # (su número se conserva: solo una trama posterior suma)
            self._ticks_modulo_es_ok = 0
        try:
            self.estado.trama_di_nueva = nueva
        except Exception:
            logger.exception("ControlLoop: no se pudo publicar trama_di_nueva")

    def _publicar_ultima_di_valida(self) -> None:
        """TMG-01 (revisión S2a): publica en `estado.ultima_di_valida_mono` el
        instante (monotonic) de la última trama DI vigente, para que el tramo
        sin datos del ciclo empiece ahí y no al detectarlo."""
        try:
            if self.estado_modulo_es != "ok":
                return
            edad = self.link.edad_ultima_di()
            if isinstance(edad, bool) or not isinstance(edad, (int, float)) or edad < 0:
                return
            self.estado.ultima_di_valida_mono = time.monotonic() - float(edad)
        except Exception:
            logger.exception("ControlLoop: no se pudo publicar la última DI válida")

    def _descontar_f0_tramo_sin_datos(self) -> None:
        """TMG-01 (revisión S2a): al abrirse un tramo sin datos del ciclo (con
        inicio en la última DI válida), resta el F0 acreditado después de ese
        instante. Una sola vez por tramo."""
        desde = getattr(self.state_machine.ciclo, "pausa_sin_datos_desde", None)
        if isinstance(desde, bool) or not isinstance(desde, (int, float)):
            return
        if desde == self._f0_tramo_descontado:
            return
        self._f0_tramo_descontado = desde
        # TMG-10 (re-revisión S2a): si el tramo se detecta ya fuera de las
        # fases que acumulan (la exposición pudo terminar por tiempo o F0
        # dentro del retroceso), no se descuenta: el registro quedaría por
        # debajo del F0 con que se dio por cumplida la fase
        if self.estado.fase_ciclo not in _F0_FASES_ACUMULAN:
            self._f0_recientes = []
            return
        exceso = sum(inc for t, inc in self._f0_recientes if t > desde)
        self._f0_recientes = [(t, inc) for t, inc in self._f0_recientes if t <= desde]
        if exceso > 0:
            self.estado.f0_acumulado = max(0.0, self.estado.f0_acumulado - exceso)
            logger.warning("ControlLoop: F0 descontado %.4f min (acreditado sin datos válidos)",
                           exceso)

    @property
    def enlace_confirmado_ok(self) -> bool:
        """T2-b (tanda 7, decisión 1.3 de Cristian): el enlace volvió a "ok"
        con _TICKS_ENLACE_OK tramas vigentes seguidas. Lo consulta el
        DESPEJAR de COM-02/03 (lectura de un int desde el hilo HTTP)."""
        return self._ticks_modulo_es_ok >= _TICKS_ENLACE_OK

    def _actualizar_estado_modulo_es(self, connected: bool, now: float) -> None:
        """U4 (tanda 2): distingue módulo E/S desconectado (no hay puerto o se
        perdió) de módulo E/S sin tramas válidas (puerto presente: sin handshake,
        CRC malo, firmware incompatible o DI vencida) y de ok. COM-01 solo con
        "desconectada"; TARJETA_SIN_TRAMA_VALIDA solo con el puerto presente;
        al pasar de una a otra se resuelve la anterior. No toca el paro ni las
        salidas: eso sigue en el flag combinado PARO_EMERGENCIA."""
        presente = self.link.puerto_presente()
        if not isinstance(presente, bool):
            # Enlace que no informa el puerto (dobles de prueba viejos): se
            # deduce de la conexión; sin conexión = desconectada (falla cerrada)
            presente = connected
        if not presente:
            estado = "desconectada"
        elif connected and self._di_vigente():
            estado = "ok"
        else:
            estado = "sin_tramas_validas"
        self.estado_modulo_es = estado

        if estado == "desconectada":
            self._sin_conexion_desde = None
            self._ticks_di_vencida = 0
            if self._desconectada_desde is None:
                self._desconectada_desde = now
            # Tras una conexión real, en el flanco; en el arranque (handshake
            # aún no hecho) solo pasada la tolerancia, para que el arranque
            # normal no deje COM-01 en el historial.
            if not self._com01_activa and (
                    self._link_ever_connected
                    or now - self._desconectada_desde >= self._TOLERANCIA_DESCONEXION_SEG):
                try:
                    self.alarm_manager.activar(COM_01)
                    self._com01_activa = True
                except Exception:
                    logger.exception("ControlLoop: no se pudo activar COM-01")
            if TARJETA_SIN_TRAMA_VALIDA in self._alarmas_modulo_es or self._sin_di_activa:
                self._alarmas_modulo_es.discard(TARJETA_SIN_TRAMA_VALIDA)
                self._sin_di_activa = False
                self._resolver_alarma(TARJETA_SIN_TRAMA_VALIDA)
            return

        self._desconectada_desde = None
        if self._com01_activa:
            self._com01_activa = False
            self._resolver_alarma(COM_01)

        # DI vencida con el enlace hecho (el módulo E/S manda AI: pero no DI:),
        # fuera de la ventana de la primera DI de la conexión (paso 2a)
        primera_di_pendiente = (self.link.edad_ultima_di() is None
                                and self._conectado_desde is not None
                                and now - self._conectado_desde < self._VIGENCIA_DI_SEG)
        di_vencida = connected and estado != "ok" and not primera_di_pendiente
        self._ticks_di_vencida = self._ticks_di_vencida + 1 if di_vencida else 0
        # Puerto presente sin conexión (handshake en curso o reintentando tras
        # el cierre por timeout de datos): pasada la tolerancia, la misma
        # alarma, sin esperar a que falle el handshake (revisión SAF-07 de U4)
        if connected:
            self._sin_conexion_desde = None
        elif self._sin_conexion_desde is None:
            self._sin_conexion_desde = now
        sin_conexion_larga = (not connected
                              and now - self._sin_conexion_desde >= self._TOLERANCIA_DESCONEXION_SEG)
        if ((self._ticks_di_vencida >= _DEBOUNCE_DI_VENCIDA or sin_conexion_larga)
                and not self._sin_di_activa):
            try:
                self.alarm_manager.activar(
                    TARJETA_SIN_TRAMA_VALIDA,
                    motivo=("No llegan tramas válidas del módulo E/S (puerto presente)."
                        if sin_conexion_larga else
                        "El módulo E/S no envía la trama de entradas (DI) desde hace "
                        f"más de {self._VIGENCIA_DI_SEG:g} s."))
                self._sin_di_activa = True
            except Exception:
                logger.exception("ControlLoop: no se pudo activar TARJETA_SIN_TRAMA_VALIDA")
        elif estado == "ok" and self._sin_di_activa:
            # Solo al volver a "ok" (TMG-01 de U4): el cierre del puerto por
            # timeout de datos deja connected=False pero la causa sigue
            self._sin_di_activa = False
            # Si el handshake la reportó entretanto, la resuelve él al conectar
            if TARJETA_SIN_TRAMA_VALIDA not in self._alarmas_modulo_es:
                self._resolver_alarma(TARJETA_SIN_TRAMA_VALIDA)

    def _resolver_alarma(self, codigo: str) -> None:
        try:
            self.alarm_manager.resolver(codigo)
        except Exception:
            logger.exception("ControlLoop: no se pudo resolver %s", codigo)

    def _procesar_eventos_modulo_es(self) -> None:
        """Reacción a los eventos del enlace de E/S (E6; MOD-12). En ciclo, toda falla en operación aborta el ciclo
        (FALLO + protocolo de fallo). Fuera de ciclo, alarma bloqueante hasta
        el próximo handshake válido; el expansor fuera de línea y la
        discrepancia de salidas además piden ese handshake (WD y reinicio ya
        lo repite el propio enlace)."""
        eventos = self.link.tomar_eventos()
        if not isinstance(eventos, list):
            return
        for ev in eventos:
            # TMG-06: un error con un evento no debe perder los siguientes
            # (la cola ya se vació) ni cortar el resto del tick.
            try:
                self._procesar_evento_modulo_es(ev)
            except Exception as exc:
                logger.error("ControlLoop: error procesando evento del módulo E/S %s: %s",
                             getattr(ev, "alarm_id", None), exc)

    def _procesar_evento_modulo_es(self, ev) -> None:
        # TMG-02 de U4: un handshake cortado porque se quitó el cable reporta
        # el paso en que iba (VER, ACK…); la causa real es la desconexión,
        # que ya da COM-01. No se activa una segunda alarma por lo mismo.
        if ev.origen == "handshake" and self.link.puerto_presente() is False:
            logger.warning("ControlLoop: %s descartada, módulo E/S desconectado (%s)",
                           ev.alarm_id, ev.motivo)
            return
        if ev.origen == "conectada":
            for alarm_id in sorted(self._alarmas_modulo_es):
                self.alarm_manager.resolver(alarm_id)
            self._alarmas_modulo_es.clear()
            # D8-2.11: el handshake incluye un ALL_OFF confirmado
            self._salidas_confirmadas("handshake")
            return

        # TMG-09 (re-revisión S2a): bajo _sm_lock y sin apagado en curso, como
        # el aborto por desconexión (TMG-04)
        with self._sm_lock:
            en_ciclo = self.estado.get_machine_state() == GlobalState.CICLO
            if ev.origen == "operacion" and en_ciclo and not self._apagando:
                # TMG-07: si el ciclo ya terminaba (resultado pendiente), el
                # aborto no actúa y se sigue la ruta de fuera de ciclo.
                if self.state_machine.ciclo.abortar_por_falla_io(ev.alarm_id, ev.motivo):
                    return

        # La acción de seguridad va antes que la alarma (SAF-01 de T1): un
        # error al registrar no debe impedir el nuevo handshake.
        # Decisión 8: en CICLO (también con el resultado ya pendiente) no se
        # repite el handshake; su ALL_OFF cerraría el venteo del protocolo de
        # fallo. Al salir de CICLO lo pide el chequeo SAF-01 de _tick().
        if (ev.origen == "operacion" and ev.alarm_id in _ALARMAS_PIDEN_HANDSHAKE
                and not en_ciclo):
            self.link.solicitar_handshake()
        # Fuera de ciclo: FALLA bloqueante (nivel ALARMA del catálogo) que se
        # resuelve al completarse el siguiente handshake (E6 decisión 9).
        self._alarmas_modulo_es.add(ev.alarm_id)
        self.alarm_manager.activar(ev.alarm_id, motivo=ev.motivo)

    def _tick(self):
        # FW-D6: el latido lo renueva run() al completarse este tick (TMG-01).
        # Antes del chequeo de conexión: un WD o reinicio del módulo E/S deja
        # el enlace sin handshake y el resto del tick no correría.
        self._procesar_eventos_modulo_es()
        # SAF-01: un expansor caído en ciclo aborta el ciclo pero no repite el
        # handshake (el protocolo de fallo necesita las salidas). Fuera de
        # CICLO no se sigue operando con entradas congeladas: se repite el
        # handshake, que falla en el paso 6 mientras pcf_ok no sea 3F y deja
        # la FALLA bloqueante y el equipo sin conexión.
        if (self.estado.get_machine_state() != GlobalState.CICLO
                and self.link.expansor_fuera_de_linea() is True):
            logger.error("ControlLoop: expansor de E/S fuera de línea fuera de ciclo; "
                         "se repite el handshake")
            self.link.solicitar_handshake()

        connected = self.link.is_connected()
        now = time.monotonic()

        if not connected:
            if self.link_was_connected:
                self._desconectado_desde = now
                # La conexión verificada inicial (handshake + primer dato)
                # tarda unos instantes tras el arranque del backend; ese hueco
                # no es una desconexión real y no debe imprimirse.
                if self.realtime_printer is not None and self._link_ever_connected:
                    self.realtime_printer.enqueue(
                        format_connectivity_ticket("MODULO_ES", False, datetime.now())
                    )
            # COM-01 ya no se decide aquí: solo con el módulo E/S desconectado
            # (U4), en _actualizar_estado_modulo_es().
            # Sin conexión no hay datos frescos de sensores, así que este
            # mismo _tick() va a retornar temprano y state_machine.update()
            # no correrá — si había un ciclo en curso, no se detectaría el
            # fallo por sí solo. Se aborta aquí directamente en vez de
            # esperar a una reconexión que puede tardar o no llegar, pero
            # solo una vez agotada la tolerancia: una caída breve (ruido
            # momentáneo en el enlace) no debe tirar el ciclo completo.
            if (self._desconectado_desde is not None
                    and now - self._desconectado_desde >= self._TOLERANCIA_DESCONEXION_SEG):
                # TMG-04 (revisión S2a): bajo _sm_lock, como el resto de las
                # mutaciones del ciclo (el backend lee tolerancia_di_activa
                # con ese lock)
                with self._sm_lock:
                    if (not self._apagando
                            and self.estado.get_machine_state() == GlobalState.CICLO):
                        self.state_machine.ciclo.abortar_por_desconexion(
                            segundos=now - self._desconectado_desde)
        elif connected and not self.link_was_connected:
            self._desconectado_desde = None
            self._bloqueo_apagado = False   # tras reconectar, volver a apagar
            if self.realtime_printer is not None and self._link_ever_connected:
                self.realtime_printer.enqueue(
                    format_connectivity_ticket("MODULO_ES", True, datetime.now())
                )

        if connected:
            self._link_ever_connected = True

        self.link_was_connected = connected

        if connected and self._conectado_desde is None:
            self._conectado_desde = now
        elif not connected:
            self._conectado_desde = None

        try:
            self._actualizar_estado_modulo_es(connected, now)
        except Exception:
            # revisión SAF-05 de U4: no impedir que se publique el paro abajo
            self.estado_modulo_es = "desconectada"
            logger.exception("ControlLoop: no se pudo evaluar el estado del módulo E/S")
        self._contar_enlace_ok()

        if not connected:
            # Sin enlace no hay datos de las entradas: paro (A-3). La máquina
            # de estados no corre, pero el flag queda publicado para la UI, el
            # backend y el primer tick tras reconectar.
            self.paro_emergencia.update(None)
            self._paro_real_previo = False      # D9-9: al volver, flanco nuevo
            self._di_vista_en_conexion = False
            # TMG-01 (revisión Q1): el tramo sin datos no acredita F0
            self._f0_ultimo_tick = None
            # D8-2.7: ni cuenta como exposición (desconexión antes de COM-02)
            self._marcar_ciclo_sin_datos()
            self._descontar_f0_tramo_sin_datos()
            return

        # 1. Publicar estado global
        # `now` (inicio del tick) es anterior a la lectura de Units: sirve de
        # instante de lectura (SAF-01/TMG-02) y, por ser más antiguo, deja la
        # vigencia del estado del lado conservador; sin otra llamada al reloj
        self.estado.update(self.units.get_all())
        self.estado_leido_mono = now
        self._estado_publicado_mono = now

        # 2. Paro de emergencia → actualiza flag en estado. DI crudo, contacto
        # NC: EmergencyStop interpreta 0 o ausente como paro (D-16).
        # Trama DI vencida (el módulo E/S manda AI: pero no DI:) = sin datos (A-3)
        # TMG-04 de U4: en el primer tick con DI vigente de una conexión, el
        # valor de Units puede ser todavía el 0 que dejó _connect() (el enlace
        # fija la edad de la DI antes de notificar a Units). Un 0 en ese tick
        # cuenta como sin datos (bloquea igual) para no dar un paro real falso.
        if self.link.edad_ultima_di() is None:
            self._di_vista_en_conexion = False
            self._primera_di_mono = None
        vigente = self._di_vigente()
        valor = self.estado.sensores_di.get("paro_emergencia") if vigente else None
        if vigente and not self._di_vista_en_conexion:
            self._di_vista_en_conexion = True
            self._primera_di_mono = now        # R2-B2
            if valor is not None and not bool(valor):
                valor = None
        self.paro_emergencia.update(valor)
        self._all_off_en_flanco_de_paro()
        self._avisar_puerta_2_no_declarada()

        # 2a. Recién conectado y sin la primera DI: se publica lo anterior para
        # la UI, pero sin suministro, puertas, máquina de estados ni buzzer (las
        # entradas están en 0 por _connect()). Pasada la vigencia sin DI, se
        # sigue normal con el paro activo y la máquina de estados lo aplica.
        if (self.link.edad_ultima_di() is None
                and now - self._conectado_desde < self._VIGENCIA_DI_SEG):
            # TMG-01 (revisión Q1): sin la primera DI tampoco se acredita F0
            self._f0_ultimo_tick = None
            # D8-2.7: la ventana tras reconectar tampoco cuenta como exposición
            self._marcar_ciclo_sin_datos()
            self._descontar_f0_tramo_sin_datos()
            return

        # 2b. Suministro eléctrico → actualiza flag en estado. Sin la entrada
        # declarada en el perfil (E1-1) no se vigila: ni fallo ni apagado.
        if entrada_requerida(self.profile, "suministro_electrico"):
            # Sin la entrada en la trama = sin suministro (A-9)
            self.suministro_electrico.update(
                bool(self.estado.sensores_di.get("suministro_electrico"))
            )

        # 2d. Configuración inválida: el equipo queda con todo apagado y sin
        # puertas, máquina de estados, registro de ciclo ni buzzer. Sí se
        # siguen publicando sensores y paro de emergencia para la UI.
        if self._bloqueo_config is not None:
            if not self._bloqueo_apagado:
                self.set_do.reset_all_outputs()
                self._bloqueo_apagado = True
            return

        # Pasos 2c a 5 bajo _sm_lock: el modo prueba solo cambia con este lock
        # tomado (enter/exit_test_mode y el guard del backend), así que lo que
        # aquí se decide según _test_mode no puede quedar desfasado a mitad de
        # tick (revisión de la etapa 1 de autenticación, TMG-04 / SAF-03).
        with self._sm_lock:
            # TMG-01 de T7: apagado aceptado mientras este tick esperaba el lock
            if self._apagando:
                return
            # 2c. Salvaguarda: si se activa el paro de emergencia estando en
            # modo prueba, se cancela el modo prueba de inmediato para que la
            # máquina de estados retome el control y aplique su protocolo de
            # paro de emergencia en este mismo tick.
            cancelado_por_paro = (self._test_mode.is_set()
                                  and self.estado.get_flag("PARO_EMERGENCIA"))
            if cancelado_por_paro:
                self.set_do.reset_all_outputs()
                self._test_mode.clear()
                logger.warning(
                    "Modo prueba cancelado automáticamente: paro de emergencia activado."
                )

            # D8-2.11 (tanda 8): reintentos del ALL_OFF de la salida del modo
            # prueba. Mientras queden, la máquina sigue pausada como en el
            # modo prueba, salvo con el paro activo (aplica su protocolo).
            if self._reintentos_all_off > 0 and not self._test_mode.is_set():
                self._reintentar_all_off()
            pausada = self._test_mode.is_set() or (
                self._reintentos_all_off > 0 and not self.estado.get_flag("PARO_EMERGENCIA"))

            # 2e. D8-3.19 (tanda 8): en modo prueba, el aire atmosférico de la
            # cámara abierto con la cámara presurizada o sin lectura de presión
            # se cierra (la orden de abrir ya se rechaza en /io/test/output).
            aire_cortado = (self._vigilar_aire_atmosferico_prueba(
                                vigentes=connected and not self.desconectado
                                and self._di_vigente() and self._ai_vigente())
                            if self._test_mode.is_set() else None)
            # S9, revisión ★ SAF-01 / tanda 17 (ESG-02): salidas bloqueadas en
            # modo prueba apagadas en este mismo tick (puertas con la cámara no
            # segura en presión, vapor de cámara con una puerta no cerrada, y
            # sin lectura vigente de presión los bloqueos del estado seguro)
            salidas_cortadas = (self._vigilar_salidas_prueba_seguridad()
                                if self._test_mode.is_set() else [])

            # 3. Dispositivos → actúan (pausado durante el modo prueba: las
            # puertas re-asertan sus propias salidas, p.ej. cerrar_on() en
            # cada tick mientras están CERRADO, lo que pisaría el control
            # manual de esas mismas salidas desde /io/test/output).
            if not pausada:
                for door in self.doors:
                    door.update()

            # 4. Servicios → deciden
            self.door_service.update()

            # 5. Máquina de estados global (pausada durante el modo prueba)
            if not pausada:
                # TMG-03 de T5: el estado seguro solo avanza con datos vigentes
                # (sin volver a consultar el enlace: se usa la lectura de este tick)
                vigentes = connected and not self.desconectado and self._di_vigente()
                if vigentes and self._recuperacion_pendiente is not None:
                    self._procesar_recuperacion()
                self.state_machine.update(datos_vigentes=vigentes)
            # S9, revisión ★ TMG-02: con la trama AI vencida no se cuenta
            # ningún tick como seguro (presión posiblemente congelada)
            self._seguir_programa_ultimo_ciclo(
                vigentes=connected and not self.desconectado and self._di_vigente()
                and self._ai_vigente())
            # S9 (D9-1.6): coherencia puerta-presión, fuera de ciclo y sin
            # modo prueba (las puertas no se actualizan en pausa: el conteo
            # vuelve a cero, revisión ★ TMG-03). TMG-06: un error aquí no
            # aborta el tick.
            try:
                if not pausada:
                    self.coherencia_puerta_presion.update(
                        self.estado,
                        vigentes=connected and not self.desconectado and self._di_vigente()
                        and self._ai_vigente(),
                        seq_ai=self._secuencia_ai())
                else:
                    self.coherencia_puerta_presion.reiniciar_conteo()
            except Exception:
                logger.exception("ControlLoop: error en la coherencia puerta-presión")
                try:
                    self.coherencia_puerta_presion.reiniciar_conteo()
                except Exception:
                    logger.exception("ControlLoop: no se pudo reiniciar la coherencia")

        # Fuera del lock: quien escucha registra en la bitácora (SQLite)
        if cancelado_por_paro:
            self._avisar_cancelacion_prueba()
        for salida, codigo in salidas_cortadas:
            self._evento_seguridad("salida_prueba_cortada", {"salida": salida, "motivo": codigo})
        if aire_cortado:
            self._evento_seguridad("aire_atmosferico_cortado_prueba", {
                "motivo": aire_cortado,
                "pres_camara": self.estado.sensores_pres.get("pres_camara")})

        # 5b. Acumulación de F0 (letalidad) — solo lee estado.fase_ciclo, ya
        # publicado, así que el orden respecto al paso 5 no importa. RR-01
        # (re-revisión Q1): con los mismos datos vigentes que el paso 5.
        self._acumular_f0(now, vigentes=connected and not self.desconectado
                          and self._di_vigente())

        # 6. Data logger (observa machine_state internamente)
        if self.cycle_logger is not None:
            self.cycle_logger.update()

        # 7. Buzzer (pausado durante el modo prueba: una secuencia ya en
        # curso al entrar — p.ej. alarma de FALLA, que no bloquea la
        # entrada a modo prueba — seguiría escribiendo buzer_alarma y
        # pisaría el control manual de esa salida).
        if not self._test_mode.is_set():
            self.set_do.buzer.update()

    def _all_off_en_flanco_de_paro(self) -> None:
        """D9-9 (tanda 9): en el tick en que aparece el paro real, ALL_OFF con
        ACK de inmediato, antes de puertas y máquina de estados y sea cual sea
        el estado (sin esperar el intervalo de apagar_por_paro). Bajo _sm_lock,
        como los ALL_OFF de entrar/salir del modo prueba, para que dos ALL_OFF
        no compartan la espera del ACK (TMG-02 de la revisión B9). Nunca
        lanza: el tick tiene que seguir hasta la máquina de estados."""
        paro_real = self.estado.get_flag("PARO_REAL") is True
        flanco = paro_real and not self._paro_real_previo
        self._paro_real_previo = paro_real
        if not flanco:
            return
        logger.warning("ControlLoop: paro de emergencia detectado; ALL_OFF inmediato")
        try:
            with self._sm_lock:
                confirmado = self.set_do.apagar_por_paro(inmediato=True)
            if confirmado is False:
                logger.error("ControlLoop: el módulo E/S no confirmó el ALL_OFF del paro "
                             "(quedaron órdenes individuales; se repite en el tick)")
        except Exception:
            logger.exception("ControlLoop: no se pudo enviar el ALL_OFF del paro")

    def _marcar_ciclo_sin_datos(self) -> None:
        """D8-2.7 (tanda 8): tick de CICLO sin datos del módulo E/S (la máquina
        de estados no corre). El ciclo abre su tramo sin datos: la exposición
        de ESTERILIZACION se pausa y se descuenta al volver los datos. Nunca
        lanza: el tick sin conexión tiene que terminar igual."""
        try:
            with self._sm_lock:
                # TMG-13 (re-revisión S2a): marcar puede abortar (SAF-05)
                if self._apagando or self.estado.get_machine_state() != GlobalState.CICLO:
                    return
                marcar = getattr(self.state_machine.ciclo, "marcar_sin_datos_modulo_es", None)
                if callable(marcar):
                    marcar()
        except Exception:
            logger.exception("ControlLoop: no se pudo marcar el tramo sin datos del ciclo")

    def _vigilar_aire_atmosferico_prueba(self, vigentes: bool = True) -> str | None:
        """D8-3.19: con el modo prueba activo, mientras la condición de
        apertura del aire atmosférico de la cámara no se cumpla (presión sobre
        atm + brecha, sin lectura o datos no vigentes), se ordena cerrarlo en
        cada tick, sin mirar lo que reporta el módulo E/S (SAF-02 / TMG-01: la
        trama DO puede llegar tarde o no llegar). Cerrar es el lado seguro:
        inmediato, sin debounce, e idempotente. Si el módulo E/S lo reportaba
        abierto, devuelve el código del motivo una vez (para la bitácora);
        se rearma cuando el módulo E/S lo reporta cerrado."""
        canal = EstadoAutoclave.map_do[aire_atmosferico_prueba.CLAVE_ESTADO] + 1
        try:
            salidas = getattr(self.estado, "salidas_do", None) or {}
            reportada = bool(salidas.get(aire_atmosferico_prueba.CLAVE_ESTADO))
            if vigentes:
                permitido, codigo = aire_atmosferico_prueba.evaluar(
                    self.estado, self.config_manager,
                    senal_presente=aire_atmosferico_prueba.senal_camara(
                        self.units, leido_mono=self.estado_leido_mono))
            else:
                permitido, codigo = False, aire_atmosferico_prueba.SIN_PRESION
        except Exception:
            # TMG-06: un error aquí no debe abortar el tick; se cierra
            logger.exception("Modo prueba: no se pudo evaluar el aire atmosférico; se cierra")
            reportada, permitido, codigo = True, False, aire_atmosferico_prueba.SIN_PRESION
        if not reportada:
            self._aire_prueba_cortado = False
        if permitido:
            return None
        self.set_do.set_output(canal, False)
        if not reportada or self._aire_prueba_cortado:
            return None
        self._aire_prueba_cortado = True
        logger.warning("Modo prueba: aire atmosférico de cámara cerrado por el lazo (%s)", codigo)
        return codigo

    def _acumular_f0(self, now: float, vigentes: bool = True) -> None:
        """Acumula letalidad (F0) mientras el ciclo está en una fase con
        letalidad real y el ciclo activo tiene globals.F0 activado. El
        timestamp se resetea a None cada vez que alguna condición no se
        cumple, así que al reingresar a las fases que acumulan (p.ej. tras
        PRE_VACIO, que nunca acumula) el primer tick solo inicializa el
        timestamp sin sumar — evita un dt_min inflado por el tiempo pasado
        en fases previas."""
        # F0 solo en equipos de laboratorio (tanda §1.1); sin capacidades
        # conocidas se respeta el parámetro (comportamiento previo)
        es_lab = self.cap is None or bool(getattr(self.cap, "has_liquid_sensor", False))
        condiciones = (
            es_lab
            and self.estado.get_machine_state() == GlobalState.CICLO
            and self.estado.fase_ciclo in _F0_FASES_ACUMULAN
            and bool(self.programa_en_ejecucion().get_param("globals", "F0"))
        )
        # RR-01 (re-revisión Q1): sin datos vigentes o con la fase pausada por
        # la tolerancia de DI vencida (T2-a) no se acredita F0: fase_ciclo
        # sigue en ESTERILIZACION y los ticks llegan a 0,5 s, así que el tope
        # de 2 intervalos de abajo no lo cubre.
        # D8-2.7: tampoco en el tramo de una desconexión total o la ventana
        # tras reconectar (exposicion_en_pausa)
        ciclo = self.state_machine.ciclo
        self._descontar_f0_tramo_sin_datos()
        if condiciones and (not vigentes
                            or getattr(ciclo, "tolerancia_di_activa", False) is True
                            or getattr(ciclo, "exposicion_en_pausa", False) is True):
            condiciones = False
        if not condiciones:
            self._f0_ultimo_tick = None
            return

        ultimo = self._f0_ultimo_tick
        self._f0_ultimo_tick = now
        if ultimo is None:
            return
        # TMG-01 (revisión Q1): un hueco de más de 2 intervalos nominales
        # (enlace caído, tick bloqueado) no se acredita: solo se reinicia el
        # sello. Contar de menos alarga el ciclo; contar de más no es seguro.
        if now - ultimo > 2 * self.interval:
            return

        # F0 usa solo el sensor Principal del programa en curso (tanda §1.1;
        # reemplaza el mínimo temp_camara/temp_2_camara, decisión C-1)
        t_ref = self.estado.sensores_temp.get(sensor_principal(self.programa_en_ejecucion()))
        if not lectura_valida(t_ref):
            return

        dt_min = (now - ultimo) / 60.0
        incremento = calcular_incremento_f0(t_ref, dt_min)
        self.estado.f0_acumulado += incremento
        # TMG-01 (revisión S2a): se guardan los de los últimos segundos
        self._f0_recientes.append((now, incremento))
        self._f0_recientes = [(t, inc) for t, inc in self._f0_recientes if now - t <= 5.0]

    # =========================================================================
    # CONTROL DE VIDA
    # =========================================================================

    def start(self):
        if self._running.is_set():
            logger.warning("El bucle de control ya está en ejecución.")
            return

        self._running.set()
        self.thread = threading.Thread(target=self.run, name="ControlLoop", daemon=True)
        self.thread.start()

    @property
    def apagando(self) -> bool:
        return self._apagando

    def iniciar_apagado(self) -> None:
        """"Apagar equipo" (TMG-01 de T7): llamado bajo _sm_lock por el
        backend, en el mismo bloque que validó el apagado. Descarta un
        START_CICLO pendiente y detiene el lazo sin esperar el hilo (el tick
        espera este mismo lock); stop() hace después el join y el ALL_OFF."""
        with self._sm_lock:
            self._apagando = True
            self.estado.set_flag("START_CICLO", False)
            self._running.clear()
            # A1 (SAF-01): el lazo ya no gobierna las salidas; se apagan desde
            # ya (mejor esfuerzo, sin módulo E/S devuelve False al instante) y no
            # solo cuando stop() llegue tras la auditoría y el join del hilo
            try:
                if self.link:
                    self.link.all_off()
                    self._anotar_todo_apagado()
            except Exception:
                logger.exception("Control loop: ALL_OFF al iniciar el apagado falló")

    def _anotar_todo_apagado(self) -> None:
        """AJ-02: el ALL_OFF directo al enlace (apagado del equipo) también
        deja sin peticiones el agua del intercambiador. Nunca lanza."""
        try:
            anotar = getattr(self.set_do, "anotar_todo_apagado", None)
            if callable(anotar):
                anotar()
        except Exception:
            logger.exception("Control loop: no se pudieron anotar las salidas apagadas")

    def stop(self):
        # Primero se detiene el lazo y después se apaga (TMG-11 de E6, TMG-02
        # de T1): un tick que corriera tras el ALL_OFF podía volver a encender
        # salidas hasta el corte por vigilancia del módulo.
        self._running.clear()

        if self.thread and threading.current_thread() is not self.thread:
            self.thread.join(timeout=3)

        if self.thread and self.thread.is_alive():
            logger.error("Control loop: el hilo no terminó en 3 s; se apaga igual")

        if self.link:
            # TMG-04 de T7: un ALL_OFF sin confirmar se reintenta una vez y se
            # registra; el respaldo final es el watchdog del módulo E/S
            # A1 (tanda 3): sin módulo E/S o con el enlace roto, el ALL_OFF puede
            # fallar o lanzar; el puerto se cierra igual y el apagado sigue
            try:
                if not self.link.all_off() and not self.link.all_off():
                    logger.error("Control loop: ALL_OFF sin confirmar al detener; "
                                 "queda el watchdog del módulo E/S")
                self._anotar_todo_apagado()
            except Exception:
                logger.exception("Control loop: ALL_OFF falló al detener; "
                                 "quedan el paro y el watchdog del módulo E/S")
            try:
                self.link.stop()
            except Exception:
                logger.exception("Control loop: no se pudo cerrar el enlace con el módulo E/S")

        logger.info("Control loop detenido.")

    # =========================================================================
    # MODO PRUEBA (bench validation)
    # =========================================================================

    @property
    def test_mode_active(self) -> bool:
        return self._test_mode.is_set()

    def bloqueo_maquina(self):
        """Lock de la máquina de estados (_sm_lock, reentrante), para que el
        guard de estado del backend compruebe y escriba sin intercalarse con
        el tick — mismo precedente que set_active_cycle."""
        return self._sm_lock

    def al_cancelar_modo_prueba(self, callback) -> None:
        """Registra `callback()`, llamado desde el hilo del loop (fuera de
        _sm_lock) cuando el paro de emergencia cancela el modo prueba."""
        self._al_cancelar_prueba.append(callback)

    def _avisar_cancelacion_prueba(self) -> None:
        for callback in self._al_cancelar_prueba:
            try:
                callback()
            except Exception:
                logger.exception("Error en el aviso de cancelación del modo prueba")

    @property
    def bloqueo_configuracion(self) -> str | None:
        """Motivo del bloqueo por configuración inválida, o None."""
        return self._bloqueo_config

    def bloquear_por_configuracion(self, motivo: str) -> None:
        """Deja el equipo bloqueado hasta reiniciar: cada tick solo publica
        sensores y paro de emergencia, y las salidas se apagan en cuanto hay
        conexión con el módulo E/S. Llamar antes de start()."""
        with self._sm_lock:
            self._bloqueo_config = motivo
            self._bloqueo_apagado = False
        logger.critical("Equipo bloqueado por configuración inválida: %s", motivo)

    def enter_test_mode(self) -> tuple[bool, str]:
        """Pausa state_machine.update(), las puertas y el buzzer, y apaga
        todas las salidas para permitir control manual. No pausa la lectura
        de sensores ni el paro de emergencia. Bajo _sm_lock: ningún tick queda
        a medio camino con la decisión de modo prueba vieja."""
        with self._sm_lock:
            if self._bloqueo_config is not None:
                return False, f"Configuración inválida: {self._bloqueo_config}"

            if self._apagando:   # A1 (tanda 3): sin salidas manuales mientras se apaga
                return False, "No se puede activar el modo prueba: el equipo se está apagando."

            if self.estado.get_machine_state() == GlobalState.CICLO:
                return False, "No se puede activar el modo prueba durante un ciclo en curso."

            if self.estado.get_flag("PARO_EMERGENCIA"):
                if not self.estado.get_flag("PARO_REAL"):
                    return False, ("No se puede activar el modo prueba sin datos válidos "
                                   "del módulo E/S.")
                return False, "No se puede activar el modo prueba con el paro de emergencia activado."

            # S9 (tanda 9, D9-1.3, revierte SAF-03 de T6): permitido con el
            # estado seguro activo o la recuperación pendiente. El protocolo
            # se pausa (la máquina de estados no corre) y se reanuda al salir,
            # tras el ALL_OFF de siempre.
            self._test_mode.set()
            self.estado_seguro.pausar("modo_prueba")
            # S9, revisión ★ TMG-05: la recuperación de arranque vuelve a
            # contar sus 3 ticks seguros desde cero al salir
            self._ticks_seguros_recuperacion = 0
            self._salidas_prueba_cortadas.clear()
            self._avisos_corte_prueba.clear()
            # D8-2.11: entrar cancela los reintentos pendientes (el modo
            # prueba vuelve a pausar todo y su salida apaga de nuevo)
            self._reintentos_all_off = 0
            # TMG-04 de la revisión S2b (DECISIÓN SIN CONFIRMAR): una orden de
            # inicio anterior a las pruebas no se aplica al salir (re-revisión
            # S2b: queda en el log y en la bitácora)
            if self.estado.get_flag("START_CICLO"):
                logger.warning("Modo prueba: se descarta una orden de inicio de ciclo pendiente")
                self._evento_seguridad("inicio_descartado_por_modo_prueba", {})
            self.estado.set_flag("START_CICLO", False)
            self.set_do.buzer.stop()
            if self.set_do.reset_all_outputs() is True:
                self._salidas_confirmadas("modo_prueba")
            return True, ""

    def exit_test_mode(self) -> bool:
        """Apaga todas las salidas y reanuda state_machine.update(). Bajo
        _sm_lock y en este orden (apagar, luego reanudar): una orden de
        /io/test/output ya validada no puede llegar después del apagado, y la
        máquina de estados no corre un tick con salidas de prueba encendidas.

        R1-P1 (tanda 7): devuelve True solo si el módulo E/S confirmó el ALL_OFF
        con su ACK (`reset_all_outputs`); quien llama lo anota en la bitácora.
        Lo que se apaga no cambia."""
        with self._sm_lock:
            confirmado = self.set_do.reset_all_outputs() is True
            self._test_mode.clear()
            # D8-2.11 (tanda 8, Q1-P1): sin ACK, la máquina sigue pausada y el
            # tick reintenta el ALL_OFF hasta 3 veces (ver _reintentar_all_off)
            if confirmado:
                self._reintentos_all_off = 0
                self._salidas_confirmadas("modo_prueba")
            else:
                self._reintentos_all_off = _REINTENTOS_ALL_OFF_SALIDA_PRUEBA
                self._reintento_all_off_n = 1
        if not confirmado:
            logger.warning("Salida del modo prueba: el módulo E/S no confirmó el ALL_OFF "
                           "(quedaron órdenes individuales sin confirmación); se "
                           "reintenta %d veces", _REINTENTOS_ALL_OFF_SALIDA_PRUEBA)
        return confirmado

    @property
    def salidas_sin_confirmar_pendiente(self) -> bool:
        """D8-2.11: quedan reintentos del ALL_OFF de la salida del modo prueba
        (la máquina de estados sigue pausada)."""
        return self._reintentos_all_off > 0

    def _reintentar_all_off(self) -> None:
        """D8-2.11 (tanda 8, Q1-P1): un reintento por tick, bajo _sm_lock. Si
        confirma, se reanuda la máquina y se anota en la bitácora. Si se
        agotan los 3, alarma COM-04 (bloquea el inicio), se reanuda la máquina
        y, fuera de CICLO, se repite el handshake (su ALL_OFF confirmado es la
        confirmación que la despeja)."""
        n = self._reintento_all_off_n
        try:
            confirmado = self.set_do.reset_all_outputs(
                timeout=_TIMEOUT_ACK_REINTENTO_ALL_OFF_S) is True
        except Exception:
            logger.exception("ControlLoop: el reintento %d del ALL_OFF falló", n)
            confirmado = False
        if confirmado:
            self._reintentos_all_off = 0
            logger.info("Salida del modo prueba: ALL_OFF confirmado en el reintento %d", n)
            self._evento_seguridad("salidas_confirmadas_tras_reintento", {"reintento": n})
            self._salidas_confirmadas("reintento", registrar=False)
            return
        self._reintentos_all_off -= 1
        self._reintento_all_off_n = n + 1
        if self._reintentos_all_off > 0:
            return
        logger.error("Salida del modo prueba: ALL_OFF sin confirmar tras %d reintentos; "
                     "alarma COM-04", _REINTENTOS_ALL_OFF_SALIDA_PRUEBA)
        try:
            self.alarm_manager.activar(COM_04)
            self._com04_activa = True
        except Exception:
            logger.exception("ControlLoop: no se pudo activar COM-04")
        self._evento_seguridad("salidas_sin_confirmar",
                               {"reintentos": _REINTENTOS_ALL_OFF_SALIDA_PRUEBA})
        if self.estado.get_machine_state() != GlobalState.CICLO:
            self.link.solicitar_handshake()

    def _com04_en_gestor(self) -> bool:
        # re-revisión S2b: solo ACTIVA (una RESUELTA_SIN_RECONOCER no cuenta)
        try:
            from autoclave.state_machine.alarms.instancia import (
                EstadoInstancia, InstanciaAlarma)
            inst = self.alarm_manager.obtener(COM_04)
            return isinstance(inst, InstanciaAlarma) and inst.estado is EstadoInstancia.ACTIVA
        except Exception:
            return False

    def _salidas_confirmadas(self, origen: str, registrar: bool = True) -> None:
        """D8-2.11: llegó una confirmación (ALL_OFF con ACK o handshake
        completo): se despeja COM-04 si estaba activa."""
        # SAF-01 de la revisión S2b: también si el gestor la tiene activa
        # aunque la marca local se haya desfasado
        if not (self._com04_activa or self._com04_en_gestor()):
            return
        self._com04_activa = False
        self._resolver_alarma(COM_04)
        logger.info("COM-04 despejada: salidas confirmadas (%s)", origen)
        if registrar:
            self._evento_seguridad("salidas_confirmadas", {"origen": origen})

    # =========================================================================
    # CAMBIO DE CICLO ACTIVO
    # =========================================================================

    def _motivo_no_cambiar_ciclo(self) -> str | None:
        """S2 (tanda 2): "en curso" en sentido amplio. Además de CICLO (que
        incluye la espera de confirmación), el paro, el estado seguro (en curso
        o pendiente de confirmar), la recuperación pendiente tras un reinicio y
        un inicio ya pedido (START_CICLO): la StateMachine nueva no debe
        reemplazar a la que lleva la cámara a estado seguro ni descartar en
        silencio el inicio validado con el programa anterior. También EMERGENCIA,
        HIBERNACION, modo prueba, apagado y configuración inválida, como los
        guards de escritura del backend. Llamar bajo _sm_lock. El chequeo del
        paro es preventivo: la garantía es el update() de la StateMachine."""
        estado_maquina = self.estado.get_machine_state()
        if estado_maquina == GlobalState.CICLO:
            return "No se puede cambiar de ciclo mientras hay uno en curso."
        # D8-5.1 (tanda 8, Cristian 22-oct 12:08): sin módulo E/S o sin datos
        # vigentes (PARO_EMERGENCIA sin PARO_REAL, U4) el programa SÍ se puede
        # cambiar: elegirlo no acciona nada y el inicio del ciclo sigue
        # exigiendo datos, sensores y todas sus condiciones. Solo el paro
        # leído (PARO_REAL) bloquea.
        if self.estado.get_flag("PARO_EMERGENCIA") and self.estado.get_flag("PARO_REAL"):
            return "No se puede cambiar de ciclo con el paro de emergencia activado."
        # S9 (tanda 9, D9-1.3): con el estado seguro activo o la recuperación
        # pendiente SÍ se cambia: elegir no acciona nada, el protocolo y sus
        # copias del programa sobreviven a set_active_cycle y siguen contando
        # para la seguridad (programas_para_seguridad, temp_max_tras_ciclo);
        # el inicio sigue bloqueado mientras el protocolo esté activo.
        if self.estado.get_flag("START_CICLO"):
            return "No se puede cambiar de ciclo: ya se pidió el inicio de uno."
        if self._test_mode.is_set():
            return "No se puede cambiar de ciclo con el modo prueba activo."
        if self._apagando:
            return "No se puede cambiar de ciclo: el equipo se está apagando."
        if self._bloqueo_config is not None:
            return f"Configuración inválida: {self._bloqueo_config}"
        return None

    def set_active_cycle(self, cycle) -> tuple[bool, str]:
        """Reemplaza el ciclo activo y reconstruye la StateMachine para que el
        cambio se propague a todos los sub-estados y fases. Solo seguro fuera
        de CICLO: no hay fases en curso cuyo estado interno se pierda.

        El chequeo de estado y la reconstrucción corren dentro de _sm_lock
        para que no puedan intercalarse con state_machine.update() en
        _tick() (hilo de fondo) — sin el lock, un START_CICLO concurrente
        podía colarse entre el chequeo y la reconstrucción y dejar una
        StateMachine nueva (prev_state=None) pisando un ciclo recién
        iniciado."""
        with self._sm_lock:
            motivo = self._motivo_no_cambiar_ciclo()
            if motivo is not None:
                return False, motivo

            self.cycle = cycle
            self.state_machine = StateMachine(
                io=self.link, estado=self.estado, set_do=self.set_do,
                cycle=cycle, config=self.config_manager, cap=self.cap,
                door_service=self.door_service, profile=self.profile,
                alarm_manager=self.alarm_manager,
                programas_seguridad=self.programas_para_seguridad,
                temp_max_ciclo=self.temp_max_tras_ciclo,
                estado_seguro=self.estado_seguro,
            )
            return True, ""
