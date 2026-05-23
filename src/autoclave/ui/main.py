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
# Desarrollo (mismo PC): "http://localhost:8000"
# Producción (red): "http://192.168.100.10:8000"
BACKEND_URL = "http://localhost:8000"
SOURCE_DOOR = 1   # 👈 CAMBIAR A 2 EN EL OTRO PC


# 🔹 FUNCIONES AUXILIARES

def is_backend_alive(timeout=1):
    try:
        r = requests.get(f"{BACKEND_URL}/status", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def wait_for_backend(process=None, max_wait=40):
    """
    Espera hasta max_wait segundos a que el backend responda.
    Si se pasa el proceso, detecta si crasheó antes de tiempo.
    """
    logger.info("⏳ Esperando backend...")
    start = time.time()

    while time.time() - start < max_wait:
        # verificar si el proceso murió antes de estar listo
        if process is not None and process.poll() is not None:
            logger.error("❌ El backend terminó inesperadamente (código %s)", process.returncode)
            return False

        if is_backend_alive():
            elapsed = time.time() - start
            logger.info("✅ Backend disponible (%.1fs)", elapsed)
            return True

        time.sleep(0.5)

    logger.error("❌ Backend no respondió en %ds", max_wait)
    return False


# 🔹 MAIN

def main():
    backend_process = None

    # 🔹 Puerta 1 arranca el backend; puerta 2 solo espera que esté disponible
    if SOURCE_DOOR == 1:
        if is_backend_alive():
            logger.info("🟢 Backend ya estaba corriendo")
        else:
            logger.info("🚀 Iniciando backend...")
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "autoclave.backend.main"],
                stdout=subprocess.DEVNULL,
                stderr=None,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("❌ Backend no respondió — la UI arrancará sin datos")
    else:
        logger.info("🖥️ PC puerta 2 — esperando backend en red...")
        if not wait_for_backend(max_wait=40):
            logger.warning("⚠️ Backend no disponible, la UI seguirá intentando...")

    # 🔹 Conexión backend
    backend = BackendClient(BACKEND_URL)

    ui_service = UIServiceBackend(backend)
    door_commands = DoorCommandService(
        backend_client=backend,
        source_door=SOURCE_DOOR, 
    )

    # 🔹 CIERRE LIMPIO
    def on_close():
        logger.info("🛑 Cerrando aplicación...")

        # Apagar todas las salidas ANTES de matar el backend
        try:
            ui_service.reset_outputs()
            logger.info("✅ Salidas digitales apagadas")
        except Exception as e:
            logger.warning("⚠️ No se pudieron apagar las salidas: %s", e)

        ui_service.stop()   # detiene el hilo de fondo HTTP

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

    # 🔹 UI
    app = InterfazPrincipal(
        ui_service=ui_service,
        door_commands=door_commands,
        on_shutdown=on_close,
        source_door=SOURCE_DOOR,
    )

    logger.info("🖥️ UI Autoclave iniciada")

    app.protocol("WM_DELETE_WINDOW", on_close)

    app.mainloop()


if __name__ == "__main__":
    main()