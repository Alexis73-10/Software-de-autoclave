import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PRINTER_NAME = "Impresora_Termica"
_LOGO_PATH = Path(__file__).resolve().parents[2] / "images" / "Logo_Especifika.jpg"


def print_startup(text: str, printer_name: str = PRINTER_NAME) -> bool:
    """Imprime logo centrado seguido del texto del ticket en un solo trabajo."""
    try:
        from escpos.printer import Win32Raw
    except ImportError:
        logger.warning("python-escpos no disponible — usando impresión solo texto")
        return print_raw(text, printer_name)

    try:
        p = Win32Raw(printer_name, profile="TM-T88III")
    except Exception as exc:
        logger.warning("print_startup: no se pudo abrir impresora '%s': %s", printer_name, exc)
        return False

    try:
        if _LOGO_PATH.exists():
            from PIL import Image
            img = Image.open(_LOGO_PATH)
            w, h = img.size
            img = img.resize((int(w * 1.12), int(h * 1.12)), Image.LANCZOS)
            p.set(align="center")
            p.image(img, high_density_horizontal=True, high_density_vertical=True)
            p.set(align="left")
        p.text(text)
        return True
    except Exception as exc:
        logger.warning("print_startup: error al imprimir: %s", exc)
        return False
    finally:
        try:
            p.close()
        except Exception:
            pass


def print_raw(text: str, printer_name: str = PRINTER_NAME) -> bool:
    try:
        import win32print
    except ImportError:
        logger.warning("win32print no disponible — impresión omitida")
        return False

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        logger.warning("print_raw: no se pudo abrir impresora '%s': %s", printer_name, exc)
        return False

    try:
        win32print.StartDocPrinter(handle, 1, ("Autoclave", None, "RAW"))
        try:
            win32print.WritePrinter(handle, text.encode("cp437", errors="replace"))
        finally:
            win32print.EndDocPrinter(handle)
        return True
    except Exception as exc:
        logger.warning("print_raw: error al enviar datos: %s", exc)
        return False
    finally:
        win32print.ClosePrinter(handle)
