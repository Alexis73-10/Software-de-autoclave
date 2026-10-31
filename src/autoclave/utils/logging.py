import logging
import os
import sys

# Crear carpeta de logs si no existe
# en el .exe, en su carpeta de datos (dentro del paquete se borraría al cerrar)
if getattr(sys, "frozen", False):
    from autoclave.utils.resources import raiz_datos_exe
    LOG_DIR = os.path.join(raiz_datos_exe(), "logs")
else:
    LOG_DIR = os.path.join(os.path.dirname(__file__), "../../logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configurar logging
log_file = os.path.join(LOG_DIR, "autoclave.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()  # También lo muestra en consola
    ]
)

# Logger global
logger = logging.getLogger("autoclave")
