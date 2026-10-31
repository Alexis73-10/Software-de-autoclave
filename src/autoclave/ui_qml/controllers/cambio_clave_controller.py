# ui_qml/controllers/cambio_clave_controller.py
#
# Cambio de contraseña obligatorio (T-8; plan_t8_login_qml.md §3.3): POST
# /auth/change_password por la sesión de la ventana, en un hilo con plazo
# total y una sola operación en vuelo. Mismas reglas de longitud y
# confirmación que Nuevo usuario (validacion_usuario.py); la nueva no puede ser
# igual a la actual (igual_actual, también lo impone el backend).
#
# Errores por campo con clave de es.json: {campo: {"clave", "valores"}} con
# los campos del cuerpo (clave_actual, clave_nueva, confirmacion); mensaje
# general en `mensajeClave`.
#
# Si la sesión se cierra durante el cambio (429 por bloqueo, sin respuesta del
# equipo, 401), la sesión de la ventana deja el aviso para el login y aquí se
# emite sesionTerminada: la pantalla vuelve al Login. Abandonar (Atrás/Inicio) = logout.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.auth.validacion_usuario import (
    COD_IGUAL_ACTUAL, COD_OBLIGATORIO, PASSWORD_MAX, codigo_clave, codigo_confirmacion,
    error_ui,
)
from autoclave.ui_qml import sesion_backend

_CIERRAN_SESION = frozenset({"usuario_bloqueado", sesion_backend.BACKEND_NO_RESPONDE,
                             "sesion_invalida"})


def _errores_locales(actual: str, nueva: str, confirmacion: str) -> dict:
    errores = {}
    if not actual:
        errores["clave_actual"] = COD_OBLIGATORIO
    codigo = codigo_clave(nueva)
    if codigo is None and actual and nueva == actual:
        codigo = COD_IGUAL_ACTUAL
    if codigo:
        errores["clave_nueva"] = codigo
    codigo = codigo_confirmacion(confirmacion, nueva)
    if codigo:
        errores["confirmacion"] = codigo
    return errores


class CambioClaveController(QObject):
    erroresChanged = Signal()
    mensajeChanged = Signal()
    ocupadoChanged = Signal()
    sinConexionChanged = Signal()
    claveCambiada = Signal()
    sesionTerminada = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion or sesion_backend.ventana()
        self._errores = {}
        self._mensaje = ""
        self._sesion.ocupadoChanged.connect(self.ocupadoChanged)
        self._sesion.conexionChanged.connect(self.sinConexionChanged)
        # pantalla destruida con el cambio en vuelo: se abandona (TMG-06)
        operacion = self._sesion.operacion
        self.destroyed.connect(lambda *_: operacion.cancelar({"cambio_clave"}))

    @Property(int, constant=True)
    def longitudMaxima(self) -> int:
        """Tope del teclado para las tres contraseñas (mismo de la validación)."""
        return PASSWORD_MAX

    @Property("QVariantMap", notify=erroresChanged)
    def errores(self):
        return self._errores

    @Property(str, notify=mensajeChanged)
    def mensajeClave(self) -> str:
        return self._mensaje

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._sesion.ocupado

    @Property(bool, notify=sinConexionChanged)
    def sinConexion(self) -> bool:
        return self._sesion.sinConexion

    def _fijar(self, errores: dict, mensaje: str = "") -> None:
        self._errores = {c: error_ui(c, cod) for c, cod in errores.items()}
        self.erroresChanged.emit()
        if mensaje != self._mensaje:
            self._mensaje = mensaje
            self.mensajeChanged.emit()

    @Slot(str, str, str, result=bool)
    def cambiar(self, actual: str, nueva: str, confirmacion: str) -> bool:
        """True si la petición salió; el resultado llega por señal."""
        if self.ocupado:
            return False
        if self.sinConexion:
            self._fijar({}, "sesion.sin_conexion_escrituras")
            return False
        errores = _errores_locales(actual, nueva, confirmacion)
        self._fijar(errores)
        if errores:
            return False
        return self._sesion.cambiar_clave(actual, nueva, confirmacion, self._al_responder)

    def _al_responder(self, r) -> None:
        if r.ok:
            self._fijar({})
            self.claveCambiada.emit()
        elif r.causa in _CIERRAN_SESION:
            self._fijar({})
            self.sesionTerminada.emit()
        elif r.causa == "validacion":
            self._fijar({e.get("campo", ""): e.get("codigo", "")
                         for e in r.datos.get("errores", []) if isinstance(e, dict)})
        elif r.causa == "clave_actual_incorrecta":
            self._errores = {"clave_actual": {"clave": "sesion.clave_actual_incorrecta",
                                              "valores": {}}}
            self.erroresChanged.emit()
        else:
            self._fijar({}, sesion_backend.clave_mensaje(r.causa))

    @Slot()
    def abandonar(self) -> None:
        """Atrás/Inicio sin cambiarla: la sesión del cambio obligatorio no
        llegó a completarse y se descarta con logout (revisión de U2, tanda 2:
        no es un cierre manual de una sesión abierta, decisión 7). El
        siguiente acceso vuelve a pedir login y cambio."""
        self._sesion.cerrar_sesion()


qmlRegisterType(CambioClaveController, "Autoclave.Controllers", 1, 0, "CambioClaveController")
