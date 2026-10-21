from datetime import datetime

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
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

        self._header = self._build_header()
        root.addWidget(self._header)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._footer = self._build_footer()
        root.addWidget(self._footer)

        from autoclave.ui_pyside.views.home       import HomeView
        from autoclave.ui_pyside.views.secado     import SecadoView
        from autoclave.ui_pyside.views.login      import LoginView
        from autoclave.ui_pyside.views.ciclos     import CiclosView
        from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
        from autoclave.ui_pyside.views.admin_menu import AdminMenuView
        from autoclave.ui_pyside.views.entrdas_salidas.io_menu    import EntradasSalidasMenuView
        from autoclave.ui_pyside.views.entrdas_salidas.io_di      import EntradasDigitalesView
        from autoclave.ui_pyside.views.entrdas_salidas.io_temp    import TemperaturasView
        from autoclave.ui_pyside.views.entrdas_salidas.io_pres    import PresionesView
        from autoclave.ui_pyside.views.entrdas_salidas.io_do      import SalidasDigitalesView
        from autoclave.ui_pyside.views.params_ciclo.params_ciclo import ParametrosCicloView
        from autoclave.ui_pyside.views.entrdas_salidas.calibracion_sensor import CalibracionSensorView
        from autoclave.ui_pyside.views.nuevo_usuario.vista import NuevoUsuarioView

        self._home       = HomeView(nav_callback=self.navigate_to)
        self._secado     = SecadoView(nav_callback=self.navigate_to)
        self._login      = LoginView(nav_callback=self.navigate_to)
        self._ciclos     = CiclosView(nav_callback=self.navigate_to)
        self._impresion_menu = ImpresionMenuView(nav_callback=self.navigate_to)
        self._admin_menu = AdminMenuView(nav_callback=self.navigate_to)
        self._io_menu    = EntradasSalidasMenuView(nav_callback=self.navigate_to)
        self._io_di      = EntradasDigitalesView(nav_callback=self.navigate_to)
        self._io_temp    = TemperaturasView(nav_callback=self.navigate_to)
        self._io_pres    = PresionesView(nav_callback=self.navigate_to)
        self._io_do      = SalidasDigitalesView(nav_callback=self.navigate_to)
        self._params_ciclo = ParametrosCicloView(nav_callback=self.navigate_to)
        self._calibracion_sensor = CalibracionSensorView(nav_callback=self.navigate_to)
        self._nuevo_usuario = NuevoUsuarioView(nav_callback=self.navigate_to)

        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._impresion_menu, self._admin_menu, self._io_menu,
                     self._io_di, self._io_temp, self._io_pres, self._io_do,
                     self._params_ciclo, self._calibracion_sensor, self._nuevo_usuario):
            self._stack.addWidget(view)

        self._stack.setCurrentWidget(self._home)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        # P3 (tanda 5): renueva el token mientras la ventana está en uso (B7)
        from autoclave.ui_pyside.services import renovacion_sesion
        renovacion_sesion.instalar_en(self)

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

        btn_exit = QPushButton("✕ Salir")
        btn_exit.setFixedHeight(36)
        btn_exit.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ff6b6b;
                border: 1.5px solid #ff6b6b; border-radius: 8px;
                font-size: 13px; font-weight: bold; padding: 0 14px;
            }
            QPushButton:hover { background: rgba(255,107,107,0.15); }
        """)
        btn_exit.setToolTip("Cerrar menú y volver a pantalla principal")
        btn_exit.clicked.connect(self._salir)
        layout.addWidget(btn_exit)

        return header

    def _salir(self) -> None:
        """Cierra el menú: antes invalida el token de esta ventana (C1)."""
        try:
            from autoclave.ui_pyside.services import auth_backend
            auth_backend.cerrar_sesion()
        except Exception:
            pass
        QApplication.instance().quit()

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

    def navigate_to(self, view_name: str, payload: dict | None = None) -> None:
        views = {
            "home":         self._home,
            "secado":       self._secado,
            "login":        self._login,
            "ciclos":       self._ciclos,
            "impresion_menu": self._impresion_menu,
            "admin_menu":   self._admin_menu,
            "io_menu":      self._io_menu,
            "io_di":        self._io_di,
            "io_temp":      self._io_temp,
            "io_pres":      self._io_pres,
            "io_do":        self._io_do,
            "params_ciclo": self._params_ciclo,
            "calibracion_sensor": self._calibracion_sensor,
            "nuevo_usuario": self._nuevo_usuario,
        }
        target = views.get(view_name)
        if target:
            if payload and hasattr(target, "set_context"):
                target.set_context(**payload)
            # Una vista con oculta_marco = True trae su propio encabezado y pie
            # (p. ej. las pantallas QML alojadas en QQuickWidget)
            marco = not getattr(target, "oculta_marco", False)
            self._header.setVisible(marco)
            self._footer.setVisible(marco)
            self._stack.setCurrentWidget(target)

    # ── Reloj ────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now()
        self._lbl_time.setText(now.strftime("%H:%M"))
        self._lbl_date.setText(now.strftime("%d %b %Y"))

    # ── Cierre ───────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._clock_timer.stop()
        # C1 (SAF-01): cualquier cierre de la ventana invalida el token (y con él
        # sale de un modo prueba que esta sesión tuviera), no solo "✕ Salir"
        try:
            from autoclave.ui_pyside.services import auth_backend
            auth_backend.cerrar_sesion()
        except Exception:
            pass
        event.accept()
