# src/autoclave/installation/activation.py
#
# LIC-01 (licencia L0): los secretos NO están en el código. Se cargan, en este
# orden, del recurso empaquetado config/activacion_secretos.json (solo en el
# ejecutable) o del archivo de secretos fuera del repositorio (desarrollo y
# generador; ver installation/secretos.py). Sin secretos falla cerrada: todo
# código se rechaza y se advierte una sola vez. Nunca hay un secreto por
# defecto.
import base64
import hashlib
import hmac
import logging
import sys
import threading
from datetime import date as _date

from autoclave.installation import secretos as _secretos

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cargados: dict[str, bytes] | None = None
_intentado = False
_advertido = False


class SecretosNoDisponibles(RuntimeError):
    """No hay secretos de activación: no se puede generar ningún código."""


def configurar_secretos(instalacion: bytes | None = None,
                        fabrica: bytes | None = None) -> None:
    """SOLO PRUEBAS. Con los dos secretos, los fija; sin argumentos, olvida lo
    cargado (la próxima consulta vuelve a buscar en recurso y archivo)."""
    global _cargados, _intentado, _advertido
    with _lock:
        if instalacion is None and fabrica is None:
            _cargados, _intentado, _advertido = None, False, False
            return
        if not instalacion or not fabrica:
            raise ValueError("configurar_secretos: faltan secretos")
        _cargados, _intentado = {"instalacion": instalacion, "fabrica": fabrica}, True


def _cargar() -> dict[str, bytes] | None:
    if hasattr(sys, "_MEIPASS"):
        from autoclave.utils.resources import resource_path
        try:
            return _secretos.leer_archivo(resource_path(_secretos.RECURSO_EMPAQUETADO))
        except _secretos.SecretosInvalidos:
            pass
    try:
        return _secretos.leer_archivo(_secretos.ruta_archivo_secretos())
    except _secretos.SecretosInvalidos:
        return None


def _obtener() -> dict[str, bytes] | None:
    global _cargados, _intentado, _advertido
    with _lock:
        if not _intentado:
            _cargados, _intentado = _cargar(), True
        if _cargados is None and not _advertido:
            _advertido = True
            logger.warning("compilación sin secretos de activación: se rechaza "
                           "todo código de instalación y clave de fábrica")
        return _cargados


def secretos_disponibles() -> bool:
    return _obtener() is not None


def huella_instalacion() -> str | None:
    """Huella corta (8 hex) del secreto de instalación, o None sin secretos."""
    s = _obtener()
    return _secretos.huella(s["instalacion"]) if s else None


def _secreto(clave: str) -> bytes:
    s = _obtener()
    if s is None:
        raise SecretosNoDisponibles("compilación sin secretos de activación")
    return s[clave]


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
    return _make_code(_secreto("instalacion"), serial, day or _date.today())


def validate_installation_code(serial: str, code: str, day: _date | None = None) -> bool:
    if not secretos_disponibles():
        return False
    expected = generate_installation_code(serial, day)
    return hmac.compare_digest(expected, normalizar_codigo(code)[:12])


def generate_factory_key(serial: str, day: _date | None = None) -> str:
    return _make_code(_secreto("fabrica"), serial, day or _date.today())


def validate_factory_key(serial: str, code: str, day: _date | None = None) -> bool:
    if not secretos_disponibles():
        return False
    expected = generate_factory_key(serial, day)
    return hmac.compare_digest(expected, normalizar_codigo(code)[:12])
