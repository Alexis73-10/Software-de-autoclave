# src/autoclave/installation/activation.py
import hmac
import hashlib
import base64

_SECRET = b"EspecifikaAutoclave\xf3\x9a\x11\x2c\x87\xde"

def generate_code(serial_number: str) -> str:
    """Return a 12-char uppercase activation code for the given serial number."""
    key = serial_number.strip().upper().encode()
    digest = hmac.new(_SECRET, key, hashlib.sha256).digest()
    return base64.b32encode(digest)[:12].decode()

def validate_code(serial_number: str, code: str) -> bool:
    """Return True if code is the valid activation code for serial_number."""
    expected = generate_code(serial_number)
    return hmac.compare_digest(expected, code.strip().upper()[:12])
