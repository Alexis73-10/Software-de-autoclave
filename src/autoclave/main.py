# autoclave/main.py
# Punto de entrada principal — tkinter como UI principal, PySide6 como subprocess de settings

import logging
import subprocess
import sys
import os
import time
import requests

from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.wizard import launch_installation_wizard
from autoclave.installation.clock_guard import ClockTamperedError
from autoclave.devices.printer import heartbeat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000"


def is_backend_alive(timeout=1):
    try:
        r = requests.get(f"{BACKEND_URL}/status", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def wait_for_backend(process=None, max_wait=40):
    logger.info("Esperando backend...")
    start = time.time()
    while time.time() - start < max_wait:
        if process is not None and process.poll() is not None:
            logger.error("El backend terminó inesperadamente (código %s)", process.returncode)
            return False
        if is_backend_alive():
            logger.info("Backend disponible (%.1fs)", time.time() - start)
            return True
        time.sleep(0.5)
    logger.error("Backend no respondió en %ds", max_wait)
    return False


def main():
    # ── 1. Verificar instalación ───────────────────────────────────────────
    try:
        profile = get_installation_profile()
    except ClockTamperedError as e:
        import tkinter as tk
        from tkinter import messagebox
        _root = tk.Tk()
        _root.withdraw()
        messagebox.showerror("Error de sistema", f"No se puede iniciar el software.\n\n{e}")
        _root.destroy()
        sys.exit(1)

    if profile is None:
        logger.info("Perfil de instalación no encontrado o inválido — iniciando wizard")
        completed = launch_installation_wizard()
        if not completed:
            logger.error("Instalación requerida para continuar. Cerrando.")
            sys.exit(1)
        try:
            profile = get_installation_profile()
        except ClockTamperedError as e:
            import tkinter as tk
            from tkinter import messagebox
            _root = tk.Tk()
            _root.withdraw()
            messagebox.showerror("Error de sistema", f"No se puede iniciar el software.\n\n{e}")
            _root.destroy()
            sys.exit(1)
        if profile is None:
            logger.error("Error crítico: perfil sigue inválido tras wizard. Cerrando.")
            sys.exit(1)

    SOURCE_DOOR = profile.door_id
    logger.info("Perfil cargado — serie: %s | puerta: %s", profile.serial_number, SOURCE_DOOR)

    # ── 2. Iniciar backend ────────────────────────────────────────────────
    backend_process = None
    if SOURCE_DOOR == 1:
        if is_backend_alive():
            logger.info("Backend ya estaba corriendo")
        else:
            logger.info("Iniciando backend...")
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "autoclave.backend.main"],
                stdout=subprocess.DEVNULL,
                stderr=None,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("Backend no respondió — la UI arrancará sin datos")
    else:
        logger.info("PC puerta 2 — esperando backend en red...")
        if not wait_for_backend(max_wait=40):
            logger.warning("Backend no disponible, la UI seguirá intentando...")

    # ── 2b. Iniciar heartbeat de impresora ────────────────────────────────────
    heartbeat.start(interval=30)

    # ── 3. Arrancar UI (tkinter) ────────────────────────────────────────────
    from autoclave.ui.service_ui.backend_client import BackendClient
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.services.domain.puertas.door_command_service import DoorCommandService
    from autoclave.ui.window.main_window import InterfazPrincipal

    backend       = BackendClient(BACKEND_URL)
    ui_service    = UIServiceBackend(backend)
    door_commands = DoorCommandService(backend_client=backend, source_door=SOURCE_DOOR)

    def on_close():
        logger.info("Cerrando aplicación...")
        try:
            ui_service.reset_outputs()
            logger.info("Salidas digitales apagadas")
        except Exception as e:
            logger.warning("No se pudieron apagar las salidas: %s", e)
        ui_service.stop()
        if hasattr(app, '_settings_proc') and app._settings_proc and app._settings_proc.poll() is None:
            app._settings_proc.terminate()
        if backend_process:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
        app.destroy()

    app = InterfazPrincipal(
        ui_service=ui_service,
        door_commands=door_commands,
        on_shutdown=on_close,
        source_door=SOURCE_DOOR,
        profile=profile,
    )
    logger.info("UI Autoclave iniciada")
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
