# autoclave/backend/rutas/arranque.py
#
# Tanda 26 (ARQ-D1): POST /arranque/iniciar. El backend abre el puerto y
# espera: ninguna etapa de arranque corre hasta que la UI (la pantalla de la
# puerta 1, con su ventana ya visible y la intro empezada) lo pide. Sin token
# (como GET /arranque y POST /arranque/interfaz-lista, en
# server._RUTAS_SIN_COMPUERTA) e idempotente: un reintento o un segundo aviso
# no lanzan otra secuencia. GET /arranque y POST /arranque/interfaz-lista
# siguen en rutas/sistema.py.
#
# rutas/* nunca importa server: server.py fija el iniciador al registrar el router.

import logging

from fastapi import APIRouter

from autoclave.backend.dependencias import RechazoApi, registro_arranque

logger = logging.getLogger("autoclave.backend.server")

router = APIRouter()

_iniciador = None


def fijar_iniciador(funcion) -> None:
    """server.py: la función que lanza la secuencia (server.iniciar_arranque)."""
    global _iniciador
    _iniciador = funcion


@router.post("/arranque/iniciar")
def post_arranque_iniciar():
    """La UI ya se ve: corren las etapas de arranque (ARQ-D1). Idempotente."""
    if _iniciador is None:
        raise RechazoApi(503, "arranque_no_disponible", "Arranque no disponible")
    _iniciador()
    return {"ok": True, "instancia": registro_arranque.instancia}
