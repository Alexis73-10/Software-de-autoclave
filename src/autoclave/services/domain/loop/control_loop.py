# autoclave/services/control_loop.py

import time
import threading
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.state_machine import StateMachine
from autoclave.devices.paro_emergencia.paro_emergencia import EmergencyStop

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
                 cycle_logger=None, interval=0.5):
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

        self.state_machine     = StateMachine(
            io=self.link, estado=self.estado, set_do=set_do,
            cycle=self.cycle, config=self.config_manager
        )
        self.link_was_connected = True
        self.paro_emergencia    = EmergencyStop(estado)

        self.thread: threading.Thread | None = None

    # =========================================================================
    # LOOP DE ACTUALIZACIÓN
    # =========================================================================

    def run(self):
        while self._running.is_set():
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
            elif connected and not self.link_was_connected:
                self.alarm_manager.clear("NO_HAY_CONEXION")

            self.link_was_connected = connected

            if not connected:
                time.sleep(self.interval)
                continue

            # 1. Publicar estado global
            self.estado.update(self.units.get_all())

            # 2. Paro de emergencia → actualiza flag en estado
            self.paro_emergencia.update(
                bool(self.estado.sensores_di.get("paro_emergencia", 0))
            )

            # 3. Dispositivos → actúan
            for door in self.doors:
                door.update()

            # 4. Servicios → deciden
            self.door_service.update()

            # 5. Máquina de estados global
            self.state_machine.update()

            # 6. Data logger (observa machine_state internamente)
            if self.cycle_logger is not None:
                self.cycle_logger.update()

            # 7. Buzzer
            self.set_do.buzer.update()

            time.sleep(self.interval)

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
