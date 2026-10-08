# ui_pyside/views/nuevo_usuario/vista.py
#
# Vista "nuevo_usuario" de la pila PySide: aloja la pantalla QML Nuevo Usuario
# en un QQuickWidget (alojamiento (a) de G0, planeacion_nuevo_usuario.md).
# Comparte el proceso, y por tanto la sesión de SessionManager, con el login y
# el menú de administración.
#
# oculta_marco: MainWindowFluent oculta su encabezado y pie mientras esta vista
# está activa (la pantalla QML trae los suyos).

import logging

from PySide6.QtCore import QMetaObject, Qt, QTimer, QUrl
from PySide6.QtQuickWidgets import QQuickWidget

# Importar app registra los controladores de los teclados (Autoclave.Controllers)
from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos
from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

logger = logging.getLogger(__name__)


class NuevoUsuarioView(QQuickWidget):
    oculta_marco = True

    def __init__(self, nav_callback, sesion=None):
        super().__init__()
        self._nav = nav_callback
        self.puente = NuevoUsuarioBridge(self, sesion=sesion)
        self.puente.solicitudNavegar.connect(self._nav)
        self.puente.usuarioCreado.connect(self._al_crear)

        _cargar_fuentes()
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.engine().addImportPath(QML_DIR)   # visibiliza el módulo "Tema"
        self.setInitialProperties({"puente": self.puente, "textosJson": cargar_textos()})
        self.setSource(QUrl.fromLocalFile(f"{QML_DIR}/NuevoUsuarioHost.qml"))
        for error in self.errors():
            logger.error("NuevoUsuarioHost.qml: %s", error.toString())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.puente.actualizarSesion()
        # NU-05: sin una sesión que pueda crear usuarios la pantalla no se queda abierta
        if not self.puente.puedeCrear():
            logger.warning("Nuevo usuario abierto sin sesión que pueda crear usuarios: se vuelve al menú")
            QTimer.singleShot(0, lambda: self._nav("admin_menu"))

    def hideEvent(self, event) -> None:
        # las contraseñas no quedan en la pantalla al salir de ella
        if self.rootObject() is not None:
            QMetaObject.invokeMethod(self.rootObject(), "limpiar")
        super().hideEvent(event)

    def _al_crear(self, usuario: str) -> None:
        try:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title="Usuario creado",
                content=usuario,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window(),
            )
        except Exception as e:   # el aviso no debe impedir la navegación
            logger.warning("No se pudo mostrar el aviso de usuario creado: %s", e)
