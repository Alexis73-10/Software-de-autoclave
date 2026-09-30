# ui_qml/bridge/comandos_ciclo.py
#
# Botón "INICIAR CICLO" de la pantalla de ciclo. Misma lógica que la UI
# tkinter (_upd_listo + start_cycle de ui/window/main_window.py):
#   - solo se acepta con LISTO_PARA_CICLO activo (en QML, además, el botón
#     desaparece cuando no lo está);
#   - envía UIServiceBackend.start_cycle() (POST /cycle/start); si el backend
#     lo rechaza, solo se registra en el log, igual que tkinter.
# El backend vuelve a validar LISTO_PARA_CICLO (409 si no está listo).
# La petición HTTP corre fuera del hilo de la GUI.

import logging
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

logger = logging.getLogger(__name__)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="iniciar-ciclo").start()


class ComandoIniciarCiclo(QObject):
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
    def iniciar(self) -> None:
        if self._ocupado or not self._puente.connected or not self._puente.listoParaCiclo:
            return
        logger.info("Iniciando ciclo...")
        self._fijar_ocupado(True)

        def tarea():
            try:
                ok = bool(self._ui.start_cycle())
            except Exception as e:   # start_cycle ya captura todo; defensa extra
                logger.warning("start_cycle error: %s", e)
                ok = False
            self._terminado.emit(ok)

        self._ejecutar(tarea)

    def _al_terminar(self, ok: bool) -> None:
        self._fijar_ocupado(False)
        if ok:
            logger.info("Inicio de ciclo aceptado por el backend")
        else:
            logger.warning("Backend rechazó el inicio del ciclo")

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado
