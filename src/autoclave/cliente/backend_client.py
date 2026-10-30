# autoclave/ui/services/backend_client.py

import requests


class BackendClient:
    def __init__(self, base_url: str, token_provider=None):
        """`token_provider`: callable sin argumentos que devuelve el token de la
        sesión (o None). Solo la UI PySide lo usa (C1, tanda 3): el backend exige
        el token y el rol en calibración, modo prueba y salidas. Sin proveedor
        no se envía ninguna cabecera (comportamiento anterior)."""
        self.base_url = base_url.rstrip("/")
        self._token_provider = token_provider

    def _con_token(self, kwargs: dict) -> dict:
        if self._token_provider is None:
            return kwargs
        token = self._token_provider()
        if not token:
            return kwargs
        cabeceras = dict(kwargs.get("headers") or {})
        cabeceras["Authorization"] = f"Bearer {token}"
        return {**kwargs, "headers": cabeceras}

    # ------------------------------------------------------------------
    # Métodos nombrados (retrocompatibilidad)
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return self.get("/status")

    def get_config(self) -> dict:
        return self.get("/global_params")

    def get_cycle(self) -> dict:
        return self.get("/cycle")

    def get_calibration(self, tipo: str, sensor: str) -> dict:
        return self.get(f"/calibration/{tipo}/{sensor}")

    def save_calibration(self, tipo: str, sensor: str, body: dict) -> dict:
        return self.patch(f"/calibration/{tipo}/{sensor}", body)

    # ------------------------------------------------------------------
    # Métodos genéricos
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs) -> dict:
        r = requests.get(f"{self.base_url}{path}", timeout=0.8, **self._con_token(kwargs))
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None, timeout: float = 0.8,
             **kwargs) -> dict:
        r = requests.post(
            f"{self.base_url}{path}",
            json=body or {},
            timeout=timeout,
            **self._con_token(kwargs),
        )
        r.raise_for_status()
        return r.json()

    def patch(self, path: str, body: dict | None = None, **kwargs) -> dict:
        r = requests.patch(
            f"{self.base_url}{path}",
            json=body or {},
            timeout=0.8,
            **self._con_token(kwargs),
        )
        r.raise_for_status()
        return r.json()
