# tools/generador/lanzador.py
#
# Punto de entrada del generador (G1, tanda 2), en desarrollo y en el ejecutable
# GeneradorCodigos.exe (GeneradorCodigos.spec, sin consola):
#   1. carpeta de datos persistente y config.json (datos_generador.py);
#   2. la primera vez COPIA la generador.db heredada (no la mueve);
#   3. base en WAL y migrada; admin inicial si no hay usuarios;
#   4. respaldo al arrancar y cada 24 h;
#   5. si el puerto ya lo usa otra instancia del generador, solo abre el
#      navegador y termina; si lo usa otro programa, avisa y termina;
#   6. arranca el servidor y abre el navegador en http://localhost:<puerto>.
#      Sin archivo de secretos de activación (LIC-01) el generador no arranca:
#      lo dice en el log/consola y el servidor solo sirve la página del motivo.
# Opciones: --sin-navegador (tarea programada al iniciar Windows).

import argparse
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)

import datos_generador  # noqa: E402
import db as generador_db  # noqa: E402
import respaldo_generador  # noqa: E402
import seguridad_generador  # noqa: E402

logger = logging.getLogger("generador")


def puerto_en_uso(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def es_el_generador(puerto: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/salud", timeout=2) as r:
            return json.loads(r.read().decode("utf-8")).get("app") == "generador-especifika"
    except Exception:
        return False


def _abrir_navegador_cuando_responda(puerto: int, plazo_s: float = 20.0) -> None:
    def tarea():
        limite = time.monotonic() + plazo_s
        while time.monotonic() < limite:
            if es_el_generador(puerto):
                webbrowser.open(f"http://localhost:{puerto}")
                return
            time.sleep(0.3)
    threading.Thread(target=tarea, name="AbrirNavegador", daemon=True).start()


def _configurar_log(datos: Path) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(datos / "generador.log", encoding="utf-8")]
                 + ([logging.StreamHandler()] if sys.stdout else []))


def preparar(datos: Path) -> dict:
    """Pasos 1 a 3. Devuelve la configuración."""
    conf = datos_generador.cargar(datos)
    generador_db.DB_PATH = datos_generador.preparar_base(datos)
    generador_db.init_db()
    seguridad_generador.crear_admin_inicial(datos)
    return conf


def main(argv=None) -> int:
    args = argparse.ArgumentParser(description="Generador de códigos (Especifika)")
    args.add_argument("--sin-navegador", action="store_true")
    opciones = args.parse_args(argv)

    datos = datos_generador.carpeta_datos()
    datos.mkdir(parents=True, exist_ok=True)
    _configurar_log(datos)
    conf = datos_generador.cargar(datos)
    puerto = int(conf["puerto"])

    if puerto_en_uso(puerto):
        if es_el_generador(puerto):
            logger.info("Ya hay un generador en el puerto %d: solo se abre el navegador", puerto)
            if not opciones.sin_navegador:
                webbrowser.open(f"http://localhost:{puerto}")
            return 0
        logger.error("El puerto %d está ocupado por otro programa; cambie 'puerto' en %s",
                     puerto, datos / "config.json")
        return 2

    conf = preparar(datos)
    respaldo_generador.iniciar_periodico(generador_db.DB_PATH, datos / "Respaldos",
                                         int(conf["retencion_respaldos"]))

    import uvicorn
    from app import create_app, ip_local, motivo_sin_secretos
    motivo = motivo_sin_secretos()
    if motivo:
        # LIC-01: no arranca; el servidor solo muestra el motivo en la página
        logger.error("El generador no arranca: %s", motivo)
        if sys.stderr:
            print(f"El generador no arranca: {motivo}", file=sys.stderr)
    app = create_app(datos, conf)
    logger.info("Generador en http://localhost:%d (red local: http://%s:%d); datos en %s",
                puerto, ip_local(), puerto, datos)
    if not opciones.sin_navegador:
        _abrir_navegador_cuando_responda(puerto)
    # sin consola (ejecutable windowed) uvicorn no debe tocar sys.stdout/stderr
    uvicorn.run(app, host=conf["host"], port=puerto, log_level="warning",
                log_config=None if sys.stdout is None else uvicorn.config.LOGGING_CONFIG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
