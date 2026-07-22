from collections.abc import Callable
from PySide6.QtWidgets import QWidget


class CalibracionSensorView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
