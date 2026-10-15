# autoclave/backend/server.py

from types import SimpleNamespace
import logging
import sqlite3
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import Depends, HTTPException, FastAPI, Body, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
from autoclave.core.runtime import progreso_ciclo
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.lectura import lectura_valida
from autoclave.installation.profile import (entradas_no_monitoreadas, sondas_no_vigiladas,
                                           tarjeta_emparejada)
from autoclave.services.domain.logging.ticket_formatter import format_ticket
from autoclave.services.domain.reportes import resumen_periodo
from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point
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

# Variantes del guard de estado (§5.5). EMERGENCIA y HIBERNACION hoy no se
# alcanzan (OPC-25), pero se bloquean igual (decisiones 15 y 20).
DISTINTO_DE_CICLO = frozenset({GlobalState.CICLO})
DISTINTO_DE_CICLO_E_HIBERNACION = frozenset({
    GlobalState.CICLO, GlobalState.HIBERNACION, GlobalState.EMERGENCIA,
})

_MOTIVO_ESTADO = {
    GlobalState.CICLO:       "No permitido con un ciclo en curso",
    GlobalState.HIBERNACION: "No permitido con el equipo en suspensión",
    GlobalState.EMERGENCIA:  "No permitido en estado de emergencia",
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
        logger.exception("No se pudo registrar '%s' en audit_log", evento)


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


def _prueba_cancelada_por_paro() -> None:
    """Aviso del ControlLoop (hilo del loop, fuera de _sm_lock): el paro de
    emergencia canceló el modo prueba. Olvida la sesión dueña y lo registra."""
    global _token_modo_prueba
    with context.control_loop.bloqueo_maquina():
        if context.control_loop.test_mode_active:
            return   # ya se volvió a entrar: no es esta cancelación
        token, _token_modo_prueba = _token_modo_prueba, None
    sesion = tokens.obtener(token) if token else None
    _auditar("modo_prueba_sale", sesion, detalle={"motivo": "paro de emergencia"})



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
    entidad = f"{tipo}/{sensor}"

    # Solo comprobación bajo _sm_lock: el guard solo deja pasar en CICLO al
    # ingeniero (el técnico recibe 409), así que la escritura no necesita ser
    # atómica con la comprobación. YAML y recarga van fuera del
    # lock para no detener el tick (revisión de la etapa 1, hallazgo D).
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

        # SAF-03 de T3: si un ciclo arrancó entre la comprobación y este
        # punto, el técnico no puede cambiar la calibración en curso
        if sesion.rol != ROL_INGENIERO:
            with context.control_loop.bloqueo_maquina():
                en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
            if en_ciclo:
                raise HTTPException(status_code=409,
                                    detail="Hay un ciclo en curso: calibración no aplicada")
        write_user_calibration(
            CALIBRATION_PATH, tipo, index, new_gain, new_offset,
            shown_low, real_low, shown_high, real_high,
        )
        context.units.reload_calibration(CALIBRATION_PATH)
    detalle = {"puntos": {"shown_low": shown_low, "real_low": real_low,
                          "shown_high": shown_high, "real_high": real_high}}
    detalle.update(contexto_ciclo)

    _auditar("calibracion_cambio", sesion, entidad=entidad,
             valor_anterior={"gain": old_gain, "offset": old_offset},
             valor_nuevo={"gain": new_gain, "offset": new_offset},
             detalle=detalle)

    return {"ok": True, "gain": new_gain, "offset": new_offset}


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
    return {
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
    return {"camara_segura": segura, "no_abrir": not segura, "camara_segura_motivo": motivo}


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
        "fase_ciclo":            getattr(estado, "fase_ciclo", ""),
        "fase_en_sostenimiento": getattr(estado, "fase_en_sostenimiento", False),
        "prevacio_progreso":     getattr(estado, "prevacio_progreso", ""),
        # Del enlace serial, no de Units: Units solo se entera por on_update
        # y no refleja el handshake (ver planeacion_protocolo_serial_esp32.md).
        # E2 (fin de ciclo §5): falla cerrada; "NO ABRIR" en cualquier estado
        **_camara_segura_status(estado),
        "card_connected":        context.serial.is_connected(),
        "comunicacion":          _diagnostico_comunicacion(),
        "tarjeta":               _tarjeta_status(),
        "test_mode_active":      context.control_loop.test_mode_active,
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
    return context.config_manager.get()


@app.get("/cycle")
def get_selected_cycle():
    cycle = context.cycle_manager.get_selected_cycle()

    if cycle is None:
        raise HTTPException(status_code=404, detail="No hay ciclo seleccionado")

    return {
        "id": cycle.id,
        "name": cycle.name,
        "number": getattr(cycle, "number", None),
        "parameters": cycle.parameters
    }


@app.get("/cycles")
def list_cycles():
    return [
        {"id": c.id, "name": c.name, "source": getattr(c, "source", "user")}
        for c in context.cycle_manager.cycles.values()
    ]


class _SelectCycleBody(BaseModel):
    cycle_id: str


@app.post("/cycle/select")
def select_cycle(body: _SelectCycleBody):
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")
    if getattr(cycle, "source", "user") != "user":
        raise HTTPException(status_code=422, detail="Solo se pueden seleccionar ciclos de usuario")

    ok, reason = context.control_loop.set_active_cycle(cycle)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)

    context.cycle_manager.set_default_cycle(body.cycle_id)
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
    numeros = {tipo: getattr(c, "number", None) for tipo, c in context.cycle_manager.cycles.items()}
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


@app.post("/cycle/start")
def start_cycle():
    """
    Solicita el inicio del ciclo de esterilización.
    Sólo tiene efecto cuando el sistema está en estado PREPARADO y
    la flag LISTO_PARA_CICLO es True.  La máquina de estados gestiona
    la transición real.
    """
    estado = context.estado
    _rechazar_si_config_invalida("/cycle/start")
    if getattr(context, "sin_base_de_datos", False) is True:
        # alarma OPERANDO_SIN_BD: un ciclo sin registro rompe la trazabilidad
        _rechazar(409, "sin_base_de_datos",
                  "Base de datos no disponible: no se puede iniciar un ciclo", "/cycle/start")

    if not estado.get_flag("LISTO_PARA_CICLO"):
        raise HTTPException(
            status_code=409,
            detail="El sistema no está listo para iniciar un ciclo"
        )

    # RS-06 (tanda §1.1): asignación de sensores válida y todos los sensores
    # en uso del programa seleccionado con lectura
    rechazo = sc.verificar_inicio(getattr(context.control_loop, "cycle", None),
                                  getattr(context, "profile", None), estado)
    if rechazo is not None:
        _rechazar(409, rechazo[0], rechazo[1], "/cycle/start")

    estado.set_flag("START_CICLO", True)
    return {"ok": True, "action": "START_CICLO"}


@app.post("/cycle/abort")
def abort_cycle():
    """
    Solicita el aborto del ciclo en curso.
    Activa la flag CICLO_CANCELADO; el CicloState ejecutará el
    protocolo de fallo en el siguiente tick del control loop.
    """
    estado = context.estado

    from autoclave.state_machine.machine.enum_global import GlobalState
    if estado.get_machine_state() != GlobalState.CICLO:
        raise HTTPException(
            status_code=409,
            detail="No hay un ciclo en curso"
        )

    estado.set_flag("CICLO_CANCELADO", True)
    return {"ok": True, "action": "CICLO_CANCELADO"}


_MOTIVO_PARO = "Paro de emergencia activado: suéltelo antes de reconocer"


@app.post("/fault/reset")
def reset_fault():
    """Reconoce el estado de falla y solicita retornar a PREPARACION. Sin
    identificación (decisión 16). Con el paro de emergencia activo, 409 y no
    se guarda RESET_FALLA: tras soltarlo hay que reconocer de nuevo (§5.9)."""
    entidad = "/fault/reset"
    with guard_estado(frozenset(), entidad) as estado:
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", _MOTIVO_PARO)
        # con el modo prueba la máquina está pausada: el reconocimiento se
        # aplicaría al salir, sin uno posterior a las pruebas (TMG-07)
        if context.control_loop.test_mode_active is True:
            raise _Rechazo(409, "modo_prueba_activo", "No permitido con el modo prueba activo")
        if estado != GlobalState.FALLA:
            raise _Rechazo(409, "estado_no_permitido", "El sistema no está en estado de falla",
                           extra={"estado": getattr(estado, "name", str(estado))})
        context.estado.set_flag("RESET_FALLA", True)
    _auditar("falla_reconocida", entidad=entidad)
    return {"ok": True, "action": "RESET_FALLA"}


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
            raise _Rechazo(409, "paro_emergencia", _MOTIVO_PARO)
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

    Guard de estado: 409 en CICLO, HIBERNACION y EMERGENCIA (en PREPARACION,
    PREPARADO y FALLA se permite). Las condiciones físicas las aplica
    ServicioPuertas, fallando cerradas; si las incumple, o si la puerta no
    acepta la orden (bloqueo mecánico, no está abierta), 409 con el motivo.
    La comprobación y la orden van bajo _sm_lock para no intercalarse con el
    tick. `sin_actuador`: la puerta no tiene actuador (SimpleDoor) y la orden
    no mueve nada. `source_door` sigue sin usarse (fuera de alcance)."""
    entidad = f"/doors/{door_name}/{accion}"
    _rechazar_si_config_invalida(entidad)
    servicio = context.servicio_puertas
    if door_name not in servicio.doors:
        raise HTTPException(status_code=404, detail="Puerta desconocida")
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
            raise _Rechazo(409, "puerta_rechazada", reason or "Orden de puerta no permitida")
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


class _CycleParamValueBody(BaseModel):
    cycle_id: str
    fase: str
    path: list[str]
    value: object


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
                           sesion: Sesion = Depends(requiere_rol(ROL_INGENIERO))):
    """Actualiza un único parámetro (cualquier sección, incluido el secado) de
    cualquier ciclo cargado y persiste si es 'user'. Valida contra el
    'type'/'min'/'max' que ya trae cada parámetro en su propio JSON.
    Solo ingeniero (decisión 25). En CICLO (§5.8, T-17) el cambio se guarda
    siempre en el programa almacenado y aplica también al ciclo en curso solo
    si es su programa y la fase del parámetro no ha iniciado; la respuesta
    lo indica en `aplica` ("en_curso" o "siguiente")."""
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")

    if not body.path:
        raise HTTPException(status_code=422, detail="'path' no puede estar vacío")

    entidad = f"{body.cycle_id}/{body.fase}/{'.'.join(body.path)}"
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
        try:
            value = cycle.set_param(body.fase, body.path, body.value)
        except KeyError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=422, detail=str(e))

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

    _auditar("param_ciclo_cambio", sesion, entidad=entidad,
             valor_anterior=anterior, valor_nuevo=value, detalle=detalle)
    return {"ok": True, "value": value, "aplica": aplica}


# ── Sensores del ciclo (tanda 2026-10-14 §1.1; RS-01, RS-02) ───────────────

def _programa_por_numero(numero: int):
    for cycle in context.cycle_manager.cycles.values():
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

    path = _Path(cycle._path)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    cambiar(data)
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
        if not permitido:
            _escribir_sensores_json(cycle, anterior)       # revierte el archivo
            _rechazar(409, "estado_no_permitido",
                      "Hay un ciclo en curso: no se aplicó el cambio", entidad, sesion)

    _auditar("ROLES_SENSOR", sesion, entidad=entidad,
             valor_anterior=sc.canonica(anterior), valor_nuevo=sc.canonica(nueva),
             detalle={"programa": cycle.id, "numero": body.programa,
                      "param": "cycle_temperature_sensors"})
    return {"ok": True, "asignacion": nueva}


def _save_cycle_json(cycle) -> None:
    """Escribe cycle.parameters de vuelta al JSON del ciclo (solo ciclos user)."""
    def cambiar(data):
        data["parameters"] = cycle.parameters
    _escribir_json_programa(cycle, cambiar)


# Direct hardware access — bypasses control_loop, for bench validation only

class _OutputSetBody(BaseModel):
    value: bool


_requiere_rol_prueba = requiere_rol(ROL_TECNICO, ROL_INGENIERO)


def _rechazar_si_sin_datos_vigentes() -> None:
    """Modo prueba con el enlace caído o con la trama DI vencida: las órdenes
    se darían sobre lecturas viejas (adenda E0/E1, A-8, TMG-05). Mismo código
    de rechazo que las órdenes de puerta con el enlace caído."""
    cl = context.control_loop
    if cl.desconectado is True or cl.datos_vigentes is False:
        raise _Rechazo(409, "sin_conexion_tarjeta",
                       "Sin conexión con la tarjeta de control o datos no vigentes")


@app.post("/io/test/enter")
def io_test_enter(sesion: Sesion = Depends(_requiere_rol_prueba)):
    """Activa el modo prueba: pausa la máquina de estados (sin importar la
    fase — PREPARACION, PREPARADO o FALLA) y apaga todas las salidas para
    permitir control manual. Rechazado en CICLO, HIBERNACION, EMERGENCIA o con
    el paro de emergencia activo. Recuerda la sesión que entró (§5.4).

    El ALL_OFF de enter_test_mode corre con _sm_lock tomado (espera el ACK
    hasta 1 s); es aceptable porque el guard excluye CICLO."""
    global _token_modo_prueba
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, "/io/test/enter", sesion):
        motivo_config = context.control_loop.bloqueo_configuracion
        if isinstance(motivo_config, str) and motivo_config:
            raise _Rechazo(409, "configuracion_invalida",
                           f"Configuración inválida: {motivo_config}")
        _rechazar_si_sin_datos_vigentes()
        # un logout de esta sesión pudo llegar mientras esta petición esperaba
        if tokens.obtener(sesion.token) is None:
            raise _Rechazo(401, "sesion_invalida", _MOTIVO_SESION_INVALIDA)
        # sin esto, otra sesión le quitaría la propiedad a la que entró
        if (context.control_loop.test_mode_active
                and _token_modo_prueba not in (None, sesion.token)):
            raise _Rechazo(409, "modo_prueba_otra_sesion",
                           "El modo prueba ya está activo en otra sesión")
        ok, reason = context.control_loop.enter_test_mode()
        if not ok:
            raise _Rechazo(409, "modo_prueba_rechazado", reason)
        _token_modo_prueba = sesion.token
    _auditar("modo_prueba_entra", sesion)
    return {"ok": True}


@app.post("/io/test/exit")
def io_test_exit(sesion: Sesion = Depends(_requiere_rol_prueba)):
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
    _auditar("modo_prueba_sale", sesion, detalle={"motivo": "salida solicitada"})
    return {"ok": True}


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _entrada_digital(valor) -> bool | None:
    """1/True → True, 0/False → False; cualquier otra cosa (None, lectura
    inválida) → None, que R-02 trata como "sin lectura"."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int) and valor in (0, 1):
        return valor == 1
    return None


def _motivo_puerta_no_cerrada(door) -> str | None:
    """Posición de la puerta leída EN VIVO de sus entradas digitales, no del
    estado lógico: durante el modo prueba door.update() está en pausa y ese
    estado queda congelado (revisión de la etapa 1, hallazgo A). Cerrada exige
    cerrada=1 y, si la puerta tiene sensor de abierta, abierta=0."""
    nombre = getattr(door, "name", None)
    di = getattr(door, "di", None)
    if not nombre or not isinstance(di, dict) or "cerrada" not in di:
        return "Sin lectura del estado de las puertas"
    entradas = context.estado.sensores_di
    cerrada = _entrada_digital(entradas.get(di["cerrada"]))
    abierta = _entrada_digital(entradas.get(di["abierta"])) if "abierta" in di else False
    if cerrada is None or abierta is None:
        return f"Sin lectura del estado de {nombre}"
    if not cerrada or abierta:
        return f"{nombre} no está cerrada"
    return None


def _motivo_r02() -> str | None:
    """Condiciones de R-02 para encender una salida en prueba (§5.4): cámara a
    presión atmosférica (ambas absolutas) y todas las puertas cerradas según
    sus entradas en vivo. Sin lectura o sin configuración, rechaza. Valores
    leídos en vivo de la configuración."""
    pres = context.estado.sensores_pres.get("pres_camara")
    atm = context.config_manager.get("presion_admosferica")
    rango = context.config_manager.get("rango_presion_atm")
    if not _es_numero(pres):
        return "Sin lectura de presión de cámara"
    if not (_es_numero(atm) and _es_numero(rango)):
        return "Configuración de presión atmosférica no disponible"
    if not (atm - rango <= pres <= atm + rango):
        return f"Cámara fuera de presión atmosférica ({pres:.0f} kPa)"
    puertas = list(context.doors or [])
    if not puertas:
        return "Sin lectura del estado de las puertas"
    for door in puertas:
        motivo = _motivo_puerta_no_cerrada(door)
        if motivo:
            return motivo
    return None


@app.patch("/io/test/output/{name}")
def io_test_set_output(name: str, body: _OutputSetBody,
                       sesion: Sesion = Depends(_requiere_rol_prueba)):
    """Acciona una salida en modo prueba. Apagar siempre se permite dentro del
    modo prueba; encender exige además ser la sesión dueña y R-02 (§5.4)."""
    if name not in EstadoAutoclave.map_do:
        raise HTTPException(status_code=404, detail=f"Output '{name}' no encontrado")
    entidad = f"/io/test/output/{name}"
    with guard_estado(DISTINTO_DE_CICLO_E_HIBERNACION, entidad, sesion):
        if not context.control_loop.test_mode_active:
            raise _Rechazo(409, "modo_prueba_inactivo", "El modo prueba no está activo")
        if context.estado.get_flag("PARO_EMERGENCIA"):
            raise _Rechazo(409, "paro_emergencia", "Paro de emergencia activado")
        _rechazar_si_sin_datos_vigentes()
        if body.value:
            # encender solo desde la sesión que está a cargo de la prueba;
            # apagar queda abierto a cualquier sesión de prueba (es lo seguro)
            if _token_modo_prueba != sesion.token:
                raise _Rechazo(409, "modo_prueba_no_dueno",
                               "Solo la sesión que activó el modo prueba puede encender salidas")
            motivo = _motivo_r02()
            if motivo:
                raise _Rechazo(409, "modo_prueba_rechazado", motivo)
        # map_do es 0-indexado (posición en el bitstream DO), pero
        # serial_link.set_output() espera el número de canal DO físico
        # 1-indexado (DO1..DO24), igual que SetOutput y la fábrica de puertas.
        index = EstadoAutoclave.map_do[name]
        if body.value and context.setdo.salida_bloqueada(index + 1) is True:
            # E1b: salida de una fuente de vapor que el equipo no tiene
            raise _Rechazo(409, "fuente_vapor_no_instalada",
                           "La fuente de vapor de esta salida no está instalada")
        context.setdo.set_output(index + 1, body.value)
    _auditar("salida_prueba", sesion, entidad=name, valor_nuevo=body.value)
    return {"ok": True, "name": name, "value": body.value}
