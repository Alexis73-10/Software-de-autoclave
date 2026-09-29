# autoclave/main.py
# Punto de entrada principal — tkinter como UI principal, PySide6 como subprocess de settings

import argparse
import logging
import subprocess
import sys
import os
import time
import requests

from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.wizard import launch_installation_wizard
from autoclave.installation.clock_guard import ClockTamperedError
from autoclave.installation import backend_guard
from autoclave.devices.printer import heartbeat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000"


def _configurar_logging_archivo(sufijo: str) -> None:
    """En un build congelado (.exe) no hay consola visible ni stdout — sin
    esto, un fallo de esta ventana (p. ej. al posicionarla en un monitor)
    no dejaría ningún rastro que revisar en el PC de pruebas. `sufijo`
    distingue el log de cada ventana cuando hay dos compartiendo `data/`
    (modo doble pantalla) para que no se pisen escribiendo al mismo archivo."""
    if not getattr(sys, "frozen", False):
        return
    from autoclave.utils.paths import app_root
    log_path = app_root() / "data" / f"ui{sufijo}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def _parse_args():
    parser = argparse.ArgumentParser(description="Autoclave — interfaz de operador")
    parser.add_argument(
        "--door", type=int, choices=(1, 2), default=None,
        help="Fuerza qué puerta representa ESTA ventana, para levantar dos "
             "ventanas (una por monitor) desde un mismo PC de dos puertas. "
             "Sin este flag el comportamiento es el de siempre: la puerta la "
             "decide el perfil de instalación y solo hay una ventana. Con "
             "este flag activo, además se posiciona la ventana en el monitor "
             "correspondiente (1=el más a la izquierda, 2=el siguiente) antes "
             "de pasar a pantalla completa.",
    )
    return parser.parse_args()


def _backend_env() -> dict:
    """Entorno para el subproceso del backend.

    En un build congelado, el bootloader de PyInstaller (modo onefile) marca
    su propia carpeta de extracción con la variable `_MEIPASS2` en el entorno
    del proceso. Si se hereda tal cual al lanzar OTRO .exe de PyInstaller
    (AutoclaveBackend.exe) como hijo, su bootloader ve `_MEIPASS2` ya puesta y
    asume que es una re-ejecución de sí mismo reusando esa carpeta — que en
    realidad es la extracción de la UI, no la suya — y falla en silencio
    (proceso hijo nunca llega a arrancar). Hay que quitarla antes de heredar
    el resto del entorno."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("_MEIPASS2", None)
    return env


def _backend_command() -> list[str]:
    """Comando para lanzar el backend como subproceso.

    En un build congelado (PyInstaller), `sys.executable` es el propio .exe
    de la UI — no un intérprete de Python — así que `-m autoclave.backend.main`
    no sirve. En ese caso se lanza `AutoclaveBackend.exe`, empaquetado aparte
    y ubicado junto al ejecutable de la UI. En desarrollo se mantiene el
    lanzamiento con el intérprete actual."""
    if getattr(sys, "frozen", False):
        backend_exe = os.path.join(os.path.dirname(sys.executable), "AutoclaveBackend.exe")
        return [backend_exe]
    return [sys.executable, "-m", "autoclave.backend.main"]


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


def _hardware_connected() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/status", timeout=1)
        if r.status_code != 200:
            return False
        alarms = r.json().get("alarms", [])
        return not any(a.get("id") == "NO_HAY_CONEXION" for a in alarms)
    except requests.RequestException:
        return False


def wait_for_hardware_connection(max_wait=40) -> bool:
    """Ventana de espera mínima mientras la tarjeta no está conectada. Se cierra
    sola al conectar, o muestra un mensaje final y se cierra igual al agotar
    max_wait (no bloquea el arranque de la UI — placeholder hasta que se
    implemente la pantalla de arranque definitiva)."""
    if _hardware_connected():
        return True

    import tkinter as tk
    root = tk.Tk()
    root.title("Autoclave")
    root.geometry("360x120")
    label = tk.Label(root, text="Conectando con la tarjeta...", font=("Segoe UI", 12))
    label.pack(expand=True, padx=20, pady=20)

    start = time.time()
    connected = False

    def _poll():
        nonlocal connected
        if _hardware_connected():
            connected = True
            root.destroy()
            return
        if time.time() - start >= max_wait:
            label.config(
                text="No se pudo establecer comunicación con la tarjeta.\n"
                     "Verifique la conexión y reinicie el equipo."
            )
            root.after(5000, root.destroy)
            return
        root.after(1000, _poll)

    root.after(1000, _poll)
    root.mainloop()
    return connected


def main():
    args = _parse_args()
    _configurar_logging_archivo(f"_puerta{args.door}" if args.door is not None else "")

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

    INSTALL_DOOR = profile.door_id
    # --door ausente (caso normal, 1 PC = 1 puerta): comportamiento idéntico al
    # de siempre. --door presente: PC único con 2 monitores — esta ventana
    # puede representar una puerta distinta a la del perfil de instalación.
    SOURCE_DOOR = args.door if args.door is not None else INSTALL_DOOR
    dual_screen_mode = args.door is not None
    is_secondary_window = dual_screen_mode and args.door != INSTALL_DOOR
    logger.info(
        "Perfil cargado — serie: %s | puerta instalada: %s | puerta de esta ventana: %s%s",
        profile.serial_number, INSTALL_DOOR, SOURCE_DOOR,
        " (ventana secundaria, mismo PC)" if is_secondary_window else "",
    )

    # ── 2. Iniciar backend ────────────────────────────────────────────────
    # Una ventana secundaria nunca arranca ni posee el backend — solo se
    # conecta al que ya levantó la ventana primaria en este mismo PC.
    backend_process = None
    if is_secondary_window:
        logger.info("Ventana secundaria — esperando backend local ya iniciado por la ventana primaria...")
        if not wait_for_backend(max_wait=40):
            logger.warning("Backend no disponible, la UI seguirá intentando...")
    elif INSTALL_DOOR == 1:
        if is_backend_alive():
            logger.info("Backend ya estaba corriendo")
        else:
            backend_guard.cleanup_stale_backend()
            logger.info("Iniciando backend...")
            backend_process = subprocess.Popen(
                _backend_command(),
                stdout=subprocess.DEVNULL,
                stderr=None,
                env=_backend_env(),
            )
            backend_guard.write_backend_pid(backend_process.pid)
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("Backend no respondió — la UI arrancará sin datos")
        wait_for_hardware_connection(max_wait=40)
    else:
        logger.info("PC puerta 2 — esperando backend en red...")
        if not wait_for_backend(max_wait=40):
            logger.warning("Backend no disponible, la UI seguirá intentando...")

    # ── 2b. Iniciar heartbeat de impresora ────────────────────────────────
    # Solo la ventana que posee el backend registra el heartbeat de impresora
    # y (más abajo) imprime el ticket de arranque — una ventana secundaria en
    # el mismo PC no debe duplicarlos.
    if is_secondary_window:
        _last_shutdown_time = None
    else:
        _last_shutdown_time = heartbeat.read_last_shutdown()
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
        if is_secondary_window:
            # Esta ventana no es dueña del equipo (comparte backend con la
            # ventana primaria de la otra puerta, en el mismo PC) — cerrarla
            # NUNCA debe apagar salidas ni detener el control_loop, o se
            # abortaría un ciclo activo en la otra puerta. Ver UI-03 en
            # docs/mis_plans/planeacion_ui_dual_pantalla.md.
            ui_service.stop()
            app.destroy()
            return
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
        last_shutdown=_last_shutdown_time,
        monitor_index=(SOURCE_DOOR - 1) if dual_screen_mode else None,
        print_startup_ticket=not is_secondary_window,
    )
    logger.info("UI Autoclave iniciada")
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
