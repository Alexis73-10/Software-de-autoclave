# tests/backend_doble.py
#
# Utilidades para probar backend/server.py sin hardware: lo importa de nuevo
# con un BackendContext falso (cada importación trae su propio almacén de
# tokens y contadores de intentos) y emite tokens de sesión por rol
# (planeacion_backend_autenticacion.md §5.1-5.2).

import importlib
import sys
from unittest.mock import MagicMock, patch


def cargar_servidor(ctx=None):
    """Importa autoclave.backend.server con `ctx` (MagicMock por defecto) como
    contexto. Devuelve (módulo, ctx)."""
    ctx = ctx if ctx is not None else MagicMock()
    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    return srv, ctx


def cabecera(srv, rol: str = "ingeniero", usuario: str | None = None,
             debe_cambiar_clave: bool = False) -> dict:
    """Emite un token en el almacén del servidor y devuelve la cabecera HTTP."""
    sesion = srv.tokens.emitir(usuario or f"usuario_{rol}", rol.capitalize(), rol,
                               debe_cambiar_clave)
    return {"Authorization": f"Bearer {sesion.token}"}
