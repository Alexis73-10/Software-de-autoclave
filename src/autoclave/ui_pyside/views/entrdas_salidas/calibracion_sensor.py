from collections.abc import Callable

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autoclave.hal.measures.calibration_tools import invert_user_calibration, fit_two_point
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui_pyside.services.session_manager import SessionManager

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

_BTN_GUARDAR = """
    QPushButton { background: #2563eb; color: white; border-radius: 8px;
        border: none; font-size: 13px; font-weight: bold; padding: 0 20px; }
    QPushButton:hover { background: #1d4ed8; }
    QPushButton:disabled { background: #93c5fd; }
"""

_ROLES_PERMITIDOS = ("admin", "tecnico")


class CalibracionSensorView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._tipo: str | None = None
        self._sensor: str | None = None
        self._back_target = "io_temp"
        self._preview_gain: float | None = None
        self._preview_offset: float | None = None
        self._current_gain: float = 1.0
        self._current_offset: float = 0.0
        self._current_poly = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav(self._back_target))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)
        self._lbl_title = QLabel("CALIBRACIÓN DE SENSOR")
        self._lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self._lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(self._lbl_title)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        self._lbl_denegado = QLabel("No tienes permiso para calibrar sensores.")
        self._lbl_denegado.setStyleSheet("color: #ef4444; font-size: 14px;")
        self._lbl_denegado.hide()
        root.addWidget(self._lbl_denegado)

        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet("color: #6b7280; font-size: 12px;")
        root.addWidget(self._lbl_info)

        self._form_widget = QWidget()
        form = QFormLayout(self._form_widget)
        form.setSpacing(8)

        self._input_shown_low = QDoubleSpinBox()
        self._input_real_low = QDoubleSpinBox()
        self._input_shown_high = QDoubleSpinBox()
        self._input_real_high = QDoubleSpinBox()
        for inp in (self._input_shown_low, self._input_real_low,
                    self._input_shown_high, self._input_real_high):
            inp.setDecimals(2)
            inp.setRange(-1000.0, 1000.0)
            inp.setValue(0.0)
            inp.valueChanged.connect(self._on_inputs_changed)

        form.addRow("Mostrado bajo:", self._input_shown_low)
        form.addRow("Real bajo (patrón):", self._input_real_low)
        form.addRow("Mostrado alto:", self._input_shown_high)
        form.addRow("Real alto (patrón):", self._input_real_high)

        self._lbl_preview = QLabel("—")
        self._lbl_preview.setStyleSheet("color: #1a2a3a; font-weight: bold;")
        form.addRow("Gain/Offset resultante:", self._lbl_preview)

        root.addWidget(self._form_widget)

        self._btn_guardar = QPushButton("Guardar")
        self._btn_guardar.setFixedHeight(36)
        self._btn_guardar.setStyleSheet(_BTN_GUARDAR)
        self._btn_guardar.setEnabled(False)
        self._btn_guardar.clicked.connect(self._on_guardar)
        root.addWidget(self._btn_guardar)

        root.addStretch()

    # ── Contexto / carga ─────────────────────────────────────────────

    def set_context(self, tipo: str, sensor: str, back_target: str | None = None) -> None:
        self._tipo = tipo
        self._sensor = sensor
        self._back_target = back_target or ("io_temp" if tipo == "temperature" else "io_pres")
        self._lbl_title.setText(f"CALIBRACIÓN — {sensor}")

        for inp in (self._input_shown_low, self._input_real_low,
                    self._input_shown_high, self._input_real_high):
            inp.blockSignals(True)
            inp.setValue(0.0)
            inp.blockSignals(False)
        self._preview_gain = None
        self._preview_offset = None
        self._lbl_preview.setText("—")
        self._btn_guardar.setEnabled(False)

        if not self._tiene_permiso():
            self._form_widget.hide()
            self._btn_guardar.hide()
            self._lbl_denegado.show()
            self._lbl_info.setText("")
            return

        self._lbl_denegado.hide()

        try:
            info = self._client.get_calibration(tipo, sensor)
        except Exception:
            self._form_widget.hide()
            self._btn_guardar.hide()
            self._lbl_info.setText("No se pudo conectar con el backend — inténtalo de nuevo.")
            return

        self._form_widget.show()
        self._btn_guardar.show()

        self._current_gain = info.get("gain", 1.0)
        self._current_offset = info.get("offset", 0.0)
        self._current_poly = info.get("poly")

        if info.get("is_poly"):
            calib_txt = "polinomio (5 puntos)"
        else:
            calib_txt = f"gain={self._current_gain}, offset={self._current_offset}"

        last = info.get("last_change")
        if last:
            audit_txt = f"Última modificación: {last['usuario']} · {last['timestamp']}"
        else:
            audit_txt = "Sin modificaciones previas"

        self._lbl_info.setText(f"Calibración actual: {calib_txt}\n{audit_txt}")

    def _tiene_permiso(self) -> bool:
        if not SessionManager.is_authenticated():
            return False
        return SessionManager.current_role() in _ROLES_PERMITIDOS

    def _formulario_visible(self) -> bool:
        # `isVisible()` depende de que toda la cadena de ancestros (incluida
        # esta vista de nivel superior) esté mostrada en pantalla, lo cual no
        # ocurre en tests headless. `isVisibleTo(self)` refleja el estado
        # show()/hide() explícito sin exigir que `self` esté visible.
        return self._form_widget.isVisibleTo(self)

    # ── Vista previa ─────────────────────────────────────────────────

    def _on_inputs_changed(self) -> None:
        shown_low = self._input_shown_low.value()
        real_low = self._input_real_low.value()
        shown_high = self._input_shown_high.value()
        real_high = self._input_real_high.value()

        if shown_low == shown_high:
            self._preview_gain = None
            self._preview_offset = None
            self._lbl_preview.setText("—")
            self._btn_guardar.setEnabled(False)
            return

        try:
            fv_low = invert_user_calibration(shown_low, self._current_gain, self._current_offset, self._current_poly)
            fv_high = invert_user_calibration(shown_high, self._current_gain, self._current_offset, self._current_poly)
            gain, offset = fit_two_point(fv_low, real_low, fv_high, real_high)
        except ValueError:
            self._preview_gain = None
            self._preview_offset = None
            self._lbl_preview.setText("—")
            self._btn_guardar.setEnabled(False)
            return

        self._preview_gain = gain
        self._preview_offset = offset
        self._lbl_preview.setText(f"gain={gain:.6f}  offset={offset:.6f}")
        self._btn_guardar.setEnabled(True)

    # ── Guardar ──────────────────────────────────────────────────────

    def _on_guardar(self) -> None:
        if self._preview_gain is None or self._tipo is None or self._sensor is None:
            return

        usuario = (
            SessionManager.current_user().get("nombre", "Desconocido")
            if SessionManager.is_authenticated()
            else "Desconocido"
        )

        body = {
            "shown_low": self._input_shown_low.value(),
            "real_low": self._input_real_low.value(),
            "shown_high": self._input_shown_high.value(),
            "real_high": self._input_real_high.value(),
            "usuario": usuario,
        }
        try:
            result = self._client.save_calibration(self._tipo, self._sensor, body)
        except Exception:
            self._lbl_info.setText("No se pudo guardar la calibración — inténtalo de nuevo.")
            return

        self._current_gain = result["gain"]
        self._current_offset = result["offset"]
        self._current_poly = None
        self._lbl_info.setText(
            f"Calibración actual: gain={result['gain']}, offset={result['offset']}\n"
            f"Última modificación: {usuario} · ahora"
        )
