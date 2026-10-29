# ui_qml/bridge/comandos_ciclo_en_curso.py
#
# Comandos de la pantalla de ciclo en curso (planeacion_pantalla_ciclo_en_curso.md §10):
#   cancelar()  -> UIServiceBackend.abort_cycle()       (POST /cycle/abort, con el
#                  token de la sesión de la ventana si la hay, FC-12 de la tanda 21)
#   confirmar() -> UIServiceBackend.acknowledge_cycle() (POST /cycle/acknowledge)
# (El reconocimiento de NO CONFORME de la tanda 16 se retiró en la tanda 21, FC-08.)
# La confirmación previa a cancelar la pide el modal de la pantalla; aquí
# solo se envía. Acción de seguridad (Clase C): sin atajos ni reintentos
# automáticos. Mientras hay un envío en curso no se acepta otro (anti doble
# toque). Si falla o no hay conexión, `error` queda con la acción fallida y la
# pantalla avisa sin navegar: el ciclo NO se da por cancelado/confirmado; eso
# solo lo decide el estado que reporta el backend. La petición HTTP corre
# fuera del hilo de la GUI.

import logging
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

logger = logging.getLogger(__name__)

# D8-2.15: clave del catálogo i18n que la pantalla muestra (la traduce la QML)
AVISO_CANCELACION_EN_ESPERA = "ciclo.cancelacion_en_espera_datos"


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="comando-ciclo-en-curso").start()


class ComandosCicloEnCurso(QObject):
    ocupadoChanged = Signal()
    errorChanged = Signal()
    avisoChanged = Signal()
    terminado = Signal(str, bool)     # (acción, ok)
    _respuesta = Signal(str, bool, str)   # (acción, ok, aviso); desde el hilo de trabajo

    def __init__(self, puente, ui_service, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._puente = puente
        self._ui = ui_service
        self._ejecutar = ejecutar
        self._ocupado = False
        self._error = ""
        self._aviso = ""
        self._respuesta.connect(self._al_responder)

    @Slot()
    def cancelar(self) -> None:
        self._enviar("cancelar", self._ui.abort_cycle)

    @Slot()
    def confirmar(self) -> None:
        self._enviar("confirmar", self._ui.acknowledge_cycle)

    @Slot()
    def descartarError(self) -> None:
        self._fijar_error("")

    @Slot()
    def descartarAviso(self) -> None:
        self._fijar_aviso("")

    def _enviar(self, accion: str, operacion) -> None:
        if self._ocupado:
            return
        if not self._puente.connected:
            logger.warning("%s ciclo: sin conexión con el backend", accion)
            self._fijar_error(accion)
            return
        self._fijar_error("")
        self._fijar_aviso("")
        self._fijar_ocupado(True)
        logger.info("Solicitando %s ciclo...", accion)

        def tarea():
            aviso = ""
            try:
                r = operacion()
                ok = bool(r)
                # D8-2.15 (tanda 8): cancelación aceptada en espera de los
                # datos del módulo E/S (R1-P5 / D8-2.13) → texto del catálogo
                if ok and isinstance(r, dict) and r.get("pendiente") is True:
                    aviso = AVISO_CANCELACION_EN_ESPERA
            except Exception as e:   # abort/acknowledge ya capturan; defensa extra
                logger.warning("%s ciclo error: %s", accion, e)
                ok = False
            try:
                self._respuesta.emit(accion, ok, aviso)
            except RuntimeError:
                pass   # TMG-10 de la revisión S2b: la ventana se cerró con la petición en curso

        self._ejecutar(tarea)

    def _al_responder(self, accion: str, ok: bool, aviso: str = "") -> None:
        self._fijar_ocupado(False)
        if ok:
            logger.info("%s ciclo aceptado por el backend%s", accion,
                        " (en espera de los datos del módulo E/S)" if aviso else "")
            self._fijar_aviso(aviso)
        else:
            logger.warning("Backend no aceptó %s ciclo", accion)
            self._fijar_error(accion)
        self.terminado.emit(accion, ok)

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    def _fijar_aviso(self, valor: str) -> None:
        if valor != self._aviso:
            self._aviso = valor
            self.avisoChanged.emit()

    def _fijar_error(self, valor: str) -> None:
        if valor != self._error:
            self._error = valor
            self.errorChanged.emit()

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    # "" sin error; "cancelar" / "confirmar" = la
    # última acción no se pudo enviar
    @Property(str, notify=errorChanged)
    def error(self) -> str:
        return self._error

    # D8-2.15: "" o la clave del catálogo del aviso de la última acción aceptada
    @Property(str, notify=avisoChanged)
    def aviso(self) -> str:
        return self._aviso
