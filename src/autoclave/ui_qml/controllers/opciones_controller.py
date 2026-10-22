# ui_qml/controllers/opciones_controller.py
#
# Controlador de la pantalla OPCIONES (planeacion_opciones_parametros_ciclo.md,
# Fase 1, §4.2): identidad de la sesión, secciones visibles según el rol
# (domain/permisos_opciones.py, nunca comparando roles en QML), cierre de sesión
# y `edicionPermitida` derivada del estado global que llega por polling, del rol
# y de la sección activa.
#
# La sesión es la de SessionManager (una por proceso, es decir, por ventana QML),
# abierta por LoginController. SessionManager no notifica cambios: quien la
# altera fuera de este controlador llama refrescar(). Cerrar la sesión pasa
# por la sesión de la ventana (sesion_backend), que pide /auth/logout (T-8).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain.permisos_opciones import (
    edicion_permitida, motivo_solo_lectura, seccion_inicial, secciones_visibles,
)


class OpcionesController(QObject):
    sesionChanged = Signal()
    estadoMaquinaChanged = Signal()
    seccionChanged = Signal()
    edicionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._usuario = SessionManager.current_user()
        self._estado = ""
        self._seccion = ""

    def _dato(self, campo: str) -> str:
        return (self._usuario or {}).get(campo) or ""

    @Slot()
    def refrescar(self) -> None:
        usuario = SessionManager.current_user()
        if usuario != self._usuario:
            self._usuario = dict(usuario) if usuario else None
            self.sesionChanged.emit()
            self.edicionChanged.emit()

    @Property(bool, notify=sesionChanged)
    def sesionActiva(self) -> bool:
        return self._usuario is not None

    @Property(bool, notify=sesionChanged)
    def cambioClavePendiente(self) -> bool:
        return bool((self._usuario or {}).get("debe_cambiar_clave"))

    @Property(str, notify=sesionChanged)
    def usuario(self) -> str:
        return self._dato("usuario")

    @Property(str, notify=sesionChanged)
    def nombre(self) -> str:
        return self._dato("nombre")

    @Property(str, notify=sesionChanged)
    def rol(self) -> str:
        return self._dato("rol")

    # Lista de {clave, icono} en el orden de la navegación lateral (U-2, U-7)
    @Property("QVariantList", notify=sesionChanged)
    def secciones(self) -> list:
        return [{"clave": s.clave, "icono": s.icono} for s in secciones_visibles(self.rol)]

    @Slot()
    def cerrarSesion(self) -> None:
        sesion_backend.ventana().cerrar_sesion()
        self.refrescar()

    def _get_estado(self) -> str:
        return self._estado

    def _set_estado(self, estado: str) -> None:
        if estado != self._estado:
            self._estado = estado
            self.estadoMaquinaChanged.emit()
            self.edicionChanged.emit()

    estadoMaquina = Property(str, _get_estado, _set_estado, notify=estadoMaquinaChanged)

    # Sección activa de la pantalla: la edición depende de ella (excepción del ingeniero)
    def _get_seccion(self) -> str:
        return self._seccion

    def _set_seccion(self, seccion: str) -> None:
        if seccion != self._seccion:
            self._seccion = seccion
            self.seccionChanged.emit()
            self.edicionChanged.emit()

    seccion = Property(str, _get_seccion, _set_seccion, notify=seccionChanged)

    # Solo para mostrar o deshabilitar controles: el backend impone el bloqueo (U-8)
    @Property(bool, notify=edicionChanged)
    def edicionPermitida(self) -> bool:
        return edicion_permitida(self._estado, self.rol, self._seccion)

    # C1b: "" | "rol" | "estado" (texto del aviso de solo lectura)
    @Property(str, notify=edicionChanged)
    def motivoSoloLectura(self) -> str:
        return motivo_solo_lectura(self._estado, self.rol, self._seccion)

    @Property(str, notify=sesionChanged)
    def seccionInicial(self) -> str:
        return seccion_inicial(self.rol)


qmlRegisterType(OpcionesController, "Autoclave.Controllers", 1, 0, "OpcionesController")
