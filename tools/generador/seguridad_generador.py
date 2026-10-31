# tools/generador/seguridad_generador.py
#
# Cuentas, bloqueo por intentos y sesiones del generador (G1, tanda 2).
# - Hash: la misma función que el software usa para sus usuarios
#   (autoclave.backend.contrasenas: PBKDF2-HMAC-SHA256 con sal).
# - Bloqueo temporal tras `intentos_max` fallos seguidos de un usuario.
# - Sesiones en memoria que vencen tras `inactividad_s` sin uso; cierre manual.
# - Primer arranque sin usuarios: admin con contraseña temporal aleatoria,
#   mostrada una vez en la consola y escrita en un archivo local que se borra
#   al cambiarla; el primer ingreso exige cambiarla.
# Tiempos con time.monotonic() (inyectable en pruebas).

import logging
import os
import secrets
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from autoclave.backend.contrasenas import hash_password, simular_verificacion, verificar_password  # noqa: E402

import db as generador_db  # noqa: E402

logger = logging.getLogger(__name__)

ARCHIVO_CLAVE_INICIAL = "CLAVE_INICIAL_ADMIN.txt"
LONGITUD_MINIMA = 10


def clave_temporal() -> str:
    return secrets.token_urlsafe(12)


def validar_clave_nueva(clave: str, confirmacion: str) -> str | None:
    """Motivo del rechazo, o None si es aceptable."""
    if clave != confirmacion:
        return "Las contraseñas no coinciden"
    if len(clave) < LONGITUD_MINIMA:
        return f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres"
    return None


def crear_admin_inicial(datos: Path, iteraciones: int | None = None) -> str | None:
    """Si no hay usuarios: crea `admin` con contraseña temporal, la imprime una
    vez y la deja en `CLAVE_INICIAL_ADMIN.txt`. Devuelve la clave o None."""
    if generador_db.hay_usuarios():
        return None
    clave = clave_temporal()
    kw = {"iteraciones": iteraciones} if iteraciones else {}
    generador_db.crear_usuario("admin", hash_password(clave, **kw), "admin", debe_cambiar=True)
    archivo = datos / ARCHIVO_CLAVE_INICIAL
    archivo.write_text(
        "Generador de códigos — primer arranque\n"
        f"Usuario: admin\nContraseña temporal: {clave}\n"
        "Se pedirá cambiarla en el primer ingreso; este archivo se borra entonces.\n",
        encoding="utf-8")
    print(f"\n*** Primer arranque: usuario 'admin', contraseña temporal: {clave}")
    print(f"*** (también en {archivo}; se borra al cambiarla)\n")
    return clave


class Sesiones:
    def __init__(self, inactividad_s: float, intentos_max: int, bloqueo_s: float,
                 reloj=time.monotonic):
        self._inactividad_s = inactividad_s
        self._intentos_max = intentos_max
        self._bloqueo_s = bloqueo_s
        self._reloj = reloj
        self._lock = threading.Lock()
        self._sesiones: dict[str, list] = {}     # token -> [usuario, último uso]
        self._fallos: dict[str, list] = {}       # usuario -> [fallos, bloqueado_hasta]

    # ── login ────────────────────────────────────────────────────────────
    def bloqueado(self, usuario: str) -> float:
        """Segundos de bloqueo que quedan (0 = no bloqueado)."""
        with self._lock:
            hasta = self._fallos.get(usuario, [0, 0.0])[1]
        return max(0.0, hasta - self._reloj())

    def autenticar(self, usuario: str, clave: str) -> tuple[str | None, str]:
        """(token, "") o (None, motivo)."""
        restante = self.bloqueado(usuario)
        if restante > 0:
            return None, f"Usuario bloqueado por intentos fallidos. Intente en {int(restante // 60) + 1} min"
        fila = generador_db.obtener_usuario(usuario)
        if fila is None:
            simular_verificacion()
            return None, "Usuario o contraseña incorrectos"
        if not verificar_password(clave, fila["hash"]):
            self._registrar_fallo(usuario)
            return None, "Usuario o contraseña incorrectos"
        if not fila["activo"]:
            return None, "Usuario desactivado"
        with self._lock:
            self._fallos.pop(usuario, None)
            token = secrets.token_hex(32)
            self._sesiones[token] = [usuario, self._reloj()]
        return token, ""

    def _registrar_fallo(self, usuario: str) -> None:
        with self._lock:
            fallos, _ = self._fallos.get(usuario, [0, 0.0])
            fallos += 1
            hasta = self._reloj() + self._bloqueo_s if fallos >= self._intentos_max else 0.0
            self._fallos[usuario] = [0 if hasta else fallos, hasta]
        if hasta:
            logger.warning("Generador: usuario %s bloqueado por intentos fallidos", usuario)

    # ── sesión ───────────────────────────────────────────────────────────
    def usuario(self, token: str | None) -> dict | None:
        """Fila del usuario de una sesión vigente (y renueva su uso); None si
        no existe, venció o el usuario fue desactivado."""
        if not token:
            return None
        with self._lock:
            sesion = self._sesiones.get(token)
            if sesion is None:
                return None
            if self._reloj() - sesion[1] >= self._inactividad_s:
                del self._sesiones[token]
                return None
            sesion[1] = self._reloj()
            nombre = sesion[0]
        fila = generador_db.obtener_usuario(nombre)
        if fila is None or not fila["activo"]:
            self.cerrar(token)
            return None
        return fila

    def cerrar(self, token: str | None) -> None:
        with self._lock:
            self._sesiones.pop(token or "", None)

    def cerrar_de(self, usuario: str) -> None:
        """Cierra todas las sesiones de un usuario (desactivado o clave restablecida)."""
        with self._lock:
            for token in [t for t, s in self._sesiones.items() if s[0] == usuario]:
                del self._sesiones[token]
