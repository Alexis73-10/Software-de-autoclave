# Entradas / Salidas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar el submenú "Entradas / Salidas" al panel de administración con 4 vistas de diagnóstico: entradas digitales (14 DI), temperaturas (6), presiones (4), y salidas digitales (24 DO con modo prueba).

**Architecture:** Nueva vista `EntradasSalidasMenuView` actúa como hub de navegación (misma card blanca que `AdminMenuView`). Tres vistas de monitoreo heredan de `_MonitorBase` (poll 2 s con QTimer, showEvent/hideEvent). `SalidasDigitalesView` implementa la lógica de modo prueba directamente. Todos los datos vienen de `GET /status` del backend FastAPI; el modo prueba usa dos endpoints nuevos.

**Tech Stack:** PySide6, qfluentwidgets, FastAPI/Pydantic, requests, pytest, fastapi.testclient

## Global Constraints

- Python 3.14; PySide6; backend en `http://localhost:8000`
- Importar `BackendClient` desde `autoclave.ui.service_ui.backend_client`
- Navegación vía `nav_callback` string, igual que todas las vistas existentes
- Datos de sensores en `status["sensors"]["digital_inputs"]`, `status["sensors"]["digital_outputs"]`, `status["sensors"]["temperature"]`, `status["sensors"]["pressure"]`
- Nombres de canales snake_case → legible con `.replace("_", " ").title()`
- Sin comentarios salvo que el WHY no sea obvio; sin imports no usados

---

## File Map

| Acción | Archivo | Responsabilidad |
|--------|---------|----------------|
| Create | `src/autoclave/ui_pyside/views/_io_base.py` | `_format_name()`, `_IoCard` base, `_MonitorBase` (timer + poll) |
| Create | `src/autoclave/ui_pyside/views/io_menu.py` | `EntradasSalidasMenuView` — 4 botones de navegación |
| Create | `src/autoclave/ui_pyside/views/io_di.py` | `EntradasDigitalesView` — 14 DI cards |
| Create | `src/autoclave/ui_pyside/views/io_temp.py` | `TemperaturasView` — 6 sensores temp |
| Create | `src/autoclave/ui_pyside/views/io_pres.py` | `PresionesView` — 4 sensores presión |
| Create | `src/autoclave/ui_pyside/views/io_do.py` | `SalidasDigitalesView` — 24 DO + modo prueba |
| Modify | `src/autoclave/backend/server.py` | 2 endpoints: POST /io/test/reset_all, PATCH /io/test/output/{name} |
| Modify | `src/autoclave/ui_pyside/main_window.py` | Registrar 5 vistas nuevas + navigate_to() |
| Modify | `src/autoclave/ui_pyside/views/admin_menu.py` | Cablear "Entradas / Salidas" → "io_menu" |
| Create | `tests/test_io_endpoints.py` | Tests FastAPI endpoints IO |
| Create | `tests/conftest_pyside.py` | Fixture QApplication para tests PySide6 |
| Create | `tests/test_io_views.py` | Tests unitarios widgets IO |

---

## Task 1: Backend — endpoints IO test

**Files:**
- Modify: `src/autoclave/backend/server.py`
- Create: `tests/test_io_endpoints.py`

**Interfaces:**
- Produces: `POST /io/test/reset_all → {"ok": True}`, `PATCH /io/test/output/{name} → {"ok": True, "name": str, "value": bool}`

- [ ] **Step 1: Escribir tests que fallan**

Crear `tests/test_io_endpoints.py`:

```python
import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module")
def io_client():
    mock_setdo = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.setdo = mock_setdo

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_setdo


def test_reset_all_devuelve_ok(io_client):
    client, mock_setdo = io_client
    resp = client.post("/io/test/reset_all")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_setdo.reset_all_outputs.assert_called_once()


def test_set_output_activa_vapor_generador(io_client):
    client, mock_setdo = io_client
    mock_setdo.set_output.reset_mock()
    resp = client.patch("/io/test/output/vapor_generador", json={"value": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"ok": True, "name": "vapor_generador", "value": True}
    mock_setdo.set_output.assert_called_once_with(0, True)


def test_set_output_apaga_vapor_caldera(io_client):
    client, mock_setdo = io_client
    mock_setdo.set_output.reset_mock()
    resp = client.patch("/io/test/output/vapor_caldera", json={"value": False})
    assert resp.status_code == 200
    mock_setdo.set_output.assert_called_once_with(1, False)


def test_set_output_404_para_nombre_invalido(io_client):
    client, _ = io_client
    resp = client.patch("/io/test/output/no_existe", json={"value": True})
    assert resp.status_code == 404


def test_reset_all_se_puede_llamar_varias_veces(io_client):
    client, mock_setdo = io_client
    mock_setdo.reset_all_outputs.reset_mock()
    client.post("/io/test/reset_all")
    client.post("/io/test/reset_all")
    assert mock_setdo.reset_all_outputs.call_count == 2
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_endpoints.py -v
```

Esperado: `FAILED` con `404 Not Found` o `ImportError`.

- [ ] **Step 3: Implementar endpoints en server.py**

Agregar al final de `src/autoclave/backend/server.py`, antes del último bloque:

```python
from pydantic import BaseModel
from autoclave.core.status import EstadoAutoclave


class _OutputSetBody(BaseModel):
    value: bool


@app.post("/io/test/reset_all")
def io_test_reset_all():
    context.setdo.reset_all_outputs()
    return {"ok": True}


@app.patch("/io/test/output/{name}")
def io_test_set_output(name: str, body: _OutputSetBody):
    if name not in EstadoAutoclave.map_do:
        raise HTTPException(status_code=404, detail=f"Output '{name}' no encontrado")
    index = EstadoAutoclave.map_do[name]
    context.setdo.set_output(index, body.value)
    return {"ok": True, "name": name, "value": body.value}
```

> Nota: `pydantic` y `EstadoAutoclave` se importan dentro del bloque de endpoints nuevos para no mezclar con los imports existentes en la cabecera. Mueve los imports al top del archivo si el linter lo exige.

- [ ] **Step 4: Correr y verificar que pasan**

```
pytest tests/test_io_endpoints.py -v
```

Esperado: 5 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/backend/server.py tests/test_io_endpoints.py
git commit -m "feat: endpoints POST /io/test/reset_all y PATCH /io/test/output/{name}"
```

---

## Task 2: Shared base — `_io_base.py`

**Files:**
- Create: `src/autoclave/ui_pyside/views/_io_base.py`
- Create: `tests/test_io_views.py` (fixture QApp + tests de `_format_name` y `_MonitorBase`)

**Interfaces:**
- Produces: `_format_name(raw: str) -> str`, `_MonitorBase(title, back_target, nav_callback)` con `showEvent/hideEvent/timer/grid`

- [ ] **Step 1: Escribir tests que fallan**

Crear `tests/test_io_views.py`:

```python
import sys
import pytest

# QApplication debe existir antes de crear cualquier widget
@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_format_name_convierte_snake_case():
    from autoclave.ui_pyside.views._io_base import _format_name
    assert _format_name("aire_comprimido") == "Aire Comprimido"
    assert _format_name("pres_camara") == "Pres Camara"
    assert _format_name("buzer_alarma") == "Buzer Alarma"


def test_monitor_base_instancia_sin_crash():
    from autoclave.ui_pyside.views._io_base import _MonitorBase
    view = _MonitorBase("TEST", "home", lambda x: None)
    assert view is not None


def test_monitor_base_timer_arranca_en_show():
    from autoclave.ui_pyside.views._io_base import _MonitorBase
    from unittest.mock import patch

    view = _MonitorBase("TEST", "home", lambda x: None)
    with patch.object(view, "_refresh") as mock_refresh:
        view.show()
        assert view._timer.isActive()
        view.hide()
        assert not view._timer.isActive()
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_views.py -v
```

Esperado: `ModuleNotFoundError: autoclave.ui_pyside.views._io_base`

- [ ] **Step 3: Crear `_io_base.py`**

Crear `src/autoclave/ui_pyside/views/_io_base.py`:

```python
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from autoclave.ui.service_ui.backend_client import BackendClient

_BACKEND_URL = "http://localhost:8000"

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""


def _format_name(raw: str) -> str:
    return raw.replace("_", " ").title()


class _MonitorBase(QWidget):
    POLL_MS = 2000
    BACKEND_URL = _BACKEND_URL

    def __init__(self, title: str, back_target: str, nav_callback):
        super().__init__()
        self._nav = nav_callback
        self._client = BackendClient(self.BACKEND_URL)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav(back_target))
        hdr.addWidget(btn_back)
        hdr.addSpacing(8)
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #1a2a3a;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        self._lbl_conn = QLabel("○ Sin datos")
        self._lbl_conn.setStyleSheet("color: #999; font-size: 12px;")
        hdr.addWidget(self._lbl_conn)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(12)
        scroll.setWidget(self._grid_widget)
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

    def _refresh(self) -> None:
        try:
            status = self._client.get_status()
            self._update_cards(status)
            self._lbl_conn.setText("● Conectado")
            self._lbl_conn.setStyleSheet("color: #22c55e; font-size: 12px;")
        except Exception:
            self._lbl_conn.setText("○ Sin datos")
            self._lbl_conn.setStyleSheet("color: #ef4444; font-size: 12px;")

    def _update_cards(self, status: dict) -> None:
        raise NotImplementedError
```

- [ ] **Step 4: Correr y verificar que pasan**

```
pytest tests/test_io_views.py -v
```

Esperado: 3 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui_pyside/views/_io_base.py tests/test_io_views.py
git commit -m "feat: base _MonitorBase para vistas de monitoreo IO"
```

---

## Task 3: `EntradasSalidasMenuView` + wiring completo

**Files:**
- Create: `src/autoclave/ui_pyside/views/io_menu.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`
- Modify: `src/autoclave/ui_pyside/views/admin_menu.py`

**Interfaces:**
- Consumes: `nav_callback` string → "io_di", "io_temp", "io_pres", "io_do"
- Produces: vista registrada en stack como `"io_menu"`

- [ ] **Step 1: Agregar test de navegación**

En `tests/test_io_views.py`, añadir al final:

```python
def test_io_menu_instancia_sin_crash():
    from autoclave.ui_pyside.views.io_menu import EntradasSalidasMenuView
    nav_calls = []
    view = EntradasSalidasMenuView(nav_callback=nav_calls.append)
    assert view is not None


def test_io_menu_tiene_cuatro_botones():
    from autoclave.ui_pyside.views.io_menu import _IO_OPTIONS
    assert len(_IO_OPTIONS) == 4
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_views.py::test_io_menu_instancia_sin_crash tests/test_io_views.py::test_io_menu_tiene_cuatro_botones -v
```

Esperado: `ModuleNotFoundError`

- [ ] **Step 3: Crear `io_menu.py`**

Crear `src/autoclave/ui_pyside/views/io_menu.py`:

```python
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_IO_OPTIONS = [
    ("🔍", "Verificación de entradas digitales", "io_di"),
    ("🌡️", "Sensores de temperatura",           "io_temp"),
    ("📊", "Sensores de presión",               "io_pres"),
    ("⚡", "Salidas digitales",                 "io_do"),
]

_BTN_OPTION = """
    QPushButton {{
        background: {bg};
        color: #1a2a3a;
        border-radius: 12px;
        border: 1.5px solid #e8eaed;
        text-align: left;
        padding-left: 16px;
        font-size: 14px;
    }}
    QPushButton:hover   {{ background: #e8f0fe; border-color: #2563eb; }}
    QPushButton:pressed {{ background: #dbeafe; }}
"""

_BTN_BACK = """
    QPushButton {
        background: #f0f0f0; color: #333;
        border-radius: 8px; border: none;
        font-size: 20px; font-weight: bold;
    }
    QPushButton:hover { background: #e0e0e0; }
"""


class EntradasSalidasMenuView(QWidget):
    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        self.setStyleSheet("""
            EntradasSalidasMenuView {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a3a5c, stop:1 #3a6fa8
                );
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.addStretch(1)

        card = QFrame()
        card.setObjectName("ioCard")
        card.setStyleSheet("QFrame#ioCard { background: white; border-radius: 20px; }")
        card.setMaximumWidth(460)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(10)

        top_row = QHBoxLayout()
        btn_back = QPushButton("←")
        btn_back.setFixedSize(40, 40)
        btn_back.setStyleSheet(_BTN_BACK)
        btn_back.clicked.connect(lambda: self._nav("admin_menu"))
        top_row.addWidget(btn_back)
        top_row.addSpacing(8)
        lbl_sub = QLabel("Administración")
        lbl_sub.setFont(QFont("Segoe UI", 13))
        lbl_sub.setStyleSheet("color: #555; background: transparent;")
        top_row.addWidget(lbl_sub)
        top_row.addStretch()
        cl.addLayout(top_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e8eaed;")
        cl.addWidget(sep)

        title = QLabel("ENTRADAS / SALIDAS")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a2a3a; background: transparent;")
        cl.addWidget(title)
        cl.addSpacing(4)

        for icon, label, target in _IO_OPTIONS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setFixedHeight(52)
            btn.setFont(QFont("Segoe UI", 13))
            btn.setStyleSheet(_BTN_OPTION.format(bg="#f8f9fa"))
            btn.clicked.connect(lambda checked=False, t=target: self._nav(t))
            cl.addWidget(btn)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        root.addLayout(row)
        root.addStretch(1)
```

- [ ] **Step 4: Registrar en `main_window.py`**

En `src/autoclave/ui_pyside/main_window.py`, en `__init__`:

```python
# Añadir import junto a los demás:
from autoclave.ui_pyside.views.io_menu import EntradasSalidasMenuView

# Después de self._admin_menu = ...:
self._io_menu = EntradasSalidasMenuView(nav_callback=self.navigate_to)

# En el bucle for view in (...):
for view in (self._home, self._secado, self._login,
             self._ciclos, self._admin_menu, self._io_menu):
    self._stack.addWidget(view)
```

En `navigate_to()`:

```python
views = {
    "home":       self._home,
    "secado":     self._secado,
    "login":      self._login,
    "ciclos":     self._ciclos,
    "admin_menu": self._admin_menu,
    "io_menu":    self._io_menu,   # ← nuevo
}
```

- [ ] **Step 5: Cablear `admin_menu.py`**

En `src/autoclave/ui_pyside/views/admin_menu.py`, reemplazar `_option_clicked`:

```python
_OPTION_ROUTES = {
    "Entradas / Salidas": "io_menu",
}

def _option_clicked(self, name: str) -> None:
    target = _OPTION_ROUTES.get(name)
    if target:
        self._nav(target)
        return
    InfoBar.info(
        title=name,
        content="Esta sección estará disponible próximamente.",
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=3000,
        parent=self,
    )
```

- [ ] **Step 6: Correr tests**

```
pytest tests/test_io_views.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/ui_pyside/views/io_menu.py \
        src/autoclave/ui_pyside/main_window.py \
        src/autoclave/ui_pyside/views/admin_menu.py
git commit -m "feat: EntradasSalidasMenuView + wiring admin_menu → io_menu"
```

---

## Task 4: `EntradasDigitalesView`

**Files:**
- Create: `src/autoclave/ui_pyside/views/io_di.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: `_MonitorBase`, `EstadoAutoclave.map_di`
- Produces: vista `"io_di"` en el stack

- [ ] **Step 1: Añadir test**

En `tests/test_io_views.py`:

```python
def test_di_card_activo_muestra_verde():
    from autoclave.ui_pyside.views.io_di import _DiCard
    card = _DiCard("aire_comprimido")
    card.set_value(1)
    assert "ACTIVO" in card._lbl_state.text()


def test_di_card_inactivo_muestra_gris():
    from autoclave.ui_pyside.views.io_di import _DiCard
    card = _DiCard("presion_agua")
    card.set_value(0)
    assert "INACTIVO" in card._lbl_state.text()


def test_entradas_digitales_view_tiene_14_cards():
    from autoclave.ui_pyside.views.io_di import EntradasDigitalesView
    view = EntradasDigitalesView(nav_callback=lambda x: None)
    assert len(view._cards) == 14
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_views.py::test_di_card_activo_muestra_verde tests/test_io_views.py::test_di_card_inactivo_muestra_gris tests/test_io_views.py::test_entradas_digitales_view_tiene_14_cards -v
```

Esperado: `ModuleNotFoundError`

- [ ] **Step 3: Crear `io_di.py`**

Crear `src/autoclave/ui_pyside/views/io_di.py`:

```python
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.status import EstadoAutoclave
from autoclave.ui_pyside.views._io_base import _MonitorBase, _format_name


class _DiCard(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )
        self.setMinimumSize(160, 80)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_state = QLabel("○ INACTIVO")
        self._lbl_state.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._lbl_state.setStyleSheet("color: #9ca3af; border: none;")
        lay.addWidget(self._lbl_state)

    def set_value(self, value: int) -> None:
        if value:
            self._lbl_state.setText("● ACTIVO")
            self._lbl_state.setStyleSheet("color: #22c55e; font-weight: bold; border: none;")
        else:
            self._lbl_state.setText("○ INACTIVO")
            self._lbl_state.setStyleSheet("color: #9ca3af; font-weight: bold; border: none;")


class EntradasDigitalesView(_MonitorBase):
    _DI_NAMES = list(EstadoAutoclave.map_di.keys())

    def __init__(self, nav_callback):
        super().__init__("ENTRADAS DIGITALES", "io_menu", nav_callback)
        self._cards: dict[str, _DiCard] = {}
        for idx, name in enumerate(self._DI_NAMES):
            card = _DiCard(name)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        di = status.get("sensors", {}).get("digital_inputs", {})
        for name, card in self._cards.items():
            card.set_value(di.get(name, 0))
```

- [ ] **Step 4: Registrar en `main_window.py`**

```python
# import:
from autoclave.ui_pyside.views.io_di import EntradasDigitalesView

# instancia:
self._io_di = EntradasDigitalesView(nav_callback=self.navigate_to)

# bucle for view in (...): añadir self._io_di
# navigate_to dict: "io_di": self._io_di
```

- [ ] **Step 5: Correr tests**

```
pytest tests/test_io_views.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/views/io_di.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: EntradasDigitalesView — 14 DI con poll 2s"
```

---

## Task 5: `TemperaturasView`

**Files:**
- Create: `src/autoclave/ui_pyside/views/io_temp.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: `_MonitorBase`, `EstadoAutoclave.map_temp`
- Produces: vista `"io_temp"`

- [ ] **Step 1: Añadir tests**

En `tests/test_io_views.py`:

```python
def test_temp_card_muestra_valor_con_decimal():
    from autoclave.ui_pyside.views.io_temp import _TempCard
    card = _TempCard("temp_camara")
    card.set_value(121.5)
    assert "121.5 °C" in card._lbl_value.text()


def test_temp_card_none_muestra_guiones():
    from autoclave.ui_pyside.views.io_temp import _TempCard
    card = _TempCard("temp_ref")
    card.set_value(None)
    assert "---" in card._lbl_value.text()


def test_temperaturas_view_tiene_6_cards():
    from autoclave.ui_pyside.views.io_temp import TemperaturasView
    view = TemperaturasView(nav_callback=lambda x: None)
    assert len(view._cards) == 6
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_views.py::test_temp_card_muestra_valor_con_decimal tests/test_io_views.py::test_temp_card_none_muestra_guiones tests/test_io_views.py::test_temperaturas_view_tiene_6_cards -v
```

Esperado: `ModuleNotFoundError`

- [ ] **Step 3: Crear `io_temp.py`**

Crear `src/autoclave/ui_pyside/views/io_temp.py`:

```python
from typing import Optional
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.status import EstadoAutoclave
from autoclave.ui_pyside.views._io_base import _MonitorBase, _format_name


class _TempCard(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )
        self.setMinimumSize(180, 90)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #555; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel("---")
        self._lbl_value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #f97316; border: none;")
        lay.addWidget(self._lbl_value)

    def set_value(self, value: Optional[float]) -> None:
        if value is None:
            self._lbl_value.setText("---")
            self._lbl_value.setStyleSheet("color: #f97316; font-weight: bold; border: none;")
        else:
            self._lbl_value.setText(f"{value:.1f} °C")
            self._lbl_value.setStyleSheet("color: #1a2a3a; font-weight: bold; border: none;")


class TemperaturasView(_MonitorBase):
    _TEMP_NAMES = list(EstadoAutoclave.map_temp.keys())

    def __init__(self, nav_callback):
        super().__init__("SENSORES DE TEMPERATURA", "io_menu", nav_callback)
        self._cards: dict[str, _TempCard] = {}
        for idx, name in enumerate(self._TEMP_NAMES):
            card = _TempCard(name)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        temp = status.get("sensors", {}).get("temperature", {})
        name_map = {
            "temp_camara":     "camara",
            "temp_2_camara":   "camara_2",
            "temp_ref":        "ref",
            "temp_chaqueta":   "chaqueta",
            "temp_drenaje_cam":"drenaje_camara",
            "temp_drenaje":    "drenaje",
        }
        for name, card in self._cards.items():
            key = name_map.get(name, name)
            card.set_value(temp.get(key))
```

- [ ] **Step 4: Registrar en `main_window.py`**

```python
from autoclave.ui_pyside.views.io_temp import TemperaturasView

self._io_temp = TemperaturasView(nav_callback=self.navigate_to)
# añadir al for y al dict navigate_to con "io_temp": self._io_temp
```

- [ ] **Step 5: Correr tests**

```
pytest tests/test_io_views.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/views/io_temp.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: TemperaturasView — 6 sensores con poll 2s"
```

---

## Task 6: `PresionesView`

**Files:**
- Create: `src/autoclave/ui_pyside/views/io_pres.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: `_MonitorBase`, `EstadoAutoclave.map_pres`
- Produces: vista `"io_pres"`

- [ ] **Step 1: Añadir tests**

En `tests/test_io_views.py`:

```python
def test_pres_card_muestra_valor_con_dos_decimales():
    from autoclave.ui_pyside.views.io_pres import _PresCard
    card = _PresCard("pres_camara")
    card.set_value(2.15)
    assert "2.15 bar" in card._lbl_value.text()


def test_presiones_view_tiene_4_cards():
    from autoclave.ui_pyside.views.io_pres import PresionesView
    view = PresionesView(nav_callback=lambda x: None)
    assert len(view._cards) == 4
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_views.py::test_pres_card_muestra_valor_con_dos_decimales tests/test_io_views.py::test_presiones_view_tiene_4_cards -v
```

Esperado: `ModuleNotFoundError`

- [ ] **Step 3: Crear `io_pres.py`**

Crear `src/autoclave/ui_pyside/views/io_pres.py`:

```python
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from autoclave.core.status import EstadoAutoclave
from autoclave.ui_pyside.views._io_base import _MonitorBase, _format_name


class _PresCard(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: white; border-radius: 10px; border: 1.5px solid #e8eaed; }"
        )
        self.setMinimumSize(180, 90)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lbl_name = QLabel(_format_name(name))
        lbl_name.setFont(QFont("Segoe UI", 11))
        lbl_name.setStyleSheet("color: #555; border: none;")
        lay.addWidget(lbl_name)

        self._lbl_value = QLabel("0.00 bar")
        self._lbl_value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet("color: #1a2a3a; border: none;")
        lay.addWidget(self._lbl_value)

    def set_value(self, value: float) -> None:
        self._lbl_value.setText(f"{value:.2f} bar")


class PresionesView(_MonitorBase):
    _PRES_NAMES = list(EstadoAutoclave.map_pres.keys())

    def __init__(self, nav_callback):
        super().__init__("SENSORES DE PRESIÓN", "io_menu", nav_callback)
        self._cards: dict[str, _PresCard] = {}
        for idx, name in enumerate(self._PRES_NAMES):
            card = _PresCard(name)
            self._cards[name] = card
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

    def _update_cards(self, status: dict) -> None:
        pres = status.get("sensors", {}).get("pressure", {})
        name_map = {
            "pres_camara":    "camara",
            "pres_chaqueta":  "chaqueta",
            "pres_empaque_1": "empaque_1",
            "pres_empaque_2": "empaque_2",
        }
        for name, card in self._cards.items():
            key = name_map.get(name, name)
            card.set_value(pres.get(key, 0.0) or 0.0)
```

- [ ] **Step 4: Registrar en `main_window.py`**

```python
from autoclave.ui_pyside.views.io_pres import PresionesView

self._io_pres = PresionesView(nav_callback=self.navigate_to)
# añadir al for y al dict con "io_pres": self._io_pres
```

- [ ] **Step 5: Correr tests**

```
pytest tests/test_io_views.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui_pyside/views/io_pres.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: PresionesView — 4 sensores con poll 2s"
```

---

## Task 7: `SalidasDigitalesView` (modo prueba)

**Files:**
- Create: `src/autoclave/ui_pyside/views/io_do.py`
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: `BackendClient`, `EstadoAutoclave.map_do`, endpoints `/io/test/reset_all` y `/io/test/output/{name}`
- Produces: vista `"io_do"`; `_DoCard.refresh(int)`, `_DoCard.enable_test_mode()`, `_DoCard.disable_test_mode()`

- [ ] **Step 1: Añadir tests**

En `tests/test_io_views.py`:

```python
def test_do_card_off_por_defecto():
    from autoclave.ui_pyside.views.io_do import _DoCard
    card = _DoCard("vapor_generador", lambda n, v: None)
    card.refresh(0)
    assert "OFF" in card._lbl_state.text()
    assert not card._btn.isEnabled()


def test_do_card_on_muestra_texto():
    from autoclave.ui_pyside.views.io_do import _DoCard
    card = _DoCard("vapor_caldera", lambda n, v: None)
    card.refresh(1)
    assert "ON" in card._lbl_state.text()


def test_do_card_enable_test_mode_habilita_boton():
    from autoclave.ui_pyside.views.io_do import _DoCard
    card = _DoCard("vapor_chaqueta", lambda n, v: None)
    card.enable_test_mode()
    assert card._btn.isEnabled()


def test_do_card_toggle_llama_callback():
    from autoclave.ui_pyside.views.io_do import _DoCard
    calls = []
    card = _DoCard("bomba_vacio", lambda n, v: calls.append((n, v)))
    card.enable_test_mode()
    card.refresh(0)
    card._on_click()
    assert calls == [("bomba_vacio", True)]


def test_salidas_digitales_view_tiene_24_cards():
    from autoclave.ui_pyside.views.io_do import SalidasDigitalesView
    view = SalidasDigitalesView(nav_callback=lambda x: None)
    assert len(view._cards) == 24


def test_salidas_digitales_test_mode_inactivo_por_defecto():
    from autoclave.ui_pyside.views.io_do import SalidasDigitalesView
    view = SalidasDigitalesView(nav_callback=lambda x: None)
    assert view._test_mode is False
```

- [ ] **Step 2: Correr y verificar que fallan**

```
pytest tests/test_io_views.py::test_do_card_off_por_defecto tests/test_io_views.py::test_salidas_digitales_view_tiene_24_cards -v
```

Esperado: `ModuleNotFoundError`

- [ ] **Step 3: Crear `io_do.py`**

Crear `src/autoclave/ui_pyside/views/io_do.py`:

```python
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
from autoclave.core.status import EstadoAutoclave
from autoclave.ui_pyside.views._io_base import _format_name

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
    def __init__(self, name: str, toggle_cb):
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

    def __init__(self, nav_callback):
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

    # ── lifecycle ─────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()
        if self._test_mode:
            self._exit_test_mode()

    # ── test mode ─────────────────────────────────────────────────────

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
            self._client.post("/io/test/reset_all")
        except Exception:
            pass

        self._test_mode = True
        self._banner.show()
        self._btn_test.setText("Salir del modo prueba")
        self._btn_test.setStyleSheet("""
            QPushButton { background: #fee2e2; color: #b91c1c; border-radius: 8px;
                          border: 1px solid #fca5a5; font-size: 13px; padding: 0 12px; font-weight: bold; }
            QPushButton:hover { background: #fecaca; }
        """)
        for card in self._cards.values():
            card.enable_test_mode()

    def _exit_test_mode(self) -> None:
        try:
            self._client.post("/io/test/reset_all")
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

    # ── data ──────────────────────────────────────────────────────────

    def _toggle_output(self, name: str, value: bool) -> None:
        try:
            self._client.patch(f"/io/test/output/{name}", {"value": value})
        except Exception:
            pass

    def _refresh(self) -> None:
        try:
            status = self._client.get_status()
            do_data = status.get("sensors", {}).get("digital_outputs", {})
            for name, card in self._cards.items():
                card.refresh(do_data.get(name, 0))
            self._lbl_conn.setText("● Conectado")
            self._lbl_conn.setStyleSheet("color: #22c55e; font-size: 12px;")
        except Exception:
            self._lbl_conn.setText("○ Sin datos")
            self._lbl_conn.setStyleSheet("color: #ef4444; font-size: 12px;")
```

- [ ] **Step 4: Registrar en `main_window.py`**

```python
from autoclave.ui_pyside.views.io_do import SalidasDigitalesView

self._io_do = SalidasDigitalesView(nav_callback=self.navigate_to)
# añadir al for y al dict con "io_do": self._io_do
```

El estado final de `navigate_to()` debe quedar:

```python
def navigate_to(self, view_name: str) -> None:
    views = {
        "home":       self._home,
        "secado":     self._secado,
        "login":      self._login,
        "ciclos":     self._ciclos,
        "admin_menu": self._admin_menu,
        "io_menu":    self._io_menu,
        "io_di":      self._io_di,
        "io_temp":    self._io_temp,
        "io_pres":    self._io_pres,
        "io_do":      self._io_do,
    }
    target = views.get(view_name)
    if target:
        self._stack.setCurrentWidget(target)
```

El `for` final:

```python
for view in (self._home, self._secado, self._login,
             self._ciclos, self._admin_menu, self._io_menu,
             self._io_di, self._io_temp, self._io_pres, self._io_do):
    self._stack.addWidget(view)
```

- [ ] **Step 5: Correr todos los tests**

```
pytest tests/test_io_views.py tests/test_io_endpoints.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 6: Commit final**

```bash
git add src/autoclave/ui_pyside/views/io_do.py src/autoclave/ui_pyside/main_window.py
git commit -m "feat: SalidasDigitalesView — 24 DO con modo prueba y confirmación"
```

---

## Self-Review

**Spec coverage:**
- ✅ EntradasSalidasMenuView con 4 botones (Task 3)
- ✅ EntradasDigitalesView 14 DI (Task 4)
- ✅ TemperaturasView 6 sensores (Task 5)
- ✅ PresionesView 4 sensores (Task 6)
- ✅ SalidasDigitalesView 24 DO (Task 7)
- ✅ Modo prueba: confirmación QMessageBox (Task 7 `_enter_test_mode`)
- ✅ reset_all antes de habilitar (Task 7)
- ✅ Banner naranja modo prueba activo (Task 7)
- ✅ Auto-reset al salir de la vista con hideEvent (Task 7)
- ✅ Poll 2s showEvent/hideEvent (Tasks 4–7)
- ✅ Indicador conexión (todos los monitores vía `_MonitorBase`)
- ✅ Backend endpoints (Task 1)
- ✅ Wiring admin_menu → io_menu (Task 3)
- ✅ navigate_to completo (Task 7, Step 4)

**Consistencia de tipos:**
- `_format_name` definida en `_io_base.py`, importada en `io_di.py`, `io_temp.py`, `io_pres.py`, `io_do.py` ✅
- `_DoCard(name, toggle_cb)` — interfaz consistente en Task 7 tests y Task 7 impl ✅
- `card.refresh(int)` — usado en `_update_cards` y en los tests ✅
- `status["sensors"]["digital_inputs"]` / `["digital_outputs"]` / `["temperature"]` / `["pressure"]` — consistente con server.py ✅

**`name_map` en `TemperaturasView` y `PresionesView`:**
El backend retorna las temperaturas con claves cortas (`"camara"`, `"camara_2"`, etc.) pero `EstadoAutoclave.map_temp` usa claves largas (`"temp_camara"`, `"temp_2_camara"`). Los `name_map` en Tasks 5 y 6 manejan esta traducción correctamente.
