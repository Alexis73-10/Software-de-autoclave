# autoclave/backend/dependencias.py
#
# Dependencias compartidas de las rutas: contexto, almacén de tokens, auditoría,
# rechazos con código, requiere_rol y guard_estado.
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py.

import logging
import threading
from contextlib import contextmanager
from fastapi import Header, Request
from autoclave.backend.actividad_ui import ActividadUI
from autoclave.backend.arranque.registro import RegistroArranque
from autoclave.backend.autenticacion import AlmacenTokens, ControlIntentos, Sesion
from autoclave.backend.context import BackendContext
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_INGENIERO
from autoclave.utils.paths import calibration_path

# Mismo nombre de logger que antes de partir server.py (ORG-12): los
# registros conservan su origen "autoclave.backend.server".
logger = logging.getLogger("autoclave.backend.server")


# R11: el cierre ordenado del reinicio del software ya se hizo (ver lifespan)
_cierre_ordenado_hecho = threading.Event()

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
_contexto_operable = threading.Event()
_detener_arranque = threading.Event()


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

# Serializa las escrituras de archivos de configuración (YAML de calibración,
# JSON de ciclos), que se hacen fuera de _sm_lock.
_lock_archivos = threading.Lock()

# Revisión D8-5.7 (TMG-02): serializa PATCH /cycle/parameter completo (cambio,
# archivo, bitácora y reversión), para que la reversión de un cambio sin
# bitácora no pise otro cambio que se intercale. Siempre es el lock más externo
# (se toma antes que _sm_lock y _lock_archivos, que se toman en secuencia).
_lock_param_ciclo = threading.Lock()

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


def _log_desarrollo(evento: str, sesion: Sesion | None = None, *, usuario: str = "",
                    **campos) -> None:
    """D9-6 (tanda 9): eventos que NO van a la bitácora (audit_log) porque no
    son de seguridad, ni cambios de configuración, ni de sesión; quedan solo
    en el log de desarrollo."""
    logger.info("Evento %s (usuario=%s): %s", evento,
                sesion.usuario if sesion else usuario, campos)


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


def _rechazar(status: int, codigo: str, motivo: str, entidad: str,
              sesion: Sesion | None = None, headers: dict | None = None,
              extra: dict | None = None):
    """Registra el rechazo (rechazo_401/403/409) en el log de desarrollo y lo
    lanza como RechazoApi. D9-6 (tanda 9): ya no va a la bitácora. Dentro de
    guard_estado se sigue usando _Rechazo (no hace falta escribir con
    _sm_lock tomado)."""
    _log_desarrollo(f"rechazo_{status}", sesion, entidad=entidad, codigo=codigo, motivo=motivo)
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
