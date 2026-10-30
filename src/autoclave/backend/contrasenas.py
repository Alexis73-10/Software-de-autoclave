# autoclave/backend/contrasenas.py
#
# Hash de contraseñas (planeacion_backend_autenticacion.md, decisión 4 y §5.6):
# PBKDF2-HMAC-SHA256, sal aleatoria por usuario, formato
# `pbkdf2$iteraciones$sal$hash` (sal y hash en hex). Un hash que no empiece por
# `pbkdf2$` (p. ej. el SHA-256 sin sal anterior) nunca valida (decisión 27).
#
# Sin dependencias del resto del backend: lo usan el servidor y las pruebas.

import hashlib
import hmac
import secrets

ITERACIONES = 600_000
_PREFIJO = "pbkdf2"
_BYTES_SAL = 16


def _derivar(password: str, sal: bytes, iteraciones: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, iteraciones)


def hash_password(password: str, iteraciones: int = ITERACIONES) -> str:
    """Devuelve `pbkdf2$iteraciones$sal$hash`. `iteraciones` solo se baja en
    pruebas; la verificación lee el valor guardado en el propio hash."""
    sal = secrets.token_bytes(_BYTES_SAL)
    derivado = _derivar(password, sal, iteraciones)
    return f"{_PREFIJO}${iteraciones}${sal.hex()}${derivado.hex()}"


def verificar_password(password: str, guardado: str | None) -> bool:
    """True solo si `guardado` es un hash PBKDF2 bien formado de `password`.
    Comparación en tiempo constante."""
    if not guardado or not isinstance(guardado, str):
        return False
    partes = guardado.split("$")
    if len(partes) != 4 or partes[0] != _PREFIJO:
        return False
    try:
        iteraciones = int(partes[1])
        sal = bytes.fromhex(partes[2])
        esperado = bytes.fromhex(partes[3])
    except ValueError:
        return False
    if iteraciones <= 0 or not sal or not esperado:
        return False
    return hmac.compare_digest(_derivar(password, sal, iteraciones), esperado)


def simular_verificacion() -> None:
    """Gasta el mismo tiempo que una verificación real. Se usa cuando el
    usuario no existe, para no revelar por tiempo de respuesta cuáles existen."""
    _derivar("", b"\x00" * _BYTES_SAL, ITERACIONES)
