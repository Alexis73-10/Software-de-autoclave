# ui_pyside/services/auth_backend.py
#
# Inicio y cierre de sesión de la UI PySide contra el backend (C1, tanda 3).
# Antes el login PySide comparaba un SHA-256 con la base de datos, pero las
# contraseñas están guardadas con PBKDF2 desde la etapa 1 de autenticación: el
# menú de ajustes no admitía a nadie y, aunque lo hiciera, no obtenía token.
# Ahora se autentica con POST /auth/login (mismo bloqueo por intentos y mismo
# 401 genérico del backend) y se guarda el token en SessionManager.

import logging
from dataclasses import dataclass

import requests

from autoclave.cliente.session_manager import SessionManager

logger = logging.getLogger(__name__)

BACKEND_URL = "http://127.0.0.1:8000"

OK = "ok"
CREDENCIALES = "credenciales"
BLOQUEADO = "bloqueado"
SIN_BD = "sin_bd"
SIN_CONEXION = "sin_conexion"
CAMBIO_CLAVE = "cambio_clave"
ERROR = "error"


@dataclass(frozen=True)
class ResultadoLogin:
    estado: str
    segundos: int = 0
    nombre: str = ""


def iniciar_sesion(usuario: str, clave: str, url: str = BACKEND_URL, post=requests.post) -> ResultadoLogin:
    if SessionManager.token():
        cerrar_sesion(url, post=post)      # SAF-02: nunca deja un token anterior vivo
    try:
        r = post(f"{url}/auth/login", json={"usuario": usuario, "clave": clave}, timeout=5)
    except requests.RequestException as e:
        logger.warning("Login PySide: sin respuesta del backend (%s)", e)
        return ResultadoLogin(SIN_CONEXION)
    if r.status_code == 200:
        try:
            datos = r.json()
            token = datos["token"]
            usuario_ok = {"nombre": datos.get("nombre") or datos["usuario"], "usuario": datos["usuario"],
                          "rol": datos["rol"], "debe_cambiar_clave": bool(datos.get("debe_cambiar_clave"))}
        except (ValueError, KeyError):
            return ResultadoLogin(ERROR)
        if usuario_ok["debe_cambiar_clave"]:
            # el cambio de contraseña obligatorio solo existe en la UI principal:
            # no se deja una sesión a medias con token en esta ventana
            cerrar_sesion(url, token=token)
            return ResultadoLogin(CAMBIO_CLAVE, nombre=usuario_ok["nombre"])
        SessionManager.login(usuario_ok, token)
        return ResultadoLogin(OK, nombre=usuario_ok["nombre"])
    if r.status_code == 401:
        return ResultadoLogin(CREDENCIALES)
    if r.status_code == 429:
        try:
            segundos = int(r.json().get("segundos_restantes", 0))
        except (ValueError, AttributeError):
            segundos = 0
        return ResultadoLogin(BLOQUEADO, segundos=segundos)
    if r.status_code == 503:
        return ResultadoLogin(SIN_BD)
    return ResultadoLogin(ERROR)


def cerrar_sesion(url: str = BACKEND_URL, token: str | None = None, post=requests.post) -> None:
    """Invalida el token en el backend (mejor esfuerzo) y limpia la sesión local."""
    token = token or SessionManager.token()
    if token:
        for intento in (1, 2):             # SAF-05: un reintento
            try:
                post(f"{url}/auth/logout", headers={"Authorization": f"Bearer {token}"}, timeout=3)
                break
            except requests.RequestException as e:
                logger.warning("Logout PySide: el backend no respondió (intento %d): %s", intento, e)
    SessionManager.logout()
