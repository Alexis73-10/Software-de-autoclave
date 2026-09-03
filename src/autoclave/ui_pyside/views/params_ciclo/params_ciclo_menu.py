from collections.abc import Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_BTN_OPTION = """
    QPushButton {
        background: #f8f9fa;
        color: #1a2a3a;
        border-radius: 12px;
        border: 1.5px solid #e8eaed;
        text-align: left;
        padding-left: 16px;
        font-size: 14px;
    }
    QPushButton:hover   { background: #e8f0fe; border-color: #2563eb; }
    QPushButton:pressed { background: #dbeafe; }
"""

_OPTIONS = [
    ("🌡️", "Sensores de temperatura", "sensores_temperatura_ciclo"),
    ("📺", "Entradas exhibidas",       "entradas_exhibidas_ciclo"),
    ("🧪", "Fases del ciclo",          "params_ciclo"),
]


class ParametrosCicloMenuView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback

        self.setObjectName("paramsCicloMenuView")
        self.setStyleSheet("QWidget#paramsCicloMenuView { background: #f3f4f6; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("admin_menu"))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)

        lbl_title = QLabel("PARÁMETROS DEL CICLO")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        root.addSpacing(8)

        for icon, label, target in _OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION)
            btn.clicked.connect(lambda checked=False, t=target: self._nav(t))
            root.addWidget(btn)

        root.addStretch(1)
