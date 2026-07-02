# Parámetros del Ciclo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la vista de Parámetros del Ciclo con 10 pestañas (una por fase), tarjetas clicables de solo lectura y diálogo de edición con auditoría en SQLite.

**Architecture:** `CycleParamsAuditDB` maneja la tabla SQLite de auditoría. `ParametrosCicloView` carga ciclos de usuario via `CycleManager` directo a disco, muestra un `QTabWidget` de 10 pestañas con `_ParamCard` (read-only, click abre diálogo). `_ParamEditDialog` edita el valor, escribe el JSON y registra en auditoría.

**Tech Stack:** Python 3.14, PySide6, qfluentwidgets, SQLite (sqlite3 stdlib), JSON stdlib.

## Global Constraints

- UI: PySide6 + qfluentwidgets, pantalla fullscreen
- Tests: archivo único en `tests/`, imports directos `from autoclave.xxx`
- Solo se editan ciclos en `cycles/user/` — factory es intocable
- La BD SQLite vive en `data/autoclave.db`; `_PROJECT_ROOT = Path(__file__).resolve().parents[5]`
- Guardar con `json.dump(..., ensure_ascii=False, indent=4)`
- No usar `presion_purga` en parámetros de Purga — ese campo está en el JSON pero `PurgaFase` no lo usa

---

## File Map

| Acción   | Archivo |
|----------|---------|
| Crear    | `src/autoclave/services/domain/logging/cycle_params_audit.py` |
| Crear    | `tests/test_cycle_params_audit.py` |
| Crear    | `src/autoclave/ui_pyside/views/params_ciclo/__init__.py` |
| Crear    | `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py` |
| Modificar | `src/autoclave/ui_pyside/main_window.py` |
| Modificar | `src/autoclave/ui_pyside/views/admin_menu.py` |
| Modificar | `src/autoclave/cycles/factory/instrumental_134.json` |
| Modificar | `src/autoclave/cycles/factory/bowe_dick.json` |
| Modificar | `src/autoclave/cycles/user/instrumental_134.json` |
| Modificar | `src/autoclave/cycles/user/bowe_dick.json` |

---

## Task 1: CycleParamsAuditDB

**Files:**
- Create: `src/autoclave/services/domain/logging/cycle_params_audit.py`
- Test: `tests/test_cycle_params_audit.py`

**Interfaces:**
- Produces:
  ```python
  class CycleParamsAuditDB:
      def __init__(self, db_path: Path = _DB_DEFAULT): ...
      def log_change(self, cycle_id: str, fase: str, param: str,
                     valor_anterior, valor_nuevo, usuario: str) -> None: ...
      def get_last_change(self, cycle_id: str, fase: str, param: str) -> dict | None:
          # returns {"usuario": str, "timestamp": str} or None
  ```

- [ ] **Step 1: Escribir los 3 tests que fallarán**

```python
# tests/test_cycle_params_audit.py
import pytest
from autoclave.services.domain.logging.cycle_params_audit import CycleParamsAuditDB


@pytest.fixture
def db(tmp_path):
    return CycleParamsAuditDB(db_path=tmp_path / "test.db")


def test_get_last_change_returns_none_when_no_history(db):
    assert db.get_last_change("c1", "purga", "tiempo_purga") is None


def test_log_and_retrieve_last_change(db):
    db.log_change("c1", "purga", "tiempo_purga", 0, 5, "admin")
    result = db.get_last_change("c1", "purga", "tiempo_purga")
    assert result is not None
    assert result["usuario"] == "admin"
    assert len(result["timestamp"]) == 16   # "YYYY-MM-DD HH:MM"


def test_get_last_change_returns_most_recent(db):
    db.log_change("c1", "purga", "tiempo_purga", 0, 3, "user1")
    db.log_change("c1", "purga", "tiempo_purga", 3, 7, "user2")
    assert db.get_last_change("c1", "purga", "tiempo_purga")["usuario"] == "user2"
```

- [ ] **Step 2: Ejecutar para verificar que fallan**

```
pytest tests/test_cycle_params_audit.py -v
```
Esperado: `ModuleNotFoundError` o `ImportError`.

- [ ] **Step 3: Implementar CycleParamsAuditDB**

```python
# src/autoclave/services/domain/logging/cycle_params_audit.py
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DB_DEFAULT   = _PROJECT_ROOT / "data" / "autoclave.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cycle_params_audit (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id       TEXT NOT NULL,
    fase           TEXT NOT NULL,
    param          TEXT NOT NULL,
    valor_anterior TEXT,
    valor_nuevo    TEXT NOT NULL,
    usuario        TEXT NOT NULL,
    timestamp      TEXT NOT NULL
);
"""


class CycleParamsAuditDB:
    def __init__(self, db_path: Path = _DB_DEFAULT):
        self._db_path = db_path
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)

    def log_change(
        self,
        cycle_id: str,
        fase: str,
        param: str,
        valor_anterior,
        valor_nuevo,
        usuario: str,
    ) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO cycle_params_audit "
                "(cycle_id, fase, param, valor_anterior, valor_nuevo, usuario, timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (cycle_id, fase, param, str(valor_anterior), str(valor_nuevo), usuario, ts),
            )

    def get_last_change(self, cycle_id: str, fase: str, param: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT usuario, timestamp FROM cycle_params_audit "
                "WHERE cycle_id=? AND fase=? AND param=? "
                "ORDER BY timestamp DESC LIMIT 1",
                (cycle_id, fase, param),
            ).fetchone()
        return {"usuario": row[0], "timestamp": row[1]} if row else None
```

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```
pytest tests/test_cycle_params_audit.py -v
```
Esperado: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/services/domain/logging/cycle_params_audit.py tests/test_cycle_params_audit.py
git commit -m "feat: CycleParamsAuditDB — tabla SQLite de auditoría de parámetros"
```

---

## Task 2: Actualizar JSONs de ciclo

**Files:**
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`
- Modify: `src/autoclave/cycles/user/instrumental_134.json`
- Modify: `src/autoclave/cycles/user/bowe_dick.json`

**Interfaces:**
- Consumes: nada
- Produces: los 4 JSONs con sección `"finalizacion"` y campo `"presion_add_calentamiento"` en `"calentamiento"`

- [ ] **Step 1: Agregar `presion_add_calentamiento` en sección `calentamiento` de los 4 JSONs**

En cada archivo, dentro de `"calentamiento": { ... }`, agregar al final (antes del `}`):

```json
"presion_add_calentamiento": { "value": 9.0, "type": "float", "unit": "kPa", "min": 0, "max": 50 }
```

Los 4 archivos afectados:
- `src/autoclave/cycles/factory/instrumental_134.json`
- `src/autoclave/cycles/factory/bowe_dick.json`
- `src/autoclave/cycles/user/instrumental_134.json`
- `src/autoclave/cycles/user/bowe_dick.json`

- [ ] **Step 2: Agregar sección `finalizacion` en los 4 JSONs**

En cada archivo, dentro de `"parameters": { ... }`, agregar al final (antes del `}` que cierra `parameters`):

```json
"finalizacion": {
    "tiempo_espera_apertura": { "value": 60,   "type": "int",   "unit": "seg", "min": 0, "max": 3600 },
    "temp_max_apertura":      { "value": 80.0, "type": "float", "unit": "°C",  "min": 0, "max": 150  },
    "timeout_temperatura":    { "value": 30,   "type": "int",   "unit": "min", "min": 1, "max": 120  },
    "apertura_automatica":    { "value": false, "type": "bool",  "unit": ""                           }
}
```

- [ ] **Step 3: Verificar que los JSONs cargan correctamente**

```
python -c "
from autoclave.core.cycle_manager import CycleManager
cm = CycleManager()
cm.load_all_cycles()
c = cm.cycles['134_instrumental']
print('presion_add:', c.get_param('calentamiento', 'presion_add_calentamiento'))
print('finalizacion apertura:', c.get_param('finalizacion', 'tiempo_espera_apertura'))
print('finalizacion auto:', c.get_param('finalizacion', 'apertura_automatica'))
"
```
Esperado:
```
presion_add: 9.0
finalizacion apertura: 60
finalizacion auto: False
```

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/cycles/
git commit -m "feat: agregar sección finalizacion y presion_add_calentamiento a JSONs de ciclo"
```

---

## Task 3: ParametrosCicloView — esqueleto + integración

**Files:**
- Create: `src/autoclave/ui_pyside/views/params_ciclo/__init__.py`
- Create: `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`
- Modify: `src/autoclave/ui_pyside/views/admin_menu.py`

**Interfaces:**
- Consumes: `nav_callback: Callable[[str], None]` (igual que todas las vistas)
- Produces: `ParametrosCicloView(nav_callback)` registrado en `main_window.py` con clave `"params_ciclo"`

- [ ] **Step 1: Crear `__init__.py` vacío**

```python
# src/autoclave/ui_pyside/views/params_ciclo/__init__.py
```

- [ ] **Step 2: Crear el esqueleto de `params_ciclo.py` con tabs vacíos**

```python
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
```

- [ ] **Step 3: Agregar helpers de módulo al final del mismo archivo**

Agregar justo antes del final del archivo `params_ciclo.py`:

```python
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
```

> **Nota:** `_ParamCard` se definirá en Task 4. Por ahora el archivo compilará una vez que se defina el stub vacío en el Step 4 abajo.

- [ ] **Step 4: Agregar stub `_ParamCard` temporal para que el archivo no falle al importarse**

Al inicio del archivo `params_ciclo.py`, justo después de los imports, agregar:

```python
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
```

- [ ] **Step 5: Registrar la vista en `main_window.py`**

En `main_window.py`, en la zona de imports de vistas, agregar:
```python
from autoclave.ui_pyside.views.params_ciclo.params_ciclo import ParametrosCicloView
```

En `__init__`, después de `self._io_do = SalidasDigitalesView(...)`:
```python
self._params_ciclo = ParametrosCicloView(nav_callback=self.navigate_to)
```

En el loop `for view in (...)`:
```python
for view in (self._home, self._secado, self._login,
             self._ciclos, self._admin_menu, self._io_menu,
             self._io_di, self._io_temp, self._io_pres, self._io_do,
             self._params_ciclo):
    self._stack.addWidget(view)
```

En `navigate_to`, dentro del dict `views`:
```python
"params_ciclo": self._params_ciclo,
```

- [ ] **Step 6: Conectar ruta en `admin_menu.py`**

En `admin_menu.py`, actualizar `_OPTION_ROUTES`:
```python
_OPTION_ROUTES = {
    "Parámetros del ciclo": "params_ciclo",
    "Entradas / Salidas":   "io_menu",
}
```

- [ ] **Step 7: Verificar que la app arranca y navega a la vista**

```
python -m autoclave.ui_pyside.app
```
Pasos:
1. Hacer login como admin
2. Ir a Admin → "Parámetros del ciclo"
3. Debe aparecer la vista con 10 pestañas y cards con stub ("Pre-calentamiento", "Purga", etc.)
4. El ComboBox muestra los ciclos de usuario disponibles

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/ui_pyside/views/params_ciclo/ src/autoclave/ui_pyside/main_window.py src/autoclave/ui_pyside/views/admin_menu.py
git commit -m "feat: ParametrosCicloView — esqueleto con 10 pestañas integrado en admin_menu"
```

---

## Task 4: _ParamCard — tarjetas read-only con hover y click

**Files:**
- Modify: `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`
  (reemplazar el stub `_ParamCard` por la implementación completa)

**Interfaces:**
- Consumes:
  - `_ParamEditDialog(display_name, param_meta, factory_value, cycle, fase, path, audit_db, parent)` — producido en Task 5
- Produces:
  - `_ParamCard.refresh(new_value)` — actualiza la tarjeta tras guardar

- [ ] **Step 1: Definir estilos de tarjeta**

Al principio del archivo `params_ciclo.py`, después de `_BTN_BACK`, agregar:

```python
_CARD_NORMAL = (
    "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
)
_CARD_HOVER = (
    "QFrame { background: #eff6ff; border-radius: 10px; border: 1.5px solid #2563eb; }"
)
_CARD_READONLY = (
    "QFrame { background: #f9fafb; border-radius: 10px; border: 1.5px solid #e8eaed; }"
)
```

- [ ] **Step 2: Reemplazar el stub `_ParamCard` por la implementación completa**

Eliminar el stub y colocar:

```python
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
        self._display_name = display_name
        self._param_meta   = param_meta
        self._factory_value = factory_value
        self._cycle        = cycle
        self._fase         = fase
        self._path         = path
        self._audit_db     = audit_db
        self._is_readonly  = is_readonly

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
        lbl_name.setStyleSheet("color: #6b7280; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel(self._render_value())
        self._lbl_value.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(self._lbl_value)

        if is_readonly:
            lbl_lock = QLabel("🔒")
            lbl_lock.setStyleSheet("border: none; font-size: 10px; color: #9ca3af;")
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
        from PySide6.QtWidgets import QDialog
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
```

> **Nota:** `_ParamEditDialog` se implementa en Task 5. Hasta entonces el clic no abrirá nada (el import fallará silenciosamente porque `_open_edit` es llamado por evento, no en importación).

Para evitar el crash en runtime, agregar al inicio de `_open_edit`:
```python
def _open_edit(self) -> None:
    try:
        from PySide6.QtWidgets import QDialog
        dlg = _ParamEditDialog(...)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh(self._param_meta["value"])
    except Exception:
        pass
```

- [ ] **Step 3: Verificar visualmente**

```
python -m autoclave.ui_pyside.app
```
Pasos:
1. Admin → Parámetros del ciclo
2. Las tarjetas muestran nombre del parámetro + valor + unidad
3. Hover sobre una tarjeta: borde azul
4. Cursor cambia a mano sobre tarjetas editables
5. Pestaña "Escape" (descompresion): las tarjetas anidadas (`modo_1 / timeout`, etc.) aparecen correctamente

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py
git commit -m "feat: _ParamCard — tarjetas read-only con hover azul y cursor de mano"
```

---

## Task 5: _ParamEditDialog — edición, guardado y auditoría

**Files:**
- Modify: `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`
  (agregar clase `_ParamEditDialog` y helper `_save_to_json`)

**Interfaces:**
- Consumes:
  - `CycleParamsAuditDB.log_change(...)` — Task 1
  - `CycleParamsAuditDB.get_last_change(...)` — Task 1
  - `SessionManager.is_logged_in()`, `SessionManager.current_user["nombre"]` — ya existe en `services/session_manager.py`
- Produces: `_ParamEditDialog(...)` completamente funcional

- [ ] **Step 1: Agregar helper `_save_to_json` al módulo**

Al final del bloque de helpers de módulo en `params_ciclo.py`, agregar:

```python
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
```

- [ ] **Step 2: Agregar imports adicionales necesarios**

En la zona de imports de `params_ciclo.py`, agregar:

```python
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
)
```

- [ ] **Step 3: Implementar `_ParamEditDialog`**

Agregar la clase después de `_ParamCard` en `params_ciclo.py`:

```python
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
```

- [ ] **Step 4: Actualizar `_open_edit` en `_ParamCard` para usar el import sin try/except**

Reemplazar el método `_open_edit` (con el try/except temporal de Task 4) por:

```python
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
```

- [ ] **Step 5: Verificar flujo completo**

```
python -m autoclave.ui_pyside.app
```
Pasos a verificar:
1. Admin → Parámetros del ciclo → pestaña "Purga"
2. Clic en tarjeta "Tiempo purga" → se abre diálogo
3. El diálogo muestra: valor actual, mínimo, máximo, valor por defecto (del factory), "Sin modificaciones previas"
4. Cambiar el valor → Guardar
5. La tarjeta se actualiza con el nuevo valor
6. Clic de nuevo en la misma tarjeta → el diálogo muestra el nombre del usuario logueado + timestamp

Verificar que el JSON se actualizó:
```
python -c "
from autoclave.core.cycle_manager import CycleManager
cm = CycleManager(); cm.load_all_cycles()
c = cm.cycles['134_instrumental']
print('tiempo_purga:', c.get_param('purga', 'tiempo_purga'))
"
```

- [ ] **Step 6: Verificar flujo de finalización**

1. Ir a pestaña "Finalización"
2. Se muestran 4 tarjetas: tiempo espera apertura, temp max apertura, timeout temperatura, apertura automática
3. La tarjeta "apertura automática" muestra "Sí"/"No" y su input es un checkbox

- [ ] **Step 7: Commit final**

```bash
git add src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py
git commit -m "feat: _ParamEditDialog — edición de parámetros con auditoría SQLite"
```
