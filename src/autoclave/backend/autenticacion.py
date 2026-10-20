# autoclave/backend/autenticacion.py
#
# Sesiones y bloqueo por intentos (planeacion_backend_autenticacion.md §5.1,
# §5.6). Todo en memoria: un reinicio del backend invalida los tokens y borra
# los contadores (decisión 2). Sin dependencias del resto del backend.
#
# Los plazos usan time.monotonic(): un ajuste del reloj de pared no debe
# alargar ni acortar un bloqueo. `emitido` es solo un sello de registro.
#
# Caducidad por inactividad (B7, tanda 4): un token sin peticiones autenticadas
# durante PLAZO_TOKEN_BACKEND_S (el plazo de la UI más dos avisos, para que la
# UI cierre primero) deja de valer (401).
# Cada petición autenticada lo renueva. La caducidad solo afecta a las
# peticiones que exigen sesión: el control del ciclo no depende de ella.

import math
import secrets
import threading
import time
from dataclasses import dataclass, field

from autoclave.core.runtime.sesion_inactividad import PLAZO_TOKEN_BACKEND_S

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
    actividad: float = 0.0      # monotónico de la última petición autenticada


class AlmacenTokens:
    """Token aleatorio → sesión. Una sesión por login (una por ventana QML);
    invalidar un token no toca los demás."""

    def __init__(self, reloj=time.monotonic, inactividad_s: float = PLAZO_TOKEN_BACKEND_S):
        self._sesiones: dict[str, Sesion] = {}
        self._lock = threading.Lock()
        self._reloj = reloj
        self._inactividad_s = inactividad_s
        # token -> (usuario, rol) de los últimos emitidos, también tras caducar o
        # cerrar sesión: la bitácora del modo prueba huérfano (B8) debe poder
        # decir a quién se le sacó del modo. Acotado; solo nombres, nunca el token.
        self._quien: dict[str, tuple[str, str]] = {}

    def emitir(self, usuario: str, nombre: str, rol: str, debe_cambiar_clave: bool) -> Sesion:
        sesion = Sesion(secrets.token_urlsafe(32), usuario, nombre, rol, bool(debe_cambiar_clave))
        sesion.actividad = self._reloj()
        with self._lock:
            self._purgar_vencidas()
            self._sesiones[sesion.token] = sesion
            self._quien[sesion.token] = (sesion.usuario, sesion.rol)
            while len(self._quien) > 256:
                del self._quien[next(iter(self._quien))]
        return sesion

    def quien_fue(self, token: str | None) -> tuple[str, str] | None:
        """(usuario, rol) que tuvo el token, aunque ya no esté vigente; None si
        no se conoce."""
        with self._lock:
            return self._quien.get(token) if token else None

    def _vencida(self, sesion: Sesion) -> bool:
        return self._reloj() - sesion.actividad >= self._inactividad_s

    def _purgar_vencidas(self) -> None:
        """Con self._lock tomado."""
        for token in [t for t, s in self._sesiones.items() if self._vencida(s)]:
            del self._sesiones[token]

    def obtener(self, token: str | None, renovar: bool = True) -> Sesion | None:
        """La sesión del token, o None si no existe o caducó por inactividad (se
        borra). `renovar=True` (petición autenticada) reinicia el plazo;
        `renovar=False` es una consulta interna que no cuenta como actividad."""
        if not token:
            return None
        with self._lock:
            sesion = self._sesiones.get(token)
            if sesion is None:
                return None
            if self._vencida(sesion):
                del self._sesiones[token]
                return None
            if renovar:
                sesion.actividad = self._reloj()
            return sesion

    def invalidar(self, token: str) -> Sesion | None:
        """Quita el token; devuelve la sesión que tenía, o None si no existía."""
        with self._lock:
            return self._sesiones.pop(token, None)

    def clave_cambiada(self, token: str) -> None:
        with self._lock:
            sesion = self._sesiones.get(token)
            if sesion is not None:
                sesion.debe_cambiar_clave = False

    def existe(self, token: str | None) -> bool:
        """¿Sigue vigente el token? No cuenta como actividad."""
        return self.obtener(token, renovar=False) is not None


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

    def segundos_restantes(self, usuario: str) -> int:
        """Segundos que faltan para que venza el bloqueo, redondeados hacia
        arriba (mínimo 1 mientras dure); 0 si no está bloqueado."""
        clave = self._clave(usuario)
        with self._lock:
            if not self._bloqueado(clave):
                return 0
            return max(1, math.ceil(self._bloqueado_hasta[clave] - self._reloj()))

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
