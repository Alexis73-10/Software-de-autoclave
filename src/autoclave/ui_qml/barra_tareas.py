# ui_qml/barra_tareas.py
#
# Oculta la barra de tareas de Windows mientras corren las pantallas QML y la
# devuelve al terminar. Con dos pantallas (dos procesos) solo una ventana puede
# estar en primer plano, y Windows solo esconde la barra del monitor cuya
# ventana a pantalla completa está en primer plano: la del otro monitor queda
# encima de la UI, y además parpadea en naranja cuando a esa ventana se le niega
# el foco. Ni WindowStaysOnTopHint ni Qt.Tool lo evitan (probado 2026-10-19).
#
# Fuera de Windows no hace nada.

import ctypes
import functools
import logging
import sys

logger = logging.getLogger(__name__)

# barra del monitor principal y las de los demás monitores
_CLASES = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
_SW_HIDE = 0
_SW_SHOWNA = 8


@functools.cache
def _user32():
    if sys.platform != "win32":
        return None
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowExW.argtypes = (wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.FindWindowExW.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    return user32


def _barras(user32) -> list:
    hwnds = []
    for clase in _CLASES:
        h = user32.FindWindowExW(None, None, clase, None)
        while h:
            hwnds.append(h)
            h = user32.FindWindowExW(None, h, clase, None)
    return hwnds


def ocultar() -> None:
    """Oculta las barras visibles. Se llama en cada vuelta del vigilante:
    Explorer las vuelve a mostrar si se reinicia o cambia la configuración
    de monitores."""
    try:
        user32 = _user32()
        if user32 is None:
            return
        for h in _barras(user32):
            if user32.IsWindowVisible(h):
                user32.ShowWindow(h, _SW_HIDE)
    except Exception:
        logger.exception("No se pudo ocultar la barra de tareas")


def mostrar() -> None:
    try:
        user32 = _user32()
        if user32 is None:
            return
        for h in _barras(user32):
            user32.ShowWindow(h, _SW_SHOWNA)
    except Exception:
        logger.exception("No se pudo volver a mostrar la barra de tareas")
