# ui_qml/controllers/login_controller.py
#
# Login QML contra el backend (T-8; plan_t8_login_qml.md §3): POST /auth/login
# en un hilo de trabajo, con plazo total y una sola operación en vuelo, vía la
# sesión de esta ventana (sesion_backend.ventana()). El token queda solo en
# memoria, en SessionManager.
#
# Mensajes por clave de es.json ("seccion.clave", `mensajeClave`), un solo
# mensaje para usuario inexistente y contraseña incorrecta. Con el usuario
# bloqueado (429), cuenta regresiva local en m:ss (`tiempoBloqueo`) desde los
# segundos que envía el backend, sin consultarlo; al llegar a cero solo se
# habilita el botón. Como el bloqueo del backend es por usuario, el botón solo
# se deshabilita para ese usuario (`usuarioBloqueado`); otro usuario puede
# intentar. Un timeout de red nunca se muestra como bloqueo.
#
# Al abrir, toma el aviso que dejó la sesión (sesión inválida, bloqueo desde
# el cambio de contraseña, clave que pudo cambiar). Nunca registra la
# contraseña ni el token.

import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

CAMPOS_VACIOS = "sesion.campos_vacios"


class LoginController(QObject):
    mensajeChanged = Signal()
    bloqueoChanged = Signal()
    ocupadoChanged = Signal()
    sesionIniciada = Signal(str, str)   # usuario, rol
    cambioClaveRequerido = Signal()

    def __init__(self, parent=None, sesion=None, reloj=time.monotonic, intervalo_ms: int = 250):
        super().__init__(parent)
        self._sesion = sesion or sesion_backend.ventana()
        self._reloj = reloj
        self._mensaje = ""
        self._bloqueo_hasta = None
        self._usuario_bloqueado = ""
        self._sesion.ocupadoChanged.connect(self.ocupadoChanged)
        # Login fuera de pantalla (casa, standby) con la petición en vuelo: se
        # cancela y, si responde bien, su token se invalida (TMG-01, TMG-06)
        operacion = self._sesion.operacion
        self.destroyed.connect(lambda *_: operacion.cancelar({"login"}))
        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self._tic_bloqueo)

        aviso = self._sesion.tomar_aviso()
        if aviso:
            clave, segundos, usuario = (tuple(aviso) + ("",))[:3]
            self._fijar_mensaje(clave)
            if segundos:
                self._bloquear(segundos, usuario)

    # ── estado ───────────────────────────────────────────────────────

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    @Property(str, notify=mensajeChanged)
    def mensajeClave(self) -> str:
        """Clave de es.json del mensaje ("sesion.credenciales_invalidas"); "" si no hay."""
        return self._mensaje

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._sesion.ocupado

    @Property(bool, notify=bloqueoChanged)
    def bloqueado(self) -> bool:
        return self._bloqueo_hasta is not None

    @Property(str, notify=bloqueoChanged)
    def usuarioBloqueado(self) -> str:
        """Usuario bloqueado, en minúsculas (el backend no distingue mayúsculas)."""
        return self._usuario_bloqueado if self.bloqueado else ""

    @Property(str, notify=bloqueoChanged)
    def tiempoBloqueo(self) -> str:
        if self._bloqueo_hasta is None:
            return sesion_backend.formato_tiempo(0)
        return sesion_backend.formato_tiempo(self._bloqueo_hasta - self._reloj())

    def _bloquear(self, segundos, usuario: str) -> None:
        self._usuario_bloqueado = usuario.strip().lower()
        self._bloqueo_hasta = self._reloj() + max(1, int(segundos or 0))
        self._timer.start()
        self.bloqueoChanged.emit()

    def _tic_bloqueo(self) -> None:
        if self._bloqueo_hasta is not None and self._reloj() >= self._bloqueo_hasta:
            self._bloqueo_hasta = None
            self._timer.stop()
        self.bloqueoChanged.emit()

    # ── acciones ─────────────────────────────────────────────────────

    @Slot(str, str, result=bool)
    def iniciarSesion(self, usuario: str, clave: str) -> bool:
        """True si la petición salió; el resultado llega por señal."""
        usuario = usuario.strip()
        if self.ocupado or (self.bloqueado and usuario.lower() == self._usuario_bloqueado):
            return False
        if not usuario or not clave:
            self._fijar_mensaje(CAMPOS_VACIOS)
            return False
        self._fijar_mensaje("")
        return self._sesion.iniciar_sesion(
            usuario, clave, lambda r: self._al_responder(r, usuario))

    def _al_responder(self, r, usuario: str) -> None:
        if r.ok:
            self._fijar_mensaje("")
            if r.datos.get("debe_cambiar_clave"):
                self.cambioClaveRequerido.emit()
            else:
                self.sesionIniciada.emit(r.datos.get("usuario", ""), r.datos.get("rol", ""))
            return
        self._fijar_mensaje(sesion_backend.clave_mensaje(r.causa))
        if r.causa == "usuario_bloqueado":
            self._bloquear(r.datos.get("segundos_restantes"), usuario)

    @Slot()
    def cerrarSesion(self) -> None:
        self._sesion.cerrar_sesion()
        self._fijar_mensaje("")


qmlRegisterType(LoginController, "Autoclave.Controllers", 1, 0, "LoginController")
