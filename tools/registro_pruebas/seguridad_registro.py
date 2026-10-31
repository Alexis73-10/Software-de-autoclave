# tools/registro_pruebas/seguridad_registro.py
#
# Cuentas, bloqueo por intentos y sesiones de la app de registro de pruebas
# (F1, tanda 3). Mismo esquema que el generador (G1): hash PBKDF2 del software,
# bloqueo temporal tras `intentos_max` fallos, primer arranque con un admin de
# contraseña temporal aleatoria (sin credenciales por defecto). La diferencia:
# la sesión es LARGA (8 a 12 h, configurable) porque la campaña se hace en una
# jornada. Tiempos con time.monotonic() (inyectable en pruebas).

import logging
import os
import secrets
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from autoclave.backend.contrasenas import hash_password, simular_verificacion, verificar_password  # noqa: E402

logger = logging.getLogger(__name__)

ARCHIVO_CLAVE_INICIAL = "CLAVE_INICIAL_ADMIN.txt"
LONGITUD_MINIMA = 10


def hashear(clave: str, iteraciones: int = 0) -> str:
    return hash_password(clave, **({"iteraciones": iteraciones} if iteraciones else {}))


def clave_temporal() -> str:
    return secrets.token_urlsafe(12)


def validar_clave_nueva(clave: str, confirmacion: str) -> str | None:
    if clave != confirmacion:
        return "Las contraseñas no coinciden"
    if len(clave) < LONGITUD_MINIMA:
        return f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres"
    return None


def crear_admin_inicial(almacen, datos: Path, iteraciones: int = 0) -> str | None:
    """Sin usuarios: crea `admin` con contraseña temporal, la imprime una vez y
    la deja en CLAVE_INICIAL_ADMIN.txt (se borra al cambiarla)."""
    if almacen.hay_usuarios():
        return None
    clave = clave_temporal()
    almacen.crear_usuario("admin", "Administrador", hashear(clave, iteraciones), "admin", debe_cambiar=True)
    archivo = datos / ARCHIVO_CLAVE_INICIAL
    archivo.write_text(
        "Registro de pruebas de banco — primer arranque\n"
        f"Usuario: admin\nContraseña temporal: {clave}\n"
        "Se pedirá cambiarla en el primer ingreso; este archivo se borra entonces.\n", encoding="utf-8")
    print(f"\n*** Primer arranque: usuario 'admin', contraseña temporal: {clave}")
    print(f"*** (también en {archivo}; se borra al cambiarla)\n")
    return clave


class Sesiones:
    def __init__(self, almacen, duracion_s: float, intentos_max: int, bloqueo_s: float,
                 reloj=time.monotonic):
        self._almacen = almacen
        self._duracion_s = duracion_s
        self._intentos_max = intentos_max
        self._bloqueo_s = bloqueo_s
        self._reloj = reloj
        self._lock = threading.Lock()
        self._sesiones: dict[str, list] = {}     # token -> [usuario, vence]
        self._fallos: dict[str, list] = {}       # usuario -> [fallos, bloqueado_hasta]

    def bloqueado(self, usuario: str) -> float:
        with self._lock:
            hasta = self._fallos.get(usuario, [0, 0.0])[1]
        return max(0.0, hasta - self._reloj())

    def autenticar(self, usuario: str, clave: str) -> tuple[str | None, str]:
        """(token, "") o (None, motivo). El motivo no distingue usuario inexistente."""
        restante = self.bloqueado(usuario)
        if restante > 0:
            return None, f"Usuario bloqueado por intentos fallidos. Intente en {int(restante // 60) + 1} min"
        fila = self._almacen.usuario(usuario)
        if fila is None:
            simular_verificacion()
            self._registrar_fallo(usuario)       # también cuentan los usuarios inexistentes
            return None, "Usuario o contraseña incorrectos"
        if not verificar_password(clave, fila["hash"]):
            self._registrar_fallo(usuario)
            return None, "Usuario o contraseña incorrectos"
        if not fila["activo"]:
            return None, "Usuario desactivado"
        with self._lock:
            self._fallos.pop(usuario, None)
            token = secrets.token_hex(32)
            self._sesiones[token] = [usuario, self._reloj() + self._duracion_s]
        return token, ""

    def verificar_clave(self, usuario: str, clave: str) -> bool:
        """Comprobación de la contraseña actual (cambio de clave). Los fallos
        cuentan para el bloqueo, como en el login."""
        if self.bloqueado(usuario) > 0:
            return False
        fila = self._almacen.usuario(usuario)
        if fila is None or not verificar_password(clave, fila["hash"]):
            self._registrar_fallo(usuario)
            return False
        return True

    def _registrar_fallo(self, usuario: str) -> None:
        with self._lock:
            fallos, _ = self._fallos.get(usuario, [0, 0.0])
            fallos += 1
            hasta = self._reloj() + self._bloqueo_s if fallos >= self._intentos_max else 0.0
            self._fallos[usuario] = [0 if hasta else fallos, hasta]
        if hasta:
            logger.warning("Registro de pruebas: usuario %s bloqueado por intentos fallidos", usuario)

    def usuario(self, token: str | None) -> dict | None:
        """Fila del usuario de una sesión vigente; None si no existe, venció o
        el usuario fue desactivado. La sesión no se renueva: vence a las N horas."""
        if not token:
            return None
        with self._lock:
            sesion = self._sesiones.get(token)
            if sesion is None:
                return None
            if self._reloj() >= sesion[1]:
                del self._sesiones[token]
                return None
            nombre = sesion[0]
        fila = self._almacen.usuario(nombre)
        if fila is None or not fila["activo"]:
            self.cerrar(token)
            return None
        return fila

    def cerrar(self, token: str | None) -> None:
        with self._lock:
            self._sesiones.pop(token or "", None)

    def cerrar_de(self, usuario: str, excepto: str | None = None) -> None:
        with self._lock:
            for token in [t for t, s in self._sesiones.items() if s[0] == usuario and t != excepto]:
                del self._sesiones[token]
