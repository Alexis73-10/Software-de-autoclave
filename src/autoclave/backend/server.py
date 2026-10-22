# autoclave/backend/server.py

from types import SimpleNamespace
import logging
import sqlite3
import sys
import json
import os
import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import Depends, HTTPException, FastAPI, Body, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt

from autoclave.backend.actividad_ui import ActividadUI
from autoclave.backend.arranque.registro import RegistroArranque
from autoclave.backend.arranque.secuencia import ejecutar_arranque
from autoclave.backend.arranque.sin_bd import BdNoDisponibleError
from autoclave.backend.autenticacion import AlmacenTokens, ControlIntentos, Sesion
from autoclave.backend.contrasenas import hash_password, simular_verificacion, verificar_password
from autoclave.backend.context import BackendContext
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.catalogo import Nivel
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.core.runtime import io_names
from autoclave.core.runtime import progreso_ciclo
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime import motivos
from autoclave.core.runtime.lectura import lectura_valida
from autoclave.installation.profile import (entradas_no_monitoreadas, sondas_no_vigiladas,
                                           tarjeta_emparejada)
from autoclave.services.domain.logging.ticket_formatter import format_ticket
from autoclave.services.domain.reportes import resumen_periodo
from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point
from autoclave.core.managers.catalogo_parametros import evaluar_calibracion, evaluar_desviacion_acumulada
from autoclave.config.calibration_writer import write_user_calibration
from autoclave.config import load_config
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.ui_pyside.services.roles import ROL_ADMIN, ROL_INGENIERO, ROL_TECNICO, ROLES_CREABLES
from autoclave.ui_pyside.services.validacion_usuario import (
    COD_IGUAL_ACTUAL, COD_OBLIGATORIO, USUARIO_EXISTE, codigo_clave, codigo_confirmacion,
    codigos_nuevo_usuario,
)
from autoclave.utils import periodos
from autoclave.utils.paths import calibration_path

logger = logging.getLogger(__name__)

@asynccontextmanager
async def _ciclo_de_vida(_app):
    yield
    # Apagado ordenado del backend (Ctrl+C, SIGTERM de uvicorn): detiene el
    # loop y apaga todas las salidas. Un TerminateProcess de Windows no pasa
    # por aquí; por eso la UI no termina el backend con un ciclo en curso
    # (revisión de la etapa 1 de autenticación, hallazgo B).
    _detener_arranque.set()
    control_loop = getattr(context, "control_loop", None)
    if control_loop is None:
        # el arranque no llegó a construirlo: no hay loop ni orden a la tarjeta
        logger.info("Backend detenido antes de construir el control loop")
        return
    try:
        control_loop.stop()
        logger.info("Backend detenido: control loop parado y salidas apagadas")
    except Exception:
        logger.exception("Error al detener el control loop en el apagado del backend")


app = FastAPI(title="Autoclave Backend", lifespan=_ciclo_de_vida)

# Sin E/S: cada parte se construye en su etapa de arranque (iniciar_arranque),
# así el puerto 8000 responde desde t = 0 (fase B, ARR-01 / BAR-01).
context = BackendContext()


# =============================================================================
# ARRANQUE POR ETAPAS (planeacion_barra_arranque_real.md §5)
# =============================================================================
# GET /arranque responde desde que el puerto abre, sin token (D-C). Mientras el
# control no esté construido, el resto de rutas responde 503: la compuerta la
# activa backend/main.py (preparar_arranque) antes de abrir el puerto; quien
# importa este módulo sin pasar por main.py (pruebas) no la tiene.

registro_arranque = RegistroArranque()
_compuerta_arranque = False
_contexto_operable = threading.Event()
_detener_arranque = threading.Event()
_hilo_arranque: threading.Thread | None = None
_RUTAS_SIN_COMPUERTA = frozenset({"/arranque", "/ui/activity"})


def preparar_arranque() -> None:
    """Activa la compuerta 503: llamar antes de abrir el puerto."""
    global _compuerta_arranque
    _compuerta_arranque = True


def iniciar_arranque() -> None:
    """Lanza la secuencia de etapas en su hilo. Llamar con el puerto ya
    enlazado (backend/main.py): si el enlace falla, nunca se abre el serial."""
    global _hilo_arranque
    if _hilo_arranque is not None:
        return
    _hilo_arranque = threading.Thread(
        target=ejecutar_arranque,
        args=(context, registro_arranque),
        kwargs={"al_cancelar_prueba": _prueba_cancelada_por_paro,
                "al_operable": _contexto_operable.set,
                "detener": _detener_arranque},
        name="arranque", daemon=True)
    _hilo_arranque.start()
    _iniciar_vigilancia_dueno_prueba()   # SAF-01 (revisión de B7)


@app.middleware("http")
async def _compuerta_de_arranque(request: Request, call_next):
    if (_compuerta_arranque and not _contexto_operable.is_set()
            and request.url.path not in _RUTAS_SIN_COMPUERTA):
        fallido = registro_arranque.fallo_bloqueante
        return JSONResponse(status_code=503, content={
            "detail": "Arranque fallido" if fallido else "Arranque en curso",
            "codigo": "arranque_fallido" if fallido else "arranque_en_curso",
        })
    return await call_next(request)


@app.get("/arranque")
def get_arranque():
    return registro_arranque.instantanea()


@app.exception_handler(BdNoDisponibleError)
def _responder_sin_bd(_request: Request, _e: BdNoDisponibleError):
    # PROVISIONAL hasta el modo sin BD (§7 de planeacion_arranque_y_modo_sin_bd.md)
    return JSONResponse(status_code=503, content={
        "detail": "Base de datos no disponible", "codigo": "sin_base_de_datos"})


# Actividad compartida de las pantallas QML (standby simultáneo); solo presentación.
actividad_ui = ActividadUI()

CALIBRATION_PATH = calibration_path()


# =============================================================================
# SEGURIDAD (planeacion_backend_autenticacion.md)
# =============================================================================
# Sesiones en memoria: un reinicio del backend invalida todos los tokens
# (decisión 2). Nada de esto toca el ControlLoop: un token vencido nunca afecta
# a un ciclo en curso, solo a escrituras de configuración y al modo de prueba.

tokens = AlmacenTokens()
intentos_login = ControlIntentos()

# Token de la sesión que activó el modo prueba: solo ella enciende salidas y
# sale (§5.4). Se lee y escribe con _sm_lock tomado (bloqueo_maquina).
_token_modo_prueba: str | None = None

# Serializa las escrituras de archivos de configuración (YAML de calibración,
# JSON de ciclos), que se hacen fuera de _sm_lock.
_lock_archivos = threading.Lock()

# Variantes del guard de estado (§5.5). P-8 (tanda 6): EMERGENCIA e
# HIBERNACION se retiraron (inalcanzables); el nombre de la segunda variante se
# conserva por compatibilidad y hoy equivale a DISTINTO_DE_CICLO.
DISTINTO_DE_CICLO = frozenset({GlobalState.CICLO})
DISTINTO_DE_CICLO_E_HIBERNACION = DISTINTO_DE_CICLO

_MOTIVO_ESTADO = {
    GlobalState.CICLO:       "No permitido con un ciclo en curso",
}


def _auditar(evento: str, sesion: Sesion | None = None, *, usuario: str = "",
             entidad: str = "", valor_anterior=None, valor_nuevo=None,
             detalle: dict | None = None) -> None:
    """Escribe en audit_log. Un fallo de la bitácora queda en el log pero no
    deshace ni bloquea la acción que se está registrando."""
    try:
        context.db.registrar_auditoria(
            evento,
            usuario=sesion.usuario if sesion else usuario,
            rol=sesion.rol if sesion else "",
            entidad=entidad,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            detalle=detalle,
        )
    except Exception:
        if getattr(context, "sin_base_de_datos", False) is True:
            # T8: sin base no hay bitácora; queda en el log de texto (S2, TMG-05)
            logger.warning("Sin base de datos: '%s' no queda en audit_log (%s, %s -> %s, %s)",
                           evento, entidad, valor_anterior, valor_nuevo, detalle)
        else:
            logger.exception("No se pudo registrar '%s' en audit_log", evento)


def _nombre_estado() -> str:
    """Estado de la máquina para la bitácora; "" si no se puede leer."""
    try:
        return str(getattr(context.estado.get_machine_state(), "name", ""))
    except Exception:
        return ""


class RechazoApi(Exception):
    """Rechazo con código estable (spec v7, decisiones 33 y 34). Cuerpo:
    {"detail": <texto en español>, "codigo": <código>, **extra}. `detail` sigue
    siendo texto para los clientes que ya lo muestran (puertas, Tk)."""
    def __init__(self, status: int, codigo: str, motivo: str, extra: dict | None = None,
                 headers: dict | None = None):
        super().__init__(motivo)
        self.status = status
        self.codigo = codigo
        self.motivo = motivo
        self.extra = extra or {}
        self.headers = headers


@app.exception_handler(RechazoApi)
def _responder_rechazo(_request: Request, r: RechazoApi):
    return JSONResponse(status_code=r.status, headers=r.headers,
                        content={"detail": r.motivo, "codigo": r.codigo, **r.extra})


def _rechazar(status: int, codigo: str, motivo: str, entidad: str,
              sesion: Sesion | None = None, headers: dict | None = None,
              extra: dict | None = None):
    """Registra el rechazo (rechazo_401/403/409) y lo lanza como RechazoApi.
    Escribe en SQLite: nunca llamarla con _sm_lock tomado (usar _Rechazo)."""
    _auditar(f"rechazo_{status}", sesion, entidad=entidad, detalle={"motivo": motivo})
    raise RechazoApi(status, codigo, motivo, extra=extra, headers=headers)


class _Rechazo(Exception):
    """Rechazo decidido dentro de guard_estado. El guard lo registra y lo
    convierte en RechazoApi después de soltar _sm_lock, para que la
    bitácora no detenga el tick del control loop."""
    def __init__(self, status: int, codigo: str, motivo: str, extra: dict | None = None):
        super().__init__(motivo)
        self.status = status
        self.codigo = codigo
        self.motivo = motivo
        self.extra = extra


def _rechazar_validacion(errores: dict[str, str]):
    """422 de las pantallas de sesión y usuarios: lista {campo, codigo} en el
    orden de los campos del cuerpo. Sin auditoría (no es un rechazo de acceso)."""
    raise RechazoApi(422, "validacion", "Datos inválidos", extra={
        "errores": [{"campo": c, "codigo": cod} for c, cod in errores.items()]})


_MOTIVO_SESION_INVALIDA = "Sesión no válida o vencida; inicie sesión de nuevo"
_MOTIVO_BLOQUEADO = "Usuario bloqueado por intentos fallidos; espere 5 minutos"


def _rechazar_bloqueado(usuario: str):
    """429 del bloqueo por intentos (decisión 33): código, segundos restantes
    y Retry-After con el mismo valor."""
    segundos = max(1, intentos_login.segundos_restantes(usuario))
    raise RechazoApi(429, "usuario_bloqueado", _MOTIVO_BLOQUEADO,
                     extra={"segundos_restantes": segundos},
                     headers={"Retry-After": str(segundos)})


def _token_de(authorization: str | None) -> str | None:
    if not authorization:
        return None
    esquema, _, token = authorization.partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def requiere_rol(*roles: str, permitir_cambio_pendiente: bool = False):
    """Dependencia FastAPI (§5.2): 401 sin token o con token inválido; 403 si
    la sesión debe cambiar la contraseña (salvo en change_password y logout) o
    si su rol no está en `roles` (vacío = cualquier rol). El rol sale siempre
    del token, nunca del cuerpo de la petición."""
    def dependencia(request: Request, authorization: str | None = Header(None)) -> Sesion:
        entidad = request.url.path
        sesion = tokens.obtener(_token_de(authorization))
        if sesion is None:
            _rechazar(401, "sesion_invalida", _MOTIVO_SESION_INVALIDA, entidad,
                      headers={"WWW-Authenticate": "Bearer"})
        if sesion.debe_cambiar_clave and not permitir_cambio_pendiente:
            _rechazar(403, "clave_pendiente", "Debe cambiar la contraseña", entidad, sesion)
        if roles and sesion.rol not in roles:
            _rechazar(403, "rol_sin_permiso", "Su rol no tiene permiso para esta acción",
                      entidad, sesion)
        return sesion
    return dependencia


@contextmanager
def guard_estado(prohibidos: frozenset, entidad: str, sesion: Sesion | None = None,
                 excepcion_ingeniero: bool = False):
    """Guard de estado (§5.5): comprueba el estado de máquina dentro de
    _sm_lock y mantiene el lock mientras dura el bloque, para que la acción
    no se intercale con el tick (p. ej. con START_CICLO).
    Con `excepcion_ingeniero`, un ingeniero pasa en CICLO (§5.8).
    Devuelve el estado observado.

    El bloque solo debe hacer comprobaciones y cambios en memoria o en la
    tarjeta: mientras dura, el tick completo del control loop espera. Archivos
    y bitácora van fuera. Para rechazar dentro del bloque se lanza _Rechazo,
    que se registra cuando el lock ya está libre."""
    try:
        with context.control_loop.bloqueo_maquina():
            estado = context.estado.get_machine_state()
            exceptuado = (excepcion_ingeniero and estado == GlobalState.CICLO
                          and sesion is not None and sesion.rol == ROL_INGENIERO)
            if estado in prohibidos and not exceptuado:
                raise _Rechazo(409, "estado_no_permitido",
                               _MOTIVO_ESTADO.get(estado, "No permitido en el estado actual"),
                               extra={"estado": getattr(estado, "name", str(estado))})
            yield estado
    except _Rechazo as r:
        _rechazar(r.status, r.codigo, r.motivo, entidad, sesion, extra=r.extra)


def _rechazar_si_config_invalida(entidad: str) -> None:
    """409 si el backend arrancó con la configuración inválida
    (CONFIGURACION_INVALIDA): sin ciclo, puertas ni modo prueba."""
    motivo = context.control_loop.bloqueo_configuracion
    if isinstance(motivo, str) and motivo:
        _rechazar(409, "configuracion_invalida", f"Configuración inválida: {motivo}", entidad)


def _contexto_ciclo() -> dict:
    """Ciclo y fase en curso para el `detalle` de la bitácora; vacío fuera de CICLO."""
    if context.estado.get_machine_state() != GlobalState.CICLO:
        return {}
    return {
        "ciclo": _ciclo_de_pantalla(),
        "fase": getattr(context.estado, "fase_ciclo", ""),
        "programa": getattr(getattr(context.control_loop, "cycle", None), "id", None),
    }


def _salir_modo_prueba() -> None:
    """Apaga las salidas, reanuda la máquina y olvida la sesión dueña. Llamar
    con _sm_lock tomado; quien llama registra modo_prueba_sale al soltarlo."""
    global _token_modo_prueba
    context.control_loop.exit_test_mode()
    _token_modo_prueba = None
    _cierres_invertidos.clear()
    _cancelar_vigilancias_prueba()


def _prueba_cancelada_por_paro() -> None:
    """Aviso del ControlLoop (hilo del loop, fuera de _sm_lock): el paro de
    emergencia canceló el modo prueba. Olvida la sesión dueña y lo registra."""
    global _token_modo_prueba
    with context.control_loop.bloqueo_maquina():
        if context.control_loop.test_mode_active:
            return   # ya se volvió a entrar: no es esta cancelación
        token, _token_modo_prueba = _token_modo_prueba, None
    _cancelar_vigilancias_prueba()
    sesion = tokens.obtener(token, renovar=False) if token else None
    dueno = tokens.quien_fue(token) if sesion is None else None
    _auditar("modo_prueba_sale", sesion, usuario=dueno[0] if dueno else "",
             detalle={"motivo": "paro de emergencia"})


# SAF-01 (revisión de B7): si la sesión dueña del modo prueba caduca (o se
# invalida por otra vía que no lo cerró), el modo prueba no puede quedar con
# salidas manuales y la máquina pausada sin nadie que pueda salir: un vigilante
# del backend lo cierra igual que la salida normal (ALL_OFF y se reanuda la
# máquina). Orden de candados: _sm_lock -> tokens (nunca al revés).
VIGILANCIA_DUENO_PRUEBA_S = 2.0
_hilo_vigilancia_dueno = None


def _revisar_dueno_modo_prueba() -> bool:
    """Una pasada del vigilante. True si sacó del modo prueba. Nunca lanza
    hacia el hilo (el bucle lo protege)."""
    token = _token_modo_prueba
    if token is None or tokens.existe(token):
        return False
    with context.control_loop.bloqueo_maquina():
        if (not context.control_loop.test_mode_active or _token_modo_prueba != token
                or tokens.existe(token)):
            return False
        _salir_modo_prueba()
    dueno = tokens.quien_fue(token)
    logger.warning("Modo prueba cerrado: la sesión dueña (%s) ya no es válida",
                   dueno[0] if dueno else "?")
    _auditar("modo_prueba_sale", usuario=dueno[0] if dueno else "",
             detalle={"motivo": "sesión del dueño caducada o cerrada"})
    return True


def _vigilar_dueno_modo_prueba(cada_s: float = VIGILANCIA_DUENO_PRUEBA_S) -> None:
    while True:
        try:
            _revisar_dueno_modo_prueba()
        except Exception:
            logger.exception("Vigilancia del dueño del modo prueba")
        time.sleep(cada_s)


def _iniciar_vigilancia_dueno_prueba() -> None:
    global _hilo_vigilancia_dueno
    if _hilo_vigilancia_dueno is not None:
        return
    _hilo_vigilancia_dueno = threading.Thread(
        target=_vigilar_dueno_modo_prueba, name="vigilancia-dueno-prueba", daemon=True)
    _hilo_vigilancia_dueno.start()



# ── Endpoints de sesión ──────────────────────────────────────────────────────

class _LoginBody(BaseModel):
    usuario: str
    clave: str


@app.post("/auth/login")
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


def _invalidar_sesion(sesion: Sesion) -> bool:
    """Invalida el token y, si esta sesión tenía el modo prueba, sale de él
    (decisión 30: nadie más podría salir). Bajo el lock: un /io/test/enter de
    esta misma sesión en vuelo vuelve a validar el token dentro del lock y se
    rechaza. Devuelve True si salió del modo prueba; quien llama lo registra."""
    with context.control_loop.bloqueo_maquina():
        tokens.invalidar(sesion.token)
        salio = (_token_modo_prueba == sesion.token
                 and context.control_loop.test_mode_active)
        if salio:
            _salir_modo_prueba()
    return salio


@app.post("/auth/logout")
def logout(sesion: Sesion = Depends(requiere_rol(permitir_cambio_pendiente=True))):
    salio = _invalidar_sesion(sesion)
    _auditar("logout", sesion)
    if salio:
        _auditar("modo_prueba_sale", sesion, detalle={"motivo": "sesión cerrada"})
    return {"ok": True}


@app.get("/auth/sesion")
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
        _auditar("modo_prueba_sale", sesion, detalle={"motivo": "sesión bloqueada"})
    _rechazar_bloqueado(sesion.usuario)


@app.post("/auth/change_password")
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
    return {"ok": True}


class _NuevoUsuarioBody(BaseModel):
    nombre: str
    usuario: str
    clave: str
    confirmacion: str
    rol: str
    activo: bool = True


@app.post("/usuarios")
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
                                  "creado_por", "creado_en", "ultimo_ingreso")}


@app.get("/usuarios")
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
            _auditar("modo_prueba_sale", s, detalle={"motivo": motivo})
    return cerradas


class _ActivoBody(BaseModel):
    activo: StrictBool


@app.put("/usuarios/{usuario}/activo")
def fijar_activo_usuario(usuario: str, body: _ActivoBody,
                         sesion: Sesion = Depends(requiere_rol(*_GESTION_USUARIOS))):
    entidad = f"/usuarios/{usuario}/activo"
    if usuario == sesion.usuario and not body.activo:
        _rechazar(409, "autodesactivacion", "Nadie puede desactivarse a sí mismo", entidad, sesion)
    _objetivo_gestionable(usuario, sesion, entidad)
    resultado = context.db.fijar_activo_usuario(usuario, body.activo, ROL_INGENIERO)
    if resultado == "no_existe":
        raise RechazoApi(404, "no_existe", "El usuario no existe")
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


@app.post("/usuarios/{usuario}/restablecer_clave")
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
    return {"ok": True, "usuario": usuario}


@app.get("/operadores")
def listar_operadores(activos: bool = False):
    """Operadores (nombre, sin contraseña). Lectura libre: se eligen al iniciar
    ciclo, que no exige sesión."""
    return {"operadores": [{k: o[k] for k in ("id", "nombre", "activo")}       # H-05
                           for o in context.db.listar_operadores(solo_activos=activos)]}


class _OperadorBody(BaseModel):
    nombre: str


@app.post("/operadores")
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


@app.put("/operadores/{id_}/activo")
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


# ── Fecha y hora (O2c, tanda 6; decisión 1.10): SOLO LECTURA ──────────────
# No hay ajuste: el reloj es el de Windows. Se informa la hora, la zona y si
# el reloj es anterior a la fecha de instalación (M1-01, clock_guard).

def _info_reloj(ahora: datetime | None = None) -> dict:
    ahora = (ahora or datetime.now()).astimezone()
    perfil = getattr(context, "profile", None)
    inst = getattr(perfil, "created_at", None) if perfil is not None else None
    inst = inst if isinstance(inst, datetime) else None
    off = ahora.utcoffset()
    minutos = int(off.total_seconds() // 60) if off is not None else 0
    signo = "+" if minutos >= 0 else "-"
    h, m = divmod(abs(minutos), 60)
    nombre = ahora.tzname() or ""
    zona = f"UTC{signo}{h:02d}:{m:02d}"
    if nombre and not nombre.startswith("UTC"):
        zona += f" ({nombre})"
    return {
        "ahora": ahora.isoformat(timespec="seconds"),
        "zona": zona,
        "utc_offset_min": minutos,
        "instalacion": inst.isoformat(timespec="seconds") if inst else None,
        "reloj_anterior_instalacion": bool(inst and ahora.date() < inst.date()),
        "ajuste_habilitado": False,
    }


@app.get("/system/time")
def get_system_time():
    return _info_reloj()


# ── Información del sistema (O2d, tanda 6; mockup 8): solo lectura ──────────
# Cada parte se lee por separado: un dato que falla queda en None ("—") sin
# afectar a los demás.

def _parte(lector):
    try:
        return lector()
    except Exception:
        logger.debug("Información del sistema: dato no disponible", exc_info=True)
        return None


def _hay_red() -> bool:
    """True si el PC tiene alguna dirección IPv4 distinta del loopback."""
    import socket
    nombre = socket.gethostname()
    return any(not ip.startswith("127.") for ip in socket.gethostbyname_ex(nombre)[2])


def _estado_impresora() -> str:
    if not context.config_impresora.habilitada():
        return "deshabilitada"
    estado = context.realtime_printer.estado()
    return estado if isinstance(estado, str) and estado else "desconocido"


@app.get("/system/info")
def get_system_info():
    import importlib.metadata
    perfil = getattr(context, "profile", None)

    def de_perfil(attr):
        v = getattr(perfil, attr, None) if perfil is not None else None
        if isinstance(v, datetime):
            return v.isoformat(timespec="seconds")
        return getattr(v, "value", v) if isinstance(v, (str, int, float)) or hasattr(v, "value") else None

    tarjeta = _parte(_tarjeta_status) or {}
    unidades = _parte(context.config_unidades.leer)
    red = _parte(_hay_red)
    return {
        "equipo": {"modelo": de_perfil("model_id"), "serie": de_perfil("serial_number"),
                   "instalacion": de_perfil("created_at"), "fuente_vapor": de_perfil("vapor_source")},
        "software": {"version": _parte(lambda: importlib.metadata.version("autoclave")),
                     "firmware": tarjeta.get("version") if isinstance(tarjeta, dict) else None,
                     "id_tarjeta": tarjeta.get("id") if isinstance(tarjeta, dict) else None},
        "uso": {"ciclos": _parte(context.db.max_numero_ciclo),
                "mantenimiento": _parte(context.mantenimiento.resumen)},
        "configuracion": {"idioma": _parte(context.config_idioma.leer),
                          "unidades": unidades if isinstance(unidades, dict) else None,
                          "impresora": _parte(_estado_impresora),
                          "red": None if red is None else ("conectada" if red else "sin_red")},
    }


# ── Bitácora de auditoría (O2e, tanda 6): solo lectura ────────────────────
# La ven admin, técnico e ingeniero; nadie edita ni borra (audit_log es de
# solo anexar, migración v4). Valores en la unidad vigente.

_POR_PAGINA_MAX = 100


@app.get("/audit_log")
def get_audit_log(pagina: int = 1, por_pagina: int = 20, desde: date | None = None,
                  hasta: date | None = None, usuario: str | None = None, evento: str | None = None,
                  sesion: Sesion = Depends(requiere_rol(ROL_ADMIN, ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime import bitacora
    pagina = max(1, pagina)
    por_pagina = max(1, min(por_pagina, _POR_PAGINA_MAX))
    filas, total = context.db.consultar_auditoria(
        desde=desde.isoformat() if desde else None,
        hasta=(hasta + timedelta(days=1)).isoformat() if hasta else None,
        usuario=usuario or None, evento=evento or None,
        limite=por_pagina, desplazamiento=(pagina - 1) * por_pagina)
    usuarios, eventos = context.db.valores_auditoria()
    try:
        metas = {p["clave"]: p for p in context.config_manager.describir()}
    except Exception:
        metas = {}
    try:
        unidades = context.config_unidades.leer()
        unidades = unidades if isinstance(unidades, dict) else {}
    except Exception:
        unidades = {}
    p_atm = _parte(_p_atm_vigente)
    paginas = max(1, (total + por_pagina - 1) // por_pagina)
    return {"filas": [bitacora.presentar(f, metas, unidades, p_atm) for f in filas],
            "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "paginas": paginas, "usuarios": usuarios, "tipos": eventos}


class _SuspensionBody(BaseModel):
    activa: StrictBool
    pantalla: str = ""


@app.post("/ui/standby")
def registrar_suspension(body: _SuspensionBody):
    """O2e: una pantalla QML informa que entró o salió de suspensión (solo
    bitácora; no cambia nada del equipo)."""
    _auditar("suspension_entra" if body.activa else "suspension_sale", usuario="sistema",
             entidad=body.pantalla[:40])
    return {"ok": True}


def _resolve_sensor_index(tipo: str, sensor: str) -> int:
    name_map = {"temperature": EstadoAutoclave.map_temp, "pressure": EstadoAutoclave.map_pres}.get(tipo)
    if name_map is None:
        raise HTTPException(status_code=404, detail=f"Tipo de sensor desconocido: {tipo}")
    if sensor not in name_map:
        raise HTTPException(status_code=404, detail=f"Sensor desconocido: {sensor}")
    return name_map[sensor]


@app.get("/calibration/{tipo}/{sensor}")
def get_calibration(tipo: str, sensor: str):
    index = _resolve_sensor_index(tipo, sensor)
    config = load_config(CALIBRATION_PATH)
    calib = (config.calibration.user.temperature if tipo == "temperature"
             else config.calibration.user.pressure)[index]
    last = _ultimo_cambio_calibracion(tipo, sensor)
    return {
        "sensor": sensor,
        "tipo": tipo,
        "is_poly": bool(calib.poly),
        "gain": calib.gain,
        "offset": calib.offset,
        "poly": calib.poly,
        "last_change": last,
    }


def _ultimo_cambio_calibracion(tipo: str, sensor: str) -> dict | None:
    """Último cambio: primero audit_log; si no hay, la tabla histórica
    sensor_calibration_audit (§5.10), que ya no recibe escrituras."""
    try:
        filas = context.db.get_auditoria(evento="calibracion_cambio",
                                         entidad=f"{tipo}/{sensor}", limite=1)
    except Exception:
        logger.exception("No se pudo leer audit_log")
        filas = []
    if isinstance(filas, list) and filas:
        fila = filas[0]
        try:
            ts = datetime.fromisoformat(fila["ts"]).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            ts = fila["ts"]
        return {"usuario": fila["usuario"], "timestamp": ts}
    return context.calibration_audit.get_last_change(tipo, sensor)


@app.patch("/calibration/{tipo}/{sensor}")
def update_calibration(tipo: str, sensor: str, body: dict = Body(...),
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Técnico e ingeniero (tanda 2026-10-14 §1.1, C-5; antes solo ingeniero).
    Técnico solo fuera de CICLO; el ingeniero también en CICLO, donde aplica de
    inmediato (§5.8). El usuario sale del token: un `usuario` en el cuerpo se
    ignora."""
    index = _resolve_sensor_index(tipo, sensor)

    try:
        shown_low  = float(body["shown_low"]);  real_low  = float(body["real_low"])
        shown_high = float(body["shown_high"]); real_high = float(body["real_high"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="shown_low, real_low, shown_high, real_high son obligatorios y numericos",
        )
    origen_lectura = body.get("origen_lectura")
    if "origen_lectura" in body and not (
            isinstance(origen_lectura, dict) and set(origen_lectura) == {"bajo", "alto"}
            and all(v in ("capturada", "escrita") for v in origen_lectura.values())):
        raise HTTPException(
            status_code=422,
            detail='origen_lectura debe ser {"bajo": "capturada"|"escrita", "alto": "capturada"|"escrita"}',
        )
    entidad = f"{tipo}/{sensor}"

    # S3a (tanda 2): plausibilidad por tipo de canal (catálogo). Lo imposible
    # se rechaza; una corrección grande pide confirmación explícita
    nivel, motivo = evaluar_calibracion(tipo, body, sensor)
    if nivel == "rechazo":
        _rechazar(422, "CALIBRACION_IMPLAUSIBLE", f"Calibración no plausible: {motivo}",
                  f"/calibration/{entidad}", sesion)
    confirmado = body.get("confirmar_fuera_de_rango") is True
    if nivel == "aviso" and not confirmado:
        _rechazar(409, "CALIBRACION_REQUIERE_CONFIRMACION",
                  f"Calibración fuera del rango habitual: {motivo}",
                  f"/calibration/{entidad}", sesion)

    # Solo comprobación bajo _sm_lock: el guard solo deja pasar en CICLO al
    # ingeniero (el técnico recibe 409), así que la escritura no necesita ser
    # atómica con la comprobación. YAML y recarga van fuera del
    # lock para no detener el tick (revisión de la etapa 1, hallazgo D).
    # SAF-05 de T8: sin base no hay auditoría; no se toca el archivo
    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "sin_base_de_datos", "Base de datos no disponible: calibración no aplicada",
                  f"/calibration/{entidad}", sesion)
    with guard_estado(DISTINTO_DE_CICLO, f"/calibration/{entidad}", sesion,
                      excepcion_ingeniero=True):
        contexto_ciclo = _contexto_ciclo()

    with _lock_archivos:
        config = load_config(CALIBRATION_PATH)
        user_list = (config.calibration.user.temperature if tipo == "temperature"
                     else config.calibration.user.pressure)
        old_calib = user_list[index]
        old_gain, old_offset = old_calib.gain, old_calib.offset

        try:
            fv_low  = invert_user_calibration(shown_low, old_calib.gain, old_calib.offset, old_calib.poly)
            fv_high = invert_user_calibration(shown_high, old_calib.gain, old_calib.offset, old_calib.poly)
            new_gain, new_offset = fit_two_point(fv_low, real_low, fv_high, real_high)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        # S3a (revisión): desviación ACUMULADA de la calibración resultante
        # respecto de la neutra, y canal con polinomio vigente (la recta nueva
        # lo reemplaza fuera de los puntos): aviso confirmable o rechazo
        nivel_acum, motivo_acum = evaluar_desviacion_acumulada(tipo, new_gain, new_offset, sensor)
        if old_calib.poly and nivel_acum is None:
            nivel_acum, motivo_acum = "aviso", ("el canal tiene un polinomio de calibración vigente: "
                                                 "la recta nueva lo reemplaza")
        if nivel_acum == "rechazo":
            _rechazar(422, "CALIBRACION_IMPLAUSIBLE", f"Calibración no plausible: {motivo_acum}",
                      f"/calibration/{entidad}", sesion)
        if nivel_acum == "aviso" and not confirmado:
            _rechazar(409, "CALIBRACION_REQUIERE_CONFIRMACION",
                      f"Calibración fuera del rango habitual: {motivo_acum}",
                      f"/calibration/{entidad}", sesion)
        if nivel_acum is not None and nivel is None:
            nivel, motivo = nivel_acum, motivo_acum

        # SAF-03 de T3: si un ciclo arrancó entre la comprobación y este
        # punto, el técnico no puede cambiar la calibración en curso
        if sesion.rol != ROL_INGENIERO:
            with context.control_loop.bloqueo_maquina():
                en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            if en_ciclo:
                raise HTTPException(status_code=409,
                                    detail="Hay un ciclo en curso: calibración no aplicada")
        detalle = {"puntos": {"shown_low": shown_low, "real_low": real_low,
                              "shown_high": shown_high, "real_high": real_high}}
        if nivel is not None:
            detalle["plausibilidad"] = {"nivel": nivel, "motivo": motivo,
                                        "confirmado": confirmado}
        if origen_lectura is not None:
            detalle["origen_lectura"] = dict(origen_lectura)
        detalle.update(contexto_ciclo)
        # BD-03 (T8, §7.6): sin registro en audit_log la calibración no queda
        # activa. Se guarda el archivo previo y se restaura si la auditoría falla.
        previo = Path(CALIBRATION_PATH).read_bytes()
        write_user_calibration(
            CALIBRATION_PATH, tipo, index, new_gain, new_offset,
            shown_low, real_low, shown_high, real_high,
        )
        context.units.reload_calibration(CALIBRATION_PATH)
        try:
            context.db.registrar_auditoria(
                "calibracion_cambio", usuario=sesion.usuario, rol=sesion.rol,
                entidad=entidad,
                valor_anterior={"gain": old_gain, "offset": old_offset},
                valor_nuevo={"gain": new_gain, "offset": new_offset},
                detalle=detalle)
        except Exception:
            logger.exception("Calibración %s sin auditoría: se revierte", entidad)
            # restauración atómica (SAF-05/TMG-05 de T8): temporal + fsync + replace
            ruta = Path(CALIBRATION_PATH)
            tmp = ruta.with_name(ruta.name + ".restaurar")
            with open(tmp, "wb") as f:
                f.write(previo)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ruta)
            context.units.reload_calibration(CALIBRATION_PATH)
            _rechazar(503, "auditoria_no_disponible",
                      "No se pudo registrar el cambio: calibración no aplicada",
                      f"/calibration/{entidad}", sesion)

    return {"ok": True, "gain": new_gain, "offset": new_offset}


@app.post("/calibration/{tipo}/{sensor}/restaurar")
def restaurar_calibracion(tipo: str, sensor: str, body: dict = Body(...),
                          sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """B-ES-4 / §7.4: devuelve el sensor a la calibración neutra ("defecto":
    ganancia 1.0, offset 0.0) o a los valores previos a la última modificación
    ("ultimo", de valor_anterior en audit_log). Mismas reglas que el PATCH:
    rol, estado, auditoría obligatoria con reversión del archivo."""
    index = _resolve_sensor_index(tipo, sensor)
    destino = body.get("destino")
    if destino not in ("ultimo", "defecto"):
        raise HTTPException(status_code=422, detail='destino debe ser "ultimo" o "defecto"')
    entidad = f"{tipo}/{sensor}"
    ruta = f"/calibration/{entidad}/restaurar"

    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "sin_base_de_datos", "Base de datos no disponible: calibración no aplicada",
                  ruta, sesion)
    with guard_estado(DISTINTO_DE_CICLO, ruta, sesion, excepcion_ingeniero=True):
        contexto_ciclo = _contexto_ciclo()

    with _lock_archivos:
        if destino == "defecto":
            nuevo_gain, nuevo_offset = 1.0, 0.0
        else:
            try:
                filas = context.db.get_auditoria(evento="calibracion_cambio",
                                                 entidad=entidad, limite=1)
                previo_json = filas[0]["valor_anterior"] if filas else None
                anterior = json.loads(previo_json) if isinstance(previo_json, str) else previo_json
                nuevo_gain, nuevo_offset = float(anterior["gain"]), float(anterior["offset"])
            except (IndexError, KeyError, TypeError, ValueError):
                _rechazar(409, "sin_calibracion_previa",
                          "No hay una calibración anterior que restaurar", ruta, sesion)

        config = load_config(CALIBRATION_PATH)
        user_list = (config.calibration.user.temperature if tipo == "temperature"
                     else config.calibration.user.pressure)
        old_gain, old_offset = user_list[index].gain, user_list[index].offset

        if sesion.rol != ROL_INGENIERO:
            with context.control_loop.bloqueo_maquina():
                en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            if en_ciclo:
                raise HTTPException(status_code=409,
                                    detail="Hay un ciclo en curso: calibración no aplicada")
        detalle = {"accion": f"restaurar_{destino}"}
        detalle.update(contexto_ciclo)
        previo = Path(CALIBRATION_PATH).read_bytes()
        write_user_calibration(CALIBRATION_PATH, tipo, index, nuevo_gain, nuevo_offset,
                               0.0, 0.0, 0.0, 0.0, nota=f"restaurada ({destino})")
        context.units.reload_calibration(CALIBRATION_PATH)
        try:
            context.db.registrar_auditoria(
                "calibracion_cambio", usuario=sesion.usuario, rol=sesion.rol,
                entidad=entidad,
                valor_anterior={"gain": old_gain, "offset": old_offset},
                valor_nuevo={"gain": nuevo_gain, "offset": nuevo_offset},
                detalle=detalle)
        except Exception:
            logger.exception("Restauración %s sin auditoría: se revierte", entidad)
            archivo = Path(CALIBRATION_PATH)
            tmp = archivo.with_name(archivo.name + ".restaurar")
            with open(tmp, "wb") as f:
                f.write(previo)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, archivo)
            context.units.reload_calibration(CALIBRATION_PATH)
            _rechazar(503, "auditoria_no_disponible",
                      "No se pudo registrar el cambio: calibración no aplicada", ruta, sesion)

    return {"ok": True, "gain": nuevo_gain, "offset": nuevo_offset}


def _diagnostico_comunicacion() -> dict | None:
    """Contadores y estado del enlace serial con la tarjeta (diagnóstico)."""
    try:
        diag = context.serial.get_diagnostico()
    except Exception:
        return None
    return diag if isinstance(diag, dict) else None


def _tarjeta_status() -> dict:
    """Versión e ID de la tarjeta de E/S del último handshake y si coincide
    con la emparejada en el perfil (FW-D7: solo advertencia, no bloquea)."""
    try:
        info = context.serial.tarjeta()
    except Exception:
        info = None
    if not isinstance(info, dict):
        info = {}
    ident = info.get("id")
    return {
        "version": info.get("version"),
        "id": ident,
        "emparejada": tarjeta_emparejada(getattr(context, "profile", None), ident),
    }


def _hora_iso(dt) -> str | None:
    return dt.isoformat(timespec="seconds") if dt is not None else None


def _alarma_dto(inst) -> dict:
    """Instancia de alarma → JSON de /status (spec 2026-10-06 §7.1). Los
    campos id/level/description/source_state mantienen compatible a la UI
    actual hasta la Parte C."""
    origen = inst.origen or ""
    from autoclave.core.runtime import alarmas_i18n
    return {
        # I1 (tanda 5): código + parámetros y los textos en cada idioma; la
        # descripción en español sigue siendo la registrada (compatibilidad)
        "valores": alarmas_i18n.valores_json(inst.valores),
        "textos": alarmas_i18n.por_idioma(inst.definicion, inst.valores or {}),
        "clave": inst.clave,
        "codigo": inst.codigo,
        "nivel": inst.nivel.name,
        "titulo": inst.titulo,
        "descripcion": inst.descripcion,
        "accion": inst.definicion.accion,
        "origen": origen,
        "aparecida": _hora_iso(inst.aparecida),
        "estado": inst.estado.value,
        "requiere_reconocimiento": inst.nivel.requiere_reconocimiento,
        "reconocida_por": inst.reconocida_por,
        "id": inst.clave,
        "level": inst.nivel.nombre_compat,
        "description": inst.descripcion,
        "source_state": origen,
    }


def _evento_dto(inst) -> dict:
    return {
        "codigo": inst.codigo,
        "titulo": inst.titulo,
        "descripcion": inst.descripcion,
        "origen": inst.origen or "",
        "hora": _hora_iso(inst.aparecida),
    }


def _estado_seguro_status() -> dict:
    """Protocolo de estado seguro (fin de ciclo §15): activo y si espera la
    confirmación "Confirmar y llevar a estado seguro"."""
    es = getattr(context.control_loop, "estado_seguro", None)
    activo = getattr(es, "activo", False) is True
    motivo = getattr(es, "bloqueado_motivo", None) if activo else None
    try:
        ack_confirma = getattr(context.control_loop.state_machine.ciclo,
                               "ack_confirma_estado_seguro", False) is True
    except Exception:
        ack_confirma = False
    return {"activo": activo,
            # P-6 (tanda 6): el CONFIRMAR del ciclo también confirma el estado seguro
            "ack_confirma_estado_seguro": ack_confirma,
            "requiere_confirmacion": activo and getattr(es, "requiere_confirmacion", False) is True,
            # S4: CIC-10 (el protocolo no puede terminar solo); None si avanza
            "bloqueado_motivo": motivo if isinstance(motivo, str) else None}


def _camara_segura_status(estado) -> dict:
    try:
        programas = context.programas_para_seguridad()
        vigentes = getattr(context.control_loop, "datos_vigentes", False) is True
        segura, motivo = camara_segura.evaluar(estado, context.config_manager, programas,
                                               getattr(context, "profile", None),
                                               datos_vigentes=vigentes,
                                               temp_max_ciclo=context.temp_max_tras_ciclo())
    except Exception as exc:
        logger.exception("/status: no se pudo evaluar camara_segura")
        segura, motivo = False, f"No se pudo evaluar: {exc}"
    campos = _campos_motivo(motivo)
    return {"camara_segura": segura, "no_abrir": not segura, "camara_segura_motivo": motivo,
            # I4 (tanda 6): código, parámetros y textos es/en del motivo (o None)
            "camara_segura_motivo_codigo": campos.get("motivo_codigo"),
            "camara_segura_motivo_valores": campos.get("motivo_valores"),
            "camara_segura_motivo_textos": campos.get("motivo_textos")}


def _campos_motivo(motivo) -> dict:
    """Código, parámetros y textos es/en de un motivo con código, en las
    unidades vigentes; {} si no tiene código o algo falla (nunca lanza)."""
    try:
        if not motivos.codigo_de(motivo):
            return {}
        from autoclave.core.runtime import unidades as u
        try:
            unidades = context.config_unidades.leer()
            t, p = unidades["temperatura"], unidades["presion"]
            u.validar(t, p)
        except Exception:
            t, p = "C", "kPa"
        try:
            p_atm = u.p_atm_valida(_p_atm_vigente())
        except Exception:
            p_atm = None
        return motivos.campos_respuesta(motivo, t, p, p_atm)
    except Exception:
        logger.exception("No se pudieron armar los textos del motivo")
        return {}


def _sensores_programa(estado) -> dict:
    try:
        programa = context.programa_para_sensores()
    except Exception:
        programa = None
    # una sola lectura de la asignación (TMG-05 de T3)
    instantanea = SimpleNamespace(sensores=dict(sc.asignacion_de(programa)))
    principal = sc.sensor_principal(instantanea)
    return {
        "sensor": principal,
        "nombre": sc.NOMBRES[principal],
        "valor": estado.sensores_temp.get(principal),
        "referencias": [{"sensor": s, "nombre": sc.NOMBRES[s],
                         "valor": estado.sensores_temp.get(s)}
                        for s in sc.sensores_referencia(instantanea)],
    }


def _cuentas_adc() -> dict:
    """B-ES-1: cuentas ADC crudas por sensor (clave de EstadoAutoclave).
    raw_ai: 0-7 temperatura, 8-15 presión. None si no hay datos de la tarjeta."""
    try:
        raw = context.units.get_all()["raw_ai"]
        if not isinstance(raw, (list, tuple)):
            raw = []
    except Exception:
        raw = []

    def cuenta(i):
        return raw[i] if i < len(raw) else None

    adc = {k: cuenta(i) for k, i in EstadoAutoclave.map_temp.items()}
    adc.update({k: cuenta(8 + i) for k, i in EstadoAutoclave.map_pres.items()})
    return adc


@app.get("/status", response_model=None)
def get_status():
    estado = context.estado

    # ------------------------------
    # ESTADO DE LA MÁQUINA
    # ------------------------------
    machine_state = None
    try:
        machine_state = estado.get_machine_state().name
    except Exception:
        machine_state = "DESCONOCIDO"

    # ------------------------------
    # ESTADO DE PUERTAS
    # ------------------------------
    doors = {
        door_name: door_state.name
        for door_name, door_state in estado.estado_puertas.items()
    }

    # ------------------------------
    # SENSORES
    # ------------------------------
    sensors = {
        "temperature": {
            "camara": estado.sensores_temp.get("temp_camara"),
            "camara_2": estado.sensores_temp.get("temp_2_camara"),
            "ref": estado.sensores_temp.get("temp_ref"),
            "drenaje": estado.sensores_temp.get("temp_drenaje"),
        },
        # Tanda §1.1: sensor Principal del programa vigente (seleccionado; en
        # CICLO, el del ciclo en curso) y sus Referencias
        "principal": _sensores_programa(estado),
        "pressure": {
            "camara": estado.sensores_pres.get("pres_camara"),
            "chaqueta": estado.sensores_pres.get("pres_chaqueta"),
            "empaque_1": estado.sensores_pres.get("pres_empaque_1"),
            "empaque_2": estado.sensores_pres.get("pres_empaque_2"),
        },
        "adc": _cuentas_adc(),
        "digital_inputs": dict(estado.sensores_di),

        "digital_outputs": dict(estado.salidas_do),

        "flags": dict(estado.flags),
    }

    # ------------------------------
    # ALARMAS
    # ------------------------------
    # Hasta la Parte C (botón de reconocer en la UI) las pantallas actuales solo
    # ven las ACTIVA en "alarms"; las RESUELTA_SIN_RECONOCER van aparte.
    instancias = context.alarm_manager.activas()
    alarms = [_alarma_dto(inst) for inst in instancias
              if inst.estado is EstadoInstancia.ACTIVA]
    alarmas_sin_reconocer = [_alarma_dto(inst) for inst in instancias
                             if inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER]
    eventos_recientes = [_evento_dto(inst) for inst in context.alarm_manager.eventos_recientes()]

    # ------------------------------
    # RESPUESTA FINAL (DTO)
    # ------------------------------
    return {
        "machine_state":        machine_state,
        # T8 (§7.1): operación sin base de datos (alarma OPERANDO_SIN_BD)
        "sin_base_de_datos":    getattr(context, "sin_base_de_datos", False) is True,
        "fase_ciclo":            getattr(estado, "fase_ciclo", ""),
        "fase_en_sostenimiento": getattr(estado, "fase_en_sostenimiento", False),
        "prevacio_progreso":     getattr(estado, "prevacio_progreso", ""),
        # Del enlace serial, no de Units: Units solo se entera por on_update
        # y no refleja el handshake (ver planeacion_protocolo_serial_esp32.md).
        # E2 (fin de ciclo §5): falla cerrada; "NO ABRIR" en cualquier estado
        **_camara_segura_status(estado),
        "estado_seguro":         _estado_seguro_status(),
        "card_connected":        context.serial.is_connected(),
        # U4 (tanda 2): desconectada / sin_tramas_validas / ok
        "estado_tarjeta":        _estado_tarjeta(),
        "comunicacion":          _diagnostico_comunicacion(),
        "tarjeta":               _tarjeta_status(),
        "test_mode_active":      context.control_loop.test_mode_active,
        "calibracion_atm_en_curso": _calibracion_atm_en_curso(),   # O2f
        "ui_inactividad_s":      actividad_ui.inactividad_s(),
        "doors":   doors,
        "sensors": sensors,
        "alarms":  alarms,
        # Entradas de suministro que el perfil declara sin cablear (E1-1)
        "entradas_no_monitoreadas": entradas_no_monitoreadas(getattr(context, "profile", None)),
        # Canales de temperatura que el perfil declara sin sonda (A-2)
        "sondas_no_vigiladas": sondas_no_vigiladas(getattr(context, "profile", None)),
        "alarmas_sin_reconocer": alarmas_sin_reconocer,
        "eventos_recientes": eventos_recientes,
    }

@app.post("/ui/activity")
def registrar_actividad_ui():
    """Una pantalla QML informa un toque/tecla del operador. Reinicia el
    contador de inactividad común a ambas pantallas (standby simultáneo)."""
    actividad_ui.registrar()
    return {"ok": True}


@app.get("/global_params")
def get_global_params():
    cm = context.config_manager
    return cm.instantanea() if hasattr(cm, "instantanea") else cm.get()


# ── Parámetros del equipo (O2a, tanda 6; planeacion_opciones.md v4 §3.2) ──
# Lectura libre (como /global_params). Cambio y restablecimiento: técnico e
# ingeniero (el admin los ve en solo lectura: 403, decisión 1.5), solo fuera de
# CICLO para todos (409, también el ingeniero) y aplicados sin reiniciar: el
# ConfigManager escribe en system_params y en memoria, y cada lector consulta
# el valor vigente (OPC-11). Auditoría `param_sistema_cambio`.
# La presión atmosférica de referencia no se cambia por aquí (solo O2f).

class _ParametroSistemaBody(BaseModel):
    valor: StrictInt | StrictFloat


_CODIGO_PARAMETRO = {
    "no_existe": (404, "Parámetro desconocido"),
    "solo_lectura": (403, "Este parámetro no se puede modificar"),
    "tipo_invalido": (422, "Valor inválido para este parámetro"),
    "fuera_de_rango": (422, "Valor fuera del rango permitido"),
    "incoherente": (422, "Valor incompatible con la presión atmosférica o el otro parámetro de empaque"),
    "sin_base_de_datos": (503, "No se pudo guardar el parámetro"),
}


def _parametro_o_404(clave: str) -> dict:
    from autoclave.core.managers.config_manager import ErrorParametro
    try:
        return context.config_manager.describir(clave)
    except ErrorParametro:
        raise RechazoApi(404, "no_existe", "Parámetro desconocido")


@app.get("/system_params")
def get_system_params():
    """Lista para la pantalla: valor vigente, defecto, rango, unidad, clase,
    submenú y último cambio (usuario y fecha)."""
    return {"parametros": context.config_manager.describir()}


@app.get("/global_params/{clave}")
def get_global_param(clave: str):
    return _parametro_o_404(clave)


def _cambiar_parametro_sistema(clave: str, sesion: Sesion, valor=None, restablecer=False):
    from autoclave.core.managers.config_manager import ErrorParametro
    entidad = f"/global_params/{clave}"
    p = _parametro_o_404(clave)
    if p["solo_lectura"]:
        _rechazar(403, "solo_lectura", _CODIGO_PARAMETRO["solo_lectura"][1], entidad, sesion)
    error = None
    # TMG-01: validación y escritura en SQLite FUERA del guard (no detienen el
    # tick); dentro solo se comprueba el estado y se publica en memoria. Si
    # mientras tanto arrancó un ciclo: 409 y se deshace la escritura.
    if _calibracion_atm_en_curso():         # O2f: la referencia está midiéndose
        _rechazar(409, "calibracion_en_curso", "Calibración atmosférica en curso", entidad, sesion)
    cm = context.config_manager
    with cm.lock_cambios:
        return _cambiar_serializado(cm, clave, p, entidad, sesion, valor, restablecer)


def _cambiar_serializado(cm, clave, p, entidad, sesion, valor, restablecer):
    from autoclave.core.managers.config_manager import ErrorParametro
    if _calibracion_atm_en_curso():         # TMG-03 de O2f: de nuevo, bajo lock_cambios
        _rechazar(409, "calibracion_en_curso", "Calibración atmosférica en curso", entidad, sesion)
    error = None
    try:
        if restablecer:
            anterior, nuevo = cm.restablecer(clave, sesion.usuario, aplicar=False)
        else:
            anterior, nuevo = cm.fijar(clave, valor, sesion.usuario, aplicar=False)
    except ErrorParametro as e:
        error = e
    if error is None:
        try:
            with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
                cm.aplicar_valor(p["clave"], nuevo, sesion.usuario)
        except RechazoApi:
            cm.revertir_bd(p["clave"], anterior)
            raise
    if error is not None:
        status, motivo = _CODIGO_PARAMETRO.get(error.codigo, (422, "Valor inválido"))
        if status in (401, 403, 409):
            _rechazar(status, error.codigo, motivo, entidad, sesion)
        raise RechazoApi(status, error.codigo, motivo,
                         extra={"min": p["min"], "max": p["max"]} if error.codigo == "fuera_de_rango" else None)
    _auditar("param_sistema_cambio", sesion, entidad=entidad,
             valor_anterior={p["clave"]: anterior}, valor_nuevo={p["clave"]: nuevo},
             detalle={"clave": p["clave"], "accion": "restablecer" if restablecer else "cambio"})
    return {"ok": True, "parametro": context.config_manager.describir(p["clave"])}


@app.patch("/global_params/{clave}")
def patch_global_param(clave: str, body: _ParametroSistemaBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    return _cambiar_parametro_sistema(clave, sesion, valor=body.valor)


@app.post("/global_params/{clave}/reset")
def reset_global_param(clave: str,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    return _cambiar_parametro_sistema(clave, sesion, restablecer=True)


@app.get("/cycle")
def get_selected_cycle():
    cycle = context.cycle_manager.get_selected_cycle()

    if cycle is None:
        raise HTTPException(status_code=404, detail="No hay ciclo seleccionado")

    return {
        "id": cycle.id,
        "name": cycle.name,
        "nombres": _nombres_ciclo(cycle),
        "number": getattr(cycle, "number", None),
        "parameters": cycle.parameters,
        **_entradas_mostradas_de(cycle),
    }


# Sensor de temperatura del programa (sensores_ciclo) -> nombre de la AI
_AI_DE_SENSOR = {"temp_camara": "temp_camara", "temp_2_camara": "temp_2_camara",
                 "temp_ref": "temp_referencia"}


def _entradas_mostradas_de(cycle) -> dict:
    """O3 (tanda 6): entradas mostradas (1 a 3) del programa para Preciclo,
    Ciclo y gráfica, y las que tienen el sensor "No en uso" en el programa.
    Solo presentación; ante cualquier error, las de omisión."""
    from autoclave.core.managers import gestion_programas as gp
    try:
        entradas = gp.entradas_de(cycle, _ai_habilitadas())
    except Exception:
        entradas = list(gp.ENTRADAS_POR_OMISION)
    try:
        asignacion = sc.asignacion_de(cycle)
        no_en_uso = [_AI_DE_SENSOR[s] for s, rol in asignacion.items()
                     if rol == sc.NO_EN_USO and s in _AI_DE_SENSOR]
    except Exception:
        no_en_uso = []
    return {"entradas_mostradas": entradas, "entradas_no_en_uso": no_en_uso}


def _nombres_ciclo(cycle) -> dict:
    """I4 (tanda 6; D-14): nombre del ciclo en es y en (catálogo para los de
    fábrica). `name`/`nombre` siguen siendo el display_name."""
    try:
        return context.cycle_manager.nombres_de(cycle)
    except Exception:
        return {"es": cycle.name, "en": cycle.name}


@app.get("/cycles")
def list_cycles():
    return [
        {"id": c.id, "name": c.name, "nombres": _nombres_ciclo(c),
         "source": getattr(c, "source", "user")}
        for c in list(context.cycle_manager.cycles.values())
    ]


# S2 (tanda 2): origen declarado por el cliente (no autenticado) del cambio de
# programa, para la bitácora. Lista cerrada: un valor desconocido se rechaza.
ORIGENES_SELECCION = ("puerta_1", "puerta_2", "remoto", "desconocido")


class _SelectCycleBody(BaseModel):
    cycle_id: str
    # Opcional: el endpoint sigue sin sesión (decisión 2 de Cristian)
    origen: str | None = None


@app.post("/cycle/select")
def select_cycle(body: _SelectCycleBody, request: Request):
    """Cambia el programa activo. Sin sesión y permitido en FALLA (decisión 2
    de Cristian, 19-oct: ningún fallo exige técnico). Rechazado con un ciclo
    en curso en sentido amplio (ControlLoop._motivo_no_cambiar_ciclo), con un
    programa dañado (RB-04.4) y con un programa de líquidos en un equipo sin
    esa capacidad (T11). El cambio y todos sus rechazos quedan en audit_log
    con el origen DECLARADO (no autenticado), el cliente HTTP y el estado (S2).
    Lectura del programa anterior, cambio en el lazo y en el CycleManager van
    juntos bajo el lock de la máquina; la bitácora se escribe al soltarlo."""
    entidad = "/cycle/select"
    detalle = {"origen": body.origen or "desconocido",
               "origen_autenticado": False,
               "cliente": request.client.host if request.client else ""}
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    nombre = getattr(cycle, "name", None)

    def rechazar(status: int, codigo: str, motivo: str, anterior=None, estado=""):
        _auditar("PROGRAMA_SELECCION_RECHAZADA", entidad=entidad,
                 valor_anterior=anterior, valor_nuevo=body.cycle_id,
                 detalle={**detalle, "estado": estado or _nombre_estado(),
                          "codigo": codigo, "motivo": motivo, "programa": nombre})
        raise RechazoApi(status, codigo, motivo)

    if detalle["origen"] not in ORIGENES_SELECCION:
        rechazar(422, "origen_invalido",
                 "Origen desconocido: %r (válidos: %s)"
                 % (detalle["origen"][:40], ", ".join(ORIGENES_SELECCION)))
    if cycle is None:
        rechazar(404, "programa_no_encontrado", f"Ciclo '{body.cycle_id}' no encontrado")
    if getattr(cycle, "source", "user") != "user":
        rechazar(422, "programa_de_fabrica", "Solo se pueden seleccionar ciclos de usuario")
    # RB-04.4 (T10): un programa dañado no es ejecutable
    if getattr(cycle, "danado", None):
        rechazar(409, "PROGRAMA_NO_EDITABLE",
                 f"Programa dañado (fuera del catálogo): {cycle.danado[0]}")
    # O1 (tanda 5): un programa deshabilitado no se selecciona
    if getattr(cycle, "habilitado", True) is False:
        rechazar(409, "programa_deshabilitado", "Programa deshabilitado")
    # T11 (revisión de S2): líquidos solo en equipos con esa capacidad
    if _carga_liquida(cycle) and getattr(getattr(context, "cap", None), "has_liquids", None) is False:
        rechazar(409, "carga_liquida_no_disponible",
                 "Este equipo no admite programas de carga líquida")

    loop = context.control_loop
    with loop.bloqueo_maquina():
        anterior = getattr(getattr(loop, "cycle", None), "id", None)
        estado = _nombre_estado()
        ok, reason = loop.set_active_cycle(cycle)
        if ok:
            context.cycle_manager.set_default_cycle(body.cycle_id)
    detalle["estado"] = estado
    if not ok:
        rechazar(409, "cambio_no_permitido", reason, anterior=anterior, estado=estado)

    _auditar("PROGRAMA_SELECCIONADO", entidad=entidad, valor_anterior=anterior,
             valor_nuevo=body.cycle_id, detalle={**detalle, "programa": nombre})
    return {"ok": True, "id": cycle.id, "name": cycle.name}

@app.get("/cycle/current/readings")
def get_current_cycle_readings():
    """
    Retorna todas las lecturas del ciclo activo (para la gráfica en vivo).
    Si no hay ciclo activo retorna lista vacía.
    """
    logger_svc = context.cycle_logger
    ciclo_id   = logger_svc.ciclo_id if logger_svc else None

    if ciclo_id is None:
        return {"ciclo_id": None, "lecturas": []}

    rows = context.db.get_lecturas_ciclo(ciclo_id)
    return {
        "ciclo_id": ciclo_id,
        "lecturas": [
            {
                "timestamp_rel": r["timestamp_rel"],
                "timestamp_abs": r["timestamp_abs"],
                "fase_codigo":   r["fase_codigo"],
                "temp_camara":   r["temp_camara"],
                "pres_camara":   r["pres_camara"],
            }
            for r in rows
        ],
    }


def _ciclo_de_pantalla() -> int | None:
    """ID en BD del ciclo que muestra la pantalla de ciclo en curso, o None
    si la máquina no está en CICLO."""
    from autoclave.state_machine.machine.enum_global import GlobalState
    if context.estado.get_machine_state() != GlobalState.CICLO:
        return None
    logger_svc = context.cycle_logger
    return logger_svc.ciclo_id_pantalla if logger_svc else None


@app.get("/cycle/current/progress")
def get_current_cycle_progress():
    """Progreso del ciclo en curso para la pantalla QML (fases que aplican,
    fase activa, duración por fase, transcurrido y restante en segundos
    monotónicos). Separado de /status para no cargar su sondeo de 200 ms.
    Sigue respondiendo con el ciclo terminado mientras la máquina espera la
    confirmación del operador. Sin ciclo: {"activo": false}."""
    ciclo_id = _ciclo_de_pantalla()
    transcurrido = context.cycle_logger.transcurrido_s() if ciclo_id is not None else None
    if ciclo_id is None or transcurrido is None:
        return {"activo": False}

    # las fases que aplican salen de la copia con la que corre el ciclo (T-17)
    cycle = context.control_loop.programa_en_ejecucion()
    aplicables = progreso_ciclo.fases_aplicables(cycle, context.cap)
    filas = [dict(f) for f in context.db.get_fases_ciclo(ciclo_id)]

    fila_ciclo = context.db.get_ciclo(ciclo_id)
    tipo = fila_ciclo["tipo_ciclo"] if fila_ciclo is not None else getattr(cycle, "id", "")
    referencias = {}
    for fase, duracion in context.db.get_duraciones_referencia(tipo).items():
        fase_ui = progreso_ciclo.fase_ui(fase)
        if fase_ui is not None:
            referencias[fase_ui] = referencias.get(fase_ui, 0.0) + duracion

    fase_ciclo = getattr(context.estado, "fase_ciclo", "") or ""
    return {
        "activo": True,
        "ciclo_db_id": ciclo_id,
        "fase_ciclo": fase_ciclo,
        **progreso_ciclo.armar_progreso(aplicables, filas, fase_ciclo, transcurrido, referencias),
    }


@app.get("/cycle/current/graph")
def get_current_cycle_graph(desde_id: int | None = None):
    """Serie de la gráfica del ciclo en curso (~1 s, t_s monotónico, con
    temp_ref). Sin desde_id devuelve el histórico completo (al entrar o tras
    reiniciar la UI); con desde_id solo las lecturas posteriores a ese id."""
    ciclo_id = _ciclo_de_pantalla()
    if ciclo_id is None:
        return {"ciclo_db_id": None, "lecturas": []}
    rows = context.db.get_lecturas_grafica(ciclo_id, desde_id)
    return {
        "ciclo_db_id": ciclo_id,
        "lecturas": [
            {
                "id":          r["id"],
                "t_s":         r["t_s"],
                "fase":        r["fase"],
                "fase_ui":     progreso_ciclo.fase_ui(r["fase"]),
                "temp_camara": r["temp_camara"],
                "temp_ref":    r["temp_ref"],
                "pres_camara": r["pres_camara"],
            }
            for r in rows
        ],
    }


def _inicio_del_dia() -> str:
    """Medianoche local en el formato de ciclos.fecha_fin (ISO sin zona, hora
    local del equipo). Reloj de pared: solo para presentar "ciclos hoy", no
    temporiza nada del proceso (C-01)."""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _rango_del_periodo(periodo: str, fecha: date) -> tuple[str, str]:
    """Periodo de calendario que contiene `fecha` (Historial, utils/periodos.py):
    (desde, hasta) como medianoche local en el formato de la tabla ciclos; `hasta`
    es exclusivo (medianoche del primer día del periodo siguiente)."""
    inicio, fin = periodos.rango(periodo, fecha)
    return datetime.combine(inicio, time()).isoformat(), datetime.combine(fin, time()).isoformat()


def _ciclo_json(fila) -> dict:
    """Un ciclo de la tabla `ciclos` para el Menú Principal. El número de programa
    no se guarda en `ciclos`: se toma del programa actual con ese id (None si ya
    no existe o no tiene número)."""
    programa = context.cycle_manager.cycles.get(fila["tipo_ciclo"])
    return {
        "id":              fila["id"],   # para pedir su curva a /cycle/history/{id}/graph
        "numero_ciclo":    fila["numero_ciclo"],
        "fecha_inicio":    fila["fecha_inicio"],
        "fecha_fin":       fila["fecha_fin"],
        "programa_id":     fila["tipo_ciclo"],
        "programa_nombre": fila["nombre_ciclo"],
        "programa_numero": getattr(programa, "number", None),
        "resultado":       fila["resultado"],
        # CycleLogger hoy no lo guarda (siempre ''): queda None hasta que exista
        # el registro de operadores (B-02 de planeacion_menu_principal.md)
        "operador":        fila["operador"] or None,
    }


# ── Mantenimiento (M1, tanda 3) ─────────────────────────────────────────────
# Solo informa: nunca bloquea ni interviene en un ciclo. La lectura es abierta
# (la ve el Menú Principal sin sesión); configurar y registrar exigen técnico o
# ingeniero y quedan en la bitácora.

class _MantenimientoConfigBody(BaseModel):
    intervalo_dias: int
    intervalo_ciclos: int


class _MantenimientoRegistroBody(BaseModel):
    tipo: str
    observaciones: str = ""


def _rechazo_mantenimiento(e, entidad: str, sesion) -> None:
    estado = 422 if e.codigo == "validacion" else 409
    _rechazar(estado, e.codigo, e.motivo, entidad, sesion)


@app.get("/maintenance")
def get_maintenance():
    """Próximo vencimiento, último mantenimiento, ciclos restantes y los
    intervalos configurados (por defecto 365 días y 1000 ciclos)."""
    return context.mantenimiento.resumen()


@app.get("/maintenance/records")
def get_maintenance_records(limite: int = 50,
                            sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    return {"registros": context.mantenimiento.historial(max(1, min(limite, 500)))}


@app.put("/maintenance/config")
def put_maintenance_config(body: _MantenimientoConfigBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime.servicio_mantenimiento import ErrorMantenimiento
    entidad = "/maintenance/config"
    anterior = context.mantenimiento.configuracion()
    try:
        nueva = context.mantenimiento.guardar_configuracion(body.intervalo_dias,
                                                            body.intervalo_ciclos)
    except ErrorMantenimiento as e:
        _rechazo_mantenimiento(e, entidad, sesion)
    _auditar("mantenimiento_configurado", sesion, entidad=entidad,
             valor_anterior=anterior, valor_nuevo=nueva)
    context.mantenimiento.evaluar_alarma()
    return {"ok": True, "configuracion": nueva}


@app.post("/maintenance/records")
def post_maintenance_record(body: _MantenimientoRegistroBody,
                            sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """"Registrar mantenimiento realizado": desde ese momento la base del
    cálculo pasa a ser hoy y el contador de ciclos actual."""
    from autoclave.core.runtime.servicio_mantenimiento import ErrorMantenimiento
    entidad = "/maintenance/records"
    try:
        registro = context.mantenimiento.registrar(sesion.usuario, body.tipo, body.observaciones)
    except ErrorMantenimiento as e:
        _rechazo_mantenimiento(e, entidad, sesion)
    _auditar("mantenimiento_registrado", sesion, entidad=entidad, valor_nuevo=registro,
             detalle={"observaciones": body.observaciones[:200]})
    return {"ok": True, "registro": registro}


# ── Impresora (B5, tanda 4) ─────────────────────────────────────────────────
# `habilitada` solo gobierna la verificación de arranque y el aviso de impresora
# desconectada; no impide imprimir ni bloquea nada.

# ── Idioma (I1, tanda 5; planeacion_i18n.md §5 F2) ───────────────────────
# Admin e ingeniero (decisión 1.9, tanda 6), también en ciclo (no afecta al control). R-06
# sigue vigente: el inglés no se habilita en campo hasta cerrar la voz; el
# endpoint existe, pero ninguna pantalla de operador ofrece el selector.

class _IdiomaBody(BaseModel):
    idioma: Literal["es", "en"]


@app.get("/language")
def get_language():
    return {"idioma": context.config_idioma.leer()}


@app.put("/language")
def put_language(body: _IdiomaBody,
                 sesion: Sesion = Depends(requiere_rol(ROL_ADMIN, ROL_INGENIERO))):
    """Decisión 1.9 (tanda 6): admin e ingeniero; también en ciclo."""
    entidad = "/language"
    anterior = context.config_idioma.leer()
    try:
        context.config_idioma.guardar(body.idioma)
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar el idioma", entidad, sesion)
    _auditar("idioma_configurado", sesion, entidad=entidad,
             valor_anterior={"idioma": anterior}, valor_nuevo={"idioma": body.idioma})
    return {"ok": True, "idioma": body.idioma}


# ── Unidades de presentación (U1, tanda 5; decisión 6 de Cristian) ─────────
# Solo presentación y entrada de datos: el control, la BD, los JSON y esta API
# siguen en °C y kPa absolutos. P_atm es la calibrada del equipo; sin valor
# vigente se publica null y la UI no muestra psi.

class _UnidadesBody(BaseModel):
    temperatura: Literal["C", "F"]
    presion: Literal["kPa", "bar", "mbar", "psi"]


def _p_atm_vigente():
    try:
        v = context.config_manager.get("presion_admosferica")
    except Exception:
        return None
    from autoclave.core.runtime.unidades import p_atm_valida
    return p_atm_valida(v)       # fuera de 50-110 kPa: null (la UI no muestra psi)


@app.get("/units")
def get_units():
    return {**context.config_unidades.leer(), "p_atm": _p_atm_vigente()}


@app.put("/units")
def put_units(body: _UnidadesBody,
              sesion: Sesion = Depends(requiere_rol(ROL_INGENIERO))):
    """Decisión 1.9 (tanda 6): solo el ingeniero, y solo fuera de ciclo (también el ingeniero: un
    cambio de unidades a mitad de ciclo se presta a leer mal un valor)."""
    entidad = "/units"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        anterior = context.config_unidades.leer()
    try:
        nuevo = context.config_unidades.guardar(body.temperatura, body.presion)
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar la configuración",
                  entidad, sesion)
    _auditar("unidades_configuradas", sesion, entidad=entidad,
             valor_anterior=anterior, valor_nuevo=nuevo)
    return {"ok": True, **nuevo}


class _ImpresoraConfigBody(BaseModel):
    habilitada: StrictBool     # P2: solo el literal JSON true/false (SAF-06)


@app.get("/printer/config")
def get_printer_config():
    return {"habilitada": context.config_impresora.habilitada()}


@app.put("/printer/config")
def put_printer_config(body: _ImpresoraConfigBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = "/printer/config"
    anterior = context.config_impresora.habilitada()
    try:
        context.config_impresora.guardar(body.habilitada)
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar la configuración",
                  entidad, sesion)
    _auditar("impresora_configurada", sesion, entidad=entidad,
             valor_anterior={"habilitada": anterior}, valor_nuevo={"habilitada": body.habilitada})
    try:
        context.aplicar_config_impresora()   # el aviso SIS-05 sigue a la bandera
    except Exception:
        logger.exception("No se pudo aplicar la configuración de la impresora")
    return {"ok": True, "habilitada": body.habilitada}


# ── Calibración atmosférica e impresiones de Mantenimiento (O2f, tanda 6) ──
# planeacion_opciones.md v4 §5 y planeacion_backend_parametros.md §8. Técnico e
# ingeniero. La medición corre en su hilo (core/runtime/calibracion_atm.py) y
# solo lee; la referencia se escribe con la función interna del ConfigManager
# (permitir_solo_lectura) y se publica en memoria dentro de _sm_lock (sin E/S),
# igual que un parámetro del equipo (TMG-01 de O2a). Mientras mide, los
# parámetros del equipo no se cambian (409 calibracion_en_curso).

_calibracion_atm_obj = None
_calibracion_atm_lock = threading.Lock()


def _leer_para_calibracion_atm() -> dict:
    # TMG-02 de O2f: instantánea coherente bajo _sm_lock (solo memoria)
    with context.control_loop.bloqueo_maquina():
        return _leer_para_calibracion_atm_sin_lock()


def _leer_para_calibracion_atm_sin_lock() -> dict:
    estado = context.estado
    try:
        maquina = estado.get_machine_state().name
    except Exception:
        maquina = ""
    try:
        programas = context.programas_para_seguridad()
        temp = sc.temp_seguridad(estado, programas, getattr(context, "profile", None))
    except Exception:
        temp = None
    return {"estado_maquina": maquina,
            "puertas": dict(getattr(estado, "estado_puertas", {}) or {}),
            "temp": temp,
            "pres": estado.sensores_pres.get("pres_camara"),
            "datos_vigentes": getattr(context.control_loop, "datos_vigentes", False) is True}


def _aplicar_presion_atmosferica(valor: float, usuario: str) -> None:
    """Escribe la referencia: base fuera del lock de la máquina; memoria
    dentro, y solo fuera de CICLO. Lanza ErrorParametro si no se puede."""
    from autoclave.core.managers.config_manager import ErrorParametro
    cm = context.config_manager
    with cm.lock_cambios:
        anterior, nuevo = cm.fijar("presion_atmosferica", valor, usuario,
                                   permitir_solo_lectura=True, aplicar=False)
        aplicado = False
        try:
            with context.control_loop.bloqueo_maquina():
                if context.estado.get_machine_state() == GlobalState.CICLO:
                    raise ErrorParametro("estado_no_permitido")
                cm.aplicar_valor("presion_atmosferica", nuevo, usuario)
                aplicado = True
        finally:
            if not aplicado:
                cm.revertir_bd("presion_atmosferica", anterior)


def _auditar_calibracion_atm(evento, usuario, rol, anterior, nuevo, detalle) -> None:
    context.db.registrar_auditoria(
        evento, usuario=usuario or "", rol=rol or "", entidad="presion_atmosferica",
        valor_anterior={"presion_atmosferica": anterior},
        valor_nuevo={"presion_atmosferica": nuevo} if nuevo is not None else None,
        detalle=detalle)


def _auditar_seguro(funcion, *args) -> None:
    try:
        funcion(*args)
    except Exception:
        logger.exception("No se pudo registrar la calibración atmosférica en audit_log")


def _calibracion_atm():
    global _calibracion_atm_obj
    with _calibracion_atm_lock:
        if _calibracion_atm_obj is None:
            from autoclave.core.runtime.calibracion_atm import CalibracionAtm
            _calibracion_atm_obj = CalibracionAtm(
                leer=_leer_para_calibracion_atm,
                aplicar=_aplicar_presion_atmosferica,
                auditar=lambda *a: _auditar_seguro(_auditar_calibracion_atm, *a),
                anterior=lambda: context.config_manager.get("presion_atmosferica"))
        return _calibracion_atm_obj


def _calibracion_atm_en_curso() -> bool:
    obj = _calibracion_atm_obj
    return obj is not None and obj.en_curso


def _estado_calibracion_atm() -> dict:
    d = _calibracion_atm().estado()
    try:
        ref = context.config_manager.describir("presion_atmosferica")
        um = ref.get("ultima_modificacion") or {}
        d["referencia"] = {"valor": ref.get("valor"), "usuario": um.get("usuario"),
                           "fecha": um.get("fecha")}
    except Exception:
        d["referencia"] = {"valor": None, "usuario": None, "fecha": None}
    return d


_MOTIVO_CONDICION_ATM = {
    "en_curso": "Ya hay una calibración en curso",
    "puerta_abierta": "La puerta debe estar abierta",
    "temp_baja": "La cámara debe estar por debajo de 80 °C",
    "fuera_de_ciclo": "No se puede calibrar con un ciclo en curso",
    "lecturas_validas": "Sin lectura válida de presión o temperatura de cámara",
}


@app.get("/maintenance/atm-calibration")
def get_atm_calibration():
    return _estado_calibracion_atm()


@app.post("/maintenance/atm-calibration/start")
def start_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = "/maintenance/atm-calibration/start"
    with context.config_manager.lock_cambios:      # TMG-03: no se cruza con un PATCH
        ok, codigo = _calibracion_atm().iniciar(sesion.usuario, sesion.rol)
    if not ok:
        _rechazar(409, "calibracion_en_curso" if codigo == "en_curso" else "precondicion",
                  _MOTIVO_CONDICION_ATM.get(codigo, "No se puede iniciar"), entidad, sesion,
                  extra={"condicion": codigo})
    return _estado_calibracion_atm()


@app.post("/maintenance/atm-calibration/cancel")
def cancel_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    if not _calibracion_atm().cancelar(sesion.usuario, sesion.rol):
        raise RechazoApi(409, "sin_calibracion", "No hay calibración en curso")
    return _estado_calibracion_atm()


@app.post("/maintenance/atm-calibration/confirm")
def confirm_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    ok, codigo = _calibracion_atm().confirmar(sesion.usuario, sesion.rol)
    if not ok:
        raise RechazoApi(409, codigo or "no_aplicada", "No se pudo aplicar la calibración")
    return _estado_calibracion_atm()


@app.post("/maintenance/atm-calibration/discard")
def discard_atm_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    if not _calibracion_atm().descartar(sesion.usuario, sesion.rol):
        raise RechazoApi(409, "sin_pendiente", "No hay calibración por confirmar")
    return _estado_calibracion_atm()


def _meta_equipo() -> dict:
    perfil = getattr(context, "profile", None)
    serie = getattr(perfil, "serial_number", "")
    modelo = getattr(perfil, "model_id", "")
    return {"serie": serie if isinstance(serie, str) else "",
            "modelo": modelo if isinstance(modelo, str) else ""}


@app.post("/printer/test-page")
def print_test_page(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Página de prueba de la impresora térmica (409 en ciclo; 503 sin impresora)."""
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    _encolar_en_impresora([tm.pagina_prueba(_meta_equipo())])
    _auditar("impresora_prueba", sesion, entidad="/printer/test-page")
    return {"ok": True}


@app.post("/maintenance/print/calibration")
def print_calibration(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Imprime ganancias y compensaciones (de usuario) de todos los sensores
    y la presión atmosférica de referencia."""
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    config = load_config(CALIBRATION_PATH)
    sensores = []
    for tipo, mapa, lista in (("temperature", EstadoAutoclave.map_temp,
                               config.calibration.user.temperature),
                              ("pressure", EstadoAutoclave.map_pres,
                               config.calibration.user.pressure)):
        for nombre, i in mapa.items():
            if i < len(lista):
                c = lista[i]
                sensores.append({"tipo": tipo, "sensor": nombre, "gain": c.gain,
                                 "offset": c.offset, "poly": bool(c.poly)})
    try:
        ref = context.config_manager.describir("presion_atmosferica")
    except Exception:
        ref = {}
    texto = tm.ganancias(_meta_equipo(), sensores, ref.get("valor"),
                         (ref.get("ultima_modificacion") or {}).get("fecha"))
    _encolar_en_impresora([texto])
    _auditar("impresion_ganancias", sesion, entidad="/maintenance/print/calibration",
             detalle={"sensores": len(sensores)})
    return {"ok": True, "sensores": len(sensores)}


# ── Conectividad (O2g, tanda 6; decisiones 1.4 y 1.9) ───────────────────────
# Red en SOLO LECTURA (cambiar Wi-Fi o IP no se habilita: DECISIÓN SIN
# CONFIRMAR). Correo de ciclos: admin, técnico e ingeniero leen; admin e
# ingeniero cambian destinatarios e interruptor (el técnico, 403) y envían el
# correo de prueba. La contraseña del relay nunca se devuelve ni se registra:
# solo `contrasena_configurada`. Cambios con ciclo en curso: 409 (R-01).

_LEEN_CONECTIVIDAD = (ROL_ADMIN, ROL_TECNICO, ROL_INGENIERO)
_EDITAN_CORREO = (ROL_ADMIN, ROL_INGENIERO)


class _CorreoConfigBody(BaseModel):
    envio_activo: StrictBool
    destinatarios: list[dict]


def _cargar_config_correo():
    from autoclave.ui_qml.exportacion import config_correo
    return config_correo.cargar()


def _enviar_correo(config, mensaje) -> None:
    """C2 (tanda 7): correo.enviar ya no lanza si el relay rechaza a todos
    (devuelve el resultado por destinatario); aquí eso sigue siendo un fallo."""
    import smtplib
    from autoclave.ui_qml.exportacion import correo
    r = correo.enviar(config, mensaje)
    if not isinstance(r, correo.ResultadoEnvio) or r.ninguno_aceptado:
        raise smtplib.SMTPRecipientsRefused(dict(getattr(r, "rechazados", {}) or {}))


# C2 (tanda 7): bitácora de los envíos del Historial y de Reportes. El envío lo
# hace la UI (ui_qml/bridge/acciones_ciclos.py), que no tiene la base; aquí
# solo se registra. Sin sesión obligatoria: el Menú Principal envía sin
# iniciar sesión, y el backend solo escucha en 127.0.0.1 (backend/main.py). Si
# llega un token válido, se anota el usuario. El cuerpo se valida a mano para
# que un 422 nunca repita lo recibido (podría traer algo que no debe salir).
_MAX_DIRECCIONES_REGISTRO = 20


class _CorreoEnviadoBody(BaseModel):
    model_config = {"extra": "forbid"}
    tipo: Literal["ciclos", "resumen", "consolidado"]
    destinatarios: list[str] = Field(default_factory=list, max_length=_MAX_DIRECCIONES_REGISTRO)
    manuales: list[str] = Field(default_factory=list, max_length=_MAX_DIRECCIONES_REGISTRO)
    ciclos: list[StrictInt] = Field(default_factory=list, max_length=500)
    aceptados: list[str] = Field(default_factory=list, max_length=_MAX_DIRECCIONES_REGISTRO)
    rechazados: dict[str, StrictInt] = Field(default_factory=dict,
                                              max_length=_MAX_DIRECCIONES_REGISTRO)
    resultado: Literal["enviado", "parcial", "rechazado", "error_conexion",
                       "error_autenticacion", "sin_confirmacion"]


@app.post("/email/sent")
def post_email_sent(body: dict, authorization: str | None = Header(None)):
    entidad = "/email/sent"
    try:
        datos = _CorreoEnviadoBody.model_validate(body)
    except Exception:
        raise RechazoApi(422, "validacion", "Datos inválidos")
    direcciones = (datos.destinatarios + datos.manuales + datos.aceptados
                   + list(datos.rechazados))
    if any(not isinstance(d, str) or len(d) > 254 for d in direcciones):
        raise RechazoApi(422, "validacion", "Datos inválidos")
    sesion = tokens.obtener(_token_de(authorization))
    _auditar("correo_enviado", sesion, entidad=entidad, detalle=datos.model_dump())
    return {"ok": True}


@app.get("/network/status")
def get_network_status(sesion: Sesion = Depends(requiere_rol(*_LEEN_CONECTIVIDAD))):
    return context.estado_red.leer()


def _correo_dto() -> dict:
    from autoclave.core.runtime.config_correo_equipo import MAX_DESTINATARIOS
    equipo = context.config_correo_equipo.leer()
    try:
        base = _cargar_config_correo()
        remitente, servidor, puerto = base.remitente, base.servidor, base.puerto
        con_clave = bool(base.contrasena)
    except Exception:
        logger.exception("No se pudo leer la configuración de correo")
        remitente, servidor, puerto, con_clave = "", "", None, False
    return {"envio_activo": equipo["envio_activo"], "destinatarios": equipo["destinatarios"],
            "personalizado": equipo["personalizado"], "remitente": remitente,
            "servidor": servidor, "puerto": puerto, "contrasena_configurada": con_clave,
            "max_destinatarios": MAX_DESTINATARIOS}


@app.get("/email/config")
def get_email_config(sesion: Sesion = Depends(requiere_rol(*_LEEN_CONECTIVIDAD))):
    return _correo_dto()


@app.put("/email/config")
def put_email_config(body: _CorreoConfigBody,
                     sesion: Sesion = Depends(requiere_rol(*_EDITAN_CORREO))):
    from autoclave.core.runtime.config_correo_equipo import ErrorCorreo
    entidad = "/email/config"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    anterior = context.config_correo_equipo.leer()
    try:
        nuevo = context.config_correo_equipo.guardar(body.envio_activo, body.destinatarios)
    except ErrorCorreo as e:
        raise RechazoApi(422, e.codigo, "Destinatarios inválidos", extra={"campo": e.campo})
    except OSError:
        _rechazar(503, "ARCHIVO_NO_ESCRIBIBLE", "No se pudo guardar la configuración", entidad, sesion)
    _auditar("correo_configurado", sesion, entidad=entidad,
             valor_anterior={"envio_activo": anterior["envio_activo"],
                             "destinatarios": [d["correo"] for d in anterior["destinatarios"]]},
             valor_nuevo={"envio_activo": nuevo["envio_activo"],
                          "destinatarios": [d["correo"] for d in nuevo["destinatarios"]]})
    return _correo_dto()


@app.post("/email/test")
def post_email_test(sesion: Sesion = Depends(requiere_rol(*_EDITAN_CORREO))):
    """Correo de prueba a cada destinatario GUARDADO (nunca a uno escrito a mano)."""
    from autoclave import i18n
    from autoclave.ui_qml.exportacion.config_correo import correo_valido
    from email.message import EmailMessage
    entidad = "/email/test"
    config = _cargar_config_correo()
    if not config.envio_activo:
        raise RechazoApi(409, "envio_desactivado", "El envío de correo está desactivado")
    destinos = [d["correo"] for d in config.destinos if correo_valido(d.get("correo"))]
    if not destinos:
        raise RechazoApi(409, "sin_destinatarios", "No hay destinatarios guardados")
    if not config.configurado:
        raise RechazoApi(409, "correo_no_configurado", "Falta remitente, servidor o contraseña")
    meta = _meta_equipo()
    enviados, fallidos = 0, []
    for destino in destinos:
        m = EmailMessage()
        m["From"], m["To"] = config.remitente, destino
        m["Subject"] = i18n.t("conectividad.asunto_prueba", None, serie=meta["serie"] or "-")
        m.set_content(i18n.t("conectividad.cuerpo_prueba", None, serie=meta["serie"] or "-",
                             modelo=meta["modelo"] or "-",
                             fecha=datetime.now().strftime("%Y-%m-%d %H:%M")))
        try:
            _enviar_correo(config, m)
            enviados += 1
        except Exception as e:
            # el texto de la excepción no se devuelve ni se audita (podría
            # contener credenciales del servidor); solo su tipo
            logger.warning("Correo de prueba a %s fallido (%s)", destino, type(e).__name__)
            fallidos.append(destino)
    _auditar("correo_prueba", sesion, entidad=entidad,
             detalle={"enviados": enviados, "fallidos": fallidos})
    if not enviados:
        raise RechazoApi(502, "envio_fallido", "No se pudo enviar el correo de prueba",
                         extra={"fallidos": fallidos})
    return {"ok": True, "enviados": enviados, "fallidos": fallidos}


# ── Respaldo y restauración por USB (O2h, tanda 6) ──────────────────────────
# Técnico e ingeniero, solo fuera de CICLO (409, también el ingeniero). Ver
# core/runtime/respaldo.py: manifiesto con hash, sin hashes de contraseña, y un
# respaldo de OTRO número de serie se rechaza siempre. Restaurar pide
# `confirmar: true` y no toca usuarios, historial, perfil ni la atmosférica.

class _ExportarBody(BaseModel):
    unidad: str
    perfil_calibracion: StrictBool = True
    parametros_programas: StrictBool = True
    usuarios: StrictBool = True
    historial: StrictBool = False


class _RestaurarBody(BaseModel):
    unidad: str
    archivo: str
    confirmar: StrictBool = False


_lock_respaldo = threading.Lock()


def _unidades_usb() -> list[dict]:
    from autoclave.core.runtime import respaldo as rp
    return rp.unidades_usb()


def _version_sw() -> str:
    import importlib.metadata
    try:
        return importlib.metadata.version("autoclave")
    except importlib.metadata.PackageNotFoundError:
        return "0"


def _unidad_detectada(unidad: str, entidad: str, sesion) -> str:
    rutas = {u["ruta"] for u in _unidades_usb()}
    if unidad not in rutas:
        raise RechazoApi(404, "usb_no_detectada", "Unidad USB no detectada")
    return unidad


def _carpeta_programas_usuario() -> Path:
    return Path(context.cycle_manager.carpeta("cycles/user"))


def _usuarios_sin_hash() -> list[dict]:
    db = context.db
    with getattr(db, "_lock", threading.Lock()):
        filas = db._conn.execute("SELECT usuario, nombre, rol, activo FROM usuarios").fetchall()
    return [{"usuario": f[0], "nombre": f[1], "rol": f[2], "activo": bool(f[3])} for f in filas]


def _copia_bd() -> bytes:
    import tempfile
    db = context.db
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "historial.db"
        dst = sqlite3.connect(destino)
        try:
            with getattr(db, "_lock", threading.Lock()):
                db._conn.backup(dst)
        finally:
            dst.close()
        return destino.read_bytes()


@app.get("/backup/usb")
def get_backup_usb(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime import respaldo as rp
    equipo, version = _meta_equipo(), _version_sw()
    unidades = []
    for u in _unidades_usb():
        carpeta = Path(u["ruta"]) / rp.CARPETA
        respaldos = []
        try:
            archivos = sorted(carpeta.glob("respaldo_*.zip"), reverse=True)[:50]
        except OSError:
            archivos = []
        for a in archivos:
            respaldos.append(rp.resumen(a, equipo, version))
        unidades.append({**u, "respaldos": respaldos})
    return {"unidades": unidades, "serie": equipo["serie"], "version_sw": version}


@app.post("/backup/export")
def post_backup_export(body: _ExportarBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime import respaldo as rp
    from autoclave.utils.archivos import escribir_texto_atomico  # noqa: F401
    entidad = "/backup/export"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    unidad = _unidad_detectada(body.unidad, entidad, sesion)
    partes = body.model_dump(exclude={"unidad"})
    if not any(partes.values()):
        raise RechazoApi(422, "sin_partes", "Elija qué exportar")
    equipo = _meta_equipo()
    contenido = {"perfil.json": json.dumps(equipo, ensure_ascii=False).encode("utf-8")}
    if body.perfil_calibracion:
        with _lock_archivos:                         # SAF-05 de O2h
            contenido["calibracion.yaml"] = Path(CALIBRATION_PATH).read_bytes()
    if body.parametros_programas:
        params = {p["clave"]: p["valor"] for p in context.config_manager.describir()}
        contenido["parametros.json"] = json.dumps(params, ensure_ascii=False).encode("utf-8")
        for f in sorted(_carpeta_programas_usuario().glob("*.json")):
            contenido[f"programas/{f.name}"] = f.read_bytes()
    if body.usuarios:
        contenido["usuarios.json"] = json.dumps(_usuarios_sin_hash(), ensure_ascii=False).encode("utf-8")
    if body.historial:
        contenido["historial.db"] = _copia_bd()
    with _lock_respaldo:
        zip_bytes = rp.crear(equipo, partes, contenido, sesion.usuario, _version_sw())
        carpeta = Path(unidad) / rp.CARPETA
        nombre = rp.nombre_archivo(equipo["serie"], datetime.now())
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            temporal = carpeta / (nombre + ".tmp")
            temporal.write_bytes(zip_bytes)
            os.replace(temporal, carpeta / nombre)
        except OSError:
            _rechazar(503, "usb_no_escribible", "No se pudo escribir en la USB", entidad, sesion)
    _auditar("respaldo_exportado", sesion, entidad=entidad,
             detalle={"archivo": nombre, "partes": partes, "bytes": len(zip_bytes)})
    return {"ok": True, "archivo": nombre, "bytes": len(zip_bytes)}


@app.post("/backup/restore")
def post_backup_restore(body: _RestaurarBody,
                        sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.managers.config_manager import ErrorParametro
    from autoclave.core.runtime import respaldo as rp
    from autoclave.utils.archivos import escribir_texto_atomico
    entidad = "/backup/restore"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    unidad = _unidad_detectada(body.unidad, entidad, sesion)
    try:
        ruta = rp.ruta_respaldo_segura(unidad, body.archivo)
        m, datos = rp.leer(ruta)
    except rp.ErrorRespaldo as e:
        _auditar("respaldo_rechazado", sesion, entidad=entidad,
                 detalle={"archivo": body.archivo, "motivo": e.codigo})
        raise RechazoApi(422, e.codigo, "Respaldo inválido")
    motivo = rp.validar_para_equipo(m, _meta_equipo(), _version_sw())
    if motivo:
        _auditar("respaldo_rechazado", sesion, entidad=entidad,
                 detalle={"archivo": body.archivo, "motivo": motivo, "serie_respaldo": m.get("serie")})
        raise RechazoApi(409, motivo, "El respaldo no corresponde a este equipo",
                         extra={"serie_respaldo": m.get("serie", "")})
    if not body.confirmar:
        raise RechazoApi(428, "confirmacion_requerida", "Confirme la restauración",
                         extra={"partes": m.get("partes", {})})
    # validar todo ANTES de escribir nada. SAF-02 de O2h: los programas NO se
    # restauran (no hay aún un validador común con el editor de parámetros);
    # quedan en el respaldo como referencia.
    params = {}
    if "parametros.json" in datos:
        try:
            params = json.loads(datos["parametros.json"].decode("utf-8"))
        except ValueError:
            raise RechazoApi(422, "parametros_invalidos", "Respaldo inválido")
        if not isinstance(params, dict):
            raise RechazoApi(422, "parametros_invalidos", "Respaldo inválido")
    calib = datos.get("calibracion.yaml")
    if calib is not None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            prueba = Path(tmp) / "calibration.yaml"
            prueba.write_bytes(calib)
            try:
                cfg_resp = load_config(prueba)
            except Exception:
                raise RechazoApi(422, "calibracion_invalida", "Respaldo inválido")
        # SAF-01 de O2h: misma plausibilidad que la calibración manual, canal
        # por canal; lo dudoso (aviso) también se rechaza: fail-closed
        for tipo, mapa, lista in (("temperature", EstadoAutoclave.map_temp,
                                   cfg_resp.calibration.user.temperature),
                                  ("pressure", EstadoAutoclave.map_pres,
                                   cfg_resp.calibration.user.pressure)):
            for sensor, i in mapa.items():
                if i >= len(lista):
                    raise RechazoApi(422, "calibracion_invalida", "Respaldo inválido")
                c = lista[i]
                nivel, motivo_c = (("aviso", "polinomio") if c.poly else
                                   evaluar_desviacion_acumulada(tipo, float(c.gain),
                                                                float(c.offset), sensor))
                if nivel is not None:
                    _auditar("respaldo_rechazado", sesion, entidad=entidad,
                             detalle={"archivo": body.archivo, "motivo": "calibracion_implausible",
                                      "sensor": sensor, "detalle": motivo_c})
                    raise RechazoApi(422, "calibracion_implausible",
                                     f"Calibración no plausible en {sensor}: {motivo_c}")
    aplicado = {"calibracion": False, "parametros": [], "parametros_omitidos": [], "programas": []}
    with _lock_respaldo:
      try:
        if calib is not None:
            with _lock_archivos:
                with context.control_loop.bloqueo_maquina():     # SAF-03: de nuevo, justo antes
                    en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
                if en_ciclo:
                    _rechazar(409, "estado_no_permitido", "Hay un ciclo en curso", entidad, sesion)
                escribir_texto_atomico(CALIBRATION_PATH, calib.decode("utf-8"))
                context.units.reload_calibration(CALIBRATION_PATH)   # SAF-04: sin reiniciar
            aplicado["calibracion"] = True
        cm = context.config_manager
        for clave, valor in params.items():
            try:
                p = cm.describir(clave)
            except ErrorParametro:
                aplicado["parametros_omitidos"].append(clave)
                continue
            if p["solo_lectura"] or p["valor"] == valor:
                if p["solo_lectura"]:
                    aplicado["parametros_omitidos"].append(clave)
                continue
            with cm.lock_cambios:
                try:
                    anterior, nuevo = cm.fijar(clave, valor, sesion.usuario, aplicar=False)
                except ErrorParametro:
                    aplicado["parametros_omitidos"].append(clave)
                    continue
                try:
                    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
                        cm.aplicar_valor(clave, nuevo, sesion.usuario)
                except RechazoApi:
                    cm.revertir_bd(clave, anterior)
                    raise
            aplicado["parametros"].append(clave)
      finally:
        # SAF-03: se audita siempre lo que sí se aplicó, también si falla a medias
        _auditar("respaldo_restaurado", sesion, entidad=entidad,
                 detalle={"archivo": body.archivo, "creado_en": m.get("creado_en"), **aplicado})
    return {"ok": True, **aplicado, "reinicio_requerido": False}


@app.get("/cycle/summary")
def get_cycle_summary():
    """Resumen de solo lectura para el Resumen del Sistema del Menú Principal
    (planeacion_menu_principal_ui_qml.md, D-14)."""
    r = context.db.get_resumen_ciclos(_inicio_del_dia())
    ultimo = _ciclo_json(r["ultimo"]) if r["ultimo"] is not None else None
    return {
        "ciclos_totales": r["total"],   # TODO(MP-06a): último numero_ciclo, no contador persistente
        "ciclos_hoy":     r["hoy"],
        "ultimo_ciclo":   ultimo,
    }


@app.get("/cycle/list")
def get_cycle_list(periodo: Literal["dia", "semana", "mes"] = "dia",
                   fecha: date | None = None,
                   terminados: bool = False, limite: int = 500):
    """Ciclos del periodo de calendario que contiene `fecha` (por defecto hoy), más
    recientes primero; solo lectura. Lo usan la ventana de Ciclos hoy (periodo=dia,
    terminados=true: los mismos que cuenta /cycle/summary) y la de Historial (por
    fecha de inicio, con los interrumpidos). truncado = había más de `limite`;
    desde/hasta = primer y último día del periodo, para rotularlo."""
    limite = max(1, min(limite, 2000))
    if fecha is None:
        fecha = date.fromisoformat(_inicio_del_dia()[:10])
    desde, hasta = _rango_del_periodo(periodo, fecha)
    filas = context.db.get_ciclos_desde(desde, terminados, limite + 1, hasta=hasta)
    return {
        "periodo":   periodo,
        "desde":     desde[:10],
        "hasta":     (date.fromisoformat(hasta[:10]) - timedelta(days=1)).isoformat(),
        "ciclos":    [_ciclo_json(f) for f in filas[:limite]],
        "truncado":  len(filas) > limite,
    }


class _ImprimirCiclosBody(BaseModel):
    ids: list[int] = Field(min_length=1)


def _encolar_en_impresora(tickets: list[str]) -> None:
    """Pone los tickets en la cola de la impresora térmica, la misma de la
    impresión en tiempo real. Se rechaza durante un ciclo (409): el ticket en
    vivo se imprime línea a línea por esa cola y lo nuevo quedaría intercalado
    en él. Y si Windows no reporta la impresora lista (503, detail.impresora =
    desconectada / sin_papel / no_instalada / error): Windows acepta el trabajo
    aunque esté desconectada y lo deja en su cola, así que se avisa en vez de
    encolar a ciegas."""
    from autoclave.state_machine.machine.enum_global import GlobalState
    if context.estado.get_machine_state() == GlobalState.CICLO:
        raise HTTPException(status_code=409, detail="No se puede imprimir durante un ciclo")
    estado_impresora = context.realtime_printer.estado()
    if estado_impresora != "lista":
        raise HTTPException(status_code=503, detail={"impresora": estado_impresora})
    for texto in tickets:
        context.realtime_printer.enqueue(texto)


@app.post("/cycle/history/print")
def print_cycle_history(body: _ImprimirCiclosBody):
    """Reimprime en la impresora térmica el ticket de cada ciclo pedido, en ese
    orden (404 y nada impreso si alguno no existe; 409/503: _encolar_en_impresora)."""
    tickets = []
    for ciclo_id in body.ids:
        ciclo = context.db.get_ciclo(ciclo_id)
        if ciclo is None:
            raise HTTPException(status_code=404, detail=f"Ciclo {ciclo_id} no encontrado")
        lecturas = [dict(r) for r in context.db.get_lecturas_para_imprimir(ciclo_id)]
        tickets.append(format_ticket(dict(ciclo), lecturas))
    _encolar_en_impresora(tickets)
    return {"ok": True, "impresos": len(tickets)}


def _resumen_periodo(periodo: str, fecha: date | None) -> dict:
    if fecha is None:
        fecha = date.fromisoformat(_inicio_del_dia()[:10])
    desde, hasta = _rango_del_periodo(periodo, fecha)
    numeros = {tipo: getattr(c, "number", None) for tipo, c in list(context.cycle_manager.cycles.items())}
    resumen = resumen_periodo.resumir(context.db.get_conteo_resultados(desde, hasta), numeros)
    perfil = context.profile
    return {
        "periodo": periodo,
        "serie":   getattr(perfil, "serial_number", "") or "",
        "modelo":  getattr(perfil, "model_id", "") or "",
        "desde":   desde[:10],
        "hasta":   (date.fromisoformat(hasta[:10]) - timedelta(days=1)).isoformat(),
        **resumen,
    }


@app.get("/report/summary")
def get_report_summary(periodo: Literal["dia", "semana", "mes"] = "dia", fecha: date | None = None):
    """Resumen de los ciclos iniciados en el periodo de calendario que contiene
    `fecha` (por defecto hoy): totales por resultado, por programa y causas de
    fallo (services/domain/reportes/resumen_periodo.py). Solo lectura."""
    return _resumen_periodo(periodo, fecha)


class _ImprimirResumenBody(BaseModel):
    periodo: Literal["dia", "semana", "mes"] = "dia"
    fecha: date | None = None


@app.post("/report/summary/print")
def print_report_summary(body: _ImprimirResumenBody):
    """Imprime el resumen del periodo en la impresora térmica (409/503:
    _encolar_en_impresora)."""
    r = _resumen_periodo(body.periodo, body.fecha)
    _encolar_en_impresora([resumen_periodo.format_ticket_resumen(
        r, r["desde"], r["hasta"], serie=r["serie"], modelo=r["modelo"])])
    return {"ok": True}


@app.get("/cycle/history/{ciclo_id}/graph")
def get_cycle_history_graph(ciclo_id: int):
    """Serie de la gráfica (lecturas_grafica, ~1 s, t_s monotónico) de un ciclo
    del historial, con el mismo formato que /cycle/current/graph. Solo lectura;
    la usa la ventana flotante de Último ciclo del Menú Principal (D-21)."""
    if context.db.get_ciclo(ciclo_id) is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    rows = context.db.get_lecturas_grafica(ciclo_id)
    return {
        "ciclo_db_id": ciclo_id,
        "lecturas": [
            {
                "id":          r["id"],
                "t_s":         r["t_s"],
                "fase":        r["fase"],
                "fase_ui":     progreso_ciclo.fase_ui(r["fase"]),
                "temp_camara": r["temp_camara"],
                "temp_ref":    r["temp_ref"],
                "pres_camara": r["pres_camara"],
            }
            for r in rows
        ],
    }


@app.get("/cycle/history")
def get_cycle_history(limite: int = 50):
    """Lista de ciclos registrados (más recientes primero)."""
    rows = context.db.get_ciclos_recientes(limite)
    return [
        {
            "id":            r["id"],
            "numero_ciclo":  r["numero_ciclo"],
            "fecha_inicio":  r["fecha_inicio"],
            "fecha_fin":     r["fecha_fin"],
            "nombre_ciclo":  r["nombre_ciclo"],
            "resultado":     r["resultado"],
        }
        for r in rows
    ]


@app.get("/cycle/history/{ciclo_id}/readings")
def get_cycle_readings(ciclo_id: int):
    """Todas las lecturas de un ciclo histórico."""
    ciclo = context.db.get_ciclo(ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    rows = context.db.get_lecturas_ciclo(ciclo_id)
    return {
        "ciclo": dict(ciclo),
        "lecturas": [dict(r) for r in rows],
    }


@app.get("/cycle/history/{ciclo_id}/ticket")
def get_cycle_ticket(ciclo_id: int):
    """Lecturas marcadas para_imprimir (formato ticket)."""
    ciclo = context.db.get_ciclo(ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")

    rows = context.db.get_lecturas_para_imprimir(ciclo_id)
    return {
        "ciclo":    dict(ciclo),
        "lecturas": [dict(r) for r in rows],
    }


def _carga_liquida(programa) -> bool:
    try:
        return programa.get_param("globals", "tipo_carga", default="solido") == "liquido"
    except Exception:
        return False


@app.get("/db/estado")
def get_db_estado():
    """T8 (§7.1): "OK" o "DEGRADADA" (sin base de datos: alarma
    OPERANDO_SIN_BD; los ciclos van al respaldo y al ticket)."""
    sin_bd = getattr(context, "sin_base_de_datos", False) is True
    return {"estado": "DEGRADADA" if sin_bd else "OK", "sin_base_de_datos": sin_bd}


@app.post("/cycle/start")
def start_cycle(body: dict | None = Body(default=None),
                authorization: str | None = Header(None)):
    """
    Solicita el inicio del ciclo de esterilización.
    Sólo tiene efecto cuando el sistema está en estado PREPARADO y
    la flag LISTO_PARA_CICLO es True.  La máquina de estados gestiona
    la transición real.
    Sin base de datos (T8, §7.6) exige {"confirmar_sin_registro": true} en
    cada ciclo: queda sin operador y sin registro en la base (respaldo y ticket).
    O1 (tanda 3): si la petición trae un token de sesión válido, ese usuario es
    el operador del ciclo (se guarda en la base, el respaldo y el ticket). El
    inicio sigue sin exigir sesión: sin token (o con uno vencido) el ciclo queda
    sin operador identificado; el token no se valida como requisito.
    """
    sesion_operador = tokens.obtener(_token_de(authorization))
    estado = context.estado
    _rechazar_si_config_invalida("/cycle/start")
    if getattr(context, "sin_base_de_datos", False) is True:
        if not (isinstance(body, dict) and body.get("confirmar_sin_registro") is True):
            _rechazar(409, "confirmar_sin_registro",
                      "Base de datos no disponible: confirme que desea iniciar el ciclo "
                      "sin registro en la base", "/cycle/start")
        # SAF-01 de T8: sin base, el respaldo es el único registro electrónico
        error = context.respaldo_ciclos.probar_escritura()
        if error is not None:
            _rechazar(503, "respaldo_no_disponible",
                      f"Sin base de datos y sin respaldo del ciclo ({error}): no se puede "
                      "iniciar un ciclo", "/cycle/start")
    if getattr(context.control_loop, "apagando", False) is True:
        _rechazar(409, "apagado_en_curso", "El equipo se está apagando", "/cycle/start")

    # S2 (revisión): la validación del programa y START_CICLO van juntas bajo
    # el lock de la máquina: un /cycle/select concurrente no puede cambiar el
    # programa entre la validación y el inicio. La bitácora del rechazo se
    # escribe al soltar el lock.
    with context.control_loop.bloqueo_maquina():
        rechazo = _validar_inicio(estado)
        if rechazo is None:
            estado.operador_inicio = sesion_operador.usuario if sesion_operador else ""
            estado.set_flag("START_CICLO", True)
    if rechazo is not None:
        if rechazo[0] is None:
            raise HTTPException(status_code=409, detail=rechazo[1])
        _rechazar(409, rechazo[0], rechazo[1], "/cycle/start")
    return {"ok": True, "action": "START_CICLO"}


PRINCIPAL_SIN_LECTURA = "PRINCIPAL_SIN_LECTURA"


def _rechazo_principal_sin_lectura(estado) -> tuple | None:
    """(código, motivo) si el sensor Principal del programa seleccionado está
    declarado y sin lectura válida; None si lee (o no está declarado: ese
    caso lo rechaza verificar_inicio con su propio código, igual que un error
    al evaluar)."""
    seleccionado = getattr(context.control_loop, "cycle", None)
    try:
        principal = sc.sensor_principal(seleccionado)
        if sc.estado_sensor(getattr(context, "profile", None), estado, principal) != sc.SIN_SENAL:
            return None
    except Exception:
        # sin rechazo propio: verificar_inicio (RS-06) vuelve a exigir lectura
        logger.exception("/cycle/start: no se pudo evaluar el sensor Principal")
        return None
    from autoclave import i18n
    return PRINCIPAL_SIN_LECTURA, i18n.t("ciclo.principal_sin_lectura")


def _validar_inicio(estado) -> tuple | None:
    """(código, motivo) si el programa seleccionado no puede iniciarse; código
    None = rechazo sin código (no listo). Llamar bajo bloqueo_maquina()."""
    # P-2 (tanda 6): sin lectura válida del Principal del programa no se
    # inicia; el motivo se da antes que "no está listo" (con el estado seguro
    # de la pérdida del Principal en curso, el equipo nunca queda listo)
    principal_sin_lectura = _rechazo_principal_sin_lectura(estado)
    if principal_sin_lectura is not None:
        return principal_sin_lectura
    if not estado.get_flag("LISTO_PARA_CICLO"):
        return None, "El sistema no está listo para iniciar un ciclo"

    # RB-04.4 (T10): un programa dañado no se inicia
    seleccionado = getattr(context.control_loop, "cycle", None)
    danado = getattr(seleccionado, "danado", None)
    if isinstance(danado, list) and danado:
        return "PROGRAMA_NO_EDITABLE", f"Programa dañado (fuera del catálogo): {danado[0]}"

    # T11: un programa de carga líquida solo en equipos con capacidad de líquidos
    if seleccionado is not None and _carga_liquida(seleccionado):
        cap = getattr(context, "cap", None)
        if cap is not None and getattr(cap, "has_liquids", None) is False:
            return "carga_liquida_no_disponible", "Este equipo no admite programas de carga líquida"

    # RS-06 (tanda §1.1): asignación de sensores válida y todos los sensores
    # en uso del programa seleccionado con lectura
    return sc.verificar_inicio(seleccionado, getattr(context, "profile", None), estado)


@app.post("/cycle/abort")
def abort_cycle():
    """
    Solicita el aborto del ciclo en curso.
    Activa la flag CICLO_CANCELADO; el CicloState ejecutará el
    protocolo de fallo en el siguiente tick del control loop.
    """
    # P-7 (tanda 6): 409 con motivo cuando no tendría efecto (resultado ya
    # pendiente o paro); el indicador no queda puesto
    entidad = "/cycle/abort"
    with guard_estado(frozenset(), entidad) as actual:
        estado = context.estado
        if actual != GlobalState.CICLO:
            raise _Rechazo(409, "estado_no_permitido", "No hay un ciclo en curso")
        if estado.get_flag("PARO_EMERGENCIA") is True:
            raise _Rechazo(409, "paro_emergencia",
                           _motivo_paro("Paro de emergencia activado: el ciclo ya se detuvo"))
        fase = getattr(estado, "fase_ciclo", "")
        if isinstance(fase, str) and progreso_ciclo.resultado(fase) is not None:
            raise _Rechazo(409, "resultado_pendiente",
                           "El ciclo ya terminó: confirme el resultado")
        estado.set_flag("CICLO_CANCELADO", True)
    return {"ok": True, "action": "CICLO_CANCELADO"}


_MOTIVO_PARO = "Paro de emergencia activado: suéltelo antes de reconocer"
# U4 (tanda 2): el flag PARO_EMERGENCIA también bloquea sin datos de la
# tarjeta; el código de rechazo se conserva, el texto dice la causa real
_MOTIVO_SIN_DATOS_TARJETA = ("Sin datos válidos de la tarjeta de control: no se puede "
                             "verificar el paro de emergencia")


def _motivo_paro(texto_paro: str) -> str:
    if context.estado.get_flag("PARO_REAL"):
        return texto_paro
    return _MOTIVO_SIN_DATOS_TARJETA


def _estado_tarjeta() -> str:
    """U4: "desconectada", "sin_tramas_validas" u "ok"; falla cerrada."""
    valor = getattr(context.control_loop, "estado_tarjeta", None)
    return valor if valor in ("desconectada", "sin_tramas_validas", "ok") else "desconectada"


@app.post("/fault/reset")
def reset_fault():
    """Reconoce el estado de falla y solicita retornar a PREPARACION. Sin
    identificación (decisión 16). Con el paro de emergencia activo, 409 y no
    se guarda RESET_FALLA: tras soltarlo hay que reconocer de nuevo (§5.9)."""
    entidad = "/fault/reset"
    with guard_estado(frozenset(), entidad) as estado:
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _motivo_paro(_MOTIVO_PARO))
        # con el modo prueba la máquina está pausada: el reconocimiento se
        # aplicaría al salir, sin uno posterior a las pruebas (TMG-07)
        if context.control_loop.test_mode_active is True:
            raise _Rechazo(409, "modo_prueba_activo", "No permitido con el modo prueba activo")
        if estado != GlobalState.FALLA:
            raise _Rechazo(409, "estado_no_permitido", "El sistema no está en estado de falla",
                           extra={"estado": getattr(estado, "name", str(estado))})
        context.estado.set_flag("RESET_FALLA", True)
    # Fin de ciclo §15.2: reconocer la falla tras soltar el paro es también
    # "Confirmar y llevar a estado seguro" (fusionados, cualquier operador)
    context.control_loop.confirmar_estado_seguro()
    _auditar("falla_reconocida", entidad=entidad)
    return {"ok": True, "action": "RESET_FALLA"}


# ── Apagar equipo (fin de ciclo §16, D-20; tanda E5) ───────────────────────

def _apagado_windows_habilitado() -> bool:
    """El apagado real de Windows solo corre en el ejecutable empaquetado o
    con AUTOCLAVE_APAGADO_REAL=1: nunca desde las pruebas ni en desarrollo."""
    import os
    return bool(getattr(sys, "frozen", False)) or os.environ.get("AUTOCLAVE_APAGADO_REAL") == "1"


def _apagar_windows() -> None:
    import subprocess
    subprocess.run(["shutdown", "/s", "/t", "0"], check=False, timeout=30)


_TOPE_PASO_APAGADO_S = 8.0


def _paso_apagado(descripcion: str, paso, tope: float | None = None) -> None:
    """Un paso de la secuencia de apagado: un fallo se registra y NO impide
    los siguientes ni el apagado de Windows (A1, tanda 3). Con `tope`, el paso
    corre en un hilo auxiliar y, si no termina a tiempo, se sigue sin él."""
    if tope is None:
        try:
            paso()
        except BaseException:
            logger.exception("Apagar equipo: error en el paso '%s'", descripcion)
        return

    def ejecutar():
        try:
            paso()
        except BaseException:
            logger.exception("Apagar equipo: error en el paso '%s'", descripcion)

    hilo = threading.Thread(target=ejecutar, name="Apagado-" + descripcion[:20], daemon=True)
    hilo.start()
    hilo.join(tope)
    if hilo.is_alive():
        logger.error("Apagar equipo: el paso '%s' no terminó en %.0f s; se sigue", descripcion, tope)


def _secuencia_apagado() -> None:
    """ALL_OFF y parada del lazo (control_loop.stop: detiene el lazo, intenta
    ALL_OFF y cierra el puerto serial), historial de alarmas, base de datos y,
    si está habilitado, apagado de Windows. Corre en un hilo aparte para
    responder antes de cortar. Con degradación segura (A1): sin tarjeta o con
    un paso fallido se registra y se sigue; el paro y el latido de la tarjeta
    dejan las salidas en seguro por hardware."""
    _paso_apagado("detener el lazo de control", context.control_loop.stop, _TOPE_PASO_APAGADO_S)
    historial = getattr(context, "historial_alarmas", None)
    if historial is not None and hasattr(historial, "detener"):
        _paso_apagado("detener el historial de alarmas", lambda: historial.detener(2.0),
                      _TOPE_PASO_APAGADO_S)
    # S3d: vaciar las colas de escritura del respaldo y de la base ANTES de
    # cerrar la base (con el lazo ya detenido no entran tareas nuevas)
    logger_ciclo = getattr(context, "cycle_logger", None)
    if logger_ciclo is not None and hasattr(logger_ciclo, "detener"):
        _paso_apagado("vaciar la escritura del ciclo", lambda: logger_ciclo.detener(5.0),
                      _TOPE_PASO_APAGADO_S)

    def cerrar_base():
        # tras una falla de la base en caliente, context.db es BdNoDisponible
        real = getattr(context, "db_real", None)
        (real if getattr(context, "sin_base_de_datos", False) is True and real is not None
         else context.db).close()
    _paso_apagado("cerrar la base de datos", cerrar_base, _TOPE_PASO_APAGADO_S)
    if _apagado_windows_habilitado():
        logger.warning("Apagar equipo: apagando Windows")
        _paso_apagado("apagar Windows", _apagar_windows)
    else:
        logger.warning("Apagar equipo: apagado de Windows omitido (no es el ejecutable)")


def _estado_seguro_en_marcha() -> bool:
    """True si el protocolo de estado seguro está ACTUANDO sobre las válvulas.
    Pausado por un paro, esperando la confirmación del operador o sin datos de
    la tarjeta no mueve nada: el equipo ya está quieto y se puede apagar (A1)."""
    es = context.control_loop.estado_seguro
    if getattr(es, "activo", False) is not True:
        return False
    if context.estado.get_flag("PARO_EMERGENCIA"):
        return False
    if getattr(es, "requiere_confirmacion", False) is True:
        return False
    return getattr(context.control_loop, "datos_vigentes", False) is True


@app.post("/system/shutdown")
def shutdown_system(body: dict = Body(default={})):
    """"Apagar equipo" / dejar fuera de servicio (§16, A1 de la tanda 3).
    Permitido en cualquier estado salvo ciclo en curso (o estado seguro
    actuando) y salvo un apagado ya en marcha: con FALLA, EMERGENCIA, paro,
    sin tarjeta o con la cámara NO segura también se apaga (sin UPS, el
    personal técnico puede pedir dejar el equipo fuera de servicio). Solo desde
    la ventana principal (la UI de la puerta 1 envía ventana="principal").
    Confirmación: la de la propia UI; la cámara no segura solo se avisa allí."""
    entidad = "/system/shutdown"
    if body.get("ventana") != "principal":
        _rechazar(403, "solo_ventana_principal",
                  "Solo la ventana principal puede apagar el equipo", entidad)
    with guard_estado(DISTINTO_DE_CICLO, entidad) as estado:
        # TMG-05 de T7: un segundo apagado (doble toque) no lanza otra secuencia
        if getattr(context.control_loop, "apagando", False) is True:
            raise _Rechazo(409, "apagado_en_curso", "El equipo ya se está apagando")
        if _estado_seguro_en_marcha():
            raise _Rechazo(409, "estado_seguro_activo",
                           "La cámara se está llevando a estado seguro")
        # A1: solo informativo; ya no condiciona el apagado. Cualquier fallo al
        # evaluar cuenta como "no segura" (falla cerrada).
        try:
            vigentes = getattr(context.control_loop, "datos_vigentes", False) is True
            segura, _motivo = camara_segura.evaluar(
                context.estado, context.config_manager, context.programas_para_seguridad(),
                getattr(context, "profile", None), datos_vigentes=vigentes,
                temp_max_ciclo=context.temp_max_tras_ciclo())
            segura = segura is True
        except Exception:
            logger.exception("Apagar equipo: no se pudo evaluar la cámara; se asume no segura")
            segura = False
        try:
            paro = bool(context.estado.get_flag("PARO_EMERGENCIA"))
        except Exception:
            paro = None
        tarjeta = getattr(context.control_loop, "desconectado", True) is not True
        en_modo_prueba = getattr(context.control_loop, "test_mode_active", False) is True
        # TMG-01 / SAF-01 de T7: en el mismo bloque que validó, sin soltar el
        # lock: ningún tick posterior puede pasar a CICLO ni mover salidas
        context.control_loop.iniciar_apagado()
    _auditar("apagar_equipo", entidad=entidad,
             detalle={"estado": getattr(estado, "name", str(estado)),
                      "motivo": "fuera de servicio solicitado",
                      "camara_segura": segura, "tarjeta_conectada": tarjeta,
                      "paro_emergencia": paro, "modo_prueba": en_modo_prueba})
    try:
        threading.Thread(target=_secuencia_apagado, name="ApagarEquipo", daemon=False).start()
    except Exception:
        # sin hilo nuevo: el lazo ya está detenido, se apaga en línea
        logger.exception("Apagar equipo: no se pudo lanzar el hilo; se apaga en línea")
        _secuencia_apagado()
    return {"ok": True, "apagado_windows": _apagado_windows_habilitado(),
            "camara_segura": segura}


@app.post("/safe-state/confirm")
def confirm_safe_state():
    """"Confirmar y llevar a estado seguro" (fin de ciclo §15.2): tras soltar
    el paro, el protocolo de estado seguro no avanza hasta esta confirmación.
    Cualquier operador, sin rol. 409 con el paro activo o si no hace falta."""
    entidad = "/safe-state/confirm"
    if context.estado.get_flag("PARO_EMERGENCIA"):
        _rechazar(409, "paro_emergencia",
                  _motivo_paro("Paro de emergencia activado: suéltelo antes de confirmar"),
                  entidad)
    if context.control_loop.confirmar_estado_seguro() is not True:
        _rechazar(409, "sin_confirmacion_pendiente",
                  "No hay un estado seguro pendiente de confirmación", entidad)
    return {"ok": True}


@app.post("/outputs/reset")
def reset_outputs():
    """
    Apaga todas las salidas digitales y detiene el control loop.
    Llamar antes de cerrar la aplicación o ante cualquier apagado seguro.
    409 en CICLO: para detener un ciclo existe /cycle/abort.
    """
    # Solo la comprobación va dentro de _sm_lock: stop() espera al hilo del
    # loop, que puede estar esperando ese mismo lock. Si un ciclo arrancara
    # justo después, stop() lo deja con todo apagado (estado seguro).
    with guard_estado(DISTINTO_DE_CICLO, "/outputs/reset"):
        pass
    try:
        context.control_loop.stop()   # evita que el loop re-active salidas durante el reset
        context.setdo.reset_all_outputs()
        logger.info("outputs/reset: todas las salidas apagadas")
        return {"ok": True}
    except Exception as e:
        logger.error("outputs/reset error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cycle/acknowledge")
def acknowledge_cycle():
    """
    El operador confirmó que vio el resultado del ciclo.
    Activa CICLO_CONFIRMADO para que CicloState libere la transición.
    Solo tiene efecto mientras el estado sea CICLO (esperando confirmación).
    """
    entidad = "/cycle/acknowledge"
    with guard_estado(frozenset(), entidad) as actual:
        if actual != GlobalState.CICLO:
            raise _Rechazo(409, "estado_no_permitido", "No hay un ciclo esperando confirmación",
                           extra={"estado": getattr(actual, "name", str(actual))})
        # §5.9: con el paro activo no se confirma ni se guarda RESET_FALLA
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _motivo_paro(_MOTIVO_PARO))
        # solo con el ciclo ya terminado: una confirmación a mitad de ciclo
        # quedaba guardada y la máquina salía al terminar sin que el operador
        # viera el resultado (TMG-03/SAF-07)
        fase = getattr(context.estado, "fase_ciclo", "")
        if progreso_ciclo.resultado(fase) is None:
            raise _Rechazo(409, "sin_resultado", "No hay un ciclo esperando confirmación")

        context.estado.set_flag("CICLO_CONFIRMADO", True)

        # El operador ya vio el resultado en la pantalla del ciclo: si terminó
        # en cualquier FALLO (FALLO_*, EMERGENCIA, SENSOR_AUSENTE, ...), se
        # pre-arma RESET_FALLA para no exigir un segundo reconocimiento
        # (§5.9; antes solo FALLO_* y EMERGENCIA, y SENSOR_AUSENTE dejaba la
        # máquina en FALLA sin salida desde QML, OPC-22).
        reconoce_falla = progreso_ciclo.resultado(fase) == "fallo"
        if reconoce_falla:
            context.estado.set_flag("RESET_FALLA", True)
    if reconoce_falla:
        _auditar("falla_reconocida", entidad=entidad, detalle={"fase": fase})
    return {"ok": True, "action": "CICLO_CONFIRMADO"}


def _orden_puerta(door_name: str, accion: str, source_door) -> dict:
    """Abrir o cerrar una puerta (§5.3, T-13 y T-18).

    Guard de estado: 409 en CICLO (P-8: sin HIBERNACION ni EMERGENCIA; en PREPARACION,
    PREPARADO y FALLA se permite). Las condiciones físicas las aplica
    ServicioPuertas, fallando cerradas; si las incumple, o si la puerta no
    acepta la orden (bloqueo mecánico, no está abierta), 409 con el motivo.
    La comprobación y la orden van bajo _sm_lock para no intercalarse con el
    tick. `sin_actuador`: la puerta no tiene actuador (SimpleDoor) y la orden
    no mueve nada.

    `source_door` (S3e, tanda 2): la puerta que controla la pantalla que manda
    la orden (1 o 2), DECLARADA por el cliente, no autenticada. Cada pantalla
    opera solo su puerta: otra puerta se rechaza (409 `puerta_ajena`), un valor
    fuera de rango es inválido (422 `source_door_invalido`) y cada orden,
    aceptada o rechazada, queda en audit_log con el origen. Ausente (clientes
    antiguos) se acepta y queda como "desconocido". `door_id` del perfil NO
    interviene: identifica la ventana principal del PC, no qué puerta opera
    cada pantalla."""
    entidad = f"/doors/{door_name}/{accion}"
    _rechazar_si_config_invalida(entidad)
    servicio = context.servicio_puertas
    if door_name not in servicio.doors:
        raise HTTPException(status_code=404, detail="Puerta desconocida")
    origen = "desconocido" if source_door is None else source_door

    def rechazo_origen(status: int, codigo: str, motivo: str):
        _auditar("puerta_orden_rechazada", entidad=door_name, valor_nuevo=accion,
                 detalle={"source_door": origen, "codigo": codigo, "motivo": motivo})
        raise RechazoApi(status, codigo, motivo)

    if source_door is not None:
        valido = (isinstance(source_door, int) and not isinstance(source_door, bool)
                  and 1 <= source_door <= len(servicio.doors))
        if not valido:
            rechazo_origen(422, "source_door_invalido",
                           f"source_door inválido: {str(source_door)[:20]!r} "
                           f"(1 a {len(servicio.doors)})")
        if door_name != f"Puerta {source_door}":
            rechazo_origen(409, "puerta_ajena",
                           f"La pantalla de la puerta {source_door} solo opera su puerta")
    rechazo_puerta = None
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, entidad):
        # con el modo prueba las puertas no se actualizan, y con el enlace
        # caído las lecturas son viejas: la orden quedaría para después sin
        # revalidar (revisión de seguridad de la etapa 2, SAF-04)
        if context.control_loop.test_mode_active is True:
            raise _Rechazo(409, "modo_prueba_activo", "No permitido con el modo prueba activo")
        if context.control_loop.desconectado is True:
            raise _Rechazo(409, "sin_conexion_tarjeta", "Sin conexión con la tarjeta de control")
        pedir = servicio.request_open if accion == "open" else servicio.request_close
        ok, reason = pedir(door_name)
        if not ok:
            rechazo_puerta = reason or motivos.Motivo("no_permitida", "Orden de puerta no permitida")
    if rechazo_puerta is not None:
        # I4 (tanda 6): el motivo viaja también con código, parámetros y textos
        # es/en (`detail` sigue siendo el español). Se arma con _sm_lock ya
        # libre: lee la configuración de unidades del disco.
        _rechazar(409, "puerta_rechazada", rechazo_puerta, entidad,
                  extra=_campos_motivo(rechazo_puerta))
    _auditar("puerta_orden", entidad=door_name, valor_nuevo=accion,
             detalle={"source_door": origen})
    return {
        "ok": True,
        "door": door_name,
        "action": accion,
        "source_door": source_door,
        "sin_actuador": not servicio.tiene_actuador(door_name),
    }


@app.post("/alarms/{clave}/acknowledge")
def acknowledge_alarm(clave: str, body: dict = Body(default={})):
    """El operador reconoce una alarma ALARMA/FALLO_CRITICO (spec §7.2)."""
    usuario = str(body.get("usuario") or "").strip()
    if not usuario:
        raise HTTPException(status_code=422, detail="Falta el usuario que reconoce")
    inst = context.alarm_manager.obtener(clave)
    if inst is None:
        raise HTTPException(status_code=404, detail="La alarma no está activa")
    if not inst.nivel.requiere_reconocimiento:
        raise HTTPException(status_code=422, detail="Esta alarma no requiere reconocimiento")
    if not context.alarm_manager.reconocer(clave, usuario):
        # Se resolvió y retiró entre obtener() y reconocer().
        raise HTTPException(status_code=404, detail="La alarma no está activa")
    return {"ok": True}


def _fecha_iso_o_422(valor: str | None, campo: str) -> str | None:
    if valor is None:
        return None
    try:
        datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo} no es una fecha ISO válida")
    return valor


@app.get("/alarms/history")
def alarm_history(desde: str | None = None, hasta: str | None = None,
                  nivel: str | None = None, limite: int = 200):
    if nivel is not None and nivel not in Nivel.__members__:
        raise HTTPException(status_code=422, detail="Nivel desconocido")
    filas = context.db.get_alarmas_historial(
        _fecha_iso_o_422(desde, "desde"), _fecha_iso_o_422(hasta, "hasta"),
        nivel, max(1, min(int(limite), 1000)),
    )
    return {"alarmas": filas}


@app.post("/doors/{door_name}/open")
def open_door(door_name: str, body: dict = Body(...)):
    return _orden_puerta(door_name, "open", body.get("source_door"))


@app.post("/doors/{door_name}/close")
def close_door(door_name: str, body: dict = Body(...)):
    return _orden_puerta(door_name, "close", body.get("source_door"))


_SIN_VALOR = object()


class _CycleParamValueBody(BaseModel):
    cycle_id: str
    fase: str
    path: list[str]
    value: object
    # RB-06 (T10): si viene y no coincide con el valor actual, 409 VALOR_CAMBIO.
    # Opcional para no romper los clientes actuales (PySide).
    valor_anterior_esperado: object = None
    model_config = {"extra": "ignore"}


def _valor_parametro(cycle, fase: str, path: list[str]):
    """Valor actual de un parámetro, o None si la ruta no existe."""
    nodo = cycle.parameters.get(fase) if isinstance(cycle.parameters, dict) else None
    for clave in path:
        if not isinstance(nodo, dict) or clave not in nodo:
            return None
        nodo = nodo[clave]
    return nodo.get("value") if isinstance(nodo, dict) else None


@app.patch("/cycle/parameter")
def update_cycle_parameter(body: _CycleParamValueBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Actualiza un único parámetro (cualquier sección, incluido el secado) de
    cualquier ciclo cargado y persiste si es 'user'. Valida tipos estrictos y
    el rango efectivo (catálogo ∩ JSON, RB-05; T10) y las reglas entre
    parámetros (tipo_carga). Técnico e ingeniero (tanda §1.6; técnico fuera de
    CICLO). La auditoría es parte del cambio: si no se registra, el cambio se
    revierte (RB-03.5). En CICLO (§5.8, T-17) el cambio se guarda
    siempre en el programa almacenado y aplica también al ciclo en curso solo
    si es su programa y la fase del parámetro no ha iniciado; la respuesta
    lo indica en `aplica` ("en_curso" o "siguiente")."""
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")

    if not body.path:
        raise HTTPException(status_code=422, detail="'path' no puede estar vacío")

    entidad = f"{body.cycle_id}/{body.fase}/{'.'.join(body.path)}"
    if getattr(cycle, "danado", None):
        _rechazar(409, "PROGRAMA_NO_EDITABLE",
                  f"Programa dañado (fuera del catálogo): {cycle.danado[0]}", entidad, sesion)
    # RB-03.5: sin base de datos no hay auditoría; el cambio no se aplica
    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "BASE_OCUPADA", "Base de datos no disponible: cambio no aplicado",
                  entidad, sesion)
    # F0 solo en equipos de laboratorio (tanda §1.1): fuera de lab no se ofrece
    # y el backend rechaza activarlo
    if (body.fase == "globals" and body.path == ["F0"] and bool(body.value)
            and not sc.f0_disponible(getattr(context, "profile", None))):
        _rechazar(422, "f0_no_disponible",
                  "F0 solo está disponible en equipos de laboratorio", entidad, sesion)
    with guard_estado(DISTINTO_DE_CICLO, "/cycle/parameter", sesion,
                      excepcion_ingeniero=True) as estado:
        en_ciclo = estado == GlobalState.CICLO
        programa_en_curso = getattr(getattr(context.control_loop, "cycle", None), "id", None)

        anterior = _valor_parametro(cycle, body.fase, body.path)
        if (body.valor_anterior_esperado is not None
                and body.valor_anterior_esperado != anterior):
            raise _Rechazo(409, "VALOR_CAMBIO", "El valor cambió desde que se leyó",
                           extra={"valor_actual": anterior})
        previos = [(f, p, _valor_parametro(cycle, f, p)) for f, p in cycle.vinculados(body.fase, body.path)]
        try:
            value = cycle.set_param(body.fase, body.path, body.value)
        except KeyError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except (TypeError, ValueError) as e:
            raise _Rechazo(422, "VALOR_INVALIDO", str(e))

        # Fuera de CICLO, o en otro programa durante CICLO (§5.8, 5b), el
        # cambio solo rige desde el siguiente ciclo que use ese programa. El
        # ciclo en curso corre con una copia: solo una fase pendiente de su
        # programa recibe el cambio, decidido aquí bajo _sm_lock (§5.8, 4).
        aplica = "siguiente"
        if en_ciclo and body.cycle_id == programa_en_curso:
            if context.control_loop.aplicar_a_ciclo_en_curso(body.fase, body.path, value):
                aplica = "en_curso"
        detalle = {"programa": body.cycle_id, "fase": body.fase, "aplica": aplica}
        # parámetros vinculados que cambiaron con este (SAF-02 de T-17)
        vinculados = [f"{f}/{'.'.join(p)}" for f, p in cycle.vinculados(body.fase, body.path)[1:]]
        if vinculados:
            detalle["vinculados"] = vinculados
        if en_ciclo:
            ctx = _contexto_ciclo()
            detalle.update({"ciclo": ctx.get("ciclo"), "fase_en_curso": ctx.get("fase"),
                            "programa_en_curso": ctx.get("programa")})

    # El JSON se escribe fuera de _sm_lock (hallazgo D); el valor en memoria
    # ya quedó cambiado bajo el lock, atómico con la comprobación de estado.
    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        with _lock_archivos:
            _save_cycle_json(cycle)

    # RB-03.5 (T10): sin registro en audit_log el cambio no queda aplicado
    try:
        context.db.registrar_auditoria(
            "param_ciclo_cambio", usuario=sesion.usuario, rol=sesion.rol, entidad=entidad,
            valor_anterior=anterior, valor_nuevo=value, detalle=detalle)
    except Exception:
        logger.exception("Parámetro %s sin auditoría: se revierte", entidad)
        _revertir_parametro(cycle, previos, aplica == "en_curso")
        _rechazar(503, "BASE_OCUPADA", "No se pudo registrar el cambio: no se aplicó",
                  entidad, sesion)
    return {"ok": True, "value": value, "aplica": aplica}


def _revertir_parametro(cycle, previos, en_curso: bool) -> None:
    """Restaura los valores previos (también los vinculados) en el programa,
    su JSON y, si se había aplicado, la copia del ciclo en curso."""
    with context.control_loop.bloqueo_maquina():
        for fase, path, valor in previos:
            hoja = cycle._hoja(fase, path)
            if hoja is not None:
                hoja["value"] = valor
            if en_curso:
                context.control_loop.aplicar_a_ciclo_en_curso(fase, path, valor)
    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        with _lock_archivos:
            _save_cycle_json(cycle)


# ── Opciones › Parámetros del ciclo, lectura (T12; opciones §5.1, §5.2, §6) ──

# Orden de la pantalla 1: fases del ciclo y, al final, Generales y Finalización
_SECCIONES_PROGRAMA = ("precalentamiento", "prevacio", "calentamiento", "esterilizacion",
                       "descompresion", "secado", "globals", "finalizacion")


def _no_se_ejecuta(cycle, seccion: str) -> bool:
    """Q-2: la fase con su parámetro de activación en 0 se muestra con "No se
    ejecuta" (precalentamiento, secado, tipos de pulso de vacío)."""
    if seccion == "precalentamiento":
        return not cycle.get_param("precalentamiento", "tiempo_precalentamiento")
    if seccion == "secado":
        return not cycle.get_param("secado", "tiempo_secado")
    if seccion == "prevacio":
        return not any(cycle.get_param("prevacio", f"conteo_pulso_{p}") for p in "abcd")
    return False


def _programa_editable(cycle) -> bool:
    return getattr(cycle, "source", "") == "user" and not getattr(cycle, "danado", None)


@app.get("/programas")
def get_programas():
    """Programas para Opciones (§6): número, nombre, origen, estado y sus
    secciones con la marca "No se ejecuta". Sin lectura de disco en la UI."""
    salida = []
    for cycle in list(context.cycle_manager.cycles.values()):
        if cycle.number is None:
            continue
        salida.append({
            "numero": cycle.number, "cycle_id": cycle.id, "nombre": cycle.name,
            "nombres": _nombres_ciclo(cycle),
            "origen": getattr(cycle, "source", ""), "danado": bool(getattr(cycle, "danado", None)),
            "editable": _programa_editable(cycle),
            "habilitado": getattr(cycle, "habilitado", True) is not False,
            "personalizado": getattr(cycle, "personalizado", False) is True,
            "secciones": [{"clave": s, "no_se_ejecuta": _no_se_ejecuta(cycle, s)}
                          for s in _SECCIONES_PROGRAMA if s in cycle.parameters],
        })
    return {"programas": sorted(salida, key=lambda p: p["numero"])}


def _param_programa(cycle, seccion: str, nombre: str):
    try:
        return cycle.get_param(seccion, nombre)
    except Exception:
        return None


@app.get("/programas/seleccionables")
def get_programas_seleccionables():
    """Programas que el operador puede elegir en Preciclo (B6, tanda 4), ya
    ordenados: primero los 3 con más ciclos terminados en el historial (de mayor
    a menor; el empate lo decide el orden predefinido, por número) marcados
    `mas_usado`, después el resto por número. Sin historial, o sin base de datos,
    todo en el orden predefinido y sin marcas. `seleccionable` y `motivo` dicen
    si hoy se puede cambiar de programa (la misma regla que /cycle/select). Solo
    lectura, sin sesión (como /cycle/select)."""
    cap = getattr(context, "cap", None)
    filas = []
    for cycle in list(context.cycle_manager.cycles.values()):
        if getattr(cycle, "number", None) is None or getattr(cycle, "source", "user") != "user":
            continue
        if getattr(cycle, "danado", None):
            continue
        if getattr(cycle, "habilitado", True) is False:      # O1: deshabilitado
            continue
        if _carga_liquida(cycle) and getattr(cap, "has_liquids", None) is False:
            continue
        filas.append({
            "numero": cycle.number, "cycle_id": cycle.id, "nombre": cycle.name,
            "nombres": _nombres_ciclo(cycle),
            "temperatura": _param_programa(cycle, "esterilizacion", "temperatura_esterilizacion"),
            "tiempo": _param_programa(cycle, "esterilizacion", "tiempo_esterilizacion"),
            "ciclos": 0, "mas_usado": False, "seleccionado": False,
        })
    filas.sort(key=lambda f: f["numero"])
    conteos = {}
    if getattr(context, "sin_base_de_datos", False) is not True:
        try:
            conteos = context.db.conteo_ciclos_por_programa()
        except Exception:
            logger.warning("Conteo de ciclos por programa no disponible: orden predefinido")
    for f in filas:
        f["ciclos"] = int(conteos.get(f["numero"], 0) or 0)
    usados = sorted((f for f in filas if f["ciclos"] > 0), key=lambda f: (-f["ciclos"], f["numero"]))[:3]
    for f in usados:
        f["mas_usado"] = True
    filas = usados + [f for f in filas if not f["mas_usado"]]
    loop = context.control_loop
    with loop.bloqueo_maquina():
        activo = getattr(getattr(loop, "cycle", None), "id", None)
        motivo = loop._motivo_no_cambiar_ciclo()
    for f in filas:
        f["seleccionado"] = f["cycle_id"] == activo
    return {"programas": filas, "seleccionable": motivo is None, "motivo": motivo or "",
            "orden": "uso" if usados else "predefinido"}


def _hojas_seccion(cycle, seccion: str) -> list[tuple[list[str], dict]]:
    """Parámetros (ruta, hoja) de la sección. Descompresión: el modo, la
    espera previa y solo los parámetros del modo activo (Q-3)."""
    nodo = cycle.parameters.get(seccion) or {}
    salida = []

    def recorrer(n, ruta):
        if isinstance(n, dict) and "value" in n and not isinstance(n.get("value"), dict):
            salida.append((ruta, n))
            return
        if isinstance(n, dict):
            for clave, sub in n.items():
                recorrer(sub, ruta + [clave])

    recorrer(nodo, [])
    if seccion == "descompresion":
        modo = cycle.get_param("descompresion", "modo")
        activo = f"modo_{modo}"
        salida = [(r, h) for r, h in salida if len(r) == 1 or r[0] == activo]
    return salida


def _ultimas_modificaciones(entidad_prefijo: str) -> dict:
    """{entidad: {usuario, rol, ts, valor_anterior, valor_nuevo}} con la última
    modificación auditada de cada parámetro del programa (RB-03.8)."""
    try:
        filas = context.db.get_auditoria(evento="param_ciclo_cambio", limite=2000)
    except Exception:
        return {}
    ultimas = {}
    for f in filas:                       # la más reciente primero
        entidad = f.get("entidad") or ""
        if entidad.startswith(entidad_prefijo) and entidad not in ultimas:
            ultimas[entidad] = {k: f.get(k) for k in
                                ("usuario", "rol", "ts", "valor_anterior", "valor_nuevo")}
    return ultimas


@app.get("/programas/{numero}/seccion/{seccion}")
def get_programa_seccion(numero: int, seccion: str):
    """Parámetros de una sección (§5.2, §6): valor, por defecto (perfil de
    fábrica del mismo número; "—" si no lo hay, Q-4), rango efectivo (catálogo
    ∩ JSON, RB-05.2), tipo, unidad, opciones, `modificado` y última
    modificación."""
    from autoclave.core.managers import catalogo_parametros as _cp
    cycle = _programa_por_numero(numero)
    if seccion not in _SECCIONES_PROGRAMA or seccion not in cycle.parameters:
        raise HTTPException(status_code=404, detail=f"Sección '{seccion}' no encontrada")
    # O1 (tanda 5): defecto del hospital (cycles/defecto) o, si no, el de fábrica
    cm = context.cycle_manager
    fabrica = (cm.defecto(numero) if callable(getattr(cm, "defecto", None))
               else getattr(cm, "fabrica", {}).get(numero))
    ultimas = _ultimas_modificaciones(f"{cycle.id}/{seccion}/")
    parametros = []
    for ruta, hoja in _hojas_seccion(cycle, seccion):
        defecto = fabrica.get_param(seccion, *ruta) if fabrica is not None else None
        minimo, maximo = _cp.rango_efectivo(hoja, seccion, ruta)
        valor = hoja.get("value")
        parametros.append({
            "path": ruta, "clave": ".".join(ruta), "tipo": hoja.get("type") or "int",
            "unidad": (hoja.get("unit") or "").replace("\ufffd", "°"),
            "clase": hoja.get("clase"),           # C1c (tanda 6): clase explícita de U1
            "valor": valor, "defecto": defecto, "min": minimo, "max": maximo,
            "opciones": hoja.get("options") or [],
            "modificado": defecto is not None and defecto != valor,
            "ultima_modificacion": ultimas.get(f"{cycle.id}/{seccion}/{'.'.join(ruta)}"),
        })
    return {"numero": numero, "cycle_id": cycle.id, "nombre": cycle.name, "seccion": seccion,
            "editable": _programa_editable(cycle), "parametros": parametros}


# ── Gestión de programas (O1, tanda 5; planeacion_opciones.md v4 §3.1) ─────

class _HabilitadoBody(BaseModel):
    habilitado: StrictBool


class _DuplicarBody(BaseModel):
    nombre: str


def _gestion(entidad: str, sesion: Sesion, operar, evento: str, auditoria, deshacer,
             confirmar=None):
    """Técnico fuera de CICLO; ingeniero también en CICLO (como los
    parámetros). El programa activo nunca se borra ni se deshabilita: la
    lectura del activo y el cambio van bajo el lock de la máquina (guard_estado),
    el mismo que /cycle/select. Los archivos son pequeños; la escritura queda
    dentro del lock a propósito para no abrir esa carrera.
    RB-03.5 (revisión O1, SAF-01): sin registro en audit_log el cambio no
    queda aplicado; `deshacer(resultado)` lo revierte."""
    from autoclave.core.managers import gestion_programas as gp
    if getattr(context, "sin_base_de_datos", False) is True:
        _rechazar(503, "BASE_OCUPADA", "Base de datos no disponible: no se aplicó", entidad, sesion)
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion, excepcion_ingeniero=True):
        activo = getattr(getattr(context.control_loop, "cycle", None), "id", None)
        try:
            with _lock_archivos:
                resultado = operar(gp, activo)
        except gp.ErrorPrograma as e:
            raise _Rechazo(e.estado_http, e.codigo, e.motivo)
    anterior, nuevo = auditoria(resultado)
    try:
        context.db.registrar_auditoria(evento, usuario=sesion.usuario, rol=sesion.rol,
                                       entidad=entidad, valor_anterior=anterior,
                                       valor_nuevo=nuevo, detalle=None)
    except Exception:
        logger.exception("%s sin auditoría: se revierte", entidad)
        with context.control_loop.bloqueo_maquina(), _lock_archivos:
            deshacer(gp, resultado)
        _rechazar(503, "BASE_OCUPADA", "No se pudo registrar el cambio: no se aplicó",
                  entidad, sesion)
    if confirmar is not None:
        with _lock_archivos:
            confirmar(gp, resultado)
    return resultado


@app.put("/programas/{numero}/habilitado")
def put_programa_habilitado(numero: int, body: _HabilitadoBody,
                            sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/programas/{numero}/habilitado"
    cm = context.cycle_manager
    anterior, nuevo = _gestion(
        entidad, sesion,
        lambda gp, activo: gp.fijar_habilitado(cm, numero, body.habilitado, activo),
        "programa_habilitado",
        lambda r: ({"habilitado": r[0]}, {"habilitado": r[1]}),
        lambda gp, r: gp.deshacer_habilitado(cm, numero, r[0]))
    return {"ok": True, "numero": numero, "habilitado": nuevo}


@app.post("/programas/{numero}/duplicar")
def post_programa_duplicar(numero: int, body: _DuplicarBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/programas/{numero}/duplicar"
    cm = context.cycle_manager
    nuevo = _gestion(
        entidad, sesion, lambda gp, activo: gp.duplicar(cm, numero, body.nombre),
        "programa_duplicado",
        lambda c: ({"origen": numero}, {"numero": c.number, "cycle_id": c.id, "nombre": c.name}),
        lambda gp, c: gp.deshacer_duplicado(cm, c))
    return {"ok": True, "numero": nuevo.number, "cycle_id": nuevo.id, "nombre": nuevo.name}


@app.delete("/programas/{numero}")
def delete_programa(numero: int,
                    sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/programas/{numero}"
    cm = context.cycle_manager
    _gestion(entidad, sesion, lambda gp, activo: gp.borrar(cm, numero, activo),
             "programa_borrado",
             lambda c: ({"numero": numero, "cycle_id": c.id, "nombre": c.name}, None),
             lambda gp, c: gp.deshacer_borrado(cm, c),
             confirmar=lambda gp, c: gp.confirmar_borrado(c))
    return {"ok": True, "numero": numero}


class _EntradasBody(BaseModel):
    programa: int
    entradas: list


def _ai_habilitadas() -> list[str]:
    from autoclave.core.runtime.io_names import leer_io_enabled
    return leer_io_enabled()["AI"]


@app.get("/cycle/display-inputs")
def get_entradas_mostradas(programa: int):
    """Entradas mostradas del programa (1 a 3) y las AI habilitadas del equipo."""
    from autoclave.core.managers import gestion_programas as gp
    cycle = _programa_por_numero(programa)
    habilitadas = _ai_habilitadas()
    return {"programa": programa, "entradas": gp.entradas_de(cycle, habilitadas),
            "habilitadas": habilitadas, "editable": getattr(cycle, "source", "") == "user"}


@app.put("/cycle/display-inputs")
def put_entradas_mostradas(body: _EntradasBody,
                           sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    entidad = f"/cycle/display-inputs/{body.programa}"
    cm = context.cycle_manager
    previas = []

    def operar(gp, activo):
        previas.append(getattr(gp.programa(cm, body.programa), "entradas_mostradas", None))
        return gp.fijar_entradas(cm, body.programa, body.entradas, _ai_habilitadas())
    anterior, nueva = _gestion(entidad, sesion, operar, "entradas_mostradas",
                               lambda r: (r[0], r[1]),
                               lambda gp, r: gp.deshacer_entradas(cm, body.programa, previas[0]))
    return {"ok": True, "entradas": nueva}


# ── Sensores del ciclo (tanda 2026-10-14 §1.1; RS-01, RS-02) ───────────────

def _programa_por_numero(numero: int):
    for cycle in list(context.cycle_manager.cycles.values()):
        if getattr(cycle, "number", None) == numero:
            return cycle
    raise HTTPException(status_code=404, detail=f"Programa {numero} no encontrado")


@app.get("/cycle/sensors")
def get_cycle_sensors(programa: int):
    """Sensores del programa N: id, nombre (ubicación), tipo, estado
    (disponible / sin_senal / no_instalado), lectura y rol. Un sensor
    no_instalado solo se lista si el programa le asigna un rol activo."""
    cycle = _programa_por_numero(programa)
    perfil = getattr(context, "profile", None)
    asignacion = sc.asignacion_de(cycle)
    sensores = []
    for s in sc.SENSORES:
        estado_s = sc.estado_sensor(perfil, context.estado, s)
        rol = asignacion.get(s, sc.NO_EN_USO)
        if estado_s == sc.NO_INSTALADO and rol == sc.NO_EN_USO:
            continue
        lectura = context.estado.sensores_temp.get(s)
        sensores.append({
            "id": s, "nombre": sc.NOMBRES[s], "tipo": sc.TIPOS[s], "estado": estado_s,
            "lectura": lectura if lectura_valida(lectura) else None, "rol": rol,
        })
    return {
        "programa": programa,
        "cycle_id": cycle.id,
        "asignacion": asignacion,
        "errores": sc.errores_asignacion(asignacion),
        "formato_antiguo": bool(getattr(cycle, "sensores_formato_antiguo", False)),
        "editable": getattr(cycle, "source", "") == "user",
        "sensores": sensores,
    }


class _SensorRolesBody(BaseModel):
    programa: int
    asignacion: dict
    asignacion_anterior_esperada: dict


def _normalizar_asignacion(asignacion: dict) -> dict:
    """Completa con no_en_uso los sensores del catálogo que falten; conserva
    las claves desconocidas para que la validación las rechace."""
    return {**{s: sc.NO_EN_USO for s in sc.SENSORES}, **asignacion}


def _escribir_json_programa(cycle, cambiar) -> None:
    """Lee el JSON del programa, aplica `cambiar(data)` y lo escribe de forma
    atómica (.tmp + fsync + os.replace): un corte a mitad de la escritura no
    deja el programa truncado (TMG-02 de T3). Si falla, borra el .tmp."""
    import json as _json
    import os as _os
    from pathlib import Path as _Path

    import shutil as _shutil

    path = _Path(cycle._path)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    cambiar(data)
    # RB-04.2 (T10): la versión anterior queda como <nombre>.json.bak
    _shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            _os.fsync(f.fileno())
        _os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _escribir_sensores_json(cycle, asignacion: dict) -> None:
    """Campo cycle_temperature_sensors del JSON (RS-02)."""
    def cambiar(data):
        data["cycle_temperature_sensors"] = {s: asignacion[s] for s in sc.SENSORES}
    _escribir_json_programa(cycle, cambiar)


@app.put("/cycle/sensor-roles")
def put_sensor_roles(body: _SensorRolesBody,
                     sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """Asigna los roles de los sensores de un programa: todo o nada, con
    control de concurrencia por asignacion_anterior_esperada y auditoría
    ROLES_SENSOR (RS-02). Técnico fuera de CICLO; ingeniero también en CICLO
    (el ciclo en curso conserva su instantánea, RS-03.4). Solo programas de
    usuario."""
    cycle = _programa_por_numero(body.programa)
    entidad = f"{cycle.id}/cycle_temperature_sensors"
    if getattr(cycle, "source", "") != "user" or not hasattr(cycle, "_path"):
        _rechazar(409, "programa_de_fabrica",
                  "Los programas de fábrica no se modifican", entidad, sesion)
    nueva = _normalizar_asignacion(body.asignacion)
    errores = sc.errores_asignacion(nueva)
    if errores:
        _rechazar(422, sc.ASIGNACION_INVALIDA, "; ".join(errores), entidad, sesion,
                  extra={"errores": errores})
    esperada = _normalizar_asignacion(body.asignacion_anterior_esperada)

    propagado, motivo_propagacion = False, "sin_copias"
    with _lock_archivos:      # serializa escritores: la asignación no cambia entre pasos
        with guard_estado(DISTINTO_DE_CICLO, entidad, sesion, excepcion_ingeniero=True):
            anterior = dict(sc.asignacion_de(cycle))
            if sc.canonica(esperada) != sc.canonica(anterior):
                raise _Rechazo(409, "asignacion_desfasada",
                               "La asignación cambió desde que se leyó; vuelva a cargarla",
                               extra={"asignacion_actual": anterior})
            faltan = sc.errores_disponibilidad(nueva, getattr(context, "profile", None),
                                               context.estado)
            if faltan:
                raise _Rechazo(422, sc.SENSOR_NO_DISPONIBLE,
                               f"Sensores sin lectura o no instalados: {faltan}",
                               extra={"sensores": faltan})
        # archivo fuera de _sm_lock (no detener el tick); si falla, nada cambió
        try:
            _escribir_sensores_json(cycle, nueva)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo guardar el programa: {exc}")
        with context.control_loop.bloqueo_maquina():
            # SAF-05 de T3: el ciclo pudo arrancar mientras se escribía el
            # archivo; un técnico no modifica el programa en CICLO.
            en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            permitido = not en_ciclo or sesion.rol == ROL_INGENIERO
            if permitido:
                cycle.sensores = dict(nueva)
                cycle.sensores_formato_antiguo = False
                if not en_ciclo:
                    # S4: libera un estado seguro detenido por el Principal
                    # viejo, solo si la sonda nueva es segura (no más fría)
                    propagado, motivo_propagacion = context.control_loop.aplicar_roles_sensores(
                        cycle.id, nueva)
        if not permitido:
            _escribir_sensores_json(cycle, anterior)       # revierte el archivo
            _rechazar(409, "estado_no_permitido",
                      "Hay un ciclo en curso: no se aplicó el cambio", entidad, sesion)

    _auditar("ROLES_SENSOR", sesion, entidad=entidad,
             valor_anterior=sc.canonica(anterior), valor_nuevo=sc.canonica(nueva),
             detalle={"programa": cycle.id, "numero": body.programa,
                      "param": "cycle_temperature_sensors",
                      "estado_seguro_propagado": propagado,
                      "motivo_propagacion": motivo_propagacion})
    return {"ok": True, "asignacion": nueva,
            "estado_seguro_propagado": propagado}


def _save_cycle_json(cycle) -> None:
    """Escribe cycle.parameters de vuelta al JSON del ciclo (solo ciclos user)."""
    def cambiar(data):
        data["parameters"] = cycle.parameters
    _escribir_json_programa(cycle, cambiar)


# Direct hardware access — bypasses control_loop, for bench validation only

class _OutputSetBody(BaseModel):
    value: bool
    momentanea: bool = False


# P-ES-3 / P-ES-4 (propuestas pendientes de confirmar): una salida momentánea
# se apaga sola si no se renueva, y el modo prueba se cierra sin actividad.
CADUCIDAD_MOMENTANEA_S = 1.5
INACTIVIDAD_MODO_PRUEBA_S = 90.0
_timers_momentaneas: dict[int, threading.Timer] = {}
_timer_inactividad: threading.Timer | None = None
_lock_vigilancias = threading.Lock()


def _cancelar_vigilancias_prueba() -> None:
    global _timer_inactividad
    with _lock_vigilancias:
        for t in _timers_momentaneas.values():
            t.cancel()
        _timers_momentaneas.clear()
        if _timer_inactividad is not None:
            _timer_inactividad.cancel()
            _timer_inactividad = None


def _nombre_do(canal: int) -> str:
    return next((n for n, i in EstadoAutoclave.map_do.items() if i + 1 == canal), str(canal))


# TMG-07 / revisión P1 (TMG-03): cada entrada al modo prueba es una generación
# nueva; un temporizador armado en otra generación (que ya pasó su chequeo de
# identidad mientras esperaba el candado) no actúa sobre la sesión actual.
_generacion_prueba = 0


def _caducar_momentanea(canal: int, timer: threading.Timer, generacion: int = -1) -> None:
    """Hilo del temporizador: sin renovación a tiempo, apaga la salida."""
    with _lock_vigilancias:
        if _timers_momentaneas.get(canal) is not timer:
            return   # renovada o cancelada mientras tanto
        del _timers_momentaneas[canal]
    with context.control_loop.bloqueo_maquina():
        if not context.control_loop.test_mode_active or generacion != _generacion_prueba:
            return
        context.setdo.set_output(canal, False)
        token = _token_modo_prueba
    sesion = tokens.obtener(token, renovar=False) if token else None
    dueno = tokens.quien_fue(token) if sesion is None else None   # TMG-08
    _auditar("salida_prueba", sesion, usuario=dueno[0] if dueno else "",
             entidad=_nombre_do(canal), valor_nuevo=False,
             detalle={"motivo": "caducó sin renovación"})


def _armar_momentanea(canal: int) -> bool:
    """Arma o renueva la caducidad. Devuelve True si era una renovación."""
    with _lock_vigilancias:
        previo = _timers_momentaneas.pop(canal, None)
        if previo is not None:
            previo.cancel()
        generacion = _generacion_prueba
        timer = threading.Timer(CADUCIDAD_MOMENTANEA_S,
                                lambda: _caducar_momentanea(canal, timer, generacion))
        timer.daemon = True
        _timers_momentaneas[canal] = timer
        timer.start()
    return previo is not None


def _desarmar_momentanea(canal: int) -> None:
    with _lock_vigilancias:
        previo = _timers_momentaneas.pop(canal, None)
    if previo is not None:
        previo.cancel()


def _salir_por_inactividad(timer: threading.Timer, generacion: int = -1) -> None:
    global _timer_inactividad
    with _lock_vigilancias:
        if _timer_inactividad is not timer:
            return
        _timer_inactividad = None
    with context.control_loop.bloqueo_maquina():
        if not context.control_loop.test_mode_active or generacion != _generacion_prueba:
            return
        token = _token_modo_prueba
        _salir_modo_prueba()
    sesion = tokens.obtener(token, renovar=False) if token else None
    dueno = tokens.quien_fue(token) if sesion is None else None   # TMG-08
    _auditar("modo_prueba_sale", sesion, usuario=dueno[0] if dueno else "",
             detalle={"motivo": "sin actividad de la sesión (keepalive)"})


def _marcar_actividad_prueba() -> None:
    """Rearma el plazo de inactividad del modo prueba (cada orden y keepalive)."""
    global _timer_inactividad
    with _lock_vigilancias:
        if _timer_inactividad is not None:
            _timer_inactividad.cancel()
        generacion = _generacion_prueba
        timer = threading.Timer(INACTIVIDAD_MODO_PRUEBA_S,
                                lambda: _salir_por_inactividad(timer, generacion))
        timer.daemon = True
        _timer_inactividad = timer
        timer.start()


_requiere_rol_prueba = requiere_rol(ROL_TECNICO, ROL_INGENIERO)


def _rechazar_si_sin_datos_vigentes() -> None:
    """Modo prueba con el enlace caído o con la trama DI vencida: las órdenes
    se darían sobre lecturas viejas (adenda E0/E1, A-8, TMG-05). Mismo código
    de rechazo que las órdenes de puerta con el enlace caído."""
    cl = context.control_loop
    if cl.desconectado is True or cl.datos_vigentes is False:
        raise _Rechazo(409, "sin_conexion_tarjeta",
                       "Sin conexión con la tarjeta de control o datos no vigentes")


@app.get("/io/channels")
def io_channels(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """B-ES-2: canales de Entradas / Salidas del equipo (io_enabled) con id
    físico, clave i18n y si la salida es momentánea (D-ES-02, D-ES-03, D-ES-09)."""
    salidas = io_names.canales_digitales("DO")
    for c in salidas:
        canal = EstadoAutoclave.map_do[c["estado_key"]] + 1
        # fuente de vapor que el equipo no usa (E1b / S1): se muestra deshabilitada
        c["bloqueada"] = context.setdo.salida_bloqueada(canal) is True
    return {
        "DI": io_names.canales_digitales("DI"),
        "DO": salidas,
        "temperature": io_names.sensores("temperature"),
        "pressure": io_names.sensores("pressure"),
    }


@app.post("/io/test/enter")
def io_test_enter(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """Activa el modo prueba: pausa la máquina de estados (sin importar la
    fase — PREPARACION, PREPARADO o FALLA) y apaga todas las salidas para
    permitir control manual. Rechazado en CICLO o con
    el paro de emergencia activo. Recuerda la sesión que entró (§5.4).

    El ALL_OFF de enter_test_mode corre con _sm_lock tomado (espera el ACK
    hasta 1 s); es aceptable porque el guard excluye CICLO."""
    global _token_modo_prueba, _generacion_prueba
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, "/io/test/enter", sesion):
        motivo_config = context.control_loop.bloqueo_configuracion
        if isinstance(motivo_config, str) and motivo_config:
            raise _Rechazo(409, "configuracion_invalida",
                           f"Configuración inválida: {motivo_config}")
        _rechazar_si_sin_datos_vigentes()
        # un logout de esta sesión pudo llegar mientras esta petición esperaba
        if not tokens.existe(sesion.token):
            raise _Rechazo(401, "sesion_invalida", _MOTIVO_SESION_INVALIDA)
        # sin esto, otra sesión le quitaría la propiedad a la que entró
        if (context.control_loop.test_mode_active
                and _token_modo_prueba not in (None, sesion.token)):
            raise _Rechazo(409, "modo_prueba_otra_sesion",
                           "El modo prueba ya está activo en otra sesión")
        ya_activo = context.control_loop.test_mode_active
        ok, reason = context.control_loop.enter_test_mode()
        if not ok:
            raise _Rechazo(409, "modo_prueba_rechazado", reason)
        _token_modo_prueba = sesion.token
        if not ya_activo:     # reentrada de la misma sesión: misma generación
            _generacion_prueba += 1
        _marcar_actividad_prueba()
    _auditar("modo_prueba_entra", sesion)
    return {"ok": True}


# B-ES-8: causas que la UI puede declarar al salir (lista cerrada, §6.5)
_CAUSAS_SALIDA_UI = frozenset({"salida solicitada", "abandono de la sección",
                               "inactividad de la interfaz", "cierre de sesión"})


@app.post("/io/test/exit")
def io_test_exit(sesion: Sesion = Depends(_requiere_rol_prueba),
                 body: dict | None = Body(None)):
    """Sale del modo prueba: apaga todas las salidas y reanuda la máquina de
    estados. 409 si no se estaba en modo prueba o si lo pide otra sesión.
    Comprobación y salida bajo _sm_lock: ninguna orden de encendido ya
    validada puede llegar después del apagado."""
    with guard_estado(frozenset(), "/io/test/exit", sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if _token_modo_prueba != sesion.token:
            raise _Rechazo(409, "modo_prueba_no_dueno",
                           "Solo la sesión que activó el modo prueba puede salir de él")
        _salir_modo_prueba()
    causa = body.get("motivo") if isinstance(body, dict) else None
    if causa not in _CAUSAS_SALIDA_UI:
        causa = "salida solicitada"
    _auditar("modo_prueba_sale", sesion, detalle={"motivo": causa})
    return {"ok": True}


# canales cerrar_puerta_N cuya orden se invirtió y siguen pulsados (P-ES-8)
_cierres_invertidos: set[int] = set()


def _puerta_con_atrapamiento(canal_cerrar: int, encender: bool):
    """Seguro de atrapamiento en modo prueba (D-ES-16, §6.7). Devuelve
    (puerta, nueva): la puerta cuya orden de cerrar debe invertirse en abrir y
    si es la primera inversión de esta pulsación. Una vez invertida, sigue
    invertida hasta que el usuario suelta (OFF), aunque la señal se libere.
    Interpreta la entrada semántica (NC: 0 = atrapada), no el bit crudo."""
    if not encender:
        _cierres_invertidos.discard(canal_cerrar)
        return None, False
    for door in (context.doors or []):
        do, di = getattr(door, "do", None), getattr(door, "di", None)
        if not (isinstance(do, dict) and isinstance(di, dict)):
            continue
        if do.get("cerrar") != canal_cerrar or "atrapamiento" not in di or "abrir" not in do:
            continue
        if canal_cerrar in _cierres_invertidos:
            return door, False
        if context.estado.sensores_di.get(di["atrapamiento"]) == 0:
            _cierres_invertidos.add(canal_cerrar)
            return door, True
    return None, False


@app.patch("/io/test/output/{name}")
def io_test_set_output(name: str, body: _OutputSetBody,
                       sesion: Sesion = Depends(_requiere_rol_prueba)):
    """Acciona una salida en modo prueba. Apagar siempre se permite dentro del
    modo prueba; encender exige además ser la sesión dueña y R-02 (§5.4)."""
    if name not in EstadoAutoclave.map_do:
        raise HTTPException(status_code=404, detail=f"Output '{name}' no encontrado")
    entidad = f"/io/test/output/{name}"
    if body.momentanea and name not in io_names.SALIDAS_MOMENTANEAS:
        raise HTTPException(status_code=422,
                            detail=f"'{name}' no es una salida momentánea")
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, entidad, sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _motivo_paro("Paro de emergencia activado"))
        _rechazar_si_sin_datos_vigentes()
        if body.value:
            if getattr(context.control_loop, "apagando", False) is True:   # A1
                raise _Rechazo(409, "apagado_en_curso", "El equipo se está apagando")
            # encender solo desde la sesión que está a cargo de la prueba;
            # apagar queda abierto a cualquier sesión de prueba (es lo seguro)
            if _token_modo_prueba != sesion.token:
                raise _Rechazo(409, "modo_prueba_no_dueno",
                               "Solo la sesión que activó el modo prueba puede encender salidas")
            # D-ES-15: en modo prueba se permiten todas las salidas; R-02
            # (presión atmosférica y puertas cerradas) ya no se exige aquí.
        # map_do es 0-indexado (posición en el bitstream DO), pero
        # serial_link.set_output() espera el número de canal DO físico
        # 1-indexado (DO1..DO24), igual que SetOutput y la fábrica de puertas.
        index = EstadoAutoclave.map_do[name]
        if body.value and context.setdo.salida_bloqueada(index + 1) is True:
            # E1b: salida de una fuente de vapor que el equipo no tiene; S1 (tanda
            # 2): con generador interno ni DO1 ni DO2 (el generador se controla solo)
            raise _Rechazo(409, "fuente_vapor_no_instalada",
                           "Esta salida de fuente de vapor no la usa este equipo (vapor_source)")
        puerta_atrapada, nueva = _puerta_con_atrapamiento(index + 1, body.value)
        if puerta_atrapada is not None:
            # D-ES-16: la orden de cerrar con atrapamiento activo se convierte en abrir
            context.setdo.set_output(index + 1, False)
            context.setdo.set_output(puerta_atrapada.do["abrir"], True)
            _desarmar_momentanea(index + 1)
            if body.momentanea:
                _armar_momentanea(puerta_atrapada.do["abrir"])
            _marcar_actividad_prueba()
            if nueva:
                _auditar("atrapamiento_orden_invertida", sesion, entidad=name,
                         detalle={"puerta": getattr(puerta_atrapada, "name", None)})
            return {"ok": True, "name": name, "value": False, "invertida": True}
        context.setdo.set_output(index + 1, body.value)
        renovacion = False
        if body.value and body.momentanea:
            renovacion = _armar_momentanea(index + 1)
        else:
            _desarmar_momentanea(index + 1)
        _marcar_actividad_prueba()
    # una salida momentánea registra solo el primer y último pulso, no cada renovación
    if not renovacion:
        _auditar("salida_prueba", sesion, entidad=name, valor_nuevo=body.value)
    return {"ok": True, "name": name, "value": body.value}


@app.post("/io/test/keepalive")
def io_test_keepalive(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """P-ES-4: la sesión dueña avisa que sigue ahí; sin avisos (ni órdenes) el
    backend sale solo del modo prueba."""
    with guard_estado(frozenset(), "/io/test/keepalive", sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if _token_modo_prueba != sesion.token:
            raise _Rechazo(409, "modo_prueba_no_dueno",
                           "Solo la sesión que activó el modo prueba puede mantenerlo")
        _marcar_actividad_prueba()
    return {"ok": True}


class _SalidaForzadaBody(BaseModel):
    confirmar: StrictBool = False         # SAF-06: solo el literal JSON true
    motivo: str = ""


@app.post("/io/test/force-exit")
def io_test_force_exit(body: _SalidaForzadaBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    """B8 (tanda 4): salida forzada del modo prueba HUÉRFANO. Solo el dueño
    puede dejar el modo prueba; si ese usuario ya no tiene sesión (token vencido
    por inactividad, cierre de sesión, cambio de turno), un INGENIERO con sesión
    puede terminarlo con confirmación explícita (`confirmar: true`). Un técnico
    solo puede si es el mismo usuario dueño (SAF-03 de la revisión: salir es la
    dirección segura); otro técnico, 403. Con el dueño aún en sesión, 409: debe salir él (o esperar a
    que su sesión caduque). Misma salida que la normal: todas las salidas a
    seguro y se reanuda la máquina; un estado seguro en curso sigue su camino.
    Queda en audit_log quién fuerza, a quién se le sacó y por qué."""
    entidad = "/io/test/force-exit"
    if body.confirmar is not True:
        _rechazar(422, "confirmacion_requerida",
                  "Confirme explícitamente la salida forzada del modo prueba", entidad, sesion)
    motivo = (body.motivo or "").strip()[:200] or "modo prueba huérfano"
    with guard_estado(frozenset(), entidad, sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        dueno_token = _token_modo_prueba
        if (dueno_token is not None and dueno_token != sesion.token
                and tokens.existe(dueno_token)):
            raise _Rechazo(409, "modo_prueba_dueno_vigente",
                           "El dueño del modo prueba sigue con sesión: debe salir él")
        dueno = tokens.quien_fue(dueno_token)
        if sesion.rol != ROL_INGENIERO and (dueno is None or dueno[0] != sesion.usuario):
            raise _Rechazo(403, "rol_sin_permiso",
                           "Solo un ingeniero o el propio dueño pueden forzar la salida")
        estado_seguro = getattr(getattr(context.control_loop, "estado_seguro", None), "activo", False)
        _salir_modo_prueba()
    _auditar("modo_prueba_salida_forzada", sesion, entidad=entidad,
             valor_anterior={"dueno": dueno[0] if dueno else None,
                             "rol_dueno": dueno[1] if dueno else None},
             detalle={"motivo": motivo, "forzada_por": sesion.usuario,
                      "dueno": dueno[0] if dueno else None,
                      "estado_seguro_activo": estado_seguro is True})
    _auditar("modo_prueba_sale", sesion, detalle={"motivo": "salida forzada por ingeniero"})
    return {"ok": True, "dueno": dueno[0] if dueno else None}
