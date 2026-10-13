# autoclave/backend/main.py

import logging
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


def main():
    _configurar_logging_archivo()
    logger.info("Backend iniciado desde: %s", __file__)
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
    threading.Thread(target=arrancar_cuando_escuche, args=(servidor, server.iniciar_arranque),
                     name="arranque-espera-puerto", daemon=True).start()
    servidor.run()

if __name__ == "__main__":
    main()
