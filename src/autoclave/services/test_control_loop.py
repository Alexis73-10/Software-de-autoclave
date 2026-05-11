#en este archivo probaremos el flujo de las unidades y la actualizacion de datos a la interfaz
#las unidades se encuentran en src/autoclave/core/units.py
#el enlace serial en src/autoclave/protocols/serial_link.py
# el cofre de calibracion en src/autoclave/config/calibration.yaml
# el cofre de los datos en src/autoclave/core/status.py
import time
import threading
from src.autoclave.protocols.serial_link import SerialLink
from autoclave.core.estados.status import estado 
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Creamos la instancia de Units que manejará los datos convertidos
class control_loop_test:
    def __init__(self,units):
        self.units = units
        self.interval = 0.5
        self.running = threading.Event()
        self.running.set()
        self.link = None
        self.update_thread = None  
        self.nuevos_datos = {}
    # Callback que recibe los datos crudos del serial
    # Intervalo de actualización (segundos)


    def serial_callback(self, data):
        """Callback llamado por SerialLink cada vez que llega un paquete."""
        self.units.update_from_serial(data)

    def periodic_update(self):
        """Loop independiente que actualiza el estado periódicamente."""
        
        while self.running.is_set():
            nuevos_datos = self.units.get_all()
            estado.update(nuevos_datos)
            time.sleep(self.interval)
            status_info = estado.sensores_temp    # Flag para controlar el hilo de actualización
    running = threading.Event()
    running.set()

    def start (self):
        # Lanzar hilo de actualización periódica
        self.update_thread = threading.Thread(target=self.periodic_update, daemon=True)
        self.update_thread.start()

        # Configuración y arranque del SerialLink
        self.link = SerialLink(on_update=self.serial_callback)
        self.link._scan_ports()  # Fijamos puerto
        self.link.start()
        logger.info("🚀 Flujo de datos iniciado...")
        #mostar los datos resibidos en la consola



    def stop(self):
        self.running.clear()
        if self.link:
            self.link.stop()
        if self.update_thread:
            self.update_thread.join()
        logger.info("Flujo de datos detenido.")