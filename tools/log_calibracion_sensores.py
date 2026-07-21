"""
tools/log_calibracion_sensores.py

Script de diagnostico: captura lecturas crudas (ADC) y filtradas
(temperatura/presion, ya pasadas por el pipeline de converters.py) a un CSV,
para calibrar TEMP_MINCUTOFF/TEMP_BETA/PRES_MINCUTOFF/PRES_BETA en
src/autoclave/hal/measures/converters.py con datos reales del equipo.

Uso:
    python tools/log_calibracion_sensores.py --etiqueta reposo
    python tools/log_calibracion_sensores.py --etiqueta rampa

Correr una vez en reposo (equipo encendido, sin ciclo, sensores estables) y
otra vez durante una rampa real de calentamiento (parte de un ciclo real),
en corridas separadas. Detener cada corrida con Ctrl+C: guarda el CSV al salir.

Los CSV quedan en capturas_calibracion/ (carpeta ignorada por git).
"""
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

from autoclave.protocols.serial_link import SerialLink
from autoclave.hal.measures.units import Units

CONFIG_PATH = "src/autoclave/config/calibration.yaml"
CARPETA_SALIDA = Path("capturas_calibracion")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--puerto", default=None,
        help="Puerto COM forzado (ej. COM7). Si no se pasa, se auto-detecta.",
    )
    parser.add_argument(
        "--etiqueta", default="captura",
        help="Nombre corto para identificar la corrida (ej. reposo, rampa). Se usa en el nombre del CSV.",
    )
    args = parser.parse_args()

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    salida = CARPETA_SALIDA / f"{args.etiqueta}_{datetime.now():%Y%m%d_%H%M%S}.csv"

    units = Units(CONFIG_PATH)
    filas = []

    def on_update(data):
        units.update_from_serial(data)
        estado = units.get_all()
        fila = {
            "timestamp": datetime.now().isoformat(),
            "monotonic": time.monotonic(),
            "connected": estado["connected"],
        }
        for i, v in enumerate(estado["raw_ai"]):
            fila[f"raw_ai_{i}"] = v
        for i in range(8):
            fila[f"temp_{i}"] = estado["temperature"][i]
        for i in range(8):
            fila[f"pres_{i}"] = estado["pressure"][i]
        filas.append(fila)
        print(
            f"\r{len(filas)} lecturas | temp_camara={estado['temperature'][0]} "
            f"| pres_camara={estado['pressure'][0]}",
            end="", flush=True,
        )

    link = SerialLink(on_update=on_update)
    if args.puerto:
        link._scan_ports = lambda: args.puerto

    print(f"Conectando... (Ctrl+C para detener y guardar en {salida})")
    link.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()
        if filas:
            with open(salida, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
                writer.writeheader()
                writer.writerows(filas)
            print(f"\nGuardado: {salida} ({len(filas)} lecturas)")
        else:
            print("\nNo se capturo ninguna lectura (¿el puerto conecto bien?).")


if __name__ == "__main__":
    main()
