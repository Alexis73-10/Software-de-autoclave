# src/autoclave/installation/activation.py
import hmac
import hashlib
import base64
from datetime import date as _date

_SECRET_INSTALL = b"EspecifikaInstall\xf3\x9a\x11\x2c\x87\xde"
_SECRET_FACTORY = b"EspecifikaFabrica\x7e\x44\xb2\x9f\x13\xcc"

# D10-2.1 (tanda 10): el alfabeto Base32 no usa 0, 1, 8 ni 9, así que estos
# dígitos solo pueden ser una confusión al teclear la letra parecida.
_CONFUSIONES = str.maketrans({"0": "O", "1": "I", "8": "B"})


def normalizar_codigo(code: str) -> str:
    """Único punto de normalización de lo tecleado (código de instalación y
    clave de fábrica): mayúsculas, sin espacios ni guiones, y 0->O, 1->I, 8->B.
    No debilita el código: un código generado nunca contiene esos dígitos."""
    limpio = "".join(c for c in str(code or "") if not c.isspace() and c != "-")
    return limpio.upper().translate(_CONFUSIONES)


def _make_code(secret: bytes, serial: str, day: _date) -> str:
    message = f"{serial.strip().upper()}:{day.isoformat()}".encode()
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    return base64.b32encode(digest)[:12].decode()


def generate_installation_code(serial: str, day: _date | None = None) -> str:
    return _make_code(_SECRET_INSTALL, serial, day or _date.today())


def validate_installation_code(serial: str, code: str, day: _date | None = None) -> bool:
    expected = generate_installation_code(serial, day)
    return hmac.compare_digest(expected, normalizar_codigo(code)[:12])


def generate_factory_key(serial: str, day: _date | None = None) -> str:
    return _make_code(_SECRET_FACTORY, serial, day or _date.today())


def validate_factory_key(serial: str, code: str, day: _date | None = None) -> bool:
    expected = generate_factory_key(serial, day)
    return hmac.compare_digest(expected, normalizar_codigo(code)[:12])
