import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
import requests

from autoclave.ui.service_ui.backend_client import BackendClient

logger = logging.getLogger(__name__)

_BACKEND_URL = "http://localhost:8000"


class AudioConfigView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._cargando = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        title = QLabel("Anuncios por voz")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self._chk_enabled = QCheckBox("Anuncios por voz habilitados")
        self._chk_enabled.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._chk_enabled)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volumen"))
        self._slider_volume = QSlider(Qt.Orientation.Horizontal)
        self._slider_volume.setRange(0, 100)
        self._slider_volume.sliderReleased.connect(self._on_volume_released)
        vol_row.addWidget(self._slider_volume, stretch=1)
        self._lbl_volume = QLabel("--")
        self._slider_volume.valueChanged.connect(lambda v: self._lbl_volume.setText(str(v)))
        vol_row.addWidget(self._lbl_volume)
        layout.addLayout(vol_row)

        self._lbl_available = QLabel("Estado del dispositivo: —")
        layout.addWidget(self._lbl_available)

        btn_row = QHBoxLayout()
        btn_test = QPushButton("Probar")
        btn_test.clicked.connect(self._on_test_clicked)
        btn_row.addWidget(btn_test)

        btn_back = QPushButton("Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        btn_row.addWidget(btn_back)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(5000)
        self._refresh_status()

    def _refresh_status(self) -> None:
        try:
            data = self._client.get("/audio/config")
        except requests.RequestException:
            self._lbl_available.setText("Estado del dispositivo: sin conexión con el backend")
            return

        self._cargando = True
        self._chk_enabled.setChecked(bool(data.get("enabled", True)))
        self._slider_volume.setValue(int(data.get("volume", 80)))
        self._lbl_volume.setText(str(int(data.get("volume", 80))))
        self._cargando = False

        disponible = bool(data.get("available", True))
        self._lbl_available.setText(
            "Estado del dispositivo: disponible" if disponible
            else "Estado del dispositivo: NO disponible"
        )

    def _on_enabled_changed(self, _state) -> None:
        if self._cargando:
            return
        try:
            self._client.patch("/audio/config", {"enabled": self._chk_enabled.isChecked()})
        except requests.RequestException as e:
            logger.warning("No se pudo actualizar 'enabled' de audio: %s", e)

    def _on_volume_released(self) -> None:
        if self._cargando:
            return
        try:
            self._client.patch("/audio/config", {"volume": self._slider_volume.value()})
        except requests.RequestException as e:
            logger.warning("No se pudo actualizar 'volume' de audio: %s", e)

    def _on_test_clicked(self) -> None:
        try:
            self._client.post("/audio/test")
        except requests.RequestException as e:
            logger.warning("No se pudo probar el audio: %s", e)
