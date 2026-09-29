# autoclave/backend/main.py

import logging
import sys
import uvicorn

from autoclave.utils.paths import app_root


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


def main():
    _configurar_logging_archivo()
    logging.getLogger(__name__).info("Backend iniciado desde: %s", __file__)
    uvicorn.run(
        "autoclave.backend.server:app",
        host="0.0.0.0",   # CRÍTICO: escucha en red
        port=8000,
        log_level="info",
    )

if __name__ == "__main__":
    main()
