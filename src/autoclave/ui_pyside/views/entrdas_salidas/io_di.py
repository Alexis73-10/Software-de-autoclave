from collections.abc import Callable
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _MonitorBase, _format_name


class _DiCard(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )
        self.setMinimumSize(160, 80)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_state = QLabel("○ INACTIVO")
        self._lbl_state.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._lbl_state.setStyleSheet("color: #9ca3af; border: none;")
        lay.addWidget(self._lbl_state)

    def set_value(self, value: int) -> None:
        if value:
            self._lbl_state.setText("● ACTIVO")
            self._lbl_state.setStyleSheet("color: #22c55e; font-weight: bold; border: none;")
        else:
            self._lbl_state.setText("○ INACTIVO")
            self._lbl_state.setStyleSheet("color: #9ca3af; font-weight: bold; border: none;")


class EntradasDigitalesView(_MonitorBase):
    _DI_NAMES = list(EstadoAutoclave.map_di.keys())

    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__("ENTRADAS DIGITALES", "io_menu", nav_callback)
        self._cards: dict[str, _DiCard] = {}
        for idx, name in enumerate(self._DI_NAMES):
            card = _DiCard(name)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        di = status.get("sensors", {}).get("digital_inputs", {})
        for name, card in self._cards.items():
            card.set_value(di.get(name, 0))
