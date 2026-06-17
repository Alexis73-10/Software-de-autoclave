import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class SessionManager:
    _current_user: dict | None = None

    @classmethod
    def login(cls, user_dict: dict) -> None:
        cls._current_user = {
            "id":      user_dict["id"],
            "nombre":  user_dict["nombre"],
            "usuario": user_dict["usuario"],
            "rol":     user_dict["rol"],
        }

    @classmethod
    def logout(cls) -> None:
        cls._current_user = None

    @classmethod
    def is_authenticated(cls) -> bool:
        return cls._current_user is not None

    @classmethod
    def current_role(cls) -> str | None:
        return cls._current_user["rol"] if cls._current_user else None

    @classmethod
    def current_user(cls) -> dict | None:
        return cls._current_user
