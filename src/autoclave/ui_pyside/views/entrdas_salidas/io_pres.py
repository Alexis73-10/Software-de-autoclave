from collections.abc import Callable
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _MonitorBase, _format_name

_CARD_NORMAL = "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
_CARD_HOVER = "QFrame { background: #eff6ff; border-radius: 10px; border: 1.5px solid #2563eb; }"


class _PresCard(QFrame):
    def __init__(self, name: str, nav_callback: Optional[Callable] = None):
        super().__init__()
        self._name = name
        self._nav = nav_callback
        self.setStyleSheet(_CARD_NORMAL)
        self.setMinimumSize(180, 90)
        if nav_callback is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #555; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel("0.00 kPa")
        self._lbl_value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(self._lbl_value)

    def set_value(self, value: float) -> None:
        self._lbl_value.setText(f"{value:.2f} kPa")

    def enterEvent(self, event) -> None:
        if self._nav is not None:
            self.setStyleSheet(_CARD_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(_CARD_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self._nav is not None and event.button() == Qt.MouseButton.LeftButton:
            self._nav("calibracion_sensor", {"tipo": "pressure", "sensor": self._name})
        super().mousePressEvent(event)


class PresionesView(_MonitorBase):
    _PRES_NAMES = list(EstadoAutoclave.map_pres.keys())

    _NAME_MAP = {
        "pres_camara":    "camara",
        "pres_chaqueta":  "chaqueta",
        "pres_empaque_1": "empaque_1",
        "pres_empaque_2": "empaque_2",
    }

    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__("SENSORES DE PRESIÓN", "io_menu", nav_callback)
        self._cards: dict[str, _PresCard] = {}
        for idx, name in enumerate(self._PRES_NAMES):
            card = _PresCard(name, nav_callback=nav_callback)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        pres = status.get("sensors", {}).get("pressure", {})
        for name, card in self._cards.items():
            key = self._NAME_MAP.get(name, name)
            card.set_value(pres.get(key, 0.0) or 0.0)
