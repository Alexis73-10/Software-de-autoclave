# autoclave/estacion/primer_cuadro.py
#
# EST-07 (tanda 17, DECISIÓN SIN CONFIRMAR): señal "la pantalla QML de la
# puerta N ya mostró su primer cuadro", que cierra la cubierta de arranque.
#
# Mecanismo elegido: un EVENTO CON NOMBRE de Win32 por puerta
# (Local\EspecifikaAutoclavePrimerCuadroP1 y ...P2), y no un archivo de señal
# en la carpeta de datos, porque:
#   - no deja nada en disco (un archivo viejo de un arranque anterior podría
#     cerrar la cubierta antes de tiempo, o quedar sin permiso de borrado);
#   - el espacio Local\ es de la sesión: solo lo ven los procesos del
#     operador que corren en el mismo escritorio que la cubierta;
#   - el objeto desaparece cuando se cierran todos sus handles (el lanzador
#     los cierra al cerrar la cubierta).
# La cubierta CREA los eventos (reinicio manual, sin señalar) al abrirse; la
# pantalla QML solo ABRE el existente y lo señala. Si no existe (desarrollo,
# cubierta desactivada o ya cerrada) no hace nada.

import logging
import sys

logger = logging.getLogger(__name__)

PREFIJO_EVENTO = "Local\\EspecifikaAutoclavePrimerCuadroP"


def nombre_evento(puerta: int) -> str:
    return f"{PREFIJO_EVENTO}{int(puerta)}"


def senalar(puerta: int, api=None) -> bool:
    """Señala el evento de la puerta `puerta`. Nunca lanza: True si lo señaló,
    False si no había cubierta esperando o algo falló (queda en el log)."""
    if api is None and sys.platform != "win32":
        return False
    try:
        if api is None:
            from autoclave.estacion import _win32
            api = _win32.api()
            permiso = _win32.EVENT_MODIFY_STATE
        else:
            permiso = 0x0002
        h = api.OpenEventW(permiso, False, nombre_evento(puerta))
        if not h:
            return False   # sin cubierta esperando: normal en desarrollo
        try:
            return bool(api.SetEvent(h))
        finally:
            api.CloseHandle(h)
    except Exception:
        logger.exception("No se pudo avisar el primer cuadro de la puerta %s a la cubierta", puerta)
        return False
