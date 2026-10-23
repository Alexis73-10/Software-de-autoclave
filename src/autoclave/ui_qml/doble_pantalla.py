# ui_qml/doble_pantalla.py
#
# Lanzador de las dos pantallas QML de un PC con dos monitores (una por puerta):
#   python -m autoclave.ui_qml.doble_pantalla [--monitor-puerta1 0] [--monitor-puerta2 1]
#
# Levanta dos procesos de autoclave.ui_qml.app, uno con --door 1 y otro con
# --door 2, para que la identidad de cada pantalla no dependa de escribir bien
# dos comandos a mano. No arranca el backend (se lanza aparte con
# `python -m autoclave.backend.main`). Ctrl+C cierra las dos pantallas; si una
# se cierra sola, la otra sigue abierta y la cerrada se relanza hasta 3 veces,
# 5 s después de cada cierre (D-04, tanda 2026-10-14 T8). El backend nunca se
# reinicia por eso.

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

from autoclave.ui_qml import barra_tareas

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


RELANZAMIENTOS_MAX = 3
ESPERA_RELANZAR_S = 5.0
# Salida del asistente de instalación al terminar (InstalacionVentana.qml): no
# es una caída, no se relanza ni se cuenta (TMG-02 de T9). W10 (D10-4): la
# pantalla 2 en Reposo de instalación sale con el mismo código al aparecer el
# perfil, así que tampoco cuenta como caída
CODIGO_INSTALACION_TERMINADA = 3


def vigilar_pantallas(cmds, lanzar, relanzamientos=RELANZAMIENTOS_MAX,
                      espera_s=ESPERA_RELANZAR_S, reloj=time.monotonic,
                      dormir=time.sleep, periodo_s=0.5, barra=None) -> None:
    """D-04: lanza cada pantalla y, si una se cierra, la relanza hasta
    `relanzamientos` veces, `espera_s` después de cada cierre. Termina cuando
    todas están cerradas y sin relanzamientos. Ctrl+C cierra todas.

    `barra` (barra_tareas, o None para no tocarla) se oculta en cada vuelta
    mientras haya pantallas y se vuelve a mostrar al terminar."""
    def _lanzar(cmd):
        # TMG-08 de T8: un fallo al lanzar cuenta como cierre, no mata al vigilante
        try:
            return lanzar(cmd)
        except Exception:
            logger.exception("No se pudo lanzar la pantalla: %s", " ".join(cmd[1:]))
            return None

    pantallas = []
    for cmd in cmds:
        logger.info("Lanzando: %s", " ".join(cmd[1:]))
        pantallas.append({"cmd": cmd, "proc": _lanzar(cmd), "usados": 0, "cerrada_en": None})
    try:
        while True:
            if barra is not None:
                barra.ocultar()
            vivas = False
            for p in pantallas:
                codigo = p["proc"].poll() if p["proc"] is not None else 1
                if codigo is None:
                    vivas = True
                    continue
                if codigo == CODIGO_INSTALACION_TERMINADA:
                    if not p.get("terminada"):
                        p["terminada"] = True
                        logger.warning("Instalación terminada: reinicie el equipo para "
                                       "arrancar con el perfil nuevo")
                    continue
                if p["usados"] >= relanzamientos:
                    continue
                vivas = True
                ahora = reloj()
                if p["cerrada_en"] is None:
                    p["cerrada_en"] = ahora
                    logger.warning("Pantalla cerrada (%s); se relanza en %.0f s",
                                   " ".join(p["cmd"][1:]), espera_s)
                elif ahora - p["cerrada_en"] >= espera_s:
                    p["usados"] += 1
                    p["cerrada_en"] = None
                    logger.warning("Relanzando pantalla (%d de %d): %s", p["usados"],
                                   relanzamientos, " ".join(p["cmd"][1:]))
                    p["proc"] = _lanzar(p["cmd"])
            if not vivas:
                return
            dormir(periodo_s)
    except KeyboardInterrupt:
        logger.info("Cerrando las pantallas...")
        for p in pantallas:
            if p["proc"] is not None and p["proc"].poll() is None:
                p["proc"].terminate()
    finally:
        if barra is not None:
            barra.mostrar()


def main(argv=None, popen=subprocess.Popen, barra=barra_tareas) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)
    vigilar_pantallas(comandos(args.monitor_puerta1, args.monitor_puerta2),
                      lambda cmd: popen(cmd, cwd=str(RAIZ_PROYECTO)),
                      relanzamientos=RELANZAMIENTOS_MAX, espera_s=ESPERA_RELANZAR_S, barra=barra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
