# ui_pyside/views/nuevo_usuario/puente.py
#
# Puente entre la pantalla QML Nuevo Usuario y el backend
# (planeacion_backend_autenticacion.md, decisión 26, T-20; T-8). Crea el
# usuario con POST /usuarios a través de la sesión de la ventana
# (ui_qml/sesion_backend.py), que pone el token, rechaza sin red cuando no hay
# conexión y, ante un 401, cierra la sesión y avisa a la ventana.
#
# Desde T-8 vive en el proceso QML (OPCIONES › Usuarios). Los errores van por
# clave de es.json: {campo: {"clave": "seccion.clave", "valores": {...}}}, y
# "general" para los que no son de un campo; la pantalla los traduce.
#
# Control de acceso (NU-05): la pantalla solo se abre con una sesión que pueda
# crear usuarios, pero quien decide es el backend con el rol del token.
# La contraseña nunca se registra en el log ni se guarda en el objeto.

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.auth.roles import ROLES, ROLES_CREABLES, etiqueta_rol
from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.auth.validacion_usuario import (
    NOMBRE_MAX, PASSWORD_MAX, PASSWORD_MIN, USUARIO_MAX, campo_pantalla,
    codigos_nuevo_usuario, error_ui,
)

logger = logging.getLogger(__name__)


def _general(clave: str) -> dict:
    return {"general": {"clave": clave, "valores": {}}}


class NuevoUsuarioBridge(QObject):
    usuarioCreado = Signal(str)
    solicitudNavegar = Signal(str)
    sesionChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        if sesion is None:
            from autoclave.ui_qml import sesion_backend
            sesion = sesion_backend.ventana()
        self._sesion = sesion
        self._usuario_actual = ""
        self._rol_actual = ""
        self.actualizarSesion()

    # ── Propiedades ──────────────────────────────────────────────────

    @Property("QVariantList", notify=sesionChanged)
    def roles(self):
        """Solo los roles que la sesión actual puede crear."""
        creables = ROLES_CREABLES.get(self._rol_actual, frozenset())
        # I4 (tanda 6): etiqueta de catálogo roles.<valor> en el idioma vigente
        return [{"valor": v, "etiqueta": etiqueta_rol(v, e)} for v, e in ROLES if v in creables]

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

    @staticmethod
    def _errores_ui(codigos: dict) -> dict:
        return {campo_pantalla(c): error_ui(c, cod) for c, cod in codigos.items()}

    @Slot(str, str, str, str, str, result="QVariantMap")
    def validar(self, nombre, usuario, password, confirmacion, rol):
        """Validación local de formato para avisar sin ir al backend; la
        unicidad del usuario la decide el backend (409)."""
        return self._errores_ui(codigos_nuevo_usuario(
            nombre, usuario, password, confirmacion, rol, existe_usuario=lambda _u: False))

    @Slot(str, str, str, str, str, bool, result="QVariantMap")
    def guardar(self, nombre, usuario, password, confirmacion, rol, activo):
        if not self.puedeCrear():
            logger.warning("Creación de usuario rechazada: la sesión no puede crear usuarios")
            return {"ok": False, "errores": _general("usuarios.sin_permiso")}

        errores = self.validar(nombre, usuario, password, confirmacion, rol)
        if errores:
            return {"ok": False, "errores": errores}

        cuerpo = {"nombre": nombre.strip(), "usuario": usuario, "clave": password,
                  "confirmacion": confirmacion, "rol": rol, "activo": bool(activo)}
        creador = SessionManager.current_user()["usuario"]
        r = self._sesion.enviar("POST", "/usuarios", cuerpo)
        if r.ok:
            logger.info("usuario creado: %s, rol %s, por %s", usuario, rol, creador)
            self.usuarioCreado.emit(usuario)
            return {"ok": True, "errores": {}}
        return {"ok": False, "errores": self._errores_de(r)}

    def _errores_de(self, r) -> dict:
        from autoclave.ui_qml.sesion_backend import clave_mensaje
        if r.causa == "validacion":
            # contrato v7: lista {campo, codigo} con los campos del cuerpo
            return self._errores_ui({e.get("campo", ""): e.get("codigo", "")
                                     for e in r.datos.get("errores", []) if isinstance(e, dict)})
        if r.causa == "usuario_existe":
            return {"usuario": {"clave": "usuarios.usuario_existe", "valores": {}}}
        if r.causa in ("ok", "error_generico"):
            return _general("usuarios.guardado_error")
        logger.warning("Creación de usuario rechazada: %s", r.causa)
        return _general(clave_mensaje(r.causa))

    # ── Navegación ───────────────────────────────────────────────────

    @Slot(str)
    def navegar(self, destino: str) -> None:
        self.solicitudNavegar.emit(destino)

