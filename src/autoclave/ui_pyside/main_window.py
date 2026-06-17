from datetime import datetime

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, TransparentToolButton, setTheme, Theme


class MainWindowFluent(QMainWindow):

    def __init__(self):
        super().__init__()
        setTheme(Theme.LIGHT)
        self.setWindowTitle("Especifika — Autoclave")
        self.setMinimumSize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        root.addWidget(self._build_footer())

        from autoclave.ui_pyside.views.home       import HomeView
        from autoclave.ui_pyside.views.secado     import SecadoView
        from autoclave.ui_pyside.views.login      import LoginView
        from autoclave.ui_pyside.views.ciclos     import CiclosView
        from autoclave.ui_pyside.views.admin_menu import AdminMenuView

        self._home       = HomeView(nav_callback=self.navigate_to)
        self._secado     = SecadoView(nav_callback=self.navigate_to)
        self._login      = LoginView(nav_callback=self.navigate_to)
        self._ciclos     = CiclosView(nav_callback=self.navigate_to)
        self._admin_menu = AdminMenuView(nav_callback=self.navigate_to)

        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._admin_menu):
            self._stack.addWidget(view)

        self._stack.setCurrentWidget(self._home)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    # ── Header ────────────────────────────────────────────────────────

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet("background-color: #1a2a3a;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("e-specifika")
        logo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        logo.setStyleSheet("color: white;")
        layout.addWidget(logo)

        layout.addStretch()

        self._lbl_time = QLabel("--:--")
        self._lbl_time.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._lbl_time.setStyleSheet("color: white;")
        layout.addWidget(self._lbl_time)

        self._lbl_date = QLabel("")
        self._lbl_date.setFont(QFont("Segoe UI", 11))
        self._lbl_date.setStyleSheet("color: #aaccee; margin-left: 10px;")
        layout.addWidget(self._lbl_date)

        layout.addStretch()

        return header

    # ── Footer — barra de navegación ─────────────────────────────────

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(64)
        footer.setStyleSheet("""
            QFrame {
                background: white;
                border-top: 1px solid #e0e0e0;
            }
        """)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_items = [
            (FluentIcon.PEOPLE,          "login",  True),
            (FluentIcon.HISTORY,         "ciclos", True),
            (FluentIcon.DEVELOPER_TOOLS, None,     False),
            (FluentIcon.HOME,            "home",   True),
        ]

        for idx, (icon, target, active) in enumerate(nav_items):
            if idx > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setFixedWidth(1)
                sep.setStyleSheet("background: #e0e0e0;")
                layout.addWidget(sep)

            btn = TransparentToolButton(icon)
            btn.setFixedSize(64, 64)
            btn.setIconSize(QSize(28, 28))
            if active and target:
                btn.clicked.connect(
                    lambda checked=False, t=target: self.navigate_to(t)
                )
            else:
                btn.setEnabled(False)
                btn.setToolTip("Próximamente")
            layout.addWidget(btn, stretch=1)

        lbl_ver = QLabel("V:1.0")
        lbl_ver.setStyleSheet("color: #bbb; font-size: 11px; padding-right: 10px;")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl_ver)

        return footer

    # ── Navegación ───────────────────────────────────────────────────

    def navigate_to(self, view_name: str) -> None:
        views = {
            "home":       self._home,
            "secado":     self._secado,
            "login":      self._login,
            "ciclos":     self._ciclos,
            "admin_menu": self._admin_menu,
        }
        target = views.get(view_name)
        if target:
            self._stack.setCurrentWidget(target)

    # ── Reloj ────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now()
        self._lbl_time.setText(now.strftime("%H:%M"))
        self._lbl_date.setText(now.strftime("%d %b %Y"))

    # ── Cierre ───────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._clock_timer.stop()
        event.accept()
