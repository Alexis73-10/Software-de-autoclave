# ui_qml/bridge/lanzador_ajustes.py
#
# Engrane de la pantalla de ciclo: abre el menú de configuración PySide
# (autoclave.ui_pyside.app) como subproceso, con el mismo comportamiento que
# _open_settings de la UI tkinter: se oculta esta ventana mientras el menú está
# abierto, se ignora un segundo toque, y la ventana vuelve al cerrar el menú.
#
# comando_ajustes() / entorno_ajustes() replican _settings_command /
# _settings_env de ui/window/main_window.py (no se importan de ahí para no
# arrastrar tkinter a la UI QML).

import logging
import os
import subprocess
import sys

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

logger = logging.getLogger(__name__)


def comando_ajustes() -> list[str]:
    """En un build congelado sys.executable es el .exe de la UI: se lanza
    AutoclaveSettings.exe, ubicado junto a él. En desarrollo, el intérprete."""
    if getattr(sys, "frozen", False):
        return [os.path.join(os.path.dirname(sys.executable), "AutoclaveSettings.exe")]
    return [sys.executable, "-m", "autoclave.ui_pyside.app"]


def entorno_ajustes() -> dict:
    """Sin _MEIPASS2: si se hereda, el bootloader de otro .exe de PyInstaller
    confunde la carpeta de extracción y no arranca (ver _backend_env)."""
    env = {**os.environ}
    env.pop("_MEIPASS2", None)
    return env


class LanzadorAjustes(QObject):
    abiertoChanged = Signal()

    def __init__(self, parent=None, popen=subprocess.Popen, intervalo_ms: int = 500):
        super().__init__(parent)
        self._popen = popen
        self._proc = None
        self.ventana = None   # QWindow a ocultar/restaurar; la fija app.py tras cargar el QML

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self._vigilar)

    @Slot()
    def abrir(self) -> None:
        if self.abierto:
            return   # ya abierto — ignorar doble toque
        try:
            self._proc = self._popen(comando_ajustes(), env=entorno_ajustes())
        except OSError as e:
            logger.error("No se pudo lanzar el menú de configuración: %s", e)
            return
        logger.info("Menú de configuración abierto (PID %s)", getattr(self._proc, "pid", "?"))
        if self.ventana is not None:
            self.ventana.hide()
        self._timer.start()
        self.abiertoChanged.emit()

    def _vigilar(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = None
        self._timer.stop()
        logger.info("Menú de configuración cerrado")
        if self.ventana is not None:
            self.ventana.showFullScreen()
            self.ventana.requestActivate()
        self.abiertoChanged.emit()

    def cerrar(self) -> None:
        """Al salir de la UI: termina el menú si sigue abierto (como on_close en tkinter)."""
        self._timer.stop()
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None

    @Property(bool, notify=abiertoChanged)
    def abierto(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
