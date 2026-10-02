# ui_qml/bridge/comandos_ciclo_en_curso.py
#
# Comandos de la pantalla de ciclo en curso (planeacion_pantalla_ciclo_en_curso.md §10):
#   cancelar()  -> UIServiceBackend.abort_cycle()       (POST /cycle/abort)
#   confirmar() -> UIServiceBackend.acknowledge_cycle() (POST /cycle/acknowledge)
# La confirmación previa a cancelar la pide el diálogo de la pantalla; aquí
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


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="comando-ciclo-en-curso").start()


class ComandosCicloEnCurso(QObject):
    ocupadoChanged = Signal()
    errorChanged = Signal()
    terminado = Signal(str, bool)     # (acción, ok)
    _respuesta = Signal(str, bool)    # emitida desde el hilo de trabajo

    def __init__(self, puente, ui_service, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._puente = puente
        self._ui = ui_service
        self._ejecutar = ejecutar
        self._ocupado = False
        self._error = ""
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

    def _enviar(self, accion: str, operacion) -> None:
        if self._ocupado:
            return
        if not self._puente.connected:
            logger.warning("%s ciclo: sin conexión con el backend", accion)
            self._fijar_error(accion)
            return
        self._fijar_error("")
        self._fijar_ocupado(True)
        logger.info("Solicitando %s ciclo...", accion)

        def tarea():
            try:
                ok = bool(operacion())
            except Exception as e:   # abort/acknowledge ya capturan; defensa extra
                logger.warning("%s ciclo error: %s", accion, e)
                ok = False
            self._respuesta.emit(accion, ok)

        self._ejecutar(tarea)

    def _al_responder(self, accion: str, ok: bool) -> None:
        self._fijar_ocupado(False)
        if ok:
            logger.info("%s ciclo aceptado por el backend", accion)
        else:
            logger.warning("Backend no aceptó %s ciclo", accion)
            self._fijar_error(accion)
        self.terminado.emit(accion, ok)

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    def _fijar_error(self, valor: str) -> None:
        if valor != self._error:
            self._error = valor
            self.errorChanged.emit()

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    # "" sin error; "cancelar" / "confirmar" = la última acción no se pudo enviar
    @Property(str, notify=errorChanged)
    def error(self) -> str:
        return self._error
