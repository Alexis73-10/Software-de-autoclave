# src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py
import logging
from collections.abc import Callable

_logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
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

_CARD_NORMAL = (
    "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
)
_CARD_HOVER = (
    "QFrame { background: #eff6ff; border-radius: 10px; border: 1.5px solid #2563eb; }"
)
_CARD_READONLY = (
    "QFrame { background: #f9fafb; border-radius: 10px; border: 1.5px solid #e8eaed; }"
)

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
    def __init__(
        self,
        display_name: str,
        param_meta: dict,
        factory_value,
        cycle,
        fase: str,
        path: list[str],
        audit_db,
        is_readonly: bool = False,
    ):
        super().__init__()
        self._display_name  = display_name
        self._param_meta    = param_meta
        self._factory_value = factory_value
        self._cycle         = cycle
        self._fase          = fase
        self._path          = path
        self._audit_db      = audit_db
        self._is_readonly   = is_readonly

        self.setStyleSheet(_CARD_READONLY if is_readonly else _CARD_NORMAL)
        self.setMinimumSize(155, 90)
        if not is_readonly:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)

        lbl_name = QLabel(display_name)
        lbl_name.setFont(QFont("Segoe UI", 9))
        lbl_name.setWordWrap(True)
        lbl_name.setStyleSheet("color: #6b7280; border: none; background: transparent;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel(self._render_value())
        self._lbl_value.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #1a2a3a; border: none; background: transparent;")
        lay.addWidget(self._lbl_value)

        if is_readonly:
            lbl_lock = QLabel("🔒")
            lbl_lock.setStyleSheet("border: none; font-size: 10px; color: #9ca3af; background: transparent;")
            lay.addWidget(lbl_lock)

    # ── helpers ──────────────────────────────────────────────────────────

    def _render_value(self) -> str:
        val  = self._param_meta.get("value")
        unit = self._param_meta.get("unit", "")
        if isinstance(val, bool):
            return "Sí" if val else "No"
        if isinstance(val, float):
            return f"{val:.1f} {unit}".strip()
        return f"{val} {unit}".strip()

    def refresh(self, new_value) -> None:
        self._param_meta["value"] = new_value
        self._lbl_value.setText(self._render_value())

    # ── eventos de mouse ─────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        if not self._is_readonly:
            self.setStyleSheet(_CARD_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(_CARD_READONLY if self._is_readonly else _CARD_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if not self._is_readonly and event.button() == Qt.MouseButton.LeftButton:
            self._open_edit()
        super().mousePressEvent(event)

    def _open_edit(self) -> None:
        dlg = _ParamEditDialog(
            display_name=self._display_name,
            param_meta=self._param_meta,
            factory_value=self._factory_value,
            cycle=self._cycle,
            fase=self._fase,
            path=self._path,
            audit_db=self._audit_db,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh(self._param_meta["value"])


class _ParamEditDialog(QDialog):
    def __init__(
        self,
        display_name: str,
        param_meta: dict,
        factory_value,
        cycle,
        fase: str,
        path: list[str],
        audit_db,
        parent: QWidget,
    ):
        super().__init__(parent)
        self.setWindowTitle("Editar parámetro")
        self.setMinimumWidth(420)
        self._cycle      = cycle
        self._fase       = fase
        self._path       = path
        self._audit_db   = audit_db
        self._param_meta = param_meta

        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 20, 24, 20)

        # ── Título ──────────────────────────────────────────────────────
        lbl_title = QLabel(display_name)
        lbl_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a2a3a;")
        lay.addWidget(lbl_title)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #e8eaed;")
        lay.addWidget(sep1)

        # ── Formulario ──────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        param_type  = param_meta.get("type", "int")
        unit        = param_meta.get("unit", "")
        current_val = param_meta.get("value")
        pmin        = param_meta.get("min", 0)
        pmax        = param_meta.get("max", 9999)
        suffix      = f"  {unit}" if unit else ""

        if param_type == "bool":
            self._input = QCheckBox()
            self._input.setChecked(bool(current_val))
        elif param_type == "float":
            self._input = QDoubleSpinBox()
            self._input.setDecimals(1)
            self._input.setMinimum(float(pmin))
            self._input.setMaximum(float(pmax))
            self._input.setValue(float(current_val or 0))
            self._input.setSuffix(suffix)
        else:
            self._input = QSpinBox()
            self._input.setMinimum(int(pmin))
            self._input.setMaximum(int(pmax))
            self._input.setValue(int(current_val or 0))
            self._input.setSuffix(suffix)

        form.addRow("Valor:", self._input)
        form.addRow("Mínimo:", QLabel(f"{pmin}{suffix}"))
        form.addRow("Máximo:", QLabel(f"{pmax}{suffix}"))

        fv_text = (
            f"{factory_value}{suffix}" if factory_value is not None else "—"
        )
        lbl_default = QLabel(fv_text)
        lbl_default.setStyleSheet("color: #6b7280;")
        form.addRow("Por defecto:", lbl_default)
        lay.addLayout(form)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #e8eaed;")
        lay.addWidget(sep2)

        # ── Auditoría ────────────────────────────────────────────────────
        audit_key = ".".join(path)
        last = audit_db.get_last_change(cycle.id, fase, audit_key)
        if last:
            audit_text = f"Última modificación:\n  {last['usuario']}  ·  {last['timestamp']}"
        else:
            audit_text = "Sin modificaciones previas"
        lbl_audit = QLabel(audit_text)
        lbl_audit.setStyleSheet("color: #6b7280; font-size: 12px;")
        lay.addWidget(lbl_audit)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #e8eaed;")
        lay.addWidget(sep3)

        # ── Botones ──────────────────────────────────────────────────────
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #f0f0f0; color: #333; border-radius: 8px;"
            " border: none; font-size: 13px; padding: 0 16px; }"
            "QPushButton:hover { background: #e0e0e0; }"
        )
        btn_cancel.clicked.connect(self.reject)

        self._btn_save = QPushButton("Guardar")
        self._btn_save.setFixedHeight(36)
        self._btn_save.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; border-radius: 8px;"
            " border: none; font-size: 13px; font-weight: bold; padding: 0 20px; }"
            "QPushButton:hover { background: #1d4ed8; }"
            "QPushButton:disabled { background: #93c5fd; }"
        )
        self._btn_save.clicked.connect(self._on_save)

        # Deshabilitar si no hay sesión activa
        try:
            from autoclave.ui_pyside.services.session_manager import SessionManager
            self._btn_save.setEnabled(SessionManager.is_logged_in())
        except Exception:
            self._btn_save.setEnabled(False)

        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addSpacing(8)
        btns.addWidget(self._btn_save)
        lay.addLayout(btns)

    # ── Guardar ──────────────────────────────────────────────────────────

    def _get_new_value(self):
        if isinstance(self._input, QCheckBox):
            return self._input.isChecked()
        return self._input.value()

    def _on_save(self) -> None:
        new_val = self._get_new_value()
        old_val = self._param_meta.get("value")

        # 1. Escribir JSON
        _save_to_json(self._cycle._path, self._fase, self._path, new_val)

        # 2. Actualizar en memoria
        node = self._cycle.parameters[self._fase]
        for key in self._path[:-1]:
            node = node[key]
        node[self._path[-1]]["value"] = new_val
        self._param_meta["value"] = new_val

        # 3. Registrar auditoría
        try:
            from autoclave.ui_pyside.services.session_manager import SessionManager
            user = (
                SessionManager.current_user.get("nombre", "Desconocido")
                if SessionManager.is_logged_in()
                else "Desconocido"
            )
        except Exception:
            user = "Desconocido"

        audit_key = ".".join(self._path)
        self._audit_db.log_change(
            self._cycle.id, self._fase, audit_key, old_val, new_val, user
        )

        self.accept()


class ParametrosCicloView(QWidget):
    def __init__(self, nav_callback: Callable[[str], None]) -> None:
        super().__init__()
        self._nav = nav_callback
        self._audit_db = CycleParamsAuditDB()
        self._cycles: dict = {}   # cycle_id → Cycle

        self.setObjectName("paramsCicloView")
        self.setStyleSheet("QWidget#paramsCicloView { background: #f3f4f6; }")

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
            "QTabWidget::pane { background: #f3f4f6; border: 1px solid #e8eaed; }"
            "QTabBar::tab { padding: 6px 12px; font-size: 12px; background: #e5e7eb;"
            " color: #374151; border-radius: 4px 4px 0 0; margin-right: 2px; }"
            "QTabBar::tab:selected { background: #f3f4f6; font-weight: bold; color: #2563eb; }"
            "QTabBar::tab:hover { background: #d1d5db; color: #111827; }"
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
                first = sorted(user_cycles, key=lambda c: c.name)[0]
                self._load_cycle(first)
        except Exception:
            _logger.exception("Error cargando ciclos de usuario")

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


def _save_to_json(cycle_path: str, fase: str, path: list[str], new_value) -> None:
    p = Path(cycle_path)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    node = data["parameters"][fase]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]]["value"] = new_value
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


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
    gw.setObjectName("tabGrid")
    gw.setStyleSheet("QWidget#tabGrid { background: #f3f4f6; }")
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
