# ui_pyside/views/nuevo_usuario/puente.py
#
# Puente entre la pantalla QML Nuevo Usuario y el backend
# (planeacion_backend_autenticacion.md, decisión 26, T-20). Ya no escribe en
# SQLite: crea el usuario con POST /usuarios, que exige el token de la sesión,
# aplica las reglas de creación por rol, valida y guarda el hash PBKDF2.
#
# Control de acceso (NU-05): la pantalla solo se abre con una sesión que pueda
# crear usuarios, pero quien decide es el backend con el rol del token.
# La contraseña nunca se registra en el log ni se guarda en el objeto.

import logging

import requests
from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.ui_pyside.services.roles import ROLES, ROLES_CREABLES
from autoclave.ui_pyside.services.session_manager import SessionManager
from autoclave.ui_pyside.services.validacion_usuario import (
    NOMBRE_MAX, PASSWORD_MAX, PASSWORD_MIN, USUARIO_EXISTE, USUARIO_MAX,
    validar_nuevo_usuario,
)

logger = logging.getLogger(__name__)

SIN_PERMISO = "Su rol no puede crear usuarios"
SESION_VENCIDA = "Sesión no válida o vencida; inicie sesión de nuevo"
ERROR_GUARDAR = "No se pudo guardar el usuario"

# El backend tarda lo que cuesta el hash PBKDF2 (600 000 iteraciones)
_TIMEOUT_S = 5.0


def _enviar_por_defecto(ruta: str, cuerpo: dict, token: str):
    """POST al backend; devuelve (código HTTP, cuerpo JSON o {})."""
    from autoclave.ui_qml.app import url_backend
    r = requests.post(f"{url_backend()}{ruta}", json=cuerpo,
                      headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT_S)
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    return r.status_code, datos


class NuevoUsuarioBridge(QObject):
    usuarioCreado = Signal(str)
    solicitudNavegar = Signal(str)
    sesionChanged = Signal()

    def __init__(self, parent=None, enviar=_enviar_por_defecto):
        super().__init__(parent)
        self._enviar = enviar
        self._usuario_actual = ""
        self._rol_actual = ""
        self.actualizarSesion()

    # ── Propiedades ──────────────────────────────────────────────────

    @Property("QVariantList", notify=sesionChanged)
    def roles(self):
        """Solo los roles que la sesión actual puede crear."""
        creables = ROLES_CREABLES.get(self._rol_actual, frozenset())
        return [{"valor": v, "etiqueta": e} for v, e in ROLES if v in creables]

    @Property(int, constant=True)
    def minLongitudPassword(self) -> int:
        return PASSWORD_MIN

    @Property("QVariantMap", constant=True)
    def longitudesMaximas(self):
        """Límite del teclado por campo, igual a las reglas de validación."""
        return {"nombre": NOMBRE_MAX, "usuario": USUARIO_MAX,
                "password": PASSWORD_MAX, "confirmacion": PASSWORD_MAX}

    @Property(str, notify=sesionChanged)
    def usuarioActual(self) -> str:
        return self._usuario_actual

    @Slot()
    def actualizarSesion(self) -> None:
        user = SessionManager.current_user()
        usuario = user["usuario"] if user else ""
        rol = user["rol"] if user else ""
        if (usuario, rol) != (self._usuario_actual, self._rol_actual):
            self._usuario_actual = usuario
            self._rol_actual = rol
            self.sesionChanged.emit()

    # ── Reglas ───────────────────────────────────────────────────────

    @Slot(result=bool)
    def puedeCrear(self) -> bool:
        return (SessionManager.is_authenticated()
                and SessionManager.current_role() in ROLES_CREABLES)

    @Slot(str, str, str, str, str, result="QVariantMap")
    def validar(self, nombre, usuario, password, confirmacion, rol):
        """Validación local de formato para avisar sin ir al backend; la
        unicidad del usuario la decide el backend (409)."""
        return validar_nuevo_usuario(nombre, usuario, password, confirmacion, rol,
                                     existe_usuario=lambda _u: False)

    @Slot(str, str, str, str, str, bool, result="QVariantMap")
    def guardar(self, nombre, usuario, password, confirmacion, rol, activo):
        if not self.puedeCrear():
            logger.warning("Creación de usuario rechazada: la sesión no puede crear usuarios")
            return {"ok": False, "errores": {"general": SIN_PERMISO}}

        errores = self.validar(nombre, usuario, password, confirmacion, rol)
        if errores:
            return {"ok": False, "errores": errores}

        token = (SessionManager.current_user() or {}).get("token")
        if not token:
            logger.warning("Creación de usuario sin token de backend en la sesión")
            return {"ok": False, "errores": {"general": SESION_VENCIDA}}

        cuerpo = {"nombre": nombre.strip(), "usuario": usuario, "clave": password,
                  "confirmacion": confirmacion, "rol": rol, "activo": bool(activo)}
        try:
            codigo_http, datos = self._enviar("/usuarios", cuerpo, token)
        except Exception as e:
            # el detalle va al log (sin datos del formulario), no a la pantalla
            logger.error("Backend no disponible al crear usuario: %s", type(e).__name__)
            return {"ok": False, "errores": {"general": ERROR_GUARDAR}}

        if codigo_http == 200:
            creador = SessionManager.current_user()["usuario"]
            logger.info("usuario creado: %s, rol %s, por %s", usuario, rol, creador)
            self.usuarioCreado.emit(usuario)
            return {"ok": True, "errores": {}}
        return {"ok": False, "errores": self._errores_de(codigo_http, datos)}

    @staticmethod
    def _errores_de(codigo_http: int, datos: dict) -> dict:
        detalle = datos.get("detail") if isinstance(datos, dict) else None
        if codigo_http == 401:
            return {"general": SESION_VENCIDA}
        if codigo_http == 409:
            return {"usuario": USUARIO_EXISTE}
        if codigo_http == 422 and isinstance(detalle, dict) and detalle.get("errores"):
            return dict(detalle["errores"])
        if codigo_http == 403 and isinstance(detalle, str):
            return {"general": detalle}
        logger.error("Creación de usuario rechazada por el backend: HTTP %s", codigo_http)
        return {"general": ERROR_GUARDAR}

    # ── Navegación ───────────────────────────────────────────────────

    @Slot(str)
    def navegar(self, destino: str) -> None:
        self.solicitudNavegar.emit(destino)

    @Slot()
    def salir(self) -> None:
        """Salir de la barra inferior = cerrar sesión e ir al login (P-01)."""
        SessionManager.logout()
        self.actualizarSesion()
        self.solicitudNavegar.emit("login")
