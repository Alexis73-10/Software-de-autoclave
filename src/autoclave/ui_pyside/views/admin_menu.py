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
from qfluentwidgets import InfoBar, InfoBarPosition

_OPTIONS = [
    ("📋", "Parámetros del ciclo"),
    ("⚙️", "Parámetros del sistema"),
    ("🔌", "Entradas / Salidas"),
    ("🔧", "Mantenimiento"),
    ("⚡", "Opciones avanzadas"),
]

_OPTION_ROUTES = {
    "Parámetros del ciclo": "params_ciclo",
    "Entradas / Salidas":   "io_menu",
}

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
        background: #f0f0f0;
        color: #333;
        border-radius: 8px;
        border: none;
        font-size: 20px;
        font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""
_BTN_LOGOUT = """
    QPushButton {
        background: transparent;
        color: #e53e3e;
        border: 1.5px solid #e53e3e;
        border-radius: 8px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover { background: #fff5f5; }
"""


class AdminMenuView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        self.setStyleSheet("""
            AdminMenuView {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a5c, stop:1 #3a6fa8
                );
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addStretch(1)

        # Card blanca
        card = QFrame()
        card.setObjectName("adminCard")
        card.setStyleSheet("QFrame#adminCard { background: white; border-radius: 20px; }")
        card.setMaximumWidth(460)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(10)

        # Fila superior: back + usuario
        top_row = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("home"))
        top_row.addWidget(btn_back)
        top_row.addSpacing(8)

        self._lbl_user = QLabel("Administrador")
        self._lbl_user.setFont(QFont("Segoe UI", 13))
        self._lbl_user.setStyleSheet("color: #555; background: transparent;")
        top_row.addWidget(self._lbl_user)
        top_row.addStretch()

        btn_logout = QPushButton("Cerrar sesión")
        btn_logout.setFixedHeight(34)
        btn_logout.setStyleSheet(_BTN_LOGOUT)
        btn_logout.clicked.connect(self._do_logout)
        top_row.addWidget(btn_logout)
        cl.addLayout(top_row)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        cl.addWidget(sep)

        # Título
        title = QLabel("ADMINISTRACIÓN")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a2a3a; background: transparent;")
        cl.addWidget(title)

        cl.addSpacing(4)

        # Opciones
        for icon, label in _OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION.format(bg="#f8f9fa"))
            btn.clicked.connect(lambda checked=False, n=label: self._option_clicked(n))
            cl.addWidget(btn)

        # Centrar card
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch(1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            from autoclave.ui_pyside.services.session_manager import SessionManager
            if SessionManager.is_logged_in():
                self._lbl_user.setText(SessionManager.current_user["nombre"])
        except Exception:
            pass

    def _option_clicked(self, name: str) -> None:
        target = _OPTION_ROUTES.get(name)
        if target:
            self._nav(target)
            return
        InfoBar.info(
            title=name,
            content="Esta sección estará disponible próximamente.",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _do_logout(self) -> None:
        from autoclave.ui_pyside.services.session_manager import SessionManager
        SessionManager.logout()
        self._nav("login")
