# autoclave/backend/rutas/usuarios.py
#
# Sesión, usuarios y operadores (/auth, /usuarios, /operadores).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import sqlite3
from fastapi import Depends
from pydantic import BaseModel, StrictBool
from autoclave.backend.autenticacion import Sesion
from autoclave.backend.contrasenas import hash_password, simular_verificacion, verificar_password
from autoclave.auth.roles import ROL_ADMIN, ROL_INGENIERO, ROL_TECNICO, ROLES_CREABLES
from autoclave.auth.validacion_usuario import (COD_IGUAL_ACTUAL, COD_OBLIGATORIO,
    USUARIO_EXISTE, codigo_clave, codigo_confirmacion, codigos_nuevo_usuario)
from fastapi import APIRouter

from autoclave.backend.dependencias import (RechazoApi, _auditar, _rechazar,
    _rechazar_bloqueado, _rechazar_validacion, context, intentos_login, requiere_rol, tokens)
from autoclave.backend.rutas.io import _detalle_salida_prueba, _invalidar_sesion

router = APIRouter()


# ── Endpoints de sesión ──────────────────────────────────────────────────────

class _LoginBody(BaseModel):
    usuario: str
    clave: str


@router.post("/auth/login")
def login(body: _LoginBody):
    """401 genérico (sin distinguir usuario inexistente, inactivo o clave
    errónea) y 429 con el usuario bloqueado, aunque la clave sea correcta.
    Los intentos cuentan también para usuarios inexistentes (decisión 29).
    El fallo que activa el bloqueo ya responde 429 (decisión 33)."""
    usuario = body.usuario.strip()
    # comprobar y contar en un solo paso, antes de la verificación lenta
    if not intentos_login.reservar_intento(usuario):
        _auditar("login_bloqueado", usuario=usuario, entidad="/auth/login")
        _rechazar_bloqueado(usuario)

    fila = context.db.get_usuario_by_username(usuario) if usuario else None
    if fila is None:
        simular_verificacion()
        valido = False
    else:
        valido = verificar_password(body.clave, fila.get("hash_pw"))
        if valido:
            # H-01 de O2b: si durante la verificación (lenta) se desactivó al
            # usuario o se le restableció la clave, no se emite el token
            actual = context.db.get_usuario_by_username(usuario)
            valido = actual is not None and actual.get("hash_pw") == fila.get("hash_pw")
            fila = actual if valido else fila

    if not valido:
        quedo_bloqueado = intentos_login.bloqueado(usuario)
        _auditar("login_fallido", usuario=usuario, entidad="/auth/login",
                 detalle={"bloqueado": True} if quedo_bloqueado else None)
        if quedo_bloqueado:
            _rechazar_bloqueado(usuario)
        raise RechazoApi(401, "credenciales_invalidas", "Usuario o contraseña incorrectos")

    intentos_login.registrar_exito(usuario)
    sesion = tokens.emitir(fila["usuario"], fila.get("nombre") or "", fila.get("rol") or "",
                           bool(fila.get("debe_cambiar_clave")))
    _auditar("login_ok", sesion)
    return {
        "token": sesion.token,
        "usuario": sesion.usuario,
        "nombre": sesion.nombre,
        "rol": sesion.rol,
        "debe_cambiar_clave": sesion.debe_cambiar_clave,
    }


@router.post("/auth/logout")
def logout(sesion: Sesion = Depends(requiere_rol(permitir_cambio_pendiente=True))):
    salio = _invalidar_sesion(sesion)
    _auditar("logout", sesion)
    if salio:
        _auditar("modo_prueba_sale", sesion, detalle=_detalle_salida_prueba("sesión cerrada"))
    return {"ok": True}


@router.get("/auth/sesion")
def sesion_actual(sesion: Sesion = Depends(requiere_rol(permitir_cambio_pendiente=True))):
    """Valida el token (spec v7, §4.1): la UI lo llama una vez al reconectar con
    el backend, nunca en sondeo. 401 estándar si el token no es válido."""
    return {"usuario": sesion.usuario, "rol": sesion.rol}


class _CambioClaveBody(BaseModel):
    clave_actual: str
    clave_nueva: str
    confirmacion: str


def _bloquear_por_cambio_clave(sesion: Sesion, entidad: str):
    """429 en el cambio de contraseña (H-T8-01): invalida el token de la sesión,
    como un logout, y responde el mismo cuerpo que el login."""
    salio = _invalidar_sesion(sesion)
    _auditar("login_bloqueado", sesion, entidad=entidad, detalle={"origen": "cambio_clave"})
    if salio:
        _auditar("modo_prueba_sale", sesion, detalle=_detalle_salida_prueba("sesión bloqueada"))
    _rechazar_bloqueado(sesion.usuario)


def _revisar_contrasenas_semilla() -> None:
    """LIC-02: el aviso SIS-07 se despeja en cuanto Admin e Ingeniero ya no
    tienen la contraseña de fábrica."""
    revisar = getattr(context, "revisar_contrasenas_semilla", None)
    if callable(revisar):
        revisar()


@router.post("/auth/change_password")
def change_password(body: _CambioClaveBody,
                    sesion: Sesion = Depends(requiere_rol(permitir_cambio_pendiente=True))):
    """Los fallos de la clave actual suman al contador del login del mismo
    usuario (H-T8-01): al 5.º responde 429 y se invalida el token. Una clave
    actual correcta reinicia el contador. 422 con la lista {campo, codigo}."""
    entidad = "/auth/change_password"
    if not body.clave_actual:
        _rechazar_validacion({"clave_actual": COD_OBLIGATORIO})

    if not intentos_login.reservar_intento(sesion.usuario):
        _bloquear_por_cambio_clave(sesion, entidad)
    fila = context.db.get_usuario_by_username(sesion.usuario)
    if fila is None or not verificar_password(body.clave_actual, fila.get("hash_pw")):
        if intentos_login.bloqueado(sesion.usuario):
            _auditar("login_fallido", sesion, entidad=entidad,
                     detalle={"origen": "cambio_clave", "bloqueado": True})
            _bloquear_por_cambio_clave(sesion, entidad)
        _rechazar(403, "clave_actual_incorrecta", "La contraseña actual no es correcta",
                  entidad, sesion)
    intentos_login.registrar_exito(sesion.usuario)

    # Mismas reglas de longitud y confirmación que Nuevo usuario
    errores = {}
    for campo, codigo in (("clave_nueva", codigo_clave(body.clave_nueva)),
                          ("confirmacion", codigo_confirmacion(body.confirmacion,
                                                               body.clave_nueva))):
        if codigo:
            errores[campo] = codigo
    if "clave_nueva" not in errores and body.clave_nueva == body.clave_actual:
        errores = {"clave_nueva": COD_IGUAL_ACTUAL, **errores}
    if errores:
        _rechazar_validacion(errores)

    context.db.actualizar_password(sesion.usuario, hash_password(body.clave_nueva))
    tokens.clave_cambiada(sesion.token)
    _auditar("cambio_clave", sesion)
    _revisar_contrasenas_semilla()
    return {"ok": True}


class _NuevoUsuarioBody(BaseModel):
    nombre: str
    usuario: str
    clave: str
    confirmacion: str
    rol: str
    activo: bool = True


@router.post("/usuarios")
def crear_usuario(body: _NuevoUsuarioBody,
                  sesion: Sesion = Depends(requiere_rol(ROL_ADMIN, ROL_INGENIERO))):
    """Decisión 26: ingeniero crea admin, técnico e ingeniero; admin crea admin
    y técnico. 403 si el rol no puede crear el rol pedido, 409 si el usuario ya
    existe (sin distinguir mayúsculas), 422 con la lista {campo, codigo} si no
    valida (campos del cuerpo: nombre, usuario, clave, confirmacion, rol)."""
    entidad = "/usuarios"
    errores = codigos_nuevo_usuario(body.nombre, body.usuario, body.clave, body.confirmacion,
                                    body.rol, existe_usuario=lambda _u: False)
    if errores:
        _rechazar_validacion(errores)
    if body.rol not in ROLES_CREABLES.get(sesion.rol, frozenset()):
        _rechazar(403, "rol_no_creable", "Su rol no puede crear usuarios con ese rol",
                  entidad, sesion)
    if context.db.existe_usuario(body.usuario):
        _rechazar(409, "usuario_existe", USUARIO_EXISTE, entidad, sesion)

    try:
        context.db.crear_usuario(
            body.nombre.strip(), body.usuario, hash_password(body.clave), body.rol,
            activo=1 if body.activo else 0, creado_por=sesion.usuario,
        )
    except sqlite3.IntegrityError:
        # carrera con otra creación del mismo nombre entre la consulta y el INSERT
        _rechazar(409, "usuario_existe", USUARIO_EXISTE, entidad, sesion)

    _auditar("usuario_creado", sesion, entidad=body.usuario,
             valor_nuevo={"rol": body.rol, "activo": body.activo})
    return {"ok": True, "usuario": body.usuario}


# ── Gestión de usuarios y operadores (O2b, tanda 6; decisión 1.9) ────────────
# Ver: admin, técnico e ingeniero (el técnico, en solo lectura). Modificar:
# admin e ingeniero, y solo usuarios de un rol que pueden crear
# (ROLES_CREABLES: el admin no toca a un ingeniero). Nunca se borra un usuario;
# nadie se desactiva a sí mismo ni deja el equipo sin un ingeniero activo.
# Desactivar o restablecer la contraseña cierra las sesiones abiertas del usuario.

_LECTURA_USUARIOS = (ROL_ADMIN, ROL_TECNICO, ROL_INGENIERO)
_GESTION_USUARIOS = (ROL_ADMIN, ROL_INGENIERO)
OPERADOR_NOMBRE_MAX = 40


def _usuario_dto(f: dict) -> dict:
    return {k: f.get(k) for k in ("nombre", "usuario", "rol", "activo", "debe_cambiar_clave",
                                  "cuenta_sistema", "creado_por", "creado_en", "ultimo_ingreso")}


def _rechazar_cuenta_sistema(fila: dict, accion: str, entidad: str, sesion: Sesion,
                             campos: list[str] | None = None):
    """U11 (D11-6.2/6.3): las cuentas del sistema (marca `cuenta_sistema` en la
    BD, no el texto del usuario) no se desactivan, borran, cambian de rol ni
    renombran. 409 y el intento queda en la bitácora (con los campos pedidos
    si vino de PATCH, SAF-04)."""
    detalle = {"accion": accion}
    if campos:
        detalle["campos"] = campos
    _auditar("cuenta_sistema_rechazada", sesion, entidad=fila.get("usuario") or "",
             detalle=detalle)
    _rechazar(409, "cuenta_sistema",
              "Cuenta del sistema: no se puede desactivar, borrar, cambiar de rol ni renombrar",
              entidad, sesion)


@router.get("/usuarios")
def listar_usuarios(sesion: Sesion = Depends(requiere_rol(*_LECTURA_USUARIOS))):
    """Lista sin hashes. `gestionables`: roles que la sesión puede modificar."""
    return {"usuarios": [_usuario_dto(f) for f in context.db.listar_usuarios()],
            "gestionables": sorted(ROLES_CREABLES.get(sesion.rol, frozenset()))}


def _objetivo_gestionable(usuario: str, sesion: Sesion, entidad: str) -> dict:
    """404 si no existe; 403 si su rol no lo puede gestionar la sesión."""
    fila = context.db.get_usuario_cualquiera(usuario)
    if fila is None:
        raise RechazoApi(404, "no_existe", "El usuario no existe")
    if fila.get("rol") not in ROLES_CREABLES.get(sesion.rol, frozenset()):
        _rechazar(403, "rol_no_gestionable", "Su rol no puede modificar usuarios con ese rol",
                  entidad, sesion)
    return fila


def _cerrar_sesiones_de(usuario: str, motivo: str) -> int:
    cerradas = 0
    for s in tokens.sesiones_de(usuario):
        salio = _invalidar_sesion(s)
        cerradas += 1
        if salio:
            _auditar("modo_prueba_sale", s, detalle=_detalle_salida_prueba(motivo))
    return cerradas


class _ActivoBody(BaseModel):
    activo: StrictBool


@router.put("/usuarios/{usuario}/activo")
def fijar_activo_usuario(usuario: str, body: _ActivoBody,
                         sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    entidad = f"/usuarios/{usuario}/activo"
    if usuario == sesion.usuario and not body.activo:
        _rechazar(409, "autodesactivacion", "Nadie puede desactivarse a sí mismo", entidad, sesion)
    fila = context.db.get_usuario_cualquiera(usuario)
    if fila is not None and fila.get("cuenta_sistema") and not body.activo:
        _rechazar_cuenta_sistema(fila, "desactivar", entidad, sesion)
    _objetivo_gestionable(usuario, sesion, entidad)
    resultado = context.db.fijar_activo_usuario(usuario, body.activo, ROL_INGENIERO)
    if resultado == "no_existe":
        raise RechazoApi(404, "no_existe", "El usuario no existe")
    if resultado == "cuenta_sistema":
        _rechazar_cuenta_sistema(fila or {"usuario": usuario}, "desactivar", entidad, sesion)
    if resultado == "ultimo_protegido":
        _rechazar(409, "ultimo_ingeniero", "El equipo no puede quedar sin un ingeniero activo",
                  entidad, sesion)
    if resultado == "ok":
        cerradas = 0 if body.activo else _cerrar_sesiones_de(usuario, "usuario desactivado")
        _auditar("usuario_reactivado" if body.activo else "usuario_desactivado", sesion,
                 entidad=usuario, valor_anterior={"activo": not body.activo},
                 valor_nuevo={"activo": body.activo},
                 detalle={"sesiones_cerradas": cerradas} if cerradas else None)
    return {"ok": True, "usuario": usuario, "activo": body.activo}


class _RestablecerClaveBody(BaseModel):
    clave: str
    confirmacion: str


@router.post("/usuarios/{usuario}/restablecer_clave")
def restablecer_clave(usuario: str, body: _RestablecerClaveBody,
                      sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    """Contraseña temporal con cambio obligatorio en el siguiente login. La
    propia se cambia por /auth/change_password (409). 422 {campo, codigo}."""
    entidad = f"/usuarios/{usuario}/restablecer_clave"
    if usuario == sesion.usuario:
        _rechazar(409, "usar_cambio_clave", "Para su propia contraseña use Cambiar contraseña",
                  entidad, sesion)
    _objetivo_gestionable(usuario, sesion, entidad)
    errores = {}
    for campo, codigo in (("clave", codigo_clave(body.clave)),
                          ("confirmacion", codigo_confirmacion(body.confirmacion, body.clave))):
        if codigo:
            errores[campo] = codigo
    if errores:
        _rechazar_validacion(errores)
    if not context.db.restablecer_password(usuario, hash_password(body.clave)):
        raise RechazoApi(404, "no_existe", "El usuario no existe")
    cerradas = _cerrar_sesiones_de(usuario, "contraseña restablecida")
    intentos_login.registrar_exito(usuario)       # H-04: la clave temporal sirve de inmediato
    _auditar("clave_restablecida", sesion, entidad=usuario,
             detalle={"sesiones_cerradas": cerradas} if cerradas else None)
    _revisar_contrasenas_semilla()
    return {"ok": True, "usuario": usuario}


# U11 (tanda 11, D11-6.3): borrar, cambiar el rol y renombrar no existen como
# operación para ningún usuario (nunca se borra; nombre, usuario y rol no se
# editan desde O2b). Estas dos rutas solo dan un rechazo explícito: 409
# `cuenta_sistema` (auditado) para Admin e Ingeniero y 409 genérico para el
# resto. No modifican nada en ningún caso.

class _ModificarUsuarioBody(BaseModel):
    model_config = {"extra": "forbid"}
    nombre: str | None = None
    usuario: str | None = None
    rol: str | None = None


def _objetivo_existente(usuario: str) -> dict:
    fila = context.db.get_usuario_cualquiera(usuario)
    if fila is None:
        raise RechazoApi(404, "no_existe", "El usuario no existe")
    return fila


@router.delete("/usuarios/{usuario}")
def borrar_usuario(usuario: str, sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    entidad = f"/usuarios/{usuario}"
    fila = _objetivo_existente(usuario)
    if fila.get("cuenta_sistema"):
        _rechazar_cuenta_sistema(fila, "borrar", entidad, sesion)
    _rechazar(409, "usuario_no_se_borra", "Los usuarios no se borran; se desactivan",
              entidad, sesion)


@router.patch("/usuarios/{usuario}")
def modificar_usuario(usuario: str, body: _ModificarUsuarioBody,
                      sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    entidad = f"/usuarios/{usuario}"
    campos = sorted(k for k, v in body.model_dump().items() if v is not None)
    if not campos:                                     # SAF-04: cuerpo vacío
        _rechazar_validacion({"cuerpo": COD_OBLIGATORIO})
    fila = _objetivo_existente(usuario)
    if fila.get("cuenta_sistema"):
        accion = "cambiar_rol" if body.rol is not None else "renombrar"
        _rechazar_cuenta_sistema(fila, accion, entidad, sesion, campos=campos)
    _rechazar(409, "modificacion_no_disponible",
              "El nombre, el usuario y el rol no se modifican", entidad, sesion)


@router.get("/operadores")
def listar_operadores(activos: bool = False):
    """Operadores (nombre, sin contraseña). Lectura libre: se eligen al iniciar
    ciclo, que no exige sesión."""
    return {"operadores": [{k: o[k] for k in ("id", "nombre", "activo")}       # H-05
                           for o in context.db.listar_operadores(solo_activos=activos)]}


class _OperadorBody(BaseModel):
    nombre: str


@router.post("/operadores")
def crear_operador(body: _OperadorBody,
                   sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    nombre = " ".join(body.nombre.split())
    if not nombre:
        _rechazar_validacion({"nombre": COD_OBLIGATORIO})
    if len(nombre) > OPERADOR_NOMBRE_MAX:
        _rechazar_validacion({"nombre": "larga"})
    id_ = context.db.crear_operador(nombre, sesion.usuario)
    if id_ is None:
        _rechazar(409, "operador_existe", "El operador ya existe", "/operadores", sesion)
    _auditar("operador_creado", sesion, entidad=nombre, valor_nuevo={"activo": True})
    return {"ok": True, "id": id_, "nombre": nombre}


@router.put("/operadores/{id_}/activo")
def fijar_activo_operador(id_: int, body: _ActivoBody,
                          sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    anterior = context.db.fijar_activo_operador(id_, body.activo)
    if anterior is None:
        raise RechazoApi(404, "no_existe", "El operador no existe")
    if anterior["activo"] != body.activo:
        _auditar("operador_reactivado" if body.activo else "operador_desactivado", sesion,
                 entidad=anterior["nombre"], valor_anterior={"activo": anterior["activo"]},
                 valor_nuevo={"activo": body.activo})
    return {"ok": True, "id": id_, "activo": body.activo}
