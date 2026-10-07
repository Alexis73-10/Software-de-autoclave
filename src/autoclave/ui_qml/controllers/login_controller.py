# ui_qml/controllers/login_controller.py
#
# Validación del Login QML (provisional, enmienda de planeacion_nuevo_usuario.md
# del 2026-10-01). Misma regla que el login PySide (views/login.py):
# usuario activo + SHA-256 de la contraseña (D-03), por acceso directo a SQLite
# (D-04, sin endpoint FastAPI). Al validar abre la sesión en SessionManager —
# una por proceso, es decir, por ventana QML — y emite sesionIniciada; a qué
# pantalla lleva eso lo decide Main.qml cuando se defina.
#
# Nunca registra la contraseña ni su hash. El mensaje de error no distingue
# usuario inexistente de contraseña incorrecta.

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_pyside.services.session_manager import SessionManager, hash_password

logger = logging.getLogger(__name__)

CAMPOS_VACIOS = "Ingrese usuario y contraseña"
CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos"


def _db_por_defecto():
    from autoclave.services.domain.logging.db_manager import DbManager
    return DbManager()


class LoginController(QObject):
    mensajeErrorChanged = Signal()
    sesionChanged = Signal()
    sesionIniciada = Signal(str, str)   # usuario, rol

    def __init__(self, parent=None, db_factory=None):
        super().__init__(parent)
        # se resuelve al usarla: así las pruebas pueden sustituir _db_por_defecto
        self._db_factory = db_factory
        self._db = None   # una sola instancia, creada al primer uso (NU-07)
        self._mensaje_error = ""

    def _base(self):
        if self._db is None:
            self._db = (self._db_factory or _db_por_defecto)()
        return self._db

    def _set_error(self, mensaje: str) -> None:
        if mensaje != self._mensaje_error:
            self._mensaje_error = mensaje
            self.mensajeErrorChanged.emit()

    @Property(str, notify=mensajeErrorChanged)
    def mensajeError(self) -> str:
        return self._mensaje_error

    @Property(str, notify=sesionChanged)
    def nombreSesion(self) -> str:
        user = SessionManager.current_user()
        return user["nombre"] if user else ""

    @Slot(str, str, result=bool)
    def iniciarSesion(self, usuario: str, clave: str) -> bool:
        usuario = usuario.strip()
        # un intento nuevo cierra cualquier sesión previa de esta ventana
        if SessionManager.is_authenticated():
            SessionManager.logout()
            self.sesionChanged.emit()

        if not usuario or not clave:
            self._set_error(CAMPOS_VACIOS)
            return False

        user = self._base().get_usuario_by_username(usuario)
        if user is None or user["hash_pw"] != hash_password(clave):
            logger.warning("Inicio de sesión QML rechazado para '%s'", usuario)
            self._set_error(CREDENCIALES_INVALIDAS)
            return False

        SessionManager.login(user)
        self._set_error("")
        self.sesionChanged.emit()
        logger.info("Inicio de sesión QML: %s (rol %s)", user["usuario"], user["rol"])
        self.sesionIniciada.emit(user["usuario"], user["rol"])
        return True

    @Slot()
    def cerrarSesion(self) -> None:
        SessionManager.logout()
        self._set_error("")
        self.sesionChanged.emit()


qmlRegisterType(LoginController, "Autoclave.Controllers", 1, 0, "LoginController")
