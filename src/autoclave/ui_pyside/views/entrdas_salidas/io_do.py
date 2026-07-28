from collections.abc import Callable
import requests
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _format_name

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_BTN_TOGGLE_OFF = """
    QPushButton { background: #e5e7eb; color: #6b7280; border-radius: 5px; border: none; }
"""
_BTN_TOGGLE_ON_ENABLED = """
    QPushButton { background: #dcfce7; color: #15803d; border-radius: 5px; border: none; }
    QPushButton:hover { background: #bbf7d0; }
"""
_BTN_TOGGLE_DEACTIVATE = """
    QPushButton { background: #fee2e2; color: #b91c1c; border-radius: 5px; border: none; }
    QPushButton:hover { background: #fecaca; }
"""


class _DoCard(QFrame):
    def __init__(self, name: str, toggle_cb: Callable[[str, bool], None]):
        super().__init__()
        self._name = name
        self._toggle_cb = toggle_cb
        self._active = False

        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )
        self.setMinimumSize(155, 100)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 10))
        lbl_name.setWordWrap(True)
        lbl_name.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_state = QLabel("○ OFF")
        self._lbl_state.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._lbl_state.setStyleSheet("color: #9ca3af; border: none;")
        lay.addWidget(self._lbl_state)

        self._btn = QPushButton("Activar")
        self._btn.setFixedHeight(26)
        self._btn.setEnabled(False)
        self._btn.setStyleSheet(_BTN_TOGGLE_OFF)
        self._btn.clicked.connect(self._on_click)
        lay.addWidget(self._btn)

    def refresh(self, raw_value: int) -> None:
        self._active = bool(raw_value)
        if self._active:
            self._lbl_state.setText("● ON")
            self._lbl_state.setStyleSheet("color: #22c55e; font-weight: bold; border: none;")
            self._btn.setText("Desactivar")
            if self._btn.isEnabled():
                self._btn.setStyleSheet(_BTN_TOGGLE_DEACTIVATE)
        else:
            self._lbl_state.setText("○ OFF")
            self._lbl_state.setStyleSheet("color: #9ca3af; font-weight: bold; border: none;")
            self._btn.setText("Activar")
            if self._btn.isEnabled():
                self._btn.setStyleSheet(_BTN_TOGGLE_ON_ENABLED)

    def enable_test_mode(self) -> None:
        self._btn.setEnabled(True)
        self._btn.setStyleSheet(_BTN_TOGGLE_DEACTIVATE if self._active else _BTN_TOGGLE_ON_ENABLED)

    def disable_test_mode(self) -> None:
        self._btn.setEnabled(False)
        self._btn.setStyleSheet(_BTN_TOGGLE_OFF)

    def _on_click(self) -> None:
        new_val = not self._active
        self._toggle_cb(self._name, new_val)
        self.refresh(int(new_val))


class SalidasDigitalesView(QWidget):
    BACKEND_URL = _BACKEND_URL
    POLL_MS = 2000
    _DO_NAMES = list(EstadoAutoclave.map_do.keys())

    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(self.BACKEND_URL)
        self._test_mode = False
        self._cards: dict[str, _DoCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        self._banner = QFrame()
        self._banner.setFixedHeight(36)
        self._banner.setStyleSheet("QFrame { background: #b45309; border-radius: 8px; }")
        bl = QHBoxLayout(self._banner)
        bl.setContentsMargins(12, 0, 12, 0)
        lbl_b = QLabel("⚠  MODO PRUEBA ACTIVO — manipule con cuidado")
        lbl_b.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_b.setStyleSheet("color: white; border: none;")
        bl.addWidget(lbl_b)
        self._banner.hide()
        root.addWidget(self._banner)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(self._on_back)
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)
        lbl_title = QLabel("SALIDAS DIGITALES")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addSpacing(20)
        self._lbl_temp_camara = QLabel("🌡️ -- °C")
        self._lbl_temp_camara.setStyleSheet("color: #b45309; font-size: 13px; font-weight: bold;")
        hdr.addWidget(self._lbl_temp_camara)
        hdr.addSpacing(12)
        self._lbl_pres_camara = QLabel("📊 -- kPa")
        self._lbl_pres_camara.setStyleSheet("color: #1d4ed8; font-size: 13px; font-weight: bold;")
        hdr.addWidget(self._lbl_pres_camara)
        hdr.addStretch()
        self._lbl_conn = QLabel("○ Sin datos")
        self._lbl_conn.setStyleSheet("color: #999; font-size: 12px;")
        hdr.addWidget(self._lbl_conn)
        hdr.addSpacing(10)
        self._btn_test = QPushButton("🔧 Habilitar modo prueba")
        self._btn_test.setFixedHeight(34)
        self._btn_test.setStyleSheet("""
            QPushButton { background: #f0f0f0; color: #333; border-radius: 8px;
                          border: 1px solid #ccc; font-size: 13px; padding: 0 12px; }
            QPushButton:hover { background: #e0e0e0; }
        """)
        self._btn_test.clicked.connect(self._on_test_toggle)
        hdr.addWidget(self._btn_test)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        gw = QWidget()
        grid = QGridLayout(gw)
        grid.setSpacing(10)

        for idx, name in enumerate(self._DO_NAMES):
            card = _DoCard(name, self._toggle_output)
            self._cards[name] = card
            row, col = divmod(idx, 3)
            grid.addWidget(card, row, col)

        scroll.setWidget(gw)
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
        if self._test_mode:
            self._exit_test_mode()

    def _on_test_toggle(self) -> None:
        if self._test_mode:
            self._exit_test_mode()
        else:
            self._enter_test_mode()

    def _enter_test_mode(self) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("MODO PRUEBA — PRECAUCIÓN")
        msg.setText(
            "Esta función apaga todas las salidas activas y permite control manual.\n\n"
            "Use únicamente con conocimiento del sistema y personal capacitado.\n\n"
            "¿Desea continuar?"
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            self._client.post("/io/test/enter")
        except requests.HTTPError as exc:
            reason = exc.response.json().get("detail", str(exc)) if exc.response is not None else str(exc)
            QMessageBox.warning(self, "No se pudo activar el modo prueba", reason)
            return
        except Exception as exc:
            QMessageBox.warning(
                self, "No se pudo activar el modo prueba",
                f"Sin comunicación con el backend: {exc}",
            )
            return

        self._test_mode = True
        self._banner.show()
        self._btn_test.setText("Salir del modo prueba")
        self._btn_test.setStyleSheet("""
            QPushButton { background: #fee2e2; color: #b91c1c; border-radius: 8px;
                          border: 1px solid #fca5a5; font-size: 13px; padding: 0 12px;
                          font-weight: bold; }
            QPushButton:hover { background: #fecaca; }
        """)
        for card in self._cards.values():
            card.enable_test_mode()

    def _exit_test_mode(self) -> None:
        try:
            self._client.post("/io/test/exit")
        except Exception:
            pass

        self._test_mode = False
        self._banner.hide()
        self._btn_test.setText("🔧 Habilitar modo prueba")
        self._btn_test.setStyleSheet("""
            QPushButton { background: #f0f0f0; color: #333; border-radius: 8px;
                          border: 1px solid #ccc; font-size: 13px; padding: 0 12px; }
            QPushButton:hover { background: #e0e0e0; }
        """)
        for card in self._cards.values():
            card.disable_test_mode()

    def _on_back(self) -> None:
        if self._test_mode:
            self._exit_test_mode()
        self._nav("io_menu")

    def _toggle_output(self, name: str, value: bool) -> None:
        try:
            self._client.patch(f"/io/test/output/{name}", {"value": value})
        except Exception:
            pass

    def _sync_forced_exit(self, reason: str) -> None:
        """El backend canceló el modo prueba por su cuenta (p.ej. paro de
        emergencia). Sincroniza la UI sin volver a llamar a /io/test/exit."""
        self._test_mode = False
        self._banner.hide()
        self._btn_test.setText("🔧 Habilitar modo prueba")
        self._btn_test.setStyleSheet("""
            QPushButton { background: #f0f0f0; color: #333; border-radius: 8px;
                          border: 1px solid #ccc; font-size: 13px; padding: 0 12px; }
            QPushButton:hover { background: #e0e0e0; }
        """)
        for card in self._cards.values():
            card.disable_test_mode()
        QMessageBox.warning(self, "Modo prueba cancelado", reason)

    def _refresh(self) -> None:
        try:
            status = self._client.get_status()
            do_data = status.get("sensors", {}).get("digital_outputs", {})
            for name, card in self._cards.items():
                card.refresh(do_data.get(name, 0))
            self._lbl_conn.setText("● Conectado")
            self._lbl_conn.setStyleSheet("color: #22c55e; font-size: 12px;")

            temp_camara = status.get("sensors", {}).get("temperature", {}).get("camara")
            pres_camara = status.get("sensors", {}).get("pressure", {}).get("camara")
            self._lbl_temp_camara.setText(
                f"🌡️ {temp_camara:.1f} °C" if temp_camara is not None else "🌡️ -- °C"
            )
            self._lbl_pres_camara.setText(
                f"📊 {pres_camara:.2f} kPa" if pres_camara is not None else "📊 -- kPa"
            )

            if self._test_mode and not status.get("test_mode_active", True):
                self._sync_forced_exit(
                    "El sistema canceló el modo prueba automáticamente "
                    "(paro de emergencia activado)."
                )
        except Exception:
            self._lbl_conn.setText("○ Sin datos")
            self._lbl_conn.setStyleSheet("color: #ef4444; font-size: 12px;")
            self._lbl_temp_camara.setText("🌡️ -- °C")
            self._lbl_pres_camara.setText("📊 -- kPa")
