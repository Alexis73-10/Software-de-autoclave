# autoclave/backend/autenticacion.py
#
# Sesiones y bloqueo por intentos (planeacion_backend_autenticacion.md §5.1,
# §5.6). Todo en memoria: un reinicio del backend invalida los tokens y borra
# los contadores (decisión 2). Sin dependencias del resto del backend.
#
# Los plazos usan time.monotonic(): un ajuste del reloj de pared no debe
# alargar ni acortar un bloqueo. `emitido` es solo un sello de registro.

import secrets
import threading
import time
from dataclasses import dataclass, field

MAX_INTENTOS = 5
BLOQUEO_S = 5 * 60


@dataclass
class Sesion:
    token: str
    usuario: str
    nombre: str
    rol: str
    debe_cambiar_clave: bool
    emitido: float = field(default_factory=time.time)


class AlmacenTokens:
    """Token aleatorio → sesión. Una sesión por login (una por ventana QML);
    invalidar un token no toca los demás."""

    def __init__(self):
        self._sesiones: dict[str, Sesion] = {}
        self._lock = threading.Lock()

    def emitir(self, usuario: str, nombre: str, rol: str, debe_cambiar_clave: bool) -> Sesion:
        sesion = Sesion(secrets.token_urlsafe(32), usuario, nombre, rol, bool(debe_cambiar_clave))
        with self._lock:
            self._sesiones[sesion.token] = sesion
        return sesion

    def obtener(self, token: str | None) -> Sesion | None:
        if not token:
            return None
        with self._lock:
            return self._sesiones.get(token)

    def invalidar(self, token: str) -> Sesion | None:
        """Quita el token; devuelve la sesión que tenía, o None si no existía."""
        with self._lock:
            return self._sesiones.pop(token, None)

    def clave_cambiada(self, token: str) -> None:
        with self._lock:
            sesion = self._sesiones.get(token)
            if sesion is not None:
                sesion.debe_cambiar_clave = False


class ControlIntentos:
    """Bloqueo de BLOQUEO_S segundos tras MAX_INTENTOS intentos consecutivos sin
    éxito de un mismo usuario (exista o no). La clave no distingue mayúsculas,
    para que variar la capitalización no reinicie el contador.

    El intento se reserva (comprobar y contar) en una sola operación atómica
    ANTES de verificar la contraseña: logins en paralelo no pueden pasar todos
    la comprobación mientras la verificación (lenta a propósito) sigue en curso.
    Un login correcto devuelve el intento con registrar_exito."""

    def __init__(self, max_intentos: int = MAX_INTENTOS, bloqueo_s: float = BLOQUEO_S,
                 reloj=time.monotonic):
        self._max = max_intentos
        self._bloqueo_s = bloqueo_s
        self._reloj = reloj
        self._intentos: dict[str, int] = {}
        self._bloqueado_hasta: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _clave(usuario: str) -> str:
        return usuario.casefold()

    def _bloqueado(self, clave: str) -> bool:
        """Con self._lock tomado. Un bloqueo vencido se borra con su contador."""
        hasta = self._bloqueado_hasta.get(clave)
        if hasta is None:
            return False
        if self._reloj() >= hasta:
            del self._bloqueado_hasta[clave]
            self._intentos.pop(clave, None)
            return False
        return True

    def bloqueado(self, usuario: str) -> bool:
        with self._lock:
            return self._bloqueado(self._clave(usuario))

    def reservar_intento(self, usuario: str) -> bool:
        """False si el usuario está bloqueado. Si no, cuenta el intento como
        fallido de antemano (y bloquea si con él llega a MAX_INTENTOS) y
        devuelve True."""
        clave = self._clave(usuario)
        with self._lock:
            if self._bloqueado(clave):
                return False
            n = self._intentos.get(clave, 0) + 1
            self._intentos[clave] = n
            if n >= self._max:
                self._bloqueado_hasta[clave] = self._reloj() + self._bloqueo_s
            return True

    def registrar_exito(self, usuario: str) -> None:
        clave = self._clave(usuario)
        with self._lock:
            self._intentos.pop(clave, None)
            self._bloqueado_hasta.pop(clave, None)
