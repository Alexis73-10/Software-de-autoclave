# autoclave/main.py
# Punto de entrada principal — PySide6 como UI principal, tkinter como subprocess de monitoreo

import logging
import subprocess
import sys
import os
import time
import requests

from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.wizard import launch_installation_wizard
from autoclave.installation.clock_guard import ClockTamperedError

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

    # ── 3. Arrancar UI (PySide6) ────────────────────────────────────────────
    from PySide6.QtWidgets import QApplication
    from autoclave.ui_pyside.main_window import MainWindowFluent
    from autoclave.ui.service_ui.backend_client import BackendClient as _BC

    # Lanzar ventana tkinter como subprocess para monitoreo de ciclo
    tkinter_proc = subprocess.Popen(
        [sys.executable, "-m", "autoclave.ui.main"],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    qt_app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindowFluent(tkinter_proc=tkinter_proc)
    window.showMaximized()

    def on_quit():
        logger.info("Cerrando aplicación...")
        try:
            _BC(BACKEND_URL).post("/outputs/reset")
            logger.info("Salidas digitales apagadas")
        except Exception as e:
            logger.warning("No se pudieron apagar las salidas: %s", e)
        if tkinter_proc.poll() is None:
            tkinter_proc.terminate()
            try:
                tkinter_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                tkinter_proc.kill()
        if backend_process:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()

    qt_app.aboutToQuit.connect(on_quit)
    logger.info("UI PySide6 iniciada")
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
