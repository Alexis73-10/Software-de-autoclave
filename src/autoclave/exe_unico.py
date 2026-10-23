# autoclave/exe_unico.py
#
# Punto de entrada del ejecutable único (Autoclave.exe, ver Autoclave.spec):
# un solo .exe que levanta el backend y las dos pantallas QML del PC de dos
# monitores. Se relanza a sí mismo con un rol interno para cada proceso:
#
#   Autoclave.exe                       lanzador: backend + pantallas puerta 1 y 2
#   Autoclave.exe --una-pantalla        lanzador: backend + solo la puerta 1
#   Autoclave.exe --rol backend         solo el backend (127.0.0.1:8000)
#   Autoclave.exe --rol ui --door N --screen I    una pantalla QML
#   Autoclave.exe --rol ajustes         menú de configuración PySide (el engrane)
#   Autoclave.exe --rol instalar        copia a Archivos de programa (elevado, ver instalador_exe.py)
#   Autoclave.exe --portable            corre desde donde esté, sin ofrecer instalar
#
# Abierto desde fuera de %ProgramFiles%\Especifika\Autoclave (p. ej. una USB)
# ofrece instalarse ahí y abre la copia instalada; no escribe nada en la USB.
# Instalado, los datos van en %ProgramData%\Especifika\Autoclave (app_root).
#
# Los hijos reutilizan la carpeta de extracción del lanzador (no se borra
# mientras el lanzador siga abierto).
#
# Al cerrarse todas las pantallas (sin relanzamientos pendientes, D-04) se
# apagan las salidas con /outputs/reset y se detiene el backend; con un ciclo
# en curso (409) el backend NO se detiene hasta que el ciclo termine, para no
# matarlo con las salidas encendidas (mismo criterio que on_close de main.py).
# Los logs quedan en data/ de la carpeta de datos.

import argparse
import logging
import os
import subprocess
import sys
import time


def _sin_consola() -> None:
    """Sin consola (console=False) stdout/stderr son None y uvicorn/print fallan."""
    if sys.stdout is None or sys.stderr is None:
        nulo = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = sys.stdout or nulo
        sys.stderr = sys.stderr or nulo


def _log_a_archivo(nombre: str) -> None:
    from autoclave.utils.paths import app_root
    ruta = app_root() / "data" / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(ruta, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Autoclave — ejecutable único")
    parser.add_argument("--rol", choices=("lanzador", "backend", "ui", "ajustes", "instalar"), default="lanzador")
    parser.add_argument("--door", type=int, choices=(1, 2), default=1)
    parser.add_argument("--screen", type=int, default=0)
    parser.add_argument("--una-pantalla", action="store_true")
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--monitor-puerta1", type=int, default=0)
    parser.add_argument("--monitor-puerta2", type=int, default=1)
    return parser.parse_args(argv)


def _cmd_propio(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "autoclave.exe_unico", *args]


def _backend_responde(url: str) -> bool:
    import requests
    try:
        # cualquier respuesta sirve: hasta tener el control responde 503 salvo /arranque
        requests.get(f"{url}/status", timeout=0.8)
        return True
    except requests.RequestException:
        return False


def _apagar_backend(url: str, proc, logger) -> None:
    import requests
    while proc.poll() is None:
        try:
            r = requests.post(f"{url}/outputs/reset", timeout=5)
            if r.status_code == 409:
                logger.warning("Ciclo en curso: el backend sigue hasta que termine")
                time.sleep(5)
                continue
            logger.info("outputs/reset: %s", r.status_code)
        except requests.RequestException as e:
            logger.warning("outputs/reset falló: %s", e)
        break
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    logger.info("Backend detenido")


def _cerrar_reposo_instalacion(proc, logger) -> None:
    """W10: cierra la pantalla 2 de Reposo de instalación (no tiene backend ni
    salidas: solo muestra logo, reloj y aviso)."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    logger.info("Pantalla 2 de Reposo de instalación cerrada")


def _lanzador(args) -> int:
    _log_a_archivo("lanzador.log")
    logger = logging.getLogger("autoclave.exe_unico")
    logger.info("Lanzador iniciado")   # mide el arranque del propio ejecutable

    from autoclave.installation import backend_guard
    from autoclave.ui_qml import barra_tareas
    from autoclave.ui_qml.app import BACKEND_URL
    from autoclave.ui_qml.doble_pantalla import vigilar_pantallas
    from autoclave.utils.paths import app_root

    from autoclave.ui_qml.bridge.puente_instalacion import requiere_instalacion
    from autoclave.ui_qml.doble_pantalla import CODIGO_INSTALACION_TERMINADA

    entorno = {**os.environ, "AUTOCLAVE_EXE_UNICO": "1", "PYTHONIOENCODING": "utf-8"}
    entorno.pop("AUTOCLAVE_BACKEND_URL", None)   # siempre contra el backend real
    cwd = str(app_root())

    # Sin perfil de instalación (PC nuevo): primero solo el asistente, sin
    # backend (no lo necesita). Al terminarlo (código 3) se sigue con el
    # arranque normal ya con el perfil nuevo, sin reiniciar a mano.
    # W10 (D10-4): con dos pantallas, la puerta 2 muestra entretanto el Reposo
    # con el aviso de instalación en curso; al terminar el asistente se cierra
    # y se vuelve a abrir con el flujo normal junto a la puerta 1 (fuera de la
    # vigilancia de caídas, así que no cuenta como relanzamiento).
    if requiere_instalacion():
        logger.warning("Sin perfil de instalación: se abre el asistente")
        asistente = subprocess.Popen(
            _cmd_propio("--rol", "ui", "--door", "1", "--screen", str(args.monitor_puerta1)),
            cwd=cwd, env=entorno)
        reposo = None
        if not args.una_pantalla:
            try:
                reposo = subprocess.Popen(
                    _cmd_propio("--rol", "ui", "--door", "2", "--screen", str(args.monitor_puerta2)),
                    cwd=cwd, env=entorno)
            except Exception:
                logger.exception("No se pudo abrir la pantalla 2 en Reposo de instalación")
        try:
            codigo = asistente.wait()
        finally:
            _cerrar_reposo_instalacion(reposo, logger)
        if codigo != CODIGO_INSTALACION_TERMINADA or requiere_instalacion():
            logger.error("Asistente cerrado sin completar la instalación (código %s)", codigo)
            return 1
        logger.info("Instalación completada: arranque normal")

    import threading
    from autoclave.backend import reinicio

    backend = {"proc": None}
    # R8: solo el backend que este lanzador vigila sabe reiniciarse (SAF-06)
    entorno_backend = {**entorno, reinicio.VARIABLE_RELANZABLE: "1"}
    fin_vigilancia = threading.Event()
    lock_lanzar = threading.Lock()

    def lanzar_backend():
        # TMG-04 (revisión R8): no relanzar si las pantallas ya se cerraron
        # (el finally apagaría el proceso viejo y quedaría uno huérfano)
        with lock_lanzar:
            if backend["proc"] is not None and fin_vigilancia.is_set():
                logger.warning("Pantallas cerradas: no se relanza el backend")
                return
            proc = subprocess.Popen(_cmd_propio("--rol", "backend"), cwd=cwd, env=entorno_backend)
            backend_guard.write_backend_pid(proc.pid)
            backend["proc"] = proc
            logger.info("Backend lanzado (PID %d)", proc.pid)

    if _backend_responde(BACKEND_URL):
        logger.warning("Ya hay un backend en %s: se usa ese y no se arranca otro", BACKEND_URL)
    else:
        backend_guard.cleanup_stale_backend()
        lanzar_backend()
        # Las pantallas se abren ya, sin esperar al backend: su intro muestra
        # las etapas reales de GET /arranque (antes se esperaba hasta 60 s y
        # la intro aparecía con el arranque ya hecho; observación del 19-oct).

    # R8 (D8-5.12): el backend se reinicia para aplicar una reasignación de E/S
    hilo_vigilancia = None
    if backend["proc"] is not None:
        hilo_vigilancia = threading.Thread(target=reinicio.vigilar_reinicios,
                                           args=(lambda: backend["proc"], lanzar_backend, fin_vigilancia),
                                           kwargs={"log": logger}, name="vigilancia-reinicio-backend",
                                           daemon=True)
        hilo_vigilancia.start()

    pantallas = [(1, args.monitor_puerta1)] if args.una_pantalla else \
        [(1, args.monitor_puerta1), (2, args.monitor_puerta2)]
    cmds = [_cmd_propio("--rol", "ui", "--door", str(p), "--screen", str(m)) for p, m in pantallas]
    try:
        vigilar_pantallas(cmds, lambda cmd: subprocess.Popen(cmd, cwd=cwd, env=entorno),
                          barra=barra_tareas)
    finally:
        with lock_lanzar:
            fin_vigilancia.set()
        if hilo_vigilancia is not None:
            hilo_vigilancia.join(5)
        with lock_lanzar:
            proc = backend["proc"]
        if proc is not None:
            _apagar_backend(BACKEND_URL, proc, logger)
    return 0


def main(argv=None) -> int:
    _sin_consola()
    args = _parse_args(argv)
    if args.rol == "backend":
        from autoclave.backend.main import main as backend_main
        backend_main()   # escribe su propio data/backend.log en el .exe
        return 0
    if args.rol == "ui":
        _log_a_archivo(f"ui_puerta{args.door}.log")
        from autoclave.ui_qml.app import main as ui_main
        return ui_main(["--door", str(args.door), "--screen", str(args.screen)])
    if args.rol == "ajustes":
        _log_a_archivo("ajustes.log")
        sys.argv = sys.argv[:1]
        from autoclave.ui_pyside.app import main as ajustes_main
        ajustes_main()
        return 0
    if args.rol == "instalar":
        from autoclave.instalador_exe import instalar
        return instalar()
    if getattr(sys, "frozen", False) and not args.portable:
        from autoclave.instalador_exe import esta_instalado_aqui, ofrecer_instalacion
        if not esta_instalado_aqui():
            ofrecer_instalacion()   # antes de cualquier log: nada se escribe junto a este .exe
            return 0
    return _lanzador(args)


if __name__ == "__main__":
    sys.exit(main())
