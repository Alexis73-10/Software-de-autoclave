import logging
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
import requests

from autoclave.ui.service_ui.backend_client import BackendClient
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

_CARD = "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"

_ROLES = [("principal", "Principal"), ("referencia", "Referencia"), ("no_en_uso", "No en uso")]

_CANDIDATOS_SIEMPRE = ["temp_camara", "temp_ref"]


def _equipo_tiene_sonda_liquido() -> bool:
    try:
        from autoclave.installation import storage
        from autoclave.installation.equipment import get_capabilities
        if not storage.exists():
            return False
        profile = storage.load()
        return get_capabilities(profile.equipment_class).has_liquid_sensor
    except Exception:
        return False


class _SensorRoleRow(QFrame):
    def __init__(self, sensor_name: str, on_change: Callable[[str, str], None]):
        super().__init__()
        self.sensor_name = sensor_name
        self._on_change = on_change
        self.setStyleSheet(_CARD)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)

        lbl = QLabel(_format_name(sensor_name))
        lbl.setFont(QFont("Segoe UI", 12))
        lbl.setStyleSheet("border: none;")
        lay.addWidget(lbl)
        lay.addStretch()

        self._group = QButtonGroup(self)
        self._buttons: dict[str, QRadioButton] = {}
        for rol, label in _ROLES:
            rb = QRadioButton(label)
            self._group.addButton(rb)
            self._buttons[rol] = rb
            lay.addWidget(rb)
            rb.toggled.connect(lambda checked, r=rol: self._on_toggled(r, checked))

    def _on_toggled(self, rol: str, checked: bool) -> None:
        if checked:
            self._on_change(self.sensor_name, rol)

    def set_role(self, rol: str) -> None:
        btn = self._buttons.get(rol, self._buttons["no_en_uso"])
        btn.blockSignals(True)
        btn.setChecked(True)
        btn.blockSignals(False)

    def get_role(self) -> str:
        for rol, btn in self._buttons.items():
            if btn.isChecked():
                return rol
        return "no_en_uso"


class SensoresTemperaturaView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._cycles: dict = {}
        self._rows: dict[str, _SensorRoleRow] = {}
        self._cycle = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("params_ciclo_menu"))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)

        lbl_title = QLabel("SENSORES DE TEMPERATURA")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addSpacing(16)

        self._combo = QComboBox()
        self._combo.setFont(QFont("Segoe UI", 11))
        self._combo.setMinimumWidth(200)
        self._combo.currentIndexChanged.connect(self._on_cycle_changed)
        hdr.addWidget(self._combo)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setSpacing(8)
        self._rows_layout.addStretch(1)
        scroll.setWidget(self._rows_widget)
        root.addWidget(scroll, stretch=1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload_cycles()

    def _reload_cycles(self) -> None:
        try:
            from autoclave.core.managers.cycle_manager import CycleManager
            cm = CycleManager()
            cm.load_all_cycles()
            user_cycles = [
                c for c in cm.cycles.values()
                if getattr(c, "source", "user") == "user"
            ]
            self._cycles = {c.id: c for c in user_cycles}

            self._combo.blockSignals(True)
            self._combo.clear()
            for cycle in sorted(user_cycles, key=lambda c: c.name):
                self._combo.addItem(cycle.name, cycle.id)
            self._combo.blockSignals(False)

            if user_cycles:
                self._load_cycle(sorted(user_cycles, key=lambda c: c.name)[0])
        except Exception:
            _logger.exception("Error cargando ciclos de usuario")

    def _on_cycle_changed(self, idx: int) -> None:
        cycle_id = self._combo.itemData(idx)
        cycle = self._cycles.get(cycle_id)
        if cycle:
            self._load_cycle(cycle)

    def _candidatos(self) -> list[str]:
        candidatos = list(_CANDIDATOS_SIEMPRE)
        if _equipo_tiene_sonda_liquido():
            candidatos.insert(1, "temp_2_camara")
        return candidatos

    def _load_cycle(self, cycle) -> None:
        self._cycle = cycle
        for row in self._rows.values():
            row.setParent(None)
        self._rows.clear()

        for sensor in self._candidatos():
            row = _SensorRoleRow(sensor, on_change=self._on_role_changed)
            row.set_role(cycle.sensor_roles.get(sensor, "no_en_uso"))
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
            self._rows[sensor] = row

    def _on_role_changed(self, sensor: str, rol: str) -> None:
        if self._cycle is None:
            return

        if rol == "principal":
            for other_sensor, row in self._rows.items():
                if other_sensor != sensor and row.get_role() == "principal":
                    row.set_role("no_en_uso")
                    self._cycle.sensor_roles[other_sensor] = "no_en_uso"

        nuevos_roles = dict(self._cycle.sensor_roles)
        nuevos_roles[sensor] = rol

        try:
            self._client.patch("/cycle/sensor-roles", {
                "cycle_id": self._cycle.id,
                "sensor_roles": nuevos_roles,
            })
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar el rol:\n{detail}")
            return
        except requests.RequestException as e:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo contactar al backend, el cambio no se guardó:\n{e}"
            )
            return

        self._cycle.sensor_roles = nuevos_roles
