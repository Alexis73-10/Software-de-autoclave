# autoclave/services/control_loop.py

import time
import threading
from autoclave.state_machine.alarms.catalogo import COM_01
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
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.installation.profile import entrada_requerida, numero_puertas

import logging

logger = logging.getLogger(__name__)

# Fases del ciclo donde hay letalidad real y corresponde acumular F0.
# ESTABILIZACION ya no existe como fase.name propia (fusionada dentro de
# CALENTAMIENTO, ver CLAUDE.md) — se conserva en el conjunto por si una
# futura reversión de esa fusión la reintroduce; hoy nunca hace match.
_F0_FASES_ACUMULAN = {"CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION"}

# Fallas de la tarjeta que, fuera de ciclo, piden repetir el handshake
# (plan de protocolo serial §6.5 y §7).
# TMG-03 (E3): ticks fallidos seguidos antes de apagar todo (≈1,5 s con el
# periodo de 0,5 s) y frecuencia del log con traza
_EXCEPCIONES_PARA_APAGAR = 3
_LOG_CADA_EXCEPCIONES = 20

# TMG-01 de T4: ticks consecutivos de cámara segura para dejar de considerar
# el Principal del último ciclo (convención de debounce de 3 lecturas).
_TICKS_SEGUROS_OLVIDAR_CICLO = 3

_ALARMAS_PIDEN_HANDSHAKE = {"TARJETA_EXPANSOR_FUERA_DE_LINEA", "DISCREPANCIA_SALIDAS"}


class ControlLoop:

    # Loop central del sistema.
    # - Recibe datos del serial
    # - Ejecuta servicios (reglas)
    # - Actualiza dispositivos
    # - Publica estado global

    # Tolerancia a caídas breves del link durante un ciclo: una desconexión
    # de menos de este umbral no lo aborta (ruido momentáneo en el serial).
    # Si se supera, se aborta — ver abortar_por_desconexion().
    _TOLERANCIA_DESCONEXION_SEG = 5.0

    # Vigencia de la trama DI: tres periodos de 500 ms de la tarjeta. Si la
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
        # Reentrante: el backend lo toma en su guard de estado
        # (bloqueo_maquina) y dentro llama a enter/exit_test_mode, que también
        # lo toman (planeacion_backend_autenticacion.md, revisión de la etapa 1).
        self._sm_lock       = threading.RLock()
        # Avisos de "modo prueba cancelado por paro de emergencia" (el backend
        # limpia la sesión dueña y lo registra en audit_log).
        self._al_cancelar_prueba = []
        # Configuración inválida al arrancar (CONFIGURACION_INVALIDA): motivo
        # del bloqueo, o None. _bloqueo_apagado indica si ya se mandó ALL_OFF
        # en la conexión actual con la tarjeta.
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

        # Protocolo de estado seguro (fin de ciclo §15): una sola instancia que
        # sobrevive a set_active_cycle. `al_evento_seguridad(evento, detalle)`
        # lo fija el backend para el audit_log.
        self.al_evento_seguridad = None
        self.estado_seguro = ProtocoloEstadoSeguro(
            estado, config_manager, profile=profile,
            programas_seguridad=self.programas_para_seguridad,
            al_evento=self._evento_seguridad, alarm_manager=alarm_manager)

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
        self._com01_arranque_activada = False
        self.paro_emergencia    = EmergencyStop(estado)
        self.suministro_electrico = SuministroElectrico(estado, set_do)

        self.thread: threading.Thread | None = None

        # Modo prueba (bench validation): pausa state_machine.update() sin
        # detener el resto del loop (sensores, puertas, enlace serial).
        self._test_mode = threading.Event()

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

        # Alarmas de la tarjeta reportadas fuera de ciclo, que se despejan al
        # completar el siguiente handshake. Las del fallo de un ciclo no: esas
        # se liberan con el reconocimiento del operador.
        self._alarmas_tarjeta: set[str] = set()

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
                # Un lazo vivo que falla en cada tick deja de alimentar el HB y
                # el watchdog del firmware apaga todo a los 5 s.
                self.link.marcar_tick_control()
            time.sleep(self.interval)


    def _tick_fallido(self) -> None:
        """TMG-03 (E3): un tick que lanza no renueva el latido (TMG-01 de E6)
        y, tras _EXCEPCIONES_PARA_APAGAR seguidos, se apagan todas las salidas
        desde aquí, sin esperar al watchdog de la tarjeta. Log con traza, pero
        limitado (el primero y uno cada _LOG_CADA_EXCEPCIONES)."""
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
        return [p for p in (self.cycle, self._programa_ultimo_ciclo) if p is not None]

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
        Principal siga contando para la seguridad (SAF-04 de T4); si no, None."""
        programa = self._programa_ultimo_ciclo
        if programa is None or self.estado.get_machine_state() == GlobalState.CICLO:
            return None
        try:
            return programa.get_param("finalizacion", "temp_max_apertura")
        except Exception:
            return None

    def _seguir_programa_ultimo_ciclo(self) -> None:
        if self.estado.get_machine_state() == GlobalState.CICLO:
            copia = getattr(self.state_machine.ciclo, "programa_en_curso", None)
            if copia is not None:
                self._programa_ultimo_ciclo = copia
            self._ticks_seguros_tras_ciclo = 0
            return
        if self._programa_ultimo_ciclo is None:
            return
        segura, _ = camara_segura.evaluar(self.estado, self.config_manager,
                                          self.programas_para_seguridad(), self.profile,
                                          temp_max_ciclo=self.temp_max_tras_ciclo())
        # TMG-01 de T4: 3 ticks seguros consecutivos (un tick ruidoso no basta)
        self._ticks_seguros_tras_ciclo = self._ticks_seguros_tras_ciclo + 1 if segura else 0
        if self._ticks_seguros_tras_ciclo >= _TICKS_SEGUROS_OLVIDAR_CICLO:
            self._programa_ultimo_ciclo = None
            self._ticks_seguros_tras_ciclo = 0

    def aplicar_a_ciclo_en_curso(self, seccion: str, path: list[str], valor) -> bool:
        """§5.8: aplica al ciclo en curso un cambio ya guardado en el programa
        almacenado, solo si su fase no ha iniciado. Bajo _sm_lock (RLock: el
        guard del backend ya lo tiene)."""
        with self._sm_lock:
            if self.estado.get_machine_state() != GlobalState.CICLO:
                return False
            return self.state_machine.ciclo.aplicar_si_fase_pendiente(seccion, path, valor)

    @property
    def desconectado(self) -> bool:
        """True mientras el enlace con la tarjeta está caído (incluida la
        tolerancia): las lecturas no son vigentes. Solo lectura, para el
        backend (órdenes de puerta, revisión de seguridad de la etapa 2)."""
        return self._desconectado_desde is not None

    def _di_vigente(self) -> bool:
        """True si la última trama DI del enlace tiene a lo sumo
        _VIGENCIA_DI_SEG segundos. Un enlace que no informa la edad (o la
        informa con un valor no numérico) no se da por vigente."""
        edad = self.link.edad_ultima_di()
        if isinstance(edad, bool) or not isinstance(edad, (int, float)):
            return False
        return edad <= self._VIGENCIA_DI_SEG

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

    def _procesar_eventos_tarjeta(self) -> None:
        """Reacción a los eventos de la tarjeta de E/S (plan de protocolo
        serial §7, E6). En ciclo, toda falla en operación aborta el ciclo
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
                self._procesar_evento_tarjeta(ev)
            except Exception as exc:
                logger.error("ControlLoop: error procesando evento de tarjeta %s: %s",
                             getattr(ev, "alarm_id", None), exc)

    def _procesar_evento_tarjeta(self, ev) -> None:
        if ev.origen == "conectada":
            for alarm_id in sorted(self._alarmas_tarjeta):
                self.alarm_manager.resolver(alarm_id)
            self._alarmas_tarjeta.clear()
            return

        en_ciclo = self.estado.get_machine_state() == GlobalState.CICLO
        if ev.origen == "operacion" and en_ciclo:
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
        self._alarmas_tarjeta.add(ev.alarm_id)
        self.alarm_manager.activar(ev.alarm_id, motivo=ev.motivo)

    def _tick(self):
        # FW-D6: el latido lo renueva run() al completarse este tick (TMG-01).
        # Antes del chequeo de conexión: un WD o reinicio de la tarjeta deja
        # el enlace sin handshake y el resto del tick no correría.
        self._procesar_eventos_tarjeta()
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
                # Tras una conexión real, la caída activa COM-01 en el flanco.
                if self._link_ever_connected:
                    try:
                        self.alarm_manager.activar(COM_01)
                    except Exception:
                        logger.exception("ControlLoop: no se pudo activar COM-01")
                # El handshake serial inicial (escaneo de puerto + primer dato)
                # tarda unos instantes tras el arranque del backend; ese hueco
                # no es una desconexión real y no debe imprimirse.
                if self.realtime_printer is not None and self._link_ever_connected:
                    self.realtime_printer.enqueue(
                        format_connectivity_ticket("TARJETA", False, datetime.now())
                    )
            # Mientras el enlace nunca haya conectado (handshake del arranque),
            # COM-01 espera a que la desconexión continua alcance la
            # tolerancia: el arranque normal no deja COM-01 en el historial,
            # pero una tarjeta que nunca responde sí la da (una sola vez).
            if (not self._link_ever_connected
                    and not self._com01_arranque_activada
                    and self._desconectado_desde is not None
                    and now - self._desconectado_desde >= self._TOLERANCIA_DESCONEXION_SEG):
                self._com01_arranque_activada = True
                self.alarm_manager.activar(COM_01)
            # Sin conexión no hay datos frescos de sensores, así que este
            # mismo _tick() va a retornar temprano y state_machine.update()
            # no correrá — si había un ciclo en curso, no se detectaría el
            # fallo por sí solo. Se aborta aquí directamente en vez de
            # esperar a una reconexión que puede tardar o no llegar, pero
            # solo una vez agotada la tolerancia: una caída breve (ruido
            # momentáneo en el serial) no debe tirar el ciclo completo.
            if (self._desconectado_desde is not None
                    and now - self._desconectado_desde >= self._TOLERANCIA_DESCONEXION_SEG
                    and self.estado.get_machine_state() == GlobalState.CICLO):
                self.state_machine.ciclo.abortar_por_desconexion(
                    segundos=now - self._desconectado_desde)
        elif connected and not self.link_was_connected:
            self._desconectado_desde = None
            self._bloqueo_apagado = False   # tras reconectar, volver a apagar
            self.alarm_manager.resolver(COM_01)
            if self.realtime_printer is not None and self._link_ever_connected:
                self.realtime_printer.enqueue(
                    format_connectivity_ticket("TARJETA", True, datetime.now())
                )

        if connected:
            self._link_ever_connected = True

        self.link_was_connected = connected

        if connected and self._conectado_desde is None:
            self._conectado_desde = now
        elif not connected:
            self._conectado_desde = None

        if not connected:
            # Sin enlace no hay datos de las entradas: paro (A-3). La máquina
            # de estados no corre, pero el flag queda publicado para la UI, el
            # backend y el primer tick tras reconectar.
            self.paro_emergencia.update(None)
            return

        # 1. Publicar estado global
        self.estado.update(self.units.get_all())

        # 2. Paro de emergencia → actualiza flag en estado. DI crudo, contacto
        # NC: EmergencyStop interpreta 0 o ausente como paro (D-16).
        # Trama DI vencida (la tarjeta manda AI: pero no DI:) = sin datos (A-3)
        self.paro_emergencia.update(
            self.estado.sensores_di.get("paro_emergencia") if self._di_vigente() else None
        )
        self._avisar_puerta_2_no_declarada()

        # 2a. Recién conectado y sin la primera DI: se publica lo anterior para
        # la UI, pero sin suministro, puertas, máquina de estados ni buzzer (las
        # entradas están en 0 por _connect()). Pasada la vigencia sin DI, se
        # sigue normal con el paro activo y la máquina de estados lo aplica.
        if (self.link.edad_ultima_di() is None
                and now - self._conectado_desde < self._VIGENCIA_DI_SEG):
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

            # 3. Dispositivos → actúan (pausado durante el modo prueba: las
            # puertas re-asertan sus propias salidas, p.ej. cerrar_on() en
            # cada tick mientras están CERRADO, lo que pisaría el control
            # manual de esas mismas salidas desde /io/test/output).
            if not self._test_mode.is_set():
                for door in self.doors:
                    door.update()

            # 4. Servicios → deciden
            self.door_service.update()

            # 5. Máquina de estados global (pausada durante el modo prueba)
            if not self._test_mode.is_set():
                # TMG-03 de T5: el estado seguro solo avanza con datos vigentes
                # (sin volver a consultar el enlace: se usa la lectura de este tick)
                vigentes = connected and not self.desconectado and self._di_vigente()
                self.state_machine.update(datos_vigentes=vigentes)
            self._seguir_programa_ultimo_ciclo()

        # Fuera del lock: quien escucha registra en la bitácora (SQLite)
        if cancelado_por_paro:
            self._avisar_cancelacion_prueba()

        # 5b. Acumulación de F0 (letalidad) — solo lee estado.fase_ciclo, ya
        # publicado, así que el orden respecto al paso 5 no importa.
        self._acumular_f0(now)

        # 6. Data logger (observa machine_state internamente)
        if self.cycle_logger is not None:
            self.cycle_logger.update()

        # 7. Buzzer (pausado durante el modo prueba: una secuencia ya en
        # curso al entrar — p.ej. alarma de FALLA, que no bloquea la
        # entrada a modo prueba — seguiría escribiendo buzer_alarma y
        # pisaría el control manual de esa salida).
        if not self._test_mode.is_set():
            self.set_do.buzer.update()

    def _acumular_f0(self, now: float) -> None:
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
        if not condiciones:
            self._f0_ultimo_tick = None
            return

        ultimo = self._f0_ultimo_tick
        self._f0_ultimo_tick = now
        if ultimo is None:
            return

        # F0 usa solo el sensor Principal del programa en curso (tanda §1.1;
        # reemplaza el mínimo temp_camara/temp_2_camara, decisión C-1)
        t_ref = self.estado.sensores_temp.get(sensor_principal(self.programa_en_ejecucion()))
        if not lectura_valida(t_ref):
            return

        dt_min = (now - ultimo) / 60.0
        self.estado.f0_acumulado += calcular_incremento_f0(t_ref, dt_min)

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

    def stop(self):
        # Primero se detiene el lazo y después se apaga (TMG-11 de E6, TMG-02
        # de T1): un tick que corriera tras el ALL_OFF podía volver a encender
        # salidas hasta el watchdog del firmware.
        self._running.clear()

        if self.thread and threading.current_thread() is not self.thread:
            self.thread.join(timeout=3)

        if self.link:
            self.link.all_off()
            self.link.stop()

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
        conexión con la tarjeta. Llamar antes de start()."""
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

            if self.estado.get_machine_state() == GlobalState.CICLO:
                return False, "No se puede activar el modo prueba durante un ciclo en curso."

            if self.estado.get_flag("PARO_EMERGENCIA"):
                return False, "No se puede activar el modo prueba con el paro de emergencia activado."

            self._test_mode.set()
            self.set_do.buzer.stop()
            self.set_do.reset_all_outputs()
            return True, ""

    def exit_test_mode(self) -> None:
        """Apaga todas las salidas y reanuda state_machine.update(). Bajo
        _sm_lock y en este orden (apagar, luego reanudar): una orden de
        /io/test/output ya validada no puede llegar después del apagado, y la
        máquina de estados no corre un tick con salidas de prueba encendidas."""
        with self._sm_lock:
            self.set_do.reset_all_outputs()
            self._test_mode.clear()

    # =========================================================================
    # CAMBIO DE CICLO ACTIVO
    # =========================================================================

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
            if self.estado.get_machine_state() == GlobalState.CICLO:
                return False, "No se puede cambiar de ciclo mientras hay uno en curso."

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
