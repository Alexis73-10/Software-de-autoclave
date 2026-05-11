import logging
import subprocess
import sys
import os
import time
import requests

from autoclave.ui.window.main_window import InterfazPrincipal
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.services.domain.puertas.door_command_service import DoorCommandService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 🔹 CONFIG
BACKEND_URL = "http://192.168.100.10:8000"
SOURCE_DOOR = 1   # 👈 CAMBIAR A 2 EN EL OTRO PC


# 🔹 FUNCIONES AUXILIARES

def is_backend_alive(timeout=1):
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def wait_for_backend(max_wait=10): 
    logger.info("⏳ Esperando backend...")
    start = time.time()

    while time.time() - start < max_wait:
        if is_backend_alive():
            logger.info("✅ Backend disponible")
            return True
        time.sleep(0.5)

    logger.error("❌ Backend no respondió a tiempo")
    return False


# 🔹 MAIN

def main():
    backend_process = None

    # 🔹 Solo puerta 1 puede iniciar backend
    # if SOURCE_DOOR == 1:
    #     if not is_backend_alive():
    #         logger.info("🚀 Backend no detectado, iniciando...")

    #         base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    #         backend_path = os.path.join(base_path, "backend.py")  # ajusta ruta

    #         backend_process = subprocess.Popen(
    #             [sys.executable, backend_path]
    #         )

    #         # Esperar a que levante
    #         if not wait_for_backend():
    #             logger.error("❌ No se pudo iniciar el backend")
    #     else:
    #         logger.info("🟢 Backend ya estaba corriendo")
    # else:
    #     logger.info("🖥️ Cliente secundario (no inicia backend)")
    #     if not wait_for_backend():
    #         logger.warning("⚠️ Backend no disponible, UI seguirá intentando...")

    # 🔹 Conexión backend
    backend = BackendClient(BACKEND_URL)

    ui_service = UIServiceBackend(backend)
    door_commands = DoorCommandService(
        backend_client=backend,
        source_door=SOURCE_DOOR, 
    )

    # 🔹 UI
    app = InterfazPrincipal(
        ui_service=ui_service,
        door_commands=door_commands,
    )

    logger.info("🖥️ UI Autoclave iniciada")

    # 🔹 CIERRE LIMPIO
    def on_close():
        logger.info("🛑 Cerrando aplicación...")

        if backend_process:
            logger.info("🧹 Deteniendo backend...")
            backend_process.terminate()

            try:
                backend_process.wait(timeout=5)
                logger.info("✅ Backend detenido correctamente")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Backend no respondió, forzando cierre")
                backend_process.kill()

        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)

    app.mainloop()


if __name__ == "__main__":
    main()