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
#   Autoclave.exe --rol asociar-tactiles   (EST-06) asocia cada pantalla táctil con su
#                                       monitor sin MultiDigitizer.exe (administrador;
#                                       ver estacion/asociar_tactiles.py)
#   Autoclave.exe --portable            corre desde donde esté, sin ofrecer instalar
#   Autoclave.exe --esperar-pid P ...   (R11) antes de arrancar espera a que esos
#                                       procesos terminen y el puerto del backend
#                                       quede libre (relanzamiento tras reiniciar_software)
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
#
# R11 (tanda 11, D11-1): cuando el backend termina con
# CODIGO_REINICIO_SOFTWARE (reiniciar_software, p. ej. al cambiar la
# impresora; ya hizo el cierre ordenado de "Apagar equipo" sin apagar
# Windows), el lanzador cierra las pantallas y, ya terminado el backend, vuelve
# a abrir el mismo comando con --esperar-pid (el suyo y el del backend): una
# sola instancia. Si el relanzamiento falla queda en lanzador.log; la pantalla
# ya avisó al operador que apague y encienda el equipo si no vuelve a abrir.
#
# EST-07 (tanda 17, DECISIÓN SIN CONFIRMAR): lo primero que hace el lanzador,
# antes de importar PySide o lanzar el backend, es abrir la cubierta de
# arranque (estacion/cubierta_arranque.py): una ventana Win32 negra por
# monitor que tapa el escritorio hasta que las pantallas QML muestran su
# primer cuadro (o 180 s). Si falla, solo queda en el log.

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse


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
    # VER-05: la primera línea de cada log dice qué compilación corre
    from autoclave._version import version_completa
    logging.getLogger("autoclave.exe_unico").info("Autoclave %s (%s)", version_completa(), nombre)


def escribir_version(ruta: str) -> int:
    """VER-04 (§2.2 paso 5 de la etapa VER): escribe la versión en `ruta` (JSON) y
    sale, sin abrir el puerto serial, el backend ni ninguna ventana. Lo usa
    tools/entrega/compilar_entrega.py para comprobar el .exe compilado."""
    import json
    from autoclave import _version
    datos = {"version_semver": _version.VERSION_SEMVER, "version_pep440": _version.__version__,
             "mostrada": _version.version_mostrada(), "completa": _version.version_completa(),
             "compilacion": _version._info_compilacion(), "congelado": bool(getattr(sys, "frozen", False))}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return 0


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Autoclave — ejecutable único")
    parser.add_argument("--rol", choices=("lanzador", "backend", "ui", "ajustes", "instalar",
                                          "asociar-tactiles"), default="lanzador")
    parser.add_argument("--door", type=int, choices=(1, 2), default=1)
    parser.add_argument("--screen", type=int, default=0)
    parser.add_argument("--una-pantalla", action="store_true")
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--monitor-puerta1", type=int, default=0)
    parser.add_argument("--monitor-puerta2", type=int, default=1)
    parser.add_argument("--esperar-pid", type=int, action="append", default=None)
    parser.add_argument("--escribir-version", metavar="RUTA", default=None)   # VER-04
    args, sobrantes = parser.parse_known_args(argv)
    # EST-06: las opciones propias de --rol asociar-tactiles (--respaldo, --log,
    # --tope-s) pasan a su módulo; con cualquier otro rol, error como antes
    if sobrantes and args.rol != "asociar-tactiles":
        parser.error("argumentos no reconocidos: " + " ".join(sobrantes))
    args.sobrantes = sobrantes
    args.esperar_pid = list(args.esperar_pid or [])
    return args


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


# ── R11: relanzamiento con una sola instancia ──────────────────────────────

TOPE_ESPERA_INSTANCIA_S = 60.0


def _pid_vivo(pid: int) -> bool:
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False   # sin psutil o proceso ya ido: decide el puerto


def _puerto_backend_ocupado() -> bool:
    """True si algo escucha en el puerto del backend (127.0.0.1:8000)."""
    from autoclave.ui_qml.app import BACKEND_URL
    url = urlparse(BACKEND_URL)
    try:
        with socket.create_connection((url.hostname or "127.0.0.1", url.port or 8000),
                                      timeout=0.5):
            return True
    except OSError:
        return False


def esperar_instancia_anterior(pids, tope_s: float = TOPE_ESPERA_INSTANCIA_S, pid_vivo=None,
                               puerto_ocupado=None, reloj=time.monotonic, dormir=None,
                               pausa_s: float = 0.25, log=None) -> bool:
    """Espera a que terminen los procesos `pids` (lanzador y backend
    anteriores) y a que el puerto del backend quede libre. False si vence el
    tope: queda en el log y se sigue; el lanzador usa entonces el backend que
    responda y no arranca otro (nunca dos backends escuchando)."""
    pid_vivo = pid_vivo or _pid_vivo
    puerto_ocupado = puerto_ocupado or _puerto_backend_ocupado
    dormir = dormir or time.sleep
    log = log or logging.getLogger("autoclave.exe_unico")
    pendientes = [p for p in pids if p]
    limite = reloj() + tope_s
    while True:
        pendientes = [p for p in pendientes if pid_vivo(p)]
        if not pendientes and not puerto_ocupado():
            log.info("Instancia anterior terminada y puerto del backend libre")
            return True
        if reloj() >= limite:
            log.error("La instancia anterior no terminó en %.0f s (procesos vivos: %s); se sigue: "
                      "si hay un backend escuchando se usa ese y no se arranca otro",
                      tope_s, pendientes or "ninguno")
            return False
        dormir(pausa_s)


def _sin_esperar_pid(argv) -> list[str]:
    salida, saltar = [], False
    for a in argv:
        if saltar:
            saltar = False
        elif a == "--esperar-pid":
            saltar = True
        elif not a.startswith("--esperar-pid="):
            salida.append(a)
    return salida


def relanzar_software(argv, pids, popen=None, log=None) -> bool:
    """Vuelve a abrir el mismo comando con que arrancó este lanzador (el .exe
    congelado, o `python -m autoclave.exe_unico` en desarrollo), desligado de
    este proceso y con --esperar-pid para que la instancia nueva espere a que
    esta y su backend hayan terminado. False si no se pudo (queda en el log)."""
    popen = popen or subprocess.Popen
    log = log or logging.getLogger("autoclave.exe_unico")
    extra = []
    for pid in pids:
        if pid:
            extra += ["--esperar-pid", str(pid)]
    cmd = _cmd_propio(*_sin_esperar_pid(argv), *extra)
    entorno = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    entorno.pop("_MEIPASS2", None)
    entorno.pop("AUTOCLAVE_EXE_UNICO", None)
    banderas = 0
    if sys.platform == "win32":
        banderas = (getattr(subprocess, "DETACHED_PROCESS", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        popen(cmd, cwd=os.getcwd(), env=entorno, creationflags=banderas, close_fds=True)
    except Exception:
        log.exception("Reinicio del software: no se pudo volver a abrir Autoclave (%s). "
                      "Si no vuelve a abrir, apague y encienda el equipo", " ".join(cmd))
        return False
    log.warning("Reinicio del software: Autoclave relanzado: %s", " ".join(cmd))
    return True


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


def _abrir_cubierta(args):
    """EST-07: abre la cubierta de arranque (solo Windows; por defecto solo en
    el build congelado, ver cubierta_arranque.activa). Devuelve (cubierta,
    error): nunca lanza ni impide el arranque. No importa PySide."""
    try:
        from autoclave.estacion import cubierta_arranque
        if not cubierta_arranque.activa():
            return None, None
        puertas = (1,) if args.una_pantalla else (1, 2)
        cubierta = cubierta_arranque.abrir(puertas)
        return cubierta, getattr(cubierta, "error", None)
    except Exception as e:   # pragma: no cover - abrir() ya no lanza
        return None, f"{type(e).__name__}: {e}"


def _cerrar_cubierta(cubierta) -> None:
    if cubierta is None:
        return
    try:
        cubierta.cerrar()
    except Exception:
        logging.getLogger("autoclave.exe_unico").exception("No se pudo cerrar la cubierta de arranque")


def _tomar_instancia(args):
    """V17-s2-01: mutex con nombre de la sesión (estacion/instancia_unica.py).
    Devuelve la Instancia o None si la protección no está activa (desarrollo).
    Relanzado por R11 (--esperar-pid), espera a que la instancia anterior
    suelte el mutex, con el mismo tope que esperar_instancia_anterior."""
    try:
        from autoclave.estacion import instancia_unica
        if not instancia_unica.activa():
            return None
        tope = TOPE_ESPERA_INSTANCIA_S if args.esperar_pid else 0.0
        return instancia_unica.tomar(esperar_s=tope)
    except Exception as e:   # pragma: no cover - tomar() ya no lanza
        from types import SimpleNamespace
        return SimpleNamespace(primera=True, error=f"{type(e).__name__}: {e}", soltar=lambda: None)


def _lanzador(args) -> int:
    # V17-s2-01: un solo lanzador por sesión, ANTES de abrir la cubierta (un
    # segundo lanzador taparía las pantallas vivas, quizá con un ciclo en curso)
    instancia = _tomar_instancia(args)
    if instancia is not None and not instancia.primera:
        # DECISIÓN SIN CONFIRMAR: no había otra protección contra un segundo
        # lanzador (solo se reutilizaba el backend); lo más seguro es no
        # lanzar nada: ni cubierta, ni backend, ni pantallas
        try:
            _log_a_archivo("lanzador.log")
        except Exception:
            pass
        logging.getLogger("autoclave.exe_unico").error(
            "Ya hay un lanzador de Autoclave en esta sesión: este no abre la cubierta, "
            "el backend ni las pantallas")
        return 0
    try:
        # EST-07: lo primero, antes de importar PySide o arrancar el backend
        cubierta = {}
        cubierta["actual"], error_cubierta = _abrir_cubierta(args)
        try:
            return _lanzador_con_cubierta(args, cubierta, error_cubierta, instancia)
        finally:
            _cerrar_cubierta(cubierta.get("actual"))
    finally:
        if instancia is not None:
            instancia.soltar()   # el mutex vive mientras viva el lanzador


def _lanzador_con_cubierta(args, cubierta: dict, error_cubierta, instancia=None) -> int:
    _log_a_archivo("lanzador.log")
    logger = logging.getLogger("autoclave.exe_unico")
    logger.info("Lanzador iniciado")   # mide el arranque del propio ejecutable
    if instancia is not None and getattr(instancia, "error", None):
        logger.error("No se pudo comprobar si hay otro lanzador (%s): se sigue sin esa protección",
                     instancia.error)
    if error_cubierta:
        logger.error("Cubierta de arranque no disponible (%s): el arranque sigue sin ella", error_cubierta)
    elif cubierta.get("actual") is not None:
        logger.info("Cubierta de arranque pedida al iniciar el lanzador")
    if args.esperar_pid:
        # R11: relanzado tras reiniciar_software; una sola instancia
        esperar_instancia_anterior(args.esperar_pid, log=logger)

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
        # EST-07: la cubierta se cerró con el primer cuadro del asistente;
        # se vuelve a abrir mientras arrancan el backend y las pantallas normales
        _cerrar_cubierta(cubierta.get("actual"))
        cubierta["actual"], error_cubierta = _abrir_cubierta(args)
        if error_cubierta:
            logger.error("Cubierta de arranque no disponible (%s)", error_cubierta)

    import threading
    from autoclave.backend import reinicio

    backend = {"proc": None}
    # R8: solo el backend que este lanzador vigila sabe reiniciarse (SAF-06)
    entorno_backend = {**entorno, reinicio.VARIABLE_RELANZABLE: "1"}
    fin_vigilancia = threading.Event()
    lock_lanzar = threading.Lock()
    # R11: el backend terminó con CODIGO_REINICIO_SOFTWARE
    reinicio_software = threading.Event()

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
                                           kwargs={"log": logger,
                                                   "al_reiniciar_software": reinicio_software.set},
                                           name="vigilancia-reinicio-backend",
                                           daemon=True)
        hilo_vigilancia.start()

    pantallas = [(1, args.monitor_puerta1)] if args.una_pantalla else \
        [(1, args.monitor_puerta1), (2, args.monitor_puerta2)]
    cmds = [_cmd_propio("--rol", "ui", "--door", str(p), "--screen", str(m)) for p, m in pantallas]
    try:
        vigilar_pantallas(cmds, lambda cmd: subprocess.Popen(cmd, cwd=cwd, env=entorno),
                          barra=barra_tareas, detener=reinicio_software)
    finally:
        with lock_lanzar:
            fin_vigilancia.set()
        if hilo_vigilancia is not None:
            hilo_vigilancia.join(5)
        with lock_lanzar:
            proc = backend["proc"]
        if proc is not None:
            _apagar_backend(BACKEND_URL, proc, logger)
        # SAF-04 (revisión R11): las pantallas pueden haberse cerrado por su
        # cuenta justo cuando el backend salió con el código de software,
        # antes de que el vigilante lo viera: también es un reinicio
        if reinicio_software.is_set() or (
                proc is not None and proc.poll() == reinicio.CODIGO_REINICIO_SOFTWARE):
            # guardar → cerrar → relanzar: el backend ya terminó su cierre
            # ordenado; la instancia nueva espera además a este proceso
            argv = getattr(args, "argv_original", None)
            relanzar_software(sys.argv[1:] if argv is None else argv,
                              [os.getpid(), getattr(proc, "pid", None)], log=logger)
    return 0


def main(argv=None) -> int:
    _sin_consola()
    args = _parse_args(argv)
    args.argv_original = list(sys.argv[1:] if argv is None else argv)   # R11
    if args.escribir_version:
        return escribir_version(args.escribir_version)
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
    if args.rol == "asociar-tactiles":
        # EST-06: sin Qt ni backend; requiere administrador (ver el módulo).
        # V17-s2-04: sin log de archivo se sigue (la herramienta escribe además
        # en el log de la estación)
        try:
            _log_a_archivo("asociar_tactiles.log")
        except Exception:
            pass
        from autoclave.estacion.asociar_tactiles import main as asociar_main
        return asociar_main(args.sobrantes)
    if getattr(sys, "frozen", False) and not args.portable:
        from autoclave.instalador_exe import esta_instalado_aqui, ofrecer_instalacion
        if not esta_instalado_aqui():
            ofrecer_instalacion()   # antes de cualquier log: nada se escribe junto a este .exe
            return 0
    return _lanzador(args)


if __name__ == "__main__":
    sys.exit(main())
