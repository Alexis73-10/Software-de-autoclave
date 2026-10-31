# simulador/__main__.py
#
# Backend SIMULADO para probar la UI sin módulo E/S (herramienta de desarrollo):
#
#   python -m autoclave.simulador [--puerto 8001] [--velocidad 10] [--ciclo 76]
#
# y en otra terminal la UI apuntada a él (PowerShell):
#
#   $env:AUTOCLAVE_BACKEND_URL = "http://127.0.0.1:8001"   (no "localhost": en Windows tarda ~2 s por petición)
#   python -m autoclave.ui_qml.app --door 1
#
# Reproduce el último ciclo COMPLETADO con lecturas suficientes de data/autoclave.db
# (solo lectura), acelerado --velocidad veces. Escucha solo en 127.0.0.1. No usa
# el módulo E/S, el control ni la máquina de estados reales.

import argparse
import logging

import uvicorn

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.services.domain.logging.db_manager import DB_DEFAULT
from autoclave.simulador.repeticion import Repeticion, cargar_ciclo
from autoclave.simulador.servidor import crear_app

logger = logging.getLogger("autoclave.simulador")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backend SIMULADO (sin módulo E/S) para probar la UI")
    parser.add_argument("--puerto", type=int, default=8001, help="Puerto (defecto 8001)")
    parser.add_argument("--velocidad", type=float, default=10.0,
                        help="Veces más rápido que el ciclo real (defecto 10)")
    parser.add_argument("--ciclo", type=int, default=None,
                        help="ID en BD del ciclo a reproducir (defecto: último COMPLETADO)")
    parser.add_argument("--bd", default=str(DB_DEFAULT), help="Base de datos (solo lectura)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    ciclo = cargar_ciclo(args.bd, args.ciclo)
    repeticion = Repeticion(ciclo)

    ciclos = CycleManager()
    ciclos.load_all_cycles()
    # el programa mostrado es el del ciclo reproducido (selección solo en memoria)
    try:
        ciclos.set_default_cycle(ciclo["tipo_ciclo"])
    except Exception:
        ciclos.set_default_cycle(next(iter(ciclos.cycles)))
        logger.warning("Programa '%s' no encontrado; se muestra '%s'",
                       ciclo["tipo_ciclo"], ciclos.get_selected_cycle().id)
    config = ConfigManager()
    config.load_config()

    logger.warning("BACKEND SIMULADO — ciclo #%s (%s), %.1f min reales a %gx = %.1f min",
                   ciclo["numero_ciclo"], ciclo["tipo_ciclo"], repeticion.duracion_s / 60,
                   args.velocidad, repeticion.duracion_s / 60 / args.velocidad)
    app = crear_app(repeticion, ciclos, config.get(), velocidad=args.velocidad)
    uvicorn.run(app, host="127.0.0.1", port=args.puerto, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
