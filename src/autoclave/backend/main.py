# autoclave/backend/main.py

import logging
import os
import sys
import threading
import time

import uvicorn

from autoclave.utils.paths import app_root

HOST = "127.0.0.1"
PUERTO = 8000

logger = logging.getLogger(__name__)


def _configurar_logging_archivo() -> None:
    """En un build congelado (.exe) no hay consola visible ni stdout — sin
    esto, un fallo de arranque del backend no dejaría ningún rastro que el
    técnico pueda revisar en el PC de pruebas."""
    if not getattr(sys, "frozen", False):
        return
    log_path = app_root() / "data" / "backend.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def arrancar_cuando_escuche(servidor, iniciar, intervalo_s: float = 0.05, dormir=time.sleep) -> bool:
    """Llama a `iniciar` cuando uvicorn ya enlazó el puerto (`started`).
    uvicorn corre el lifespan de inicio ANTES de enlazar: disparar el arranque
    ahí abriría el serial aunque el puerto estuviera ocupado (hallazgo 1 de
    Code). Si el servidor se cierra sin llegar a escuchar, no se llama."""
    while not servidor.started:
        if servidor.should_exit:
            logger.error("El backend se cerró sin abrir el puerto %d: arranque no iniciado", PUERTO)
            return False
        dormir(intervalo_s)
    iniciar()
    return True


def latido_y_ticket(server, plazo_s: float = 120.0) -> None:
    """R1 (tanda 2): latido de apagado y ticket de arranque, que antes hacía la
    ventana principal de la UI anterior. Espera a que el arranque deje el
    contexto operable (perfil cargado); si no llega, arranca solo el latido."""
    operable = getattr(server, "_contexto_operable", None)
    if operable is None or not operable.wait(plazo_s):
        logger.warning("Arranque no operable en %.0f s: latido sin ticket de arranque", plazo_s)
    try:
        from autoclave.devices.printer import arranque_equipo
        perfil = getattr(server.context, "profile", None) if operable and operable.is_set() else None
        arranque_equipo.iniciar(perfil)
    except Exception:
        logger.exception("No se pudo iniciar el latido / ticket de arranque")


def main():
    _configurar_logging_archivo()
    from autoclave._version import version_completa
    logger.info("Autoclave %s: backend iniciado desde %s", version_completa(), __file__)   # VER-05
    from autoclave.backend import server

    server.preparar_arranque()   # 503 en todo salvo /arranque hasta tener el control
    servidor = uvicorn.Server(uvicorn.Config(
        server.app,
        # Fijo, sin configuración (planeacion_backend_autenticacion.md, decisión 1):
        # solo procesos de este PC; las escrituras exigen además token.
        host=HOST,
        port=PUERTO,
        log_level="info",
    ))
    threading.Thread(target=latido_y_ticket, args=(server,),
                     name="latido-ticket", daemon=True).start()
    threading.Thread(target=arrancar_cuando_escuche, args=(servidor, server.iniciar_arranque),
                     name="arranque-espera-puerto", daemon=True).start()
    # R8 (D8-5.12): una reasignación de E/S se aplica reiniciando este proceso.
    # Solo si hay quien lo relance (SAF-06/TMG-03 de la revisión R8): el
    # lanzador del ejecutable único marca así al backend que vigila. Sin esa
    # marca la reasignación se guarda y rige al próximo arranque.
    from autoclave.backend import reinicio
    if os.environ.get(reinicio.VARIABLE_RELANZABLE) == "1":
        reinicio.registrar(lambda: setattr(servidor, "should_exit", True))
    else:
        logger.info("Sin lanzador que relance el backend: la reasignación de E/S rige al reiniciar a mano")
    servidor.run()
    if reinicio.solicitado():
        # R11: CODIGO_REINICIO (solo el backend) o CODIGO_REINICIO_SOFTWARE (todo)
        codigo = reinicio.codigo_salida()
        logger.warning("Backend detenido para reiniciarse (código %d)", codigo)
        sys.exit(codigo)

if __name__ == "__main__":
    main()
