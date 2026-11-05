# autoclave/backend/arranque/retencion.py
#
# Tanda 26 (ARQ): el backend no actúa hasta que la UI termina el arranque.
#
# - ARQ-D1: ninguna etapa corre hasta POST /arranque/iniciar (lo envía la
#   pantalla de la puerta 1 cuando su ventana ya se ve y la intro empezó).
# - ARQ-D2/D3: desde la etapa 7 el ControlLoop existe pero queda RETENIDO
#   (un solo punto, ControlLoop._tick, con el threading.Event
#   BackendContext.arranque_liberado) hasta que (a) las etapas terminaron sin
#   fallo bloqueante y (b) llegó POST /arranque/interfaz-lista.
# - ARQ-D4: sin aviso de la UI se espera sin tope, todo apagado; a los
#   PLAZO_SIN_INTERFAZ_S se anota ARR_SIN_INTERFAZ (informativo).
# - ARQ-D7 (DECISIÓN SIN CONFIRMAR): AUTOCLAVE_ESPERA_INTERFAZ=0 desactiva las
#   dos esperas, solo fuera del compilado (sys.frozen); en el compilado se
#   ignora.

import logging
import os
import sys

logger = logging.getLogger(__name__)

VARIABLE_ESPERA = "AUTOCLAVE_ESPERA_INTERFAZ"

# ARQ-D4: DECISIÓN SIN CONFIRMAR (el valor de 60 s)
PLAZO_SIN_INTERFAZ_S = 60.0
ARR_SIN_INTERFAZ = "ARR_SIN_INTERFAZ"

# Rutas que acabarían encendiendo una salida: con el control retenido se
# rechazan (409 arranque_retenido) en vez de quedar como orden diferida que
# se ejecutaría al liberar (server._compuerta_de_arranque).
RUTAS_ACTUADORAS = frozenset({
    ("POST", "/cycle/start"),
    ("POST", "/io/test/enter"),
    ("POST", "/safe-state/confirm"),
    ("POST", "/fault/reset"),
})
PREFIJOS_ACTUADORES = (
    ("POST", "/doors/"),             # /doors/{puerta}/open|close
    ("PATCH", "/io/test/output/"),   # requiere modo prueba; defensa adicional
)


def espera_interfaz_activa(entorno=None, congelado: bool | None = None) -> bool:
    """True si el arranque espera a la UI (ARQ-D1/D3). Fuera del compilado,
    AUTOCLAVE_ESPERA_INTERFAZ=0 la desactiva (desarrollo, simulador y
    pruebas); en el compilado siempre se espera (ARQ-D7)."""
    entorno = os.environ if entorno is None else entorno
    if congelado is None:
        congelado = bool(getattr(sys, "frozen", False))
    valor = str(entorno.get(VARIABLE_ESPERA, "")).strip()
    if congelado:
        if valor == "0":
            logger.warning("%s=0 se ignora en el compilado: el arranque espera a la interfaz",
                           VARIABLE_ESPERA)
        return True
    return valor != "0"


def ruta_actuadora(metodo: str, ruta: str) -> bool:
    metodo = (metodo or "").upper()
    if (metodo, ruta) in RUTAS_ACTUADORAS:
        return True
    return any(metodo == m and ruta.startswith(p) for m, p in PREFIJOS_ACTUADORES)
