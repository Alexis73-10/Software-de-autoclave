import logging
import queue
import threading

from autoclave.devices.printer.win32_printer import PRINTER_NAME, print_raw

logger = logging.getLogger(__name__)


class RealtimePrinter:
    """Imprime líneas de texto en orden, en un hilo dedicado, sin bloquear al llamador."""

    def __init__(self, printer_name: str = PRINTER_NAME):
        self._printer_name = printer_name
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def enqueue(self, text: str) -> None:
        """Encola texto para impresión. No bloquea ni lanza excepciones."""
        self._queue.put(text)

    def _worker(self):
        while True:
            text = self._queue.get()
            try:
                if not print_raw(text, self._printer_name):
                    logger.warning("RealtimePrinter: print_raw devolvió False, línea descartada")
            except Exception as exc:
                logger.warning("RealtimePrinter: error inesperado al imprimir: %s", exc)
            finally:
                self._queue.task_done()
