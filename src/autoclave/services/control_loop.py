
#este módulo gestiona el ciclo de control principal de la aplicación Autoclave.
# Control loop service for Autoclave application.
# Lee datos de Units, actualiza la interfaz y supervisa el enlace serial.
# un control loop se uriliza para actualizar periódicamente la interfaz de usuario con los datos más recientes.
import threading #threading para ejecutar el bucle de control en un hilo separado
import time
import logging
from src.autoclave.ui.main_window import InterfazPrincipal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

#con la clase ControlLoop se gestiona el ciclo de control principal
#
class ControlLoop:
    """
    Controla el ciclo principal de actualización:
    - Lee los datos convertidos desde Units.
    - Actualiza la interfaz (si está registrada).
    - Supervisa el enlace serial.
    """

    def __init__(self, units, ui=InterfazPrincipal(), interval=0.5):
        self.units = units
        self.ui = ui
        self.interval = interval
        self._running = False
        self._thread = None

    def start(self):
        # Inicia el ciclo de control en un hilo separado.
        # Evita múltiples inicios.
        if self._running:
            logger.warning("⚠️ ControlLoop ya se está ejecutando.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("🌀 ControlLoop iniciado.")

    def stop(self):
        # Detiene el ciclo de control.
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("🛑 ControlLoop detenido.")

    def _run(self):
        # Bucle principal de actualización.
        while self._running:
            try:
                estado = self.units.get_all()  # ← datos ya convertidos y validados

                if self.ui:
                    # Asegura que la actualización se ejecute en el hilo principal de Tkinter
                    self.ui.after(0, self.ui.update_display, estado)

            except Exception as e:
                logger.exception(f"Error en ControlLoop: {e}")

            time.sleep(self.interval)

# Ejemplo de uso: