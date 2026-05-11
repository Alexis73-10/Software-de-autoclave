# Archivo: src/autoclave/services/control_loop.py
#en este archivo probaremos el flujo de las unidades y la actualizacion de datos a la interfaz
#las unidades se encuentran en src/autoclave/core/units.py
#el enlace serial en src/autoclave/protocols/serial_link.py
# el cofre de calibracion en src/autoclave/config/calibration.yaml
# el cofre de los datos en src/autoclave/core/status.py
import time
import threading
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.state_machine import StateMachine
from autoclave.devices.buzer.buzer import BuzzerPlayer
from autoclave.devices.paro_emergencia.paro_emergencia import EmergencyStop

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Creamos la instancia de Units que manejará los datos convertidos
class ControlLoop:
    
    
    # Loop central del sistema.
    # - Recibe datos del serial
    # - Ejecuta servicios (reglas)
    # - Actualiza dispositivos
    # - Publica estado global
    
    
    def __init__(self,units, door_service , doors, estado, link, set_do, alarm_manager,cycle_manager, config_manager, interval=0.5):
        self.units = units
        self.door_service = door_service
        self.doors = doors
        self.estado = estado
        self.interval = interval
        self.link = link
        self.set_do = set_do
        self._running = threading.Event()
        self.cycle = cycle_manager.get_selected_cycle()
        self.config_manager = config_manager
        
        self.update_thread = None  
        self.nuevos_datos = {}
        self.state_machine = StateMachine(io=self.link, estado=self.estado, set_do=set_do, cycle=self.cycle, config = self.config_manager)
        self.link_was_connected = True
        self.alarm_manager = alarm_manager
        self.cycle_manager = cycle_manager
        self.buzer= BuzzerPlayer
        self.paro_emergencia = EmergencyStop(estado)
    # Callback que recibe los datos crudos del serial
    # Intervalo de actualización (segundos)

#============================================================================================
#SERIAL
#============================================================================================

    def serial_callback(self, data):
        #Callback llamado por SerialLink cada vez que llega un paquete.
        self.units.update_from_serial(data)

#============================================================================================
#LOOP DE ACTUALIZACION
#============================================================================================

    def run(self):
        #logger.info(f"estado inicial del link: {self.link.is_connected()}")



        while self._running.is_set():
            connected = self.link.is_connected()

            if not connected and self.link_was_connected:
                # conexión perdida o no disponible
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
                # conexión recuperada
                self.alarm_manager.clear("NO_HAY_CONEXION")

            self.link_was_connected = connected


            # ❗ Sin conexión: no ejecutar control
            if not connected:
                time.sleep(self.interval)
                continue

            # 1. Publicar estado global
            self.estado.update(self.units.get_all())

            # 2. Dispositivos -> actúan
            for door in self.doors:
                door.update()

            # 3. Servicios -> deciden
            self.door_service.update()

            # 4. Máquina de estados global
            self.state_machine.update()

            #5. Buzer
            self.set_do.buzer.update()

            time.sleep(self.interval)

#============================================================================================
#CONTROL DE VIDA
#============================================================================================

    def start(self):
        if self._running.is_set():
            logger.warning("El bucle de control ya está en ejecución.")
            return

        self._running.set()
        self.thread = threading.Thread(
            target=self.run,
            name="ControlLoop",
            daemon=True,
        )
        self.thread.start()



    def stop(self):
        
        if self.link:
            self.link.all_off()
            self.link.stop()
        
        self._running.clear()
        
        if self.update_thread and threading.current_thread() != self.update_thread:
            self.update_thread.join()
        

        
        logger.info("Flujo de datos detenido.")

#============================================================================================