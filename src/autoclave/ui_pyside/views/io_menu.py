from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_IO_OPTIONS = [
    ("🔍", "Verificación de entradas digitales", "io_di"),
    ("🌡️", "Sensores de temperatura",           "io_temp"),
    ("📊", "Sensores de presión",               "io_pres"),
    ("⚡", "Salidas digitales",                 "io_do"),
]

_BTN_OPTION = """
    QPushButton {{
        background: {bg};
        color: #1a2a3a;
        border-radius: 12px;
        border: 1.5px solid #e8eaed;
        text-align: left;
        padding-left: 16px;
        font-size: 14px;
    }}
    QPushButton:hover   {{ background: #e8f0fe; border-color: #2563eb; }}
    QPushButton:pressed {{ background: #dbeafe; }}
"""

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""


class EntradasSalidasMenuView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        self.setStyleSheet("""
            EntradasSalidasMenuView {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a5c, stop:1 #3a6fa8
                );
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addStretch(1)

        card = QFrame()
        card.setObjectName("ioCard")
        card.setStyleSheet("QFrame#ioCard { background: white; border-radius: 20px; }")
        card.setMaximumWidth(460)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(10)

        top_row = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("admin_menu"))
        top_row.addWidget(btn_back)
        top_row.addSpacing(8)
        lbl_sub = QLabel("Administración")
        lbl_sub.setFont(QFont("Segoe UI", 13))
        lbl_sub.setStyleSheet("color: #555; background: transparent;")
        top_row.addWidget(lbl_sub)
        top_row.addStretch()
        cl.addLayout(top_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        cl.addWidget(sep)

        title = QLabel("ENTRADAS / SALIDAS")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a2a3a; background: transparent;")
        cl.addWidget(title)
        cl.addSpacing(4)

        for icon, label, target in _IO_OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION.format(bg="#f8f9fa"))
            btn.clicked.connect(lambda checked=False, t=target: self._nav(t))
            cl.addWidget(btn)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch(1)
