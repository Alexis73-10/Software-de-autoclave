# BackendClient de la UI PySide (C1, tanda 3): el mismo cliente HTTP, pero con
# el token de la sesión de esta ventana (SessionManager) en cada petición. El
# backend exige token y rol en calibración, modo prueba y salidas; sin token
# esas operaciones responden 401 y no se ejecutan.

from autoclave.cliente.backend_client import BackendClient as _BackendClientBase
from autoclave.cliente.session_manager import SessionManager


class BackendClient(_BackendClientBase):
    def __init__(self, base_url: str):
        super().__init__(base_url, token_provider=SessionManager.token)


__all__ = ["BackendClient"]
