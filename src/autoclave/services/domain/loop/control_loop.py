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

import logging

logger = logging.getLogger(__name__)


class ControlLoop:

    # Loop central del sistema.
    # - Recibe datos del serial
    # - Ejecuta servicios (reglas)
    # - Actualiza dispositivos
    # - Publica estado global

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
        self.cycle          = cycle_manager.get_selected_cycle()
        self.config_manager = config_manager
        self.alarm_manager  = alarm_manager
        self.cycle_manager  = cycle_manager
        self.cycle_logger   = cycle_logger
        self.realtime_printer = realtime_printer

        self.state_machine     = StateMachine(
            io=self.link, estado=self.estado, set_do=set_do,
            cycle=self.cycle, config=self.config_manager, cap=cap
        )
        self.link_was_connected = True
        self._link_ever_connected = False
        self.paro_emergencia    = EmergencyStop(estado)
        self.suministro_electrico = SuministroElectrico(estado, set_do)

        self.thread: threading.Thread | None = None

        # Modo prueba (bench validation): pausa state_machine.update() sin
        # detener el resto del loop (sensores, puertas, enlace serial).
        self._test_mode = threading.Event()

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

        if not connected and self.link_was_connected:
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
        elif connected and not self.link_was_connected:
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

        # 2c. Salvaguarda: si se activa el paro de emergencia estando en
        # modo prueba, se cancela el modo prueba de inmediato para que la
        # máquina de estados retome el control y aplique su protocolo de
        # paro de emergencia en este mismo tick.
        if self._test_mode.is_set() and self.estado.get_flag("PARO_EMERGENCIA"):
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

        # 6. Data logger (observa machine_state internamente)
        if self.cycle_logger is not None:
            self.cycle_logger.update()

        # 7. Buzzer (pausado durante el modo prueba: una secuencia ya en
        # curso al entrar — p.ej. alarma de FALLA, que no bloquea la
        # entrada a modo prueba — seguiría escribiendo buzer_alarma y
        # pisaría el control manual de esa salida).
        if not self._test_mode.is_set():
            self.set_do.buzer.update()

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

    def enter_test_mode(self) -> tuple[bool, str]:
        """Pausa state_machine.update(), las puertas y el buzzer, y apaga
        todas las salidas para permitir control manual. No pausa la lectura
        de sensores ni el paro de emergencia."""
        if self.estado.get_machine_state() == GlobalState.CICLO:
            return False, "No se puede activar el modo prueba durante un ciclo en curso."

        if self.estado.get_flag("PARO_EMERGENCIA"):
            return False, "No se puede activar el modo prueba con el paro de emergencia activado."

        self._test_mode.set()
        self.set_do.buzer.stop()
        self.set_do.reset_all_outputs()
        return True, ""

    def exit_test_mode(self) -> None:
        """Apaga todas las salidas y reanuda state_machine.update()."""
        self._test_mode.clear()
        self.set_do.reset_all_outputs()
