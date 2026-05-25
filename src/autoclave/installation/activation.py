# src/autoclave/installation/activation.py
import hmac
import hashlib
import base64
from datetime import date as _date

_SECRET_INSTALL = b"EspecifikaInstall\xf3\x9a\x11\x2c\x87\xde"
_SECRET_FACTORY = b"EspecifikaFabrica\x7e\x44\xb2\x9f\x13\xcc"


def _make_code(secret: bytes, serial: str, day: _date) -> str:
    message = f"{serial.strip().upper()}:{day.isoformat()}".encode()
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    return base64.b32encode(digest)[:12].decode()


def generate_installation_code(serial: str, day: _date | None = None) -> str:
    return _make_code(_SECRET_INSTALL, serial, day or _date.today())


def validate_installation_code(serial: str, code: str, day: _date | None = None) -> bool:
    expected = generate_installation_code(serial, day)
    return hmac.compare_digest(expected, code.strip().upper()[:12])


def generate_factory_key(serial: str, day: _date | None = None) -> str:
    return _make_code(_SECRET_FACTORY, serial, day or _date.today())


def validate_factory_key(serial: str, code: str, day: _date | None = None) -> bool:
    expected = generate_factory_key(serial, day)
    return hmac.compare_digest(expected, code.strip().upper()[:12])
