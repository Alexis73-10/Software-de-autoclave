# Tanda 26, H3 de la revisión ARQ: ControlLoop sin `arranque_liberado` nace
# RETENIDO (falla cerrada). Las pruebas que necesitan el lazo actuando como
# antes de la tanda 26 le pasan este evento ya fijado.

import threading


def evento_liberado() -> threading.Event:
    """Evento de liberación del arranque ya fijado (control liberado)."""
    ev = threading.Event()
    ev.set()
    return ev
