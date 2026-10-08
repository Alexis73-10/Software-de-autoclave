# autoclave/services/control_loop.py

import time
import threading
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.state_machine import StateMachine
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.devices.paro_emergencia.paro_emergencia import EmergencyStop
from autoclave.devices.suministro_electrico.suministro_electrico import SuministroElectrico
from datetime import datetime
from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket
from autoclave.core.runtime.letalidad import calcular_incremento_f0

import logging

logger = logging.getLogger(__name__)

# Fases del ciclo donde hay letalidad real y corresponde acumular F0.
# ESTABILIZACION ya no existe como fase.name propia (fusionada dentro de
# CALENTAMIENTO, ver CLAUDE.md) — se conserva en el conjunto por si una
# futura reversión de esa fusión la reintroduce; hoy nunca hace match.
_F0_FASES_ACUMULAN = {"CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION"}


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

    def __init__(self, units, door_service, doors, estado, link, set_do,
                 alarm_manager, cycle_manager, config_manager,
                 cycle_logger=None, interval=0.5, cap=None, realtime_printer=None):
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

        self.state_machine     = StateMachine(
            io=self.link, estado=self.estado, set_do=set_do,
            cycle=self.cycle, config=self.config_manager, cap=cap,
            door_service=door_service,
        )
        self.link_was_connected = True
        self._link_ever_connected = False
        self._desconectado_desde: float | None = None
        self.paro_emergencia    = EmergencyStop(estado)
        self.suministro_electrico = SuministroElectrico(estado, set_do)

        self.thread: threading.Thread | None = None

        # Modo prueba (bench validation): pausa state_machine.update() sin
        # detener el resto del loop (sensores, puertas, enlace serial).
        self._test_mode = threading.Event()

        # Acumulación de F0 (letalidad): timestamp del último tick que
        # acumuló, para calcular dt_min real (no el interval nominal).
        self._f0_ultimo_tick: float | None = None

    # =========================================================================
    # LOOP DE ACTUALIZACIÓN
    # =========================================================================

    def run(self):
        while self._running.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.warning("ControlLoop: error inesperado en el ciclo: %s", exc)
            time.sleep(self.interval)

    def _tick(self):
        connected = self.link.is_connected()
        now = time.monotonic()

        if not connected:
            if self.link_was_connected:
                self._desconectado_desde = now
                self.alarm_manager.report(
                    Alarm(
                        alarm_id="NO_HAY_CONEXION",
                        alarm_type=AlarmType.FALLA,
                        source_state="CONTROL_LOOP",
                        description="No hay comunicación con el hardware.",
                        recoverable=True,
                        blocks_operation=True,
                    )
                )
                # El handshake serial inicial (escaneo de puerto + primer dato)
                # tarda unos instantes tras el arranque del backend; ese hueco
                # no es una desconexión real y no debe imprimirse.
                if self.realtime_printer is not None and self._link_ever_connected:
                    self.realtime_printer.enqueue(
                        format_connectivity_ticket("TARJETA", False, datetime.now())
                    )
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
                self.state_machine.ciclo.abortar_por_desconexion()
        elif connected and not self.link_was_connected:
            self._desconectado_desde = None
            self._bloqueo_apagado = False   # tras reconectar, volver a apagar
            self.alarm_manager.clear("NO_HAY_CONEXION")
            if self.realtime_printer is not None and self._link_ever_connected:
                self.realtime_printer.enqueue(
                    format_connectivity_ticket("TARJETA", True, datetime.now())
                )

        if connected:
            self._link_ever_connected = True

        self.link_was_connected = connected

        if not connected:
            return

        # 1. Publicar estado global
        self.estado.update(self.units.get_all())

        # 2. Paro de emergencia → actualiza flag en estado
        self.paro_emergencia.update(
            bool(self.estado.sensores_di.get("paro_emergencia", 0))
        )

        # 2b. Suministro eléctrico → actualiza flag en estado
        self.suministro_electrico.update(
            bool(self.estado.sensores_di.get("suministro_electrico", 1))
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
                self.state_machine.update()

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
        condiciones = (
            self.estado.get_machine_state() == GlobalState.CICLO
            and self.estado.fase_ciclo in _F0_FASES_ACUMULAN
            and bool(self.cycle.get_param("globals", "F0"))
        )
        if not condiciones:
            self._f0_ultimo_tick = None
            return

        ultimo = self._f0_ultimo_tick
        self._f0_ultimo_tick = now
        if ultimo is None:
            return

        temp_camara = self.estado.sensores_temp.get("temp_camara")
        if temp_camara is None:
            return

        if self.cap is not None and getattr(self.cap, "has_liquid_sensor", False):
            temp_2 = self.estado.sensores_temp.get("temp_2_camara")
            t_ref = min(temp_camara, temp_2) if temp_2 is not None else temp_camara
        else:
            t_ref = temp_camara

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
        if self.link:
            self.link.all_off()
            self.link.stop()

        self._running.clear()

        if self.thread and threading.current_thread() is not self.thread:
            self.thread.join(timeout=3)

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
                door_service=self.door_service,
            )
            return True, ""
