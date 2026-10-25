# simulador/autenticacion_simulada.py
#
# Autenticación del BACKEND SIMULADO (T-14; planeacion_backend_autenticacion.md
# v7, decisiones 33 a 35). Replica el contrato del backend real para probar la
# UI sin tarjeta: /auth/login, /auth/logout, /auth/sesion, /auth/change_password
# y POST /usuarios, con los mismos códigos de estado y cuerpos
# ({"detail", "codigo", ...}). La batería tests/test_contrato_autenticacion*.py
# corre contra ambos.
#
# Solo herramienta de desarrollo (escucha en 127.0.0.1, ver __main__.py):
#   - usuarios sembrados en memoria por papel, con la contraseña en claro;
#   - token determinista por sesión, "sim-<usuario>-<n>", con tabla en memoria
#     para que cada login sea una sesión independiente (decisión 8).
# Nada de esto existe en el backend de producción ni recibe trato especial en
# el cliente. Reutiliza ControlIntentos (bloqueo) y las reglas de validación.

import hmac
import itertools
import threading
import time
from dataclasses import dataclass

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from autoclave.backend.autenticacion import ControlIntentos
from autoclave.core.runtime.nombre_usuario import normalizar_usuario
from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO, ROLES_CREABLES
from autoclave.auth.validacion_usuario import (
    COD_IGUAL_ACTUAL, COD_OBLIGATORIO, USUARIO_EXISTE, codigo_clave, codigo_confirmacion,
    codigos_nuevo_usuario,
)

# usuario -> (nombre, rol, clave, debe_cambiar_clave). Uno por papel, más las
# semillas del backend real con cambio obligatorio y uno dedicado al bloqueo.
USUARIOS_SEMBRADOS = {
    "tec1":      ("Técnico Simulado", "tecnico", "clave1234", False),
    "adm1":      ("Admin Simulado", "admin", "clave1234", False),
    "ing1":      ("Ingeniero Simulado", "ingeniero", "clave1234", False),
    # U11 (tanda 11, D11-6): las cuentas del sistema se llaman Admin e Ingeniero
    "Admin":     ("Admin", "admin", "admin1234", True),
    "Ingeniero": ("Ingeniero", "ingeniero", "ingeniero1234", True),
    "bloq1":     ("Usuario de bloqueo", "tecnico", "clave1234", False),
}

_MOTIVO_SESION_INVALIDA = "Sesión no válida o vencida; inicie sesión de nuevo"
_MOTIVO_BLOQUEADO = "Usuario bloqueado por intentos fallidos; espere 5 minutos"


class _Rechazo(Exception):
    def __init__(self, status: int, codigo: str, motivo: str, extra: dict | None = None,
                 headers: dict | None = None):
        super().__init__(motivo)
        self.status, self.codigo, self.motivo = status, codigo, motivo
        self.extra, self.headers = extra or {}, headers


@dataclass
class _Usuario:
    nombre: str
    rol: str
    clave: str
    debe_cambiar_clave: bool
    activo: bool = True


@dataclass
class _Sesion:
    token: str
    usuario: str
    rol: str


class _LoginBody(BaseModel):
    usuario: str
    clave: str


class _CambioClaveBody(BaseModel):
    clave_actual: str
    clave_nueva: str
    confirmacion: str


class _NuevoUsuarioBody(BaseModel):
    nombre: str
    usuario: str
    clave: str
    confirmacion: str
    rol: str
    activo: bool = True


def registrar_autenticacion(app: FastAPI, reloj=time.monotonic) -> None:
    """Añade a `app` los endpoints de sesión y usuarios del contrato v7."""
    usuarios = {u: _Usuario(*datos) for u, datos in USUARIOS_SEMBRADOS.items()}
    sesiones: dict[str, _Sesion] = {}
    contador = itertools.count(1)
    lock = threading.Lock()
    intentos = ControlIntentos(reloj=reloj)

    @app.exception_handler(_Rechazo)
    def _responder(_request: Request, r: _Rechazo):
        return JSONResponse(status_code=r.status, headers=r.headers,
                            content={"detail": r.motivo, "codigo": r.codigo, **r.extra})

    def _bloqueado(usuario: str):
        segundos = max(1, intentos.segundos_restantes(usuario))
        raise _Rechazo(429, "usuario_bloqueado", _MOTIVO_BLOQUEADO,
                       extra={"segundos_restantes": segundos},
                       headers={"Retry-After": str(segundos)})

    def _validacion(errores: dict[str, str]):
        raise _Rechazo(422, "validacion", "Datos inválidos", extra={
            "errores": [{"campo": c, "codigo": cod} for c, cod in errores.items()]})

    def _canonico(usuario: str) -> str:
        """Sin distinguir mayúsculas, como la BD del backend (U11): manda la
        coincidencia exacta; si no la hay, la única que coincide."""
        if usuario in usuarios:
            return usuario
        buscado = normalizar_usuario(usuario)          # NFKC + casefold (SAF-01)
        candidatos = [u for u in usuarios if normalizar_usuario(u) == buscado]
        return candidatos[0] if len(candidatos) == 1 else usuario

    def _clave_valida(usuario: str, clave: str) -> bool:
        u = usuarios.get(usuario)
        return (u is not None and u.activo
                and hmac.compare_digest(u.clave.encode(), clave.encode()))

    def _sesion(permitir_pendiente: bool = False, *roles: str):
        def dependencia(authorization: str | None = Header(None)) -> _Sesion:
            esquema, _, token = (authorization or "").partition(" ")
            with lock:
                sesion = sesiones.get(token.strip()) if esquema.lower() == "bearer" else None
            if sesion is None:
                raise _Rechazo(401, "sesion_invalida", _MOTIVO_SESION_INVALIDA,
                               headers={"WWW-Authenticate": "Bearer"})
            if usuarios[sesion.usuario].debe_cambiar_clave and not permitir_pendiente:
                raise _Rechazo(403, "clave_pendiente", "Debe cambiar la contraseña")
            if roles and sesion.rol not in roles:
                raise _Rechazo(403, "rol_sin_permiso", "Su rol no tiene permiso para esta acción")
            return sesion
        return dependencia

    def _invalidar(sesion: _Sesion) -> None:
        with lock:
            sesiones.pop(sesion.token, None)

    @app.post("/auth/login")
    def login(body: _LoginBody):
        usuario = body.usuario.strip()
        if not intentos.reservar_intento(usuario):
            _bloqueado(usuario)
        usuario = _canonico(usuario)
        if not _clave_valida(usuario, body.clave):
            if intentos.bloqueado(usuario):
                _bloqueado(usuario)
            raise _Rechazo(401, "credenciales_invalidas", "Usuario o contraseña incorrectos")
        intentos.registrar_exito(usuario)
        u = usuarios[usuario]
        token = f"sim-{usuario}-{next(contador)}"
        with lock:
            sesiones[token] = _Sesion(token, usuario, u.rol)
        return {"token": token, "usuario": usuario, "nombre": u.nombre, "rol": u.rol,
                "debe_cambiar_clave": u.debe_cambiar_clave}

    @app.post("/auth/logout")
    def logout(sesion: _Sesion = Depends(_sesion(True))):
        _invalidar(sesion)
        return {"ok": True}

    @app.get("/auth/sesion")
    def sesion_actual(sesion: _Sesion = Depends(_sesion(True))):
        return {"usuario": sesion.usuario, "rol": sesion.rol}

    @app.post("/auth/change_password")
    def change_password(body: _CambioClaveBody, sesion: _Sesion = Depends(_sesion(True))):
        if not body.clave_actual:
            _validacion({"clave_actual": COD_OBLIGATORIO})
        if not intentos.reservar_intento(sesion.usuario):
            _invalidar(sesion)
            _bloqueado(sesion.usuario)
        if not _clave_valida(sesion.usuario, body.clave_actual):
            if intentos.bloqueado(sesion.usuario):
                _invalidar(sesion)
                _bloqueado(sesion.usuario)
            raise _Rechazo(403, "clave_actual_incorrecta", "La contraseña actual no es correcta")
        intentos.registrar_exito(sesion.usuario)

        errores = {}
        for campo, codigo in (("clave_nueva", codigo_clave(body.clave_nueva)),
                              ("confirmacion", codigo_confirmacion(body.confirmacion,
                                                                   body.clave_nueva))):
            if codigo:
                errores[campo] = codigo
        if "clave_nueva" not in errores and body.clave_nueva == body.clave_actual:
            errores = {"clave_nueva": COD_IGUAL_ACTUAL, **errores}
        if errores:
            _validacion(errores)
        u = usuarios[sesion.usuario]
        u.clave, u.debe_cambiar_clave = body.clave_nueva, False
        return {"ok": True}

    @app.post("/usuarios")
    def crear_usuario(body: _NuevoUsuarioBody,
                      sesion: _Sesion = Depends(_sesion(False, ROL_ADMIN, ROL_INGENIERO))):
        errores = codigos_nuevo_usuario(body.nombre, body.usuario, body.clave,
                                        body.confirmacion, body.rol,
                                        existe_usuario=lambda _u: False)
        if errores:
            _validacion(errores)
        if body.rol not in ROLES_CREABLES.get(sesion.rol, frozenset()):
            raise _Rechazo(403, "rol_no_creable", "Su rol no puede crear usuarios con ese rol")
        if any(normalizar_usuario(u) == normalizar_usuario(body.usuario) for u in usuarios):
            raise _Rechazo(409, "usuario_existe", USUARIO_EXISTE)
        usuarios[body.usuario] = _Usuario(body.nombre.strip(), body.rol, body.clave, False,
                                          activo=body.activo)
        return {"ok": True, "usuario": body.usuario}
