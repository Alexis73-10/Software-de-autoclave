# ui_qml/bridge/comandos_puerta.py
#
# Botón de puerta de la pantalla de ciclo: abre o cierra la puerta de ESTA
# ventana (--door N) vía DoorCommandService, igual que _accion_puerta_1 de la
# UI tkinter. La petición HTTP corre fuera del hilo de la GUI; el resultado
# vuelve por una señal (conexión en cola al hilo de la GUI).
#
# La acción la decide UiBridge.doorOpen, la misma regla que pinta el texto del
# botón ("CERRAR PUERTA" / "ABRIR PUERTA"), para que lo que se ve y lo que se
# envía no diverjan. El interlock real lo aplica el backend (ServicioPuertas).

import logging
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

logger = logging.getLogger(__name__)

_DURACION_MENSAJE_MS = 5000


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="comando-puerta").start()


class ComandosPuerta(QObject):
    ocupadoChanged = Signal()
    mensajeChanged = Signal()
    _terminado = Signal(bool, str)   # emitida desde el hilo de trabajo

    def __init__(self, puente, door_commands, parent=None, ejecutar=_en_hilo,
                 duracion_mensaje_ms: int = _DURACION_MENSAJE_MS):
        super().__init__(parent)
        self._puente = puente
        self._cmd = door_commands
        self._ejecutar = ejecutar
        self._ocupado = False
        self._mensaje = ""
        self._terminado.connect(self._al_terminar)

        self._timer_mensaje = QTimer(self)
        self._timer_mensaje.setSingleShot(True)
        self._timer_mensaje.setInterval(duracion_mensaje_ms)
        self._timer_mensaje.timeout.connect(lambda: self._fijar_mensaje(""))

    @Slot()
    def alternar(self) -> None:
        # Sin conexión la pantalla ya deshabilita el botón; se repite aquí
        # para no depender solo de la vista.
        if self._ocupado or not self._puente.connected:
            return
        nombre = f"Puerta {self._puente.door}"
        cerrar = self._puente.doorOpen
        accion = self._cmd.close if cerrar else self._cmd.open
        logger.info("Solicitud de %s %s (estado mostrado: %s)",
                    "cierre" if cerrar else "apertura", nombre, self._puente.doorState)

        self._fijar_ocupado(True)
        self._fijar_mensaje("")

        def tarea():
            try:
                ok, motivo = accion(nombre)
            except Exception as e:   # DoorCommandService ya captura todo; defensa extra
                ok, motivo = False, str(e)
            self._terminado.emit(bool(ok), motivo or "")

        self._ejecutar(tarea)

    def _al_terminar(self, ok: bool, motivo: str) -> None:
        self._fijar_ocupado(False)
        if ok:
            logger.info("Comando de puerta aceptado")
            return
        logger.warning("Comando de puerta rechazado: %s", motivo)
        self._fijar_mensaje(motivo)
        self._timer_mensaje.start()

    def _fijar_ocupado(self, valor: bool) -> None:
        if valor != self._ocupado:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    def _fijar_mensaje(self, valor: str) -> None:
        if valor != self._mensaje:
            self._mensaje = valor
            self.mensajeChanged.emit()

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        """Motivo del último rechazo; se borra solo a los 5 s."""
        return self._mensaje
