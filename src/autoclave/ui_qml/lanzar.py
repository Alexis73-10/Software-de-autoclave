# ui_qml/lanzar.py
#
# Lanzador de la UI QML, en dos modos:
#
#   python -m autoclave.ui_qml.lanzar simulador [--velocidad 10] [--una-pantalla] [--door N]
#       Levanta el backend SIMULADO (autoclave.simulador, sin tarjeta) en 127.0.0.1:8001
#       y las pantallas apuntadas a él. Al cerrar las pantallas se detiene el simulador.
#
#   python -m autoclave.ui_qml.lanzar real [--una-pantalla] [--door N]
#       Pantallas contra el backend real (127.0.0.1:8000). NO lo arranca (ese abre
#       la tarjeta): solo avisa si no responde. Ignora AUTOCLAVE_BACKEND_URL aunque
#       haya quedado definida en la terminal.
#
# Sin --una-pantalla abre las dos pantallas (puerta 1 y 2), como doble_pantalla.py.
# Ctrl+C cierra todo.

import argparse
import logging
import os
import subprocess
import sys
import time

import requests

from autoclave.ui_qml.app import BACKEND_URL
from autoclave.ui_qml.doble_pantalla import RAIZ_PROYECTO, comandos, vigilar_pantallas

logger = logging.getLogger(__name__)

PUERTO_SIMULADOR = 8001
URL_SIMULADOR = f"http://127.0.0.1:{PUERTO_SIMULADOR}"
ESPERA_SIMULADOR_S = 20.0


def esperar_backend(url: str, segundos: float) -> bool:
    """True cuando GET {url}/status responde antes de `segundos`."""
    limite = time.monotonic() + segundos
    while True:
        try:
            requests.get(f"{url}/status", timeout=0.8).raise_for_status()
            return True
        except Exception:
            if time.monotonic() >= limite:
                return False
            time.sleep(0.3)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Autoclave — lanza la UI QML con el simulador o el backend real")
    modos = parser.add_subparsers(dest="modo", required=True)
    for nombre, ayuda in (("simulador", "Backend simulado (sin tarjeta) + UI"),
                          ("real", "UI contra el backend real (debe estar corriendo)")):
        p = modos.add_parser(nombre, help=ayuda)
        p.add_argument("--una-pantalla", action="store_true", help="Solo una pantalla")
        p.add_argument("--door", type=int, choices=(1, 2), default=1,
                       help="Puerta de la pantalla con --una-pantalla (defecto 1)")
        p.add_argument("--monitor-puerta1", type=int, default=0)
        p.add_argument("--monitor-puerta2", type=int, default=1)
        if nombre == "simulador":
            p.add_argument("--velocidad", type=float, default=10.0,
                           help="Veces más rápido que el ciclo real (defecto 10)")
    return parser.parse_args(argv)


def _comandos_ui(args) -> list[list[str]]:
    todos = comandos(args.monitor_puerta1, args.monitor_puerta2)
    return [todos[args.door - 1]] if args.una_pantalla else todos


def _entorno(url: str | None) -> dict:
    entorno = dict(os.environ)
    entorno.pop("AUTOCLAVE_BACKEND_URL", None)
    if url is not None:
        entorno["AUTOCLAVE_BACKEND_URL"] = url
    return entorno


def main(argv=None, popen=subprocess.Popen, esperar=esperar_backend) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)
    simulador = None

    if args.modo == "simulador":
        cmd = [sys.executable, "-m", "autoclave.simulador",
               "--puerto", str(PUERTO_SIMULADOR), "--velocidad", f"{args.velocidad:g}"]
        logger.info("Lanzando el backend SIMULADO en %s ...", URL_SIMULADOR)
        simulador = popen(cmd, cwd=str(RAIZ_PROYECTO), env=_entorno(None))
        if not esperar(URL_SIMULADOR, ESPERA_SIMULADOR_S):
            logger.error("El simulador no respondió en %s; no se abre la UI", URL_SIMULADOR)
            simulador.terminate()
            return 1
        entorno = _entorno(URL_SIMULADOR)
    else:
        if not esperar(BACKEND_URL, 1.0):
            logger.warning("El backend real no responde en %s. Arráncalo en otra terminal con "
                           "`python -m autoclave.backend.main`; la UI se conectará sola "
                           "cuando esté disponible.", BACKEND_URL)
        entorno = _entorno(None)

    try:
        # D-04 (T8): una pantalla cerrada se relanza hasta 3 veces, cada 5 s
        vigilar_pantallas(_comandos_ui(args),
                          lambda cmd: popen(cmd, cwd=str(RAIZ_PROYECTO), env=entorno))
    finally:
        if simulador is not None and simulador.poll() is None:
            logger.info("Deteniendo el simulador")
            simulador.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
