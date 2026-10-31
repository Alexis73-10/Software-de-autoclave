import requests


def _error_comunicacion() -> str:
    try:
        from autoclave import i18n
        return i18n.t("puerta.error_comunicacion")
    except Exception:
        return "Error de comunicación"


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
            return False, _error_comunicacion()

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
            return False, _error_comunicacion()

    @staticmethod
    def _extract_detail(e: requests.exceptions.HTTPError) -> str:
        """Extrae el campo 'detail' del cuerpo JSON de una respuesta de error HTTP."""
        try:
            body = e.response.json()
            # I4 (tanda 6): el motivo en el idioma vigente si el backend lo trae
            textos = body.get("motivo_textos")
            if isinstance(textos, dict):
                from autoclave import i18n
                texto = textos.get(i18n.idioma())
                if isinstance(texto, str) and texto:
                    return texto
            return body.get("detail", str(e))
        except Exception:
            return str(e)
