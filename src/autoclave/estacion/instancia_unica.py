# autoclave/estacion/instancia_unica.py
#
# V17-s2-01 (revisión R2, tanda 17): un solo lanzador por sesión de Windows.
#
# Antes no había ninguna protección contra un segundo lanzador: si ya había un
# backend respondiendo se usaba ese, pero igual se abrían otras dos pantallas
# QML (con la cubierta de EST-07, retirada en la tanda 18 por EST-08, además
# tapaba las pantallas vivas).
#
# Mutex con nombre de la sesión (Local\EspecifikaAutoclaveLanzador), creado
# con CreateMutexW: si GetLastError() == ERROR_ALREADY_EXISTS hay otro
# lanzador vivo en esta sesión. Basta con que exista el objeto (no se toma la
# propiedad): Windows lo destruye cuando se cierra el último handle, es decir,
# al terminar el lanzador aunque muera sin cerrarlo. El handle no se hereda
# (sin SECURITY_ATTRIBUTES), así que el backend, las pantallas y el lanzador
# relanzado por R11 no lo mantienen vivo.
#
# DECISIÓN SIN CONFIRMAR: si CreateMutexW falla (sin user32/kernel32, error de
# Win32), se sigue como antes (sin protección) y queda en el log: no impedir el
# arranque del equipo por una protección auxiliar.
#
# Activa solo en Windows y, por defecto, solo en el build congelado. AUTOCLAVE_INSTANCIA_UNICA=0 la desactiva y =1 la activa en
# desarrollo. Las pruebas inyectan un doble de la API.

import logging
import os
import sys
import time

logger = logging.getLogger(__name__)

NOMBRE_MUTEX = "Local\\EspecifikaAutoclaveLanzador"
ERROR_ALREADY_EXISTS = 183
VARIABLE_ENTORNO = "AUTOCLAVE_INSTANCIA_UNICA"


def activa(entorno=None, congelado=None, plataforma=None) -> bool:
    entorno = os.environ if entorno is None else entorno
    plataforma = sys.platform if plataforma is None else plataforma
    congelado = bool(getattr(sys, "frozen", False)) if congelado is None else congelado
    if plataforma != "win32":
        return False
    valor = str(entorno.get(VARIABLE_ENTORNO, "")).strip()
    if valor == "0":
        return False
    if valor == "1":
        return True
    return congelado


class _ApiKernel32:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ctypes = ctypes
        self._crear = k.CreateMutexW
        self._crear.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        self._crear.restype = wintypes.HANDLE
        self._cerrar = k.CloseHandle
        self._cerrar.argtypes = (wintypes.HANDLE,)
        self._cerrar.restype = wintypes.BOOL

    def CreateMutexW(self, atributos, propietario, nombre):
        return self._crear(atributos, propietario, nombre)

    def GetLastError(self):
        return self._ctypes.get_last_error()

    def CloseHandle(self, h):
        return self._cerrar(h)


class Instancia:
    """Resultado de tomar(): `primera` False si ya había otro lanzador;
    `error` con el motivo si no se pudo comprobar (se sigue sin protección)."""

    def __init__(self, handle=None, primera=True, error=None, api=None):
        self.handle = handle
        self.primera = primera
        self.error = error
        self._api = api

    def soltar(self) -> None:
        if self.handle and self._api is not None:
            try:
                self._api.CloseHandle(self.handle)
            except Exception:
                logger.exception("No se pudo cerrar el mutex del lanzador")
        self.handle = None


def _intentar(api):
    h = api.CreateMutexW(None, False, NOMBRE_MUTEX)
    ultimo = api.GetLastError()   # justo después de CreateMutexW
    if not h:
        return Instancia(primera=True, error=f"CreateMutexW falló (error {ultimo})", api=api)
    if ultimo == ERROR_ALREADY_EXISTS:
        api.CloseHandle(h)
        return Instancia(primera=False, api=api)
    return Instancia(handle=h, primera=True, api=api)


def tomar(*, esperar_s: float = 0.0, api=None, reloj=time.monotonic, dormir=time.sleep,
          pausa_s: float = 0.25) -> Instancia:
    """Crea el mutex del lanzador. Con `esperar_s` > 0 (relanzamiento R11:
    la instancia anterior está terminando) reintenta hasta ese tope. Nunca
    lanza."""
    try:
        api = api or _ApiKernel32()
        limite = reloj() + max(0.0, float(esperar_s))
        while True:
            inst = _intentar(api)
            if inst.primera or reloj() >= limite:
                return inst
            dormir(pausa_s)
    except Exception as e:
        return Instancia(primera=True, error=f"{type(e).__name__}: {e}")
