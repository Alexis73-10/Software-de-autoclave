# autoclave/devices/printer/arranque_equipo.py
#
# Latido de apagado y ticket de arranque del equipo (R1, tanda 2). Antes los
# hacía solo la ventana principal de la UI anterior (retirada en R1); pasan al
# backend, que es el proceso de
# larga vida con cualquier lanzador (ui_qml/lanzar.py o el ejecutable único) y
# hay uno solo por equipo, así que no se duplican.
#
# - heartbeat.write_timestamp cada 30 s en data/last_shutdown.json: el ticket
#   del siguiente arranque informa la hora aproximada del último apagado.
# - Ticket de arranque: modelo, serie, versión, encendido/apagado y estado del
#   backend y de la tarjeta (espera hasta 15 s a que la tarjeta tenga datos).
# Tiempos de espera con time.monotonic(); las horas del ticket son de pared.

import logging
import threading
import time
from datetime import datetime

from autoclave.devices.printer import heartbeat

logger = logging.getLogger(__name__)

URL_ESTADO = "http://127.0.0.1:8000/status"
PLAZO_TARJETA_S = 15.0
_INTERVALO_S = 0.5


def _version() -> str:
    # VER-03/VER-05: fuente única, con el commit de la compilación
    from autoclave._version import version_completa
    return version_completa()


def _consultar_estado() -> dict | None:
    import requests
    r = requests.get(URL_ESTADO, timeout=1)
    return r.json() if r.status_code == 200 else None


def _imprimir(texto: str) -> bool:
    from autoclave.devices.printer.win32_printer import print_startup
    return print_startup(texto)


def imprimir_ticket(perfil, ultimo_apagado, encendido, consultar_estado=_consultar_estado,
                    imprimir=_imprimir, dormir=time.sleep, plazo_s: float = PLAZO_TARJETA_S,
                    version: str | None = None, reloj=time.monotonic) -> None:
    from autoclave.devices.printer.startup_ticket import FALLO, OK, SIN_DATOS, format_startup_ticket
    # I18N-18: estados como código; el rótulo se pone al imprimir
    backend, tarjeta = FALLO, FALLO
    limite = reloj() + plazo_s
    while reloj() < limite:
        try:
            estado = consultar_estado()
        except Exception:
            estado = None
        if estado is None:
            backend, tarjeta = FALLO, FALLO
        else:
            backend = OK
            if estado.get("card_connected"):
                tarjeta = OK
                break
            tarjeta = SIN_DATOS
        dormir(_INTERVALO_S)
    texto = format_startup_ticket(perfil, version or _version(), ultimo_apagado, encendido,
                                  [("backend", backend), ("tarjeta", tarjeta)])
    try:
        ok = imprimir(texto)
    except Exception as exc:
        logger.warning("Ticket de arranque: error al imprimir: %s", exc)
        return
    if ok:
        logger.info("Ticket de arranque enviado a impresora")
    else:
        logger.warning("Ticket de arranque: la impresión falló")


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, name="ticket-arranque", daemon=True).start()


def iniciar(perfil, leer_ultimo=heartbeat.read_last_shutdown,
            arrancar_latido=lambda: heartbeat.start(interval=30), lanzar=_en_hilo) -> None:
    """Lee el último apagado ANTES de que el latido lo pise, arranca el latido
    e imprime el ticket en segundo plano. Sin perfil (asistente de
    instalación pendiente) no imprime."""
    ultimo = leer_ultimo()
    arrancar_latido()
    if perfil is None:
        logger.info("Sin perfil de instalación: no se imprime el ticket de arranque")
        return
    encendido = datetime.now()
    lanzar(lambda: imprimir_ticket(perfil, ultimo, encendido))
