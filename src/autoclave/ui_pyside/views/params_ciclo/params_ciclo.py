# src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from autoclave.services.domain.logging.cycle_params_audit import CycleParamsAuditDB

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""

# (label visible, clave interna usada en _build_tab_grid)
_TABS = [
    ("Pre-calentamiento", "precalentamiento"),
    ("Purga",             "purga"),
    ("Crear pulso",       "prevacio"),
    ("Calentamiento",     "calentamiento_main"),
    ("Estabilización",    "calentamiento_estab"),
    ("Esterilización",    "esterilizacion"),
    ("Escape",            "descompresion"),
    ("Secado",            "secado"),
    ("Finalización",      "finalizacion"),
    ("Global",            "globals"),
]

# Filtros para la sección "calentamiento" que se comparte entre dos pestañas
_CAL_MAIN_KEYS  = {
    "temperatura_calentamiento", "tasa_calentamiento",
    "timeout_calentamiento", "rango_presion_calentamiento",
}
_CAL_ESTAB_KEYS = {
    "tiempo_estable_preesterilizacion", "rango_temp_estabilizacion",
    "timeout_recuperacion_estabilizacion", "presion_add_calentamiento",
}


class _ParamCard(QFrame):
    """Stub — se implementa en Task 4."""
    def __init__(self, display_name, param_meta, factory_value, cycle,
                 fase, path, audit_db, is_readonly=False):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(display_name))
        self.setMinimumSize(155, 80)
        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )


class ParametrosCicloView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._audit_db = CycleParamsAuditDB()
        self._cycles: dict = {}   # cycle_id → Cycle

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ── Header ─────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("admin_menu"))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)

        lbl_title = QLabel("PARÁMETROS DEL CICLO")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl_title)
        hdr.addSpacing(16)

        self._combo = QComboBox()
        self._combo.setFont(QFont("Segoe UI", 11))
        self._combo.setMinimumWidth(200)
        self._combo.setStyleSheet(
            "QComboBox { border: 1.5px solid #e8eaed; border-radius: 8px; padding: 4px 10px; }"
        )
        self._combo.currentIndexChanged.connect(self._on_cycle_changed)
        hdr.addWidget(self._combo)
        hdr.addStretch()
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        # ── Tabs ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab { padding: 6px 12px; font-size: 12px; }"
            "QTabBar::tab:selected { font-weight: bold; color: #2563eb; }"
        )
        for label, _ in _TABS:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._tabs.addTab(scroll, label)
        root.addWidget(self._tabs, stretch=1)

    # ── Ciclo de vida ────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reload_cycles()

    def _reload_cycles(self) -> None:
        try:
            from autoclave.core.cycle_manager import CycleManager
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
                self._load_cycle(user_cycles[0])
        except Exception:
            pass

    def _on_cycle_changed(self, idx: int) -> None:
        cycle_id = self._combo.itemData(idx)
        cycle = self._cycles.get(cycle_id)
        if cycle:
            self._load_cycle(cycle)

    def _load_cycle(self, cycle) -> None:
        factory_params = _load_factory_params(cycle._path)
        for tab_idx, (_, tab_key) in enumerate(_TABS):
            gw = _build_tab_grid(cycle, factory_params, tab_key, self._audit_db)
            scroll: QScrollArea = self._tabs.widget(tab_idx)
            scroll.setWidget(gw)


# ── Helpers de módulo ────────────────────────────────────────────────────

import json
from pathlib import Path


def _load_factory_params(user_cycle_path: str) -> dict:
    user_p = Path(user_cycle_path)
    factory_p = user_p.parent.parent / "factory" / user_p.name
    if factory_p.exists():
        with open(factory_p, "r", encoding="utf-8") as f:
            return json.load(f).get("parameters", {})
    return {}


def _iter_section(section: dict, filter_keys=None):
    """Yield (flat_name, param_meta) para todos los parámetros hoja de una sección."""
    for key, val in section.items():
        if isinstance(val, dict) and "value" in val:
            if filter_keys is None or key in filter_keys:
                yield key, val
        elif isinstance(val, dict):
            for sub_key, sub_val in val.items():
                if isinstance(sub_val, dict) and "value" in sub_val:
                    flat = f"{key} — {sub_key}"
                    if filter_keys is None or flat in filter_keys:
                        yield flat, sub_val


def _get_factory_value(factory_section: dict, flat_name: str):
    if " — " in flat_name:
        keys = flat_name.split(" — ")
        node = factory_section
        for k in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(k, {})
        return node.get("value") if isinstance(node, dict) else None
    return factory_section.get(flat_name, {}).get("value")


def _format_param_name(raw: str) -> str:
    return raw.replace("_", " ").replace(" — ", " / ").capitalize()


def _build_tab_grid(cycle, factory_params: dict, tab_key: str, audit_db) -> QWidget:
    if tab_key == "calentamiento_main":
        fase, filter_keys = "calentamiento", _CAL_MAIN_KEYS
    elif tab_key == "calentamiento_estab":
        fase, filter_keys = "calentamiento", _CAL_ESTAB_KEYS
    else:
        fase, filter_keys = tab_key, None

    is_factory = getattr(cycle, "source", "user") == "factory"
    section = cycle.parameters.get(fase, {})
    factory_section = factory_params.get(fase, {})

    gw = QWidget()
    grid = QGridLayout(gw)
    grid.setSpacing(10)
    grid.setContentsMargins(8, 8, 8, 8)
    grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    cards = []
    for flat_name, param_meta in _iter_section(section, filter_keys):
        path = flat_name.split(" — ") if " — " in flat_name else [flat_name]
        factory_val = _get_factory_value(factory_section, flat_name)
        card = _ParamCard(
            display_name=_format_param_name(flat_name),
            param_meta=param_meta,
            factory_value=factory_val,
            cycle=cycle,
            fase=fase,
            path=path,
            audit_db=audit_db,
            is_readonly=is_factory,
        )
        cards.append(card)

    if not cards:
        lbl = QLabel("Sin parámetros configurados")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #9ca3af; font-size: 13px;")
        grid.addWidget(lbl, 0, 0)
    else:
        for i, card in enumerate(cards):
            grid.addWidget(card, *divmod(i, 3))

    return gw
