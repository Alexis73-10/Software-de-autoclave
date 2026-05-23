import requests


class DoorCommandService:
    def __init__(self, backend_client, source_door: int):
        self.backend = backend_client
        self.source_door = source_door

    def open(self, door_name: str) -> tuple:
        """
        Solicita la apertura de una puerta.
        Retorna (True, "") si el comando fue aceptado,
                (False, motivo) si fue rechazado o hubo un error.
        """
        try:
            self.backend.post(
                f"/doors/{door_name}/open",
                {"source_door": self.source_door},
            )
            return True, ""
        except requests.exceptions.HTTPError as e:
            return False, self._extract_detail(e)
        except Exception:
            return False, "Error de comunicación"

    def close(self, door_name: str) -> tuple:
        """
        Solicita el cierre de una puerta.
        Retorna (True, "") si el comando fue aceptado,
                (False, motivo) si fue rechazado o hubo un error.
        """
        try:
            self.backend.post(
                f"/doors/{door_name}/close",
                {"source_door": self.source_door},
            )
            return True, ""
        except requests.exceptions.HTTPError as e:
            return False, self._extract_detail(e)
        except Exception:
            return False, "Error de comunicación"

    @staticmethod
    def _extract_detail(e: requests.exceptions.HTTPError) -> str:
        """Extrae el campo 'detail' del cuerpo JSON de una respuesta de error HTTP."""
        try:
            body = e.response.json()
            return body.get("detail", str(e))
        except Exception:
            return str(e)
