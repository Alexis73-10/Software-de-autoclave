# autoclave/backend/reinicio.py
#
# R8 (tanda 8, D8-5.12; R-03): reinicio del backend para aplicar una
# reasignación de E/S. La asignación solo se aplica al arrancar (nunca en
# caliente), así que aplicarla es reiniciar el proceso del backend.
#
# - En el backend: backend/main.py registra cómo detener uvicorn (should_exit).
#   `solicitar()` lo hace tras un breve retraso (para que la respuesta HTTP
#   llegue a la UI). El apagado pasa por el lifespan de server.py: detiene el
#   ControlLoop y apaga todas las salidas. Al volver de servidor.run(), main()
#   termina con CODIGO_REINICIO.
# - En el lanzador del ejecutable único (exe_unico._lanzador):
#   `vigilar_reinicios` relanza el backend cuando termina con CODIGO_REINICIO.
#   Cualquier otro final no se relanza (comportamiento de siempre).
# - Sin lanzador (desarrollo, `python -m autoclave.backend.main`) el backend
#   termina y hay que arrancarlo de nuevo a mano.
#
# R11 (tanda 11, D11-1): `reiniciar_software` (server.py) usa el mismo
# mecanismo con CODIGO_REINICIO_SOFTWARE: el lanzador NO relanza solo el
# backend sino que cierra las pantallas y vuelve a abrir Autoclave.exe entero
# (exe_unico.relanzar_software).

import logging
import threading
import time

logger = logging.getLogger(__name__)

CODIGO_REINICIO = 75
# R11: reinicio del software completo (backend y pantallas)
CODIGO_REINICIO_SOFTWARE = 76
# El lanzador la pone en "1" al backend cuyo código de salida vigila
VARIABLE_RELANZABLE = "AUTOCLAVE_RELANZABLE"

_lock = threading.Lock()
_al_reiniciar = None
_solicitado = threading.Event()
_codigo = CODIGO_REINICIO


def registrar(funcion) -> None:
    """`funcion()` detiene el servidor (la registra backend/main.py)."""
    global _al_reiniciar, _codigo
    with _lock:
        _al_reiniciar = funcion
        _codigo = CODIGO_REINICIO
        _solicitado.clear()


def disponible() -> bool:
    return _al_reiniciar is not None


def solicitado() -> bool:
    return _solicitado.is_set()


def codigo_salida() -> int:
    """Código con el que debe terminar el backend tras un reinicio pedido."""
    return _codigo


def solicitar(motivo: str, retraso_s: float = 1.0, dormir=time.sleep,
              codigo: int = CODIGO_REINICIO) -> bool:
    """Pide el reinicio. False si este proceso no sabe reiniciarse (sin
    backend/main.py, p. ej. en pruebas): quien llama lo informa. `codigo`:
    CODIGO_REINICIO (solo el backend, R8) o CODIGO_REINICIO_SOFTWARE (R11)."""
    global _codigo
    with _lock:
        funcion = _al_reiniciar
        if funcion is None:
            logger.warning("Reinicio del backend pedido (%s) sin mecanismo registrado", motivo)
            return False
        _codigo = codigo
        _solicitado.set()
    logger.warning("Reinicio del backend (código %d): %s", codigo, motivo)

    def detener():
        dormir(retraso_s)
        try:
            funcion()
        except Exception:
            logger.exception("No se pudo detener el backend para reiniciarlo")
    threading.Thread(target=detener, name="reinicio-backend", daemon=True).start()
    return True


def vigilar_reinicios(obtener_proceso, relanzar, detener: threading.Event,
                      pausa_s: float = 0.5, log=logger, al_reiniciar_software=None) -> None:
    """Lanzador: relanza el backend cada vez que termina con CODIGO_REINICIO.
    Con CODIGO_REINICIO_SOFTWARE (R11) llama a `al_reiniciar_software` (el
    lanzador cierra las pantallas y se relanza entero) y sale. Sale también
    si termina con otro código o al activarse `detener`."""
    while not detener.is_set():
        proc = obtener_proceso()
        codigo = proc.poll() if proc is not None else None
        if codigo == CODIGO_REINICIO:
            log.warning("El backend pidió reiniciarse: se relanza")
            relanzar()
        elif codigo == CODIGO_REINICIO_SOFTWARE:
            log.warning("El backend pidió reiniciar el software: se cierran las pantallas "
                        "y se vuelve a abrir Autoclave")
            if al_reiniciar_software is not None:
                al_reiniciar_software()
            return
        elif codigo is not None:
            log.warning("El backend terminó con código %s: no se relanza", codigo)
            return
        detener.wait(pausa_s)
