from collections.abc import Callable
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from autoclave.ui.service_ui.backend_client import BackendClient

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""


def _format_name(raw: str) -> str:
    return raw.replace("_", " ").title()


class _MonitorBase(QWidget):
    POLL_MS = 2000
    BACKEND_URL = _BACKEND_URL

    def __init__(self, title: str, back_target: str, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(self.BACKEND_URL)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav(back_target))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        self._lbl_conn = QLabel("○ Sin datos")
        self._lbl_conn.setStyleSheet("color: #999; font-size: 12px;")
        hdr.addWidget(self._lbl_conn)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(12)
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll, stretch=1)

        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._refresh)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _refresh(self) -> None:
        try:
            status = self._client.get_status()
            self._update_cards(status)
            self._lbl_conn.setText("● Conectado")
            self._lbl_conn.setStyleSheet("color: #22c55e; font-size: 12px;")
        except Exception:
            self._lbl_conn.setText("○ Sin datos")
            self._lbl_conn.setStyleSheet("color: #ef4444; font-size: 12px;")

    def _update_cards(self, status: dict) -> None:
        raise NotImplementedError
