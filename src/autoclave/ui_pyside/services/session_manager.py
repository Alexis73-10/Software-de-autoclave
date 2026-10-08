import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class SessionManager:
    """Sesión de este proceso (una por ventana QML). Solo en memoria.

    El token del backend se guarda aparte del dict de current_user(): así ni
    el dict, ni su repr, ni un log que lo imprima lo contienen
    (plan_t8_login_qml.md §3.1). Se lee con token()."""
    _current_user: dict | None = None
    _token: str | None = None

    @classmethod
    def login(cls, user_dict: dict, token: str | None = None) -> None:
        cls._current_user = {
            "id":      user_dict.get("id"),   # /auth/login no lo devuelve; nadie lo usa
            "nombre":  user_dict["nombre"],
            "usuario": user_dict["usuario"],
            "rol":     user_dict["rol"],
            "debe_cambiar_clave": bool(user_dict.get("debe_cambiar_clave")),
        }
        # token del backend (POST /auth/login); None si el login fue local (PySide)
        cls._token = token if token is not None else user_dict.get("token")

    @classmethod
    def logout(cls) -> None:
        cls._current_user = None
        cls._token = None

    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None

    @classmethod
    def current_role(cls) -> str | None:
        return cls._current_user["rol"] if cls._current_user else None

    @classmethod
    def current_user(cls) -> dict | None:
        return cls._current_user

    @classmethod
    def token(cls) -> str | None:
        return cls._token

    @classmethod
    def debe_cambiar_clave(cls) -> bool:
        return bool(cls._current_user and cls._current_user["debe_cambiar_clave"])

    @classmethod
    def clave_cambiada(cls) -> None:
        if cls._current_user is not None:
            cls._current_user = {**cls._current_user, "debe_cambiar_clave": False}
