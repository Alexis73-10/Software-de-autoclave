import logging

logger = logging.getLogger(__name__)

PRINTER_NAME = "Generic / Text Only"


def print_raw(text: str, printer_name: str = PRINTER_NAME) -> None:
    try:
        import win32print
    except ImportError:
        logger.warning("win32print no disponible — impresión omitida")
        return

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        logger.warning("print_raw: no se pudo abrir impresora '%s': %s", printer_name, exc)
        return

    try:
        win32print.StartDocPrinter(handle, 1, ("Autoclave", None, "RAW"))
        try:
            win32print.WritePrinter(handle, text.encode("cp437", errors="replace"))
        finally:
            win32print.EndDocPrinter(handle)
    except Exception as exc:
        logger.warning("print_raw: error al enviar datos: %s", exc)
    finally:
        win32print.ClosePrinter(handle)
