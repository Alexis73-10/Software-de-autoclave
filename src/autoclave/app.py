# autoclave/app.py

#este módulo sirve como punto de entrada principal para la aplicación Autoclave.
# Main application entry point
# conectara la interfaz de usuario, el bucle de control y la gestión de unidades.
from src.autoclave.ui.main_window import InterfazPrincipal
from src.autoclave.services.test_control_loop import control_loop_test
from src.autoclave.core.units import Units
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # ahora con todo listo vamos a iniciar la interfaz de usuario, el bucle de control y la gestión de unidades.
    logger.info("Iniciando la aplicación Autoclave...")
    # Inicializar la gestión de unidades
    units = Units("src/autoclave/config/calibration.yaml")
    # Iniciar el bucle de control de prueba
    loop = control_loop_test(units)
    control_thread = threading.Thread(target=loop.start, daemon=True)
    control_thread.start()
    # Iniciar la interfaz de usuario
    ui = InterfazPrincipal()
    ui.mainloop()
    
if __name__ == "__main__":
    main()
