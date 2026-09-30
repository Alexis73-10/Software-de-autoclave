# ui_qml/doble_pantalla.py
#
# Lanzador de las dos pantallas QML de un PC con dos monitores (una por puerta):
#   python -m autoclave.ui_qml.doble_pantalla [--monitor-puerta1 0] [--monitor-puerta2 1]
#
# Levanta dos procesos de autoclave.ui_qml.app, uno con --door 1 y otro con
# --door 2, para que la identidad de cada pantalla no dependa de escribir bien
# dos comandos a mano. No arranca el backend (se lanza aparte con
# `python -m autoclave.backend.main`). Ctrl+C cierra las dos pantallas; si una
# se cierra sola, la otra sigue abierta.

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# raíz del repo (…/src/autoclave/ui_qml/doble_pantalla.py -> parents[3]); resource_path
# resuelve los .qml contra "src" del directorio actual, así que los hijos corren desde aquí
RAIZ_PROYECTO = Path(__file__).resolve().parents[3]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Autoclave — lanza las dos pantallas QML")
    parser.add_argument("--monitor-puerta1", type=int, default=0,
                        help="Índice del monitor de la puerta 1 (defecto: 0)")
    parser.add_argument("--monitor-puerta2", type=int, default=1,
                        help="Índice del monitor de la puerta 2 (defecto: 1)")
    return parser.parse_args(argv)


def comandos(monitor_puerta1: int, monitor_puerta2: int) -> list[list[str]]:
    """Un comando por puerta: la puerta va fija en cada uno, nunca se repite."""
    return [
        [sys.executable, "-m", "autoclave.ui_qml.app", "--door", str(puerta), "--screen", str(monitor)]
        for puerta, monitor in ((1, monitor_puerta1), (2, monitor_puerta2))
    ]


def main(argv=None, popen=subprocess.Popen) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)
    procesos = []
    for cmd in comandos(args.monitor_puerta1, args.monitor_puerta2):
        logger.info("Lanzando: %s", " ".join(cmd[1:]))
        procesos.append(popen(cmd, cwd=str(RAIZ_PROYECTO)))
    try:
        for p in procesos:
            p.wait()
    except KeyboardInterrupt:
        logger.info("Cerrando las dos pantallas...")
        for p in procesos:
            if p.poll() is None:
                p.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
