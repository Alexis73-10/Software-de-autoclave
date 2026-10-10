# ui_qml/bridge/comandos_falla.py
#
# Botón "RECONOCER FALLA" de la pantalla de preciclo (T-16;
# planeacion_backend_autenticacion.md §5.9 y decisión 22): sin rol ni token,
# visible solo con la máquina en FALLA. Envía POST /fault/reset
# (UIServiceBackend.reset_fault); el backend vuelve a validar el estado y lo
# rechaza (409) con el paro de emergencia activo. Si lo rechaza, solo queda en
# el log, igual que el inicio de ciclo. La petición corre fuera del hilo de la GUI.

import logging
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

logger = logging.getLogger(__name__)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="reconocer-falla").start()


class ComandoReconocerFalla(QObject):
    ocupadoChanged = Signal()
    _terminado = Signal(bool)   # emitida desde el hilo de trabajo

    def __init__(self, puente, ui_service, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._puente = puente
        self._ui = ui_service
        self._ejecutar = ejecutar
        self._ocupado = False
        self._terminado.connect(self._al_terminar)

    @Slot()
    def reconocer(self) -> None:
        if self._ocupado or not self._puente.connected or self._puente.machineState != "FALLA":
            return
        logger.info("Reconociendo la falla...")
        self._fijar_ocupado(True)

        def tarea():
            try:
                ok = bool(self._ui.reset_fault())
            except Exception as e:   # reset_fault ya captura todo; defensa extra
                logger.warning("reset_fault error: %s", e)
                ok = False
            try:
                self._terminado.emit(ok)
            except RuntimeError:
                pass   # la ventana se cerró con la petición en curso

        self._ejecutar(tarea)

    def _al_terminar(self, ok: bool) -> None:
        self._fijar_ocupado(False)
        if ok:
            logger.info("Reconocimiento de falla aceptado por el backend")
        else:
            logger.warning("Backend rechazó el reconocimiento de la falla")

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado
