# ui_qml/controllers/reloj_splash_controller.py
#
# Puente QObject entre domain/reloj_splash.py (funciones puras) y el
# componente QML PantallaInicio. `ahora_fn` (por defecto datetime.now, hora
# de pared — es presentación pura, no temporizado de proceso, así que no
# aplica la regla de reloj monótono del CLAUDE.md) es inyectable para
# pruebas. Un QTimer de 1 s reevalúa horaActual/fechaActual.

from datetime import datetime

from PySide6.QtCore import QObject, Property, QTimer, Signal
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml.domain import reloj_splash as dominio


class RelojSplashController(QObject):
    horaActualChanged = Signal()
    fechaActualChanged = Signal()

    def __init__(self, parent=None, ahora_fn=datetime.now, intervalo_ms=1000):
        super().__init__(parent)
        self._ahora_fn = ahora_fn
        self._hora_actual = dominio.formatear_hora(ahora_fn())
        self._fecha_actual = dominio.formatear_fecha(ahora_fn())

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.actualizar)
        self._timer.start()

    def actualizar(self) -> None:
        ahora = self._ahora_fn()

        hora = dominio.formatear_hora(ahora)
        if hora != self._hora_actual:
            self._hora_actual = hora
            self.horaActualChanged.emit()

        fecha = dominio.formatear_fecha(ahora)
        if fecha != self._fecha_actual:
            self._fecha_actual = fecha
            self.fechaActualChanged.emit()

    @Property(str, notify=horaActualChanged)
    def horaActual(self) -> str:
        return self._hora_actual

    @Property(str, notify=fechaActualChanged)
    def fechaActual(self) -> str:
        return self._fecha_actual


qmlRegisterType(RelojSplashController, "Autoclave.Controllers", 1, 0, "RelojSplashController")
