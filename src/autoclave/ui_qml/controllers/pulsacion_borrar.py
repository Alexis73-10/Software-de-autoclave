# ui_qml/controllers/pulsacion_borrar.py
#
# Temporizador de la tecla Borrar compartido por los dos controladores de
# teclado. Solo mide y avisa: la decisión (un carácter, todo o nada) vive en
# domain/borrado_tecla.py (TEC-D15). El QTimer despierta a los 600 ms; la
# duración se mide con el reloj monotónico inyectado, no con el QTimer.

import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer

from autoclave.ui_qml.domain import borrado_tecla as dominio


class PulsacionBorrar(QObject):
    def __init__(self, al_borrar_uno: Callable[[], None], al_borrar_todo: Callable[[], None],
                 reloj: Callable[[], float] = time.monotonic, parent=None):
        super().__init__(parent)
        self._al_borrar_uno = al_borrar_uno
        self._al_borrar_todo = al_borrar_todo
        self._reloj = reloj
        self._t_presion: float | None = None
        self._total_disparado = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(round(dominio.UMBRAL_BORRADO_TOTAL_S * 1000))
        self._timer.timeout.connect(self.vencer)

    def presionar(self) -> None:
        self._t_presion = self._reloj()
        self._total_disparado = False
        self._timer.start()

    def vencer(self) -> None:
        if self._t_presion is None:
            return
        accion = dominio.al_cumplir_umbral(self._t_presion, self._reloj(), self._total_disparado)
        if accion is dominio.AccionBorrado.TODO:
            self._total_disparado = True
            self._al_borrar_todo()
        elif not self._total_disparado:
            # El QTimer despertó antes de los 600 ms monotónicos: reintentar.
            self._timer.start(10)

    def soltar(self) -> None:
        if self._t_presion is None:
            return
        self._timer.stop()
        accion = dominio.al_soltar(self._t_presion, self._reloj(), self._total_disparado)
        self._t_presion = None
        if accion is dominio.AccionBorrado.TODO:
            self._al_borrar_todo()
        elif accion is dominio.AccionBorrado.UN_CARACTER:
            self._al_borrar_uno()

    def cancelar(self) -> None:
        """El dedo salió de la tecla: no se borra nada al soltar."""
        self._timer.stop()
        self._t_presion = None
