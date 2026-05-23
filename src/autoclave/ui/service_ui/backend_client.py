# autoclave/ui/services/backend_client.py

import requests


class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Métodos nombrados (retrocompatibilidad)
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return self.get("/status")

    def get_config(self) -> dict:
        return self.get("/global_params")

    def get_cycle(self) -> dict:
        return self.get("/cycle")

    # ------------------------------------------------------------------
    # Métodos genéricos
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs) -> dict:
        r = requests.get(f"{self.base_url}{path}", timeout=0.8, **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None, **kwargs) -> dict:
        r = requests.post(
            f"{self.base_url}{path}",
            json=body or {},
            timeout=0.8,
            **kwargs,
        )
        r.raise_for_status()
        return r.json()
