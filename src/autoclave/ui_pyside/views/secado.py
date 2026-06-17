import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    DoubleSpinBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
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

        # Barra superior con botón volver
        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("Tiempo de Secado"))
        desc = BodyLabel("Ajusta el tiempo de secado para el ciclo activo (0 – 120 min).")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # SpinBox
        spin_row = QHBoxLayout()
        spin_row.addWidget(BodyLabel("Tiempo de secado (min):"))
        self._spin = DoubleSpinBox()
        self._spin.setRange(0.0, 120.0)
        self._spin.setSingleStep(0.5)
        self._spin.setDecimals(1)
        self._spin.setFixedWidth(140)
        spin_row.addWidget(self._spin)
        spin_row.addStretch()
        layout.addLayout(spin_row)

        btn_save = PrimaryPushButton("Guardar")
        btn_save.setFixedWidth(160)
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

        layout.addStretch()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_current()

    def _load_current(self) -> None:
        try:
            r = requests.get(f"{self.BACKEND_URL}/cycle", timeout=1.5)
            r.raise_for_status()
            value = (
                r.json()["parameters"]["esterilizacion"]["tiempo_secado"]["value"]
            )
            self._spin.setValue(float(value))
        except Exception:
            pass  # mantiene valor actual si el backend no está disponible

    def _save(self) -> None:
        value = self._spin.value()
        try:
            r = requests.patch(
                f"{self.BACKEND_URL}/cycle/parameters",
                json={"tiempo_secado": value},
                timeout=2.0,
            )
            r.raise_for_status()
            InfoBar.success(
                title="Guardado",
                content=f"Tiempo de secado actualizado a {value:.1f} min",
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
