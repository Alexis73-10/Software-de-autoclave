import subprocess
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QFrame,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import PushButton, setTheme, Theme


class MainWindowFluent(QMainWindow):
    BACKEND_URL = "http://localhost:8000"

    def __init__(self, tkinter_proc=None):
        super().__init__()
        self._tkinter_proc = tkinter_proc
        setTheme(Theme.DARK)
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

        # Importar vistas aquí para evitar imports circulares al importar main_window
        from autoclave.ui_pyside.views.home   import HomeView
        from autoclave.ui_pyside.views.secado import SecadoView
        from autoclave.ui_pyside.views.login  import LoginView
        from autoclave.ui_pyside.views.ciclos import CiclosView

        self._home   = HomeView(nav_callback=self.navigate_to)
        self._secado = SecadoView(nav_callback=self.navigate_to)
        self._login  = LoginView(nav_callback=self.navigate_to)
        self._ciclos = CiclosView(nav_callback=self.navigate_to)

        for view in (self._home, self._secado, self._login, self._ciclos):
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

    # ── Footer ────────────────────────────────────────────────────────

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background-color: #5789a7;")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 0, 20, 0)

        btn_salir = PushButton("Salir")
        btn_salir.clicked.connect(self.close)
        layout.addWidget(btn_salir)

        layout.addStretch()

        lbl_ver = QLabel("v1.0")
        lbl_ver.setStyleSheet("color: white;")
        layout.addWidget(lbl_ver)

        layout.addStretch()

        btn_monitor = PushButton("Monitor")
        btn_monitor.clicked.connect(self._open_monitor)
        layout.addWidget(btn_monitor)

        return footer

    # ── Navegación ───────────────────────────────────────────────────

    def navigate_to(self, view_name: str) -> None:
        views = {
            "home":   self._home,
            "secado": self._secado,
            "login":  self._login,
            "ciclos": self._ciclos,
        }
        target = views.get(view_name)
        if target:
            self._stack.setCurrentWidget(target)

    # ── Reloj ────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now()
        self._lbl_time.setText(now.strftime("%H:%M"))
        self._lbl_date.setText(now.strftime("%d %b %Y"))

    # ── Monitor tkinter ──────────────────────────────────────────────

    def _open_monitor(self) -> None:
        if self._tkinter_proc is None or self._tkinter_proc.poll() is not None:
            self._tkinter_proc = subprocess.Popen(
                [sys.executable, "-m", "autoclave.ui.main"],
            )

    # ── Cierre ──────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._clock_timer.stop()
        event.accept()
