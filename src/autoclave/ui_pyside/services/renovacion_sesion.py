# ui_pyside/services/renovacion_sesion.py
#
# P3 (tanda 5): la UI PySide renueva el token mientras la ventana está en uso y,
# ante un 401, pide login sin perder lo editado (decisión 4 de Cristian, 20-oct).
#
# - RenovadorSesion: lógica pura con reloj inyectable. Con sesión y actividad
#   reciente (< SESION_INACTIVIDAD_S), avisa al backend con GET /auth/sesion
#   como máximo cada SESION_KEEPALIVE_S, igual que la UI QML (B7). Sin
#   actividad no renueva: el backend caduca el token por su cuenta.
# - guardar_con_reintento: corre el guardado; si el backend responde 401, pide
#   credenciales, inicia sesión y reintenta UNA vez con los mismos datos. Si se
#   cancela o falla el login, no se guarda y devuelve el motivo.
#
# La caducidad del token nunca impide una acción de seguridad: cancelar ciclo,
# reconocer falla, confirmar estado seguro, apagar y las puertas no usan token
# (revisión R0 de la tanda 5).

import logging
import time
from dataclasses import dataclass

import requests

from autoclave.core.runtime.sesion_inactividad import SESION_INACTIVIDAD_S, SESION_KEEPALIVE_S
from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.ui_pyside.services import auth_backend

logger = logging.getLogger(__name__)


def _consultar_sesion(token: str, url: str = auth_backend.BACKEND_URL) -> int | None:
    """Estado HTTP de GET /auth/sesion, o None si el backend no respondió."""
    try:
        r = requests.get(f"{url}/auth/sesion", headers={"Authorization": f"Bearer {token}"},
                         timeout=2)
        return r.status_code
    except requests.RequestException as e:
        logger.debug("Renovación de sesión PySide sin respuesta: %s", e)
        return None


class RenovadorSesion:
    def __init__(self, consultar=_consultar_sesion, reloj=time.monotonic,
                 al_caducar=None, inactividad_s: float = SESION_INACTIVIDAD_S,
                 cada_s: float = SESION_KEEPALIVE_S):
        self._consultar = consultar
        self._reloj = reloj
        self._al_caducar = al_caducar
        self._inactividad_s = inactividad_s
        self._cada_s = cada_s
        self._ultima_actividad: float | None = None
        self._ultimo_aviso: float | None = None

    def actividad(self) -> None:
        """Toque, tecla o clic en la ventana."""
        self._ultima_actividad = self._reloj()

    def tick(self) -> bool:
        """Llamado periódicamente (QTimer). True si consultó al backend."""
        token = SessionManager.token()
        if not token or self._ultima_actividad is None:
            return False
        ahora = self._reloj()
        if ahora - self._ultima_actividad >= self._inactividad_s:
            return False              # sin uso: no se renueva
        if self._ultimo_aviso is not None and ahora - self._ultimo_aviso < self._cada_s:
            return False
        self._ultimo_aviso = ahora
        estado = self._consultar(token)
        if estado == 401 and SessionManager.token() == token:
            # el token ya no vale: la sesión local se cierra; lo editado sigue
            # en pantalla y el próximo guardado pedirá login (guardar_con_reintento)
            global _usuario_caducado
            _usuario_caducado = (SessionManager.current_user() or {}).get("usuario") or None
            SessionManager.logout()
            if self._al_caducar is not None:
                self._al_caducar()
        return True


# ── guardado con reintento tras 401 ─────────────────────────────────────────

# Revisión C1a (SAF-01): usuario cuya sesión cerró la renovación por un 401.
# El reingreso posterior sigue limitado a esa persona (OTRO_USUARIO).
_usuario_caducado: str | None = None


def usuario_para_reingreso() -> str | None:
    if SessionManager.token():
        return (SessionManager.current_user() or {}).get("usuario") or None
    return _usuario_caducado

GUARDADO = "guardado"
CANCELADO = "cancelado"           # el usuario no volvió a iniciar sesión
LOGIN_FALLIDO = "login_fallido"
OTRO_USUARIO = "otro_usuario"     # revisión P3 (SAF-01): solo reingresa el mismo usuario


@dataclass(frozen=True)
class ResultadoGuardado:
    estado: str
    valor: object = None
    login: str = ""               # estado de auth_backend si el login falló


def es_401(exc) -> bool:
    resp = getattr(exc, "response", None)
    return resp is not None and getattr(resp, "status_code", None) == 401


def guardar_con_reintento(guardar, pedir_credenciales, iniciar_sesion=auth_backend.iniciar_sesion):
    """`guardar()` hace la escritura (lanza la excepción HTTP del backend).
    `pedir_credenciales()` devuelve (usuario, clave) o None si se cancela.
    Otras excepciones se propagan sin cambios. Si había sesión al empezar, el
    reingreso debe ser del mismo usuario (la auditoría y la pantalla no cambian
    de persona en silencio)."""
    global _usuario_caducado
    previo = usuario_para_reingreso()
    try:
        return ResultadoGuardado(GUARDADO, guardar())
    except Exception as exc:
        if not es_401(exc):
            raise
    credenciales = pedir_credenciales()
    if not credenciales:
        return ResultadoGuardado(CANCELADO)
    if previo and credenciales[0] != previo:
        return ResultadoGuardado(LOGIN_FALLIDO, login=OTRO_USUARIO)
    r = iniciar_sesion(*credenciales)
    if r.estado != auth_backend.OK:
        return ResultadoGuardado(LOGIN_FALLIDO, login=r.estado)
    _usuario_caducado = None
    return ResultadoGuardado(GUARDADO, guardar())


def mensaje_de(resultado: ResultadoGuardado) -> str:
    """Motivo visible cuando no se guardó (PySide sin i18n: español)."""
    if resultado.estado == CANCELADO:
        return "Sesión vencida: el cambio NO se guardó (se canceló el inicio de sesión)."
    if resultado.estado == LOGIN_FALLIDO and resultado.login == OTRO_USUARIO:
        return ("Sesión vencida: el cambio NO se guardó. Solo el mismo usuario puede "
                "reingresar aquí; para cambiar de usuario, salga e inicie sesión.")
    if resultado.estado == LOGIN_FALLIDO:
        return ("Sesión vencida: el cambio NO se guardó (no se pudo iniciar sesión: "
                f"{resultado.login}).")
    return ""


# ── enganche Qt (sin lógica: la lógica está arriba y tiene pruebas) ─────────

def instalar_en(ventana, intervalo_ms: int = 5000, renovador: RenovadorSesion | None = None):
    """Cuenta como actividad los clics y teclas de la aplicación y llama a
    `tick()` cada `intervalo_ms`. Devuelve el renovador."""
    from PySide6.QtCore import QEvent, QObject, QTimer
    from PySide6.QtWidgets import QApplication

    renovador = renovador or RenovadorSesion()

    class _Filtro(QObject):
        _TIPOS = (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.TouchBegin)

        def eventFilter(self, obj, evento):
            if evento.type() in self._TIPOS:
                renovador.actividad()
            return False

    filtro = _Filtro(ventana)
    app = QApplication.instance()
    if app is not None:
        app.installEventFilter(filtro)
    timer = QTimer(ventana)
    timer.setInterval(intervalo_ms)
    timer.timeout.connect(renovador.tick)
    timer.start()
    ventana._renovacion_sesion = (renovador, filtro, timer)   # mantiene vivas las referencias
    return renovador


def pedir_credenciales_dialogo(padre):
    """Diálogo de login para reintentar un guardado (P3). (usuario, clave) o
    None si se cancela. C1a (tanda 6): teclado en pantalla propio
    (_teclado_pantalla), el equipo es táctil y sin teclado físico."""
    from autoclave import i18n
    from autoclave.ui_pyside.views._teclado_pantalla import pedir_credenciales
    usuario_previo = usuario_para_reingreso() or ""
    return pedir_credenciales(padre, i18n.t("sesion.vencida_titulo"),
                              i18n.t("sesion.vencida_mensaje"), usuario_previo)
