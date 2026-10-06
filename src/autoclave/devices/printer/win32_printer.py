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


# Estado que reporta el controlador a Windows (winspool.h). Un trabajo RAW se
# acepta en la cola aunque la impresora esté desconectada, así que se consulta
# antes de reimprimir para avisar en vez de dejar tickets atascados en la cola.
_ATRIBUTO_SIN_CONEXION = 0x400          # PRINTER_ATTRIBUTE_WORK_OFFLINE (USB desenchufada)
_ESTADO_DESCONECTADA = 0x80 | 0x1000    # PRINTER_STATUS_OFFLINE | NOT_AVAILABLE
_ESTADO_SIN_PAPEL = 0x10                # PRINTER_STATUS_PAPER_OUT
_ESTADO_ERROR = (0x01 | 0x02 | 0x08     # PAUSED | ERROR | PAPER_JAM
                 | 0x100000 | 0x400000)  # USER_INTERVENTION | DOOR_OPEN


def estado_impresora(printer_name: str = PRINTER_NAME) -> str:
    """"lista", "no_instalada", "desconectada", "sin_papel" o "error". Solo
    detecta lo que el controlador informa a Windows."""
    try:
        import win32print
    except ImportError:
        return "no_instalada"
    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        logger.warning("estado_impresora: no se pudo abrir '%s': %s", printer_name, exc)
        return "no_instalada"
    try:
        info = win32print.GetPrinter(handle, 2)
    except Exception as exc:
        logger.warning("estado_impresora: no se pudo consultar '%s': %s", printer_name, exc)
        return "error"
    finally:
        win32print.ClosePrinter(handle)

    status, atributos = info.get("Status", 0), info.get("Attributes", 0)
    if atributos & _ATRIBUTO_SIN_CONEXION or status & _ESTADO_DESCONECTADA:
        return "desconectada"
    if status & _ESTADO_SIN_PAPEL:
        return "sin_papel"
    if status & _ESTADO_ERROR:
        return "error"
    return "lista"
