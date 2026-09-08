import logging
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import requests

from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui_pyside.views.entrdas_salidas._io_base import _format_name
from autoclave.core.runtime.status import EstadoAutoclave

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


def _todos_los_sensores() -> list[str]:
    return list(EstadoAutoclave.map_temp.keys()) + list(EstadoAutoclave.map_pres.keys())


class EntradasExhibidasView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(_BACKEND_URL)
        self._cycles: dict = {}
        self._cycle = None
        self._combos: list[QComboBox] = []

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

        lbl_title = QLabel("ENTRADAS EXHIBIDAS")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addSpacing(16)

        self._combo_ciclo = QComboBox()
        self._combo_ciclo.setFont(QFont("Segoe UI", 11))
        self._combo_ciclo.setMinimumWidth(200)
        self._combo_ciclo.currentIndexChanged.connect(self._on_cycle_changed)
        hdr.addWidget(self._combo_ciclo)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        root.addSpacing(8)

        for i in range(3):
            fila = QFrame()
            fila.setStyleSheet(_CARD)
            fl = QHBoxLayout(fila)
            fl.setContentsMargins(16, 10, 16, 10)

            lbl = QLabel(f"Casilla {i + 1}")
            lbl.setFont(QFont("Segoe UI", 12))
            lbl.setStyleSheet("border: none;")
            fl.addWidget(lbl)
            fl.addStretch()

            combo = QComboBox()
            combo.addItem("— Vacío —", None)
            for sensor in _todos_los_sensores():
                combo.addItem(_format_name(sensor), sensor)
            combo.currentIndexChanged.connect(lambda idx, slot=i: self._on_slot_changed(slot, idx))
            fl.addWidget(combo)

            self._combos.append(combo)
            root.addWidget(fila)

        root.addStretch(1)

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

            self._combo_ciclo.blockSignals(True)
            self._combo_ciclo.clear()
            for cycle in sorted(user_cycles, key=lambda c: c.name):
                self._combo_ciclo.addItem(cycle.name, cycle.id)
            self._combo_ciclo.blockSignals(False)

            if user_cycles:
                self._load_cycle(sorted(user_cycles, key=lambda c: c.name)[0])
        except Exception:
            _logger.exception("Error cargando ciclos de usuario")

    def _on_cycle_changed(self, idx: int) -> None:
        cycle_id = self._combo_ciclo.itemData(idx)
        cycle = self._cycles.get(cycle_id)
        if cycle:
            self._load_cycle(cycle)

    def _load_cycle(self, cycle) -> None:
        self._cycle = cycle
        slots = list(cycle.display_slots) + [None, None, None]
        for i, combo in enumerate(self._combos):
            combo.blockSignals(True)
            idx = combo.findData(slots[i])
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _on_slot_changed(self, slot_idx: int, combo_idx: int) -> None:
        if self._cycle is None:
            return

        sensor = self._combos[slot_idx].itemData(combo_idx)
        slots_previos = list(self._cycle.display_slots) + [None, None, None]
        sensor_anterior = slots_previos[:3][slot_idx]
        slots = list(self._cycle.display_slots) + [None, None, None]
        slots = slots[:3]
        slots[slot_idx] = sensor

        def _revertir_combo() -> None:
            combo = self._combos[slot_idx]
            combo.blockSignals(True)
            idx = combo.findData(sensor_anterior)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        try:
            self._client.patch("/cycle/display-slots", {
                "cycle_id": self._cycle.id,
                "display_slots": slots,
            })
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar la entrada exhibida:\n{detail}")
            _revertir_combo()
            return
        except requests.RequestException as e:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo contactar al backend, el cambio no se guardó:\n{e}"
            )
            _revertir_combo()
            return

        self._cycle.display_slots = slots
