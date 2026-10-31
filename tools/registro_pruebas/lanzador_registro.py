# tools/registro_pruebas/lanzador_registro.py
#
# Punto de entrada de la app de registro de pruebas (F1, tanda 3). Doble clic
# en `iniciar_registro.bat` (o `python lanzador.py`):
#   1. carpeta de datos persistente y config.json (datos_registro.py);
#   2. base en WAL; admin inicial si no hay usuarios (clave temporal aleatoria);
#   3. respaldo al arrancar y cada 6 h;
#   4. si el puerto ya lo usa otra instancia de la app, solo abre el navegador y
#      termina; si lo usa otro programa, avisa y termina (código 2);
#   5. arranca el servidor y muestra la URL para el teléfono.
# NO se compila a ejecutable en esta tanda. Opciones: --sin-navegador (tarea
# programada), --datos <carpeta>.

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

import datos_registro  # noqa: E402
import respaldo_registro  # noqa: E402
import seguridad_registro  # noqa: E402

logger = logging.getLogger("registro_pruebas")


def puerto_en_uso(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def es_la_app(puerto: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/salud", timeout=2) as r:
            return json.loads(r.read().decode("utf-8")).get("app") == "registro-pruebas-especifika"
    except Exception:
        return False


def _abrir_navegador_cuando_responda(puerto: int, plazo_s: float = 20.0) -> None:
    def tarea():
        limite = time.monotonic() + plazo_s
        while time.monotonic() < limite:
            if es_la_app(puerto):
                webbrowser.open(f"http://localhost:{puerto}")
                return
            time.sleep(0.3)
    threading.Thread(target=tarea, name="AbrirNavegador", daemon=True).start()


def _configurar_log(datos: Path) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(datos / "registro_pruebas.log", encoding="utf-8")]
                 + ([logging.StreamHandler()] if sys.stdout else []))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Registro de pruebas de banco (Especifika)")
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--datos", help="carpeta de datos (por defecto ProgramData\\Especifika\\RegistroPruebas)")
    opciones = ap.parse_args(argv)

    datos = Path(opciones.datos) if opciones.datos else datos_registro.carpeta_datos()
    conf = datos_registro.preparar(datos)
    _configurar_log(datos)
    puerto = int(conf["puerto"])

    if puerto_en_uso(puerto):
        if es_la_app(puerto):
            logger.info("Ya hay una instancia en el puerto %d: solo se abre el navegador", puerto)
            if not opciones.sin_navegador:
                webbrowser.open(f"http://localhost:{puerto}")
            return 0
        logger.error("El puerto %d está ocupado por otro programa; cambie 'puerto' en %s",
                     puerto, datos / "config.json")
        print(f"El puerto {puerto} está ocupado por otro programa; cambie 'puerto' en "
              f"{datos / 'config.json'}", file=sys.stderr)
        return 2

    import almacen
    from app_registro import crear_app, ip_local
    alm = almacen.Almacen(datos)
    seguridad_registro.crear_admin_inicial(alm, datos, int(conf.get("iteraciones_hash") or 0))
    respaldo_registro.iniciar_periodico(alm.ruta, datos / "respaldos", int(conf["retencion_respaldos"]))

    import uvicorn
    app = crear_app(datos, conf, almacen=alm)
    mensaje = (f"Registro de pruebas en http://localhost:{puerto} — desde el teléfono (mismo Wi-Fi): "
               f"http://{ip_local()}:{puerto} — datos en {datos}")
    logger.info(mensaje)
    print(mensaje)
    if not opciones.sin_navegador:
        _abrir_navegador_cuando_responda(puerto)
    uvicorn.run(app, host=conf["host"], port=puerto, log_level="warning",
                log_config=None if sys.stdout is None else uvicorn.config.LOGGING_CONFIG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
