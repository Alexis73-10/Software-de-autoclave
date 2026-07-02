# src/autoclave/ui_pyside/views/secado.py
import requests
from autoclave.ui.service_ui.backend_client import BackendClient
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    DoubleSpinBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
)


class SecadoView(QWidget):
    BACKEND_URL = "http://localhost:8000"

    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("Configuración de Secado"))

        # ── Modo ─────────────────────────────────────────────────────────
        modo_row = QHBoxLayout()
        modo_row.addWidget(BodyLabel("Modo (1=Vacío, 2=Vacío+Aire, 3=Pulsado):"))
        self._spin_modo = SpinBox()
        self._spin_modo.setRange(1, 3)
        self._spin_modo.setFixedWidth(100)
        self._spin_modo.valueChanged.connect(self._on_modo_changed)
        modo_row.addWidget(self._spin_modo)
        modo_row.addStretch()
        layout.addLayout(modo_row)

        # ── Tiempo ───────────────────────────────────────────────────────
        tiempo_row = QHBoxLayout()
        tiempo_row.addWidget(BodyLabel("Tiempo de secado (min):"))
        self._spin_tiempo = DoubleSpinBox()
        self._spin_tiempo.setRange(0.0, 120.0)
        self._spin_tiempo.setSingleStep(0.5)
        self._spin_tiempo.setDecimals(1)
        self._spin_tiempo.setFixedWidth(140)
        tiempo_row.addWidget(self._spin_tiempo)
        tiempo_row.addStretch()
        layout.addLayout(tiempo_row)

        # ── Presión chaqueta ─────────────────────────────────────────────
        chaqueta_row = QHBoxLayout()
        chaqueta_row.addWidget(BodyLabel("Presión chaqueta secado (kPa):"))
        self._spin_chaqueta = SpinBox()
        self._spin_chaqueta.setRange(0, 500)
        self._spin_chaqueta.setFixedWidth(120)
        chaqueta_row.addWidget(self._spin_chaqueta)
        chaqueta_row.addStretch()
        layout.addLayout(chaqueta_row)

        # ── Parámetros modo 3 (ocultos por defecto) ───────────────────────
        self._modo3_widget = QWidget()
        modo3_layout = QVBoxLayout(self._modo3_widget)
        modo3_layout.setContentsMargins(0, 0, 0, 0)
        modo3_layout.setSpacing(12)

        pres_baja_row = QHBoxLayout()
        pres_baja_row.addWidget(BodyLabel("Presión baja pulso (kPa):"))
        self._spin_pres_baja = SpinBox()
        self._spin_pres_baja.setRange(0, 200)
        self._spin_pres_baja.setFixedWidth(120)
        pres_baja_row.addWidget(self._spin_pres_baja)
        pres_baja_row.addStretch()
        modo3_layout.addLayout(pres_baja_row)

        pres_alta_row = QHBoxLayout()
        pres_alta_row.addWidget(BodyLabel("Presión alta pulso (kPa):"))
        self._spin_pres_alta = SpinBox()
        self._spin_pres_alta.setRange(0, 300)
        self._spin_pres_alta.setFixedWidth(120)
        pres_alta_row.addWidget(self._spin_pres_alta)
        pres_alta_row.addStretch()
        modo3_layout.addLayout(pres_alta_row)

        layout.addWidget(self._modo3_widget)
        self._modo3_widget.setVisible(False)

        # ── Guardar ──────────────────────────────────────────────────────
        btn_save = PrimaryPushButton("Guardar")
        btn_save.setFixedWidth(160)
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

        layout.addStretch()

    def _on_modo_changed(self, value: int) -> None:
        self._modo3_widget.setVisible(value == 3)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_current()

    def _load_current(self) -> None:
        try:
            data = BackendClient(self.BACKEND_URL).get("/cycle")
            secado = data["parameters"]["secado"]
            self._spin_modo.setValue(int(secado["modo"]["value"]))
            self._spin_tiempo.setValue(float(secado["tiempo_secado"]["value"]))
            self._spin_chaqueta.setValue(int(secado["presion_chaqueta_secado"]["value"]))
            self._spin_pres_baja.setValue(int(secado["presion_baja_secado"]["value"]))
            self._spin_pres_alta.setValue(int(secado["presion_alta_secado"]["value"]))
            self._on_modo_changed(self._spin_modo.value())
        except Exception:
            pass

    def _save(self) -> None:
        payload = {
            "modo":                    self._spin_modo.value(),
            "tiempo_secado":           self._spin_tiempo.value(),
            "presion_chaqueta_secado": self._spin_chaqueta.value(),
            "presion_baja_secado":     self._spin_pres_baja.value(),
            "presion_alta_secado":     self._spin_pres_alta.value(),
        }
        try:
            BackendClient(self.BACKEND_URL).patch("/cycle/parameters", payload)
            InfoBar.success(
                title="Guardado",
                content=f"Configuración de secado actualizada",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            InfoBar.error(
                title="Error al guardar",
                content=detail,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
        except Exception:
            InfoBar.warning(
                title="Sin conexión",
                content="No se pudo conectar al backend",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
