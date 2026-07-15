# Impresión General + Imprimir Alarmas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the home menu's "Imprimir Ciclos" card to "Impresión General", turn it into a submenu, and add an "Imprimir Alarmas" action inside it that prints all currently active alarms.

**Architecture:** A new `ImpresionMenuView` (PySide6 widget) follows the existing `EntradasSalidasMenuView` submenu pattern (card + back button + list of option buttons). "Imprimir Ciclos" keeps navigating to the existing `CiclosView`. "Imprimir Alarmas" is a direct action (no navigation): it calls `GET /status` via the existing `BackendClient`, and either shows an information dialog (no active alarms / backend unreachable) or opens the system print dialog and draws a plain-text ticket with `QPainter`, reusing the same 55mm-thermal-ticket approach already used by `CiclosView`. The backend's `/status` alarm payload is extended with `description` and `source_state` so the ticket has enough detail.

**Tech Stack:** Python, PySide6 (Qt widgets, QtPrintSupport), FastAPI (backend `/status` endpoint), pytest + `fastapi.testclient.TestClient` + `unittest.mock`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-10-impresion-general-alarmas-design.md`
- No timestamp field is added to `Alarm` (not requested).
- No new alarm-listing screen — "Imprimir Alarmas" is a direct action, not a navigable view.
- The footer quick-access icon in `main_window.py` keeps navigating directly to `"ciclos"` — it is not changed.
- "Sin alarmas activas" and "backend no disponible" show the same informational message; the cause is not distinguished in the UI copy.
- Ticket paper/font constants match `CiclosView`: 55mm width, `Courier New` 7pt, 2mm/3mm margins.
- Existing files `ciclos.py`'s printing code is not modified — the new printing helpers are self-contained in the new file.

---

### Task 1: Backend `/status` — include `description` and `source_state` per alarm

**Files:**
- Modify: `src/autoclave/backend/server.py:73-79`
- Test: Create `tests/test_status_endpoint_alarms.py`

**Interfaces:**
- Produces: `GET /status` response `alarms` field is now `list[{"id": str, "level": str, "description": str, "source_state": str}]` (previously only `id` and `level`).

- [x] **Step 1: Write the failing test**

Create `tests/test_status_endpoint_alarms.py`:

```python
import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def status_client():
    mock_ctx = MagicMock()

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx


def _stub_estado_collections(mock_ctx) -> None:
    mock_ctx.estado.estado_puertas = {}
    mock_ctx.estado.sensores_temp = {}
    mock_ctx.estado.sensores_pres = {}
    mock_ctx.estado.sensores_di = {}
    mock_ctx.estado.salidas_do = {}
    mock_ctx.estado.flags = {}


def test_status_incluye_description_y_source_state_por_alarma(status_client):
    client, mock_ctx = status_client

    fake_alarm = MagicMock()
    fake_alarm.id = "PUERTA_NO_CERRADA"
    fake_alarm.type.name = "FALLA"
    fake_alarm.description = "Puerta frontal no cerrada"
    fake_alarm.source_state = "PREPARACION"

    mock_ctx.estado.Alarmas_activas = [fake_alarm]
    _stub_estado_collections(mock_ctx)

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["alarms"] == [{
        "id": "PUERTA_NO_CERRADA",
        "level": "FALLA",
        "description": "Puerta frontal no cerrada",
        "source_state": "PREPARACION",
    }]


def test_status_alarmas_vacias_devuelve_lista_vacia(status_client):
    client, mock_ctx = status_client

    mock_ctx.estado.Alarmas_activas = []
    _stub_estado_collections(mock_ctx)

    resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["alarms"] == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_status_endpoint_alarms.py -v`
Expected: `test_status_incluye_description_y_source_state_por_alarma` FAILS — the response dict for each alarm only has `id` and `level` keys, so the equality assertion fails (extra keys `description`/`source_state` missing).

- [x] **Step 3: Implement**

In `src/autoclave/backend/server.py`, replace the alarms block (currently lines 73-79):

```python
    alarms = [
        {
            "id": alarma.id,
            "level": alarma.type.name,
        }
        for alarma in estado.Alarmas_activas
    ]
```

with:

```python
    alarms = [
        {
            "id": alarma.id,
            "level": alarma.type.name,
            "description": alarma.description,
            "source_state": alarma.source_state,
        }
        for alarma in estado.Alarmas_activas
    ]
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_status_endpoint_alarms.py -v`
Expected: both tests PASS.

- [x] **Step 5: Run the pre-existing `/status`-adjacent test to confirm no regression**

Run: `python -m pytest tests/test_io_test_mode_endpoints.py -v`
Expected: all 5 tests PASS (unchanged behavior — `test_status_incluye_test_mode_active` doesn't assert on `alarms` content).

- [x] **Step 6: Commit**

```bash
git add src/autoclave/backend/server.py tests/test_status_endpoint_alarms.py
git commit -m "feat: incluir description y source_state en alarmas de /status"
```

**STATUS: DONE** — commits 80cc77b..fcfe80d, review clean.

---

### Task 2: `ImpresionMenuView` skeleton — submenu navigation (back + Imprimir Ciclos)

**Files:**
- Create: `src/autoclave/ui_pyside/views/impresion_menu.py`
- Test: Create `tests/test_impresion_menu.py`

**Interfaces:**
- Consumes: nothing from other tasks yet (navigation-only).
- Produces:
  - `ImpresionMenuView(nav_callback: Callable[[str], None])` — QWidget subclass.
  - Module-level `_PRINT_OPTIONS: list[tuple[str, str, str | None]]` = `[(icon, label, target_view_name_or_None), ...]`. Task 4 relies on the second entry having `target is None` and being wired to `self._print_alarms`.
  - `ImpresionMenuView._print_alarms` method exists as a no-op placeholder in this task (implemented fully in Task 4) so the button wiring compiles.

**STATUS: DONE** — commits fcfe80d..8a3ab6c, review clean.

---

### Task 3: Alarm ticket text builder (`_build_alarms_ticket_lines`)

**Files:**
- Modify: `src/autoclave/ui_pyside/views/impresion_menu.py`
- Test: Modify `tests/test_impresion_menu.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_build_alarms_ticket_lines(alarms: list[dict]) -> list[str]`, where each `dict` has keys `id`, `level`, `description`, `source_state` (matching the `/status` `alarms` shape from Task 1). Task 4 calls this function directly.

**STATUS: DONE** — commits 8a3ab6c..b658924, review clean.

---

### Task 4: Wire `_print_alarms` — fetch status, show dialog, print ticket

**Files:**
- Modify: `src/autoclave/ui_pyside/views/impresion_menu.py`
- Test: Modify `tests/test_impresion_menu.py`

**Interfaces:**
- Consumes:
  - `_build_alarms_ticket_lines(alarms: list[dict]) -> list[str]` (Task 3).
  - `BackendClient` from `autoclave.ui.service_ui.backend_client` — `BackendClient(base_url).get_status() -> dict` (existing, used by `_io_base.py`).
- Produces: `ImpresionMenuView._print_alarms()` fully implemented; `ImpresionMenuView._client` attribute (a `BackendClient` instance, overridable by tests); module-level `_draw_ticket_lines(printer: QPrinter, lines: list[str]) -> None` and `_wrap(text: str, max_chars: int) -> list[str]` helpers.

**STATUS: DONE** — commits b658924..886ad74 (original 7d0fa92 + fix 886ad74), review clean after fix. Fix addressed an Important, plan-mandated test-coverage gap in the "dialog accepted" test case (see progress ledger for details).

---

### Task 5: Rename home menu card to "Impresión General"

**Files:**
- Modify: `src/autoclave/ui_pyside/views/home.py:25-29`
- Test: Create `tests/test_home_view.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `HomeView`'s `cards_data` now points the second card at `view_name="impresion_menu"`. Task 6 relies on this `view_name` matching the key registered in `main_window.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_home_view.py`:

```python
import sys
import pytest


@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_home_view_tarjeta_impresion_general_navega_a_impresion_menu():
    from autoclave.ui_pyside.views.home import HomeView
    from qfluentwidgets import SubtitleLabel

    nav_calls = []
    view = HomeView(nav_callback=nav_calls.append)

    label = next(
        lbl for lbl in view.findChildren(SubtitleLabel)
        if "Impresión General" in lbl.text()
    )
    card = label.parentWidget()
    # mousePressEvent está sobreescrito directamente en la card (ver home.py)
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF, Qt

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.mousePressEvent(event)
    assert nav_calls == ["impresion_menu"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_home_view.py -v`
Expected: FAIL — `next(...)` raises `StopIteration` because no `SubtitleLabel` contains the text "Impresión General" yet (the card still says "Imprimir Ciclos").

- [ ] **Step 3: Implement**

In `src/autoclave/ui_pyside/views/home.py`, replace the second tuple in `cards_data` (currently lines 25-29):

```python
            (
                "🖨  Imprimir Ciclos",
                "Consulta e imprime el historial de ciclos",
                "ciclos",
            ),
```

with:

```python
            (
                "🖨  Impresión General",
                "Imprime ciclos, alarmas y más",
                "impresion_menu",
            ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_home_view.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui_pyside/views/home.py tests/test_home_view.py
git commit -m "feat: renombrar tarjeta de inicio a Impresión General"
```

---

### Task 6: Wire everything together — register the new view, fix Ciclos' back button

**Files:**
- Modify: `src/autoclave/ui_pyside/main_window.py:40-68,174-187`
- Modify: `src/autoclave/ui_pyside/views/ciclos.py:269`

**Interfaces:**
- Consumes:
  - `ImpresionMenuView` from `autoclave.ui_pyside.views.impresion_menu` (Task 2/4).
  - `"impresion_menu"` view name used by `HomeView` (Task 5) and by `CiclosView`'s back button (this task).
- Produces: `MainWindowFluent.navigate_to("impresion_menu")` shows the new submenu; `CiclosView`'s back button returns to `"impresion_menu"` instead of `"home"`.

There is no existing automated test coverage for `main_window.py` or for `CiclosView`'s navigation wiring (both are exercised only manually today — `CiclosView.__init__` opens a real `DbManager`, which is why it isn't unit tested elsewhere in this codebase either). This task is verified manually in Step 4 via the `verify` skill instead of an automated test, consistent with the rest of the file.

- [ ] **Step 1: Update `ciclos.py`'s back button target**

In `src/autoclave/ui_pyside/views/ciclos.py`, change line 269:

```python
        btn_back.clicked.connect(lambda: self._nav("home"))
```

to:

```python
        btn_back.clicked.connect(lambda: self._nav("impresion_menu"))
```

- [ ] **Step 2: Register `ImpresionMenuView` in `main_window.py`**

In `src/autoclave/ui_pyside/main_window.py`, add the import alongside the existing view imports (after the `CiclosView` import, before `AdminMenuView`, around line 43):

```python
        from autoclave.ui_pyside.views.impresion_menu import ImpresionMenuView
```

Add the instantiation alongside the others (after `self._ciclos = CiclosView(...)`, around line 55):

```python
        self._impresion_menu = ImpresionMenuView(nav_callback=self.navigate_to)
```

Add `self._impresion_menu` to the `for view in (...)` tuple that populates the stack (around line 64-67):

```python
        for view in (self._home, self._secado, self._login,
                     self._ciclos, self._impresion_menu, self._admin_menu, self._io_menu,
                     self._io_di, self._io_temp, self._io_pres, self._io_do,
                     self._params_ciclo):
            self._stack.addWidget(view)
```

Add the `"impresion_menu"` entry to the `views` dict inside `navigate_to` (around line 174-187):

```python
    def navigate_to(self, view_name: str) -> None:
        views = {
            "home":           self._home,
            "secado":         self._secado,
            "login":          self._login,
            "ciclos":         self._ciclos,
            "impresion_menu": self._impresion_menu,
            "admin_menu":     self._admin_menu,
            "io_menu":        self._io_menu,
            "io_di":          self._io_di,
            "io_temp":        self._io_temp,
            "io_pres":        self._io_pres,
            "io_do":          self._io_do,
            "params_ciclo":   self._params_ciclo,
        }
        target = views.get(view_name)
        if target:
            self._stack.setCurrentWidget(target)
```

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `python -m pytest tests/ -v --ignore=tests/test_io_views.py`

(`test_io_views.py` is excluded because it already fails on `main` before this plan — its imports reference a module path, `autoclave.ui_pyside.views.io_menu`, that predates the `entrdas_salidas` package reorg. This is a pre-existing issue, out of scope for this plan.)

Expected: all tests PASS, including the new `tests/test_status_endpoint_alarms.py`, `tests/test_impresion_menu.py`, and `tests/test_home_view.py`.

- [ ] **Step 4: Manual verification**

Use the `run`/`verify` skill (or launch the app directly) and confirm:
1. Backend running (`GET /status` reachable at `http://localhost:8000`).
2. Home screen shows "🖨 Impresión General" instead of "Imprimir Ciclos".
3. Clicking it opens the new submenu with "Imprimir Ciclos" and "Imprimir Alarmas", and "←" returns to Home.
4. "Imprimir Ciclos" opens the existing cycle history screen, and its "← Volver" button now returns to the Impresión General submenu (not Home).
5. With no active alarms, "Imprimir Alarmas" shows the "No hay alarmas activas" message and does not open a print dialog.
6. With at least one active alarm (trigger one via the existing test-mode/fault flows, or temporarily inspect `estado.Alarmas_activas` in a debugger), "Imprimir Alarmas" opens the system print dialog; accepting it prints/generates a ticket containing the alarm's ID, level, origin state, and description.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui_pyside/main_window.py src/autoclave/ui_pyside/views/ciclos.py
git commit -m "feat: registrar submenú Impresión General en la navegación principal"
```

---

## Self-Review Notes

- **Spec coverage:** home card rename (Task 5), submenu with back-nav (Task 2), Imprimir Ciclos moved under submenu + Ciclos back button (Task 2/6), Imprimir Alarmas action with "no alarms" and "backend down" handling (Task 4), ticket content (ID/level/origin/description) (Task 3), `/status` extension (Task 1), main_window registration (Task 6) — all covered.
- **Pre-existing broken test:** `tests/test_io_views.py` fails on the current `main` branch (stale import paths from before the `entrdas_salidas` package reorg) — unrelated to this plan, explicitly excluded from the Task 6 regression run rather than silently left failing.
- **Type/name consistency check:** `_PRINT_OPTIONS` (Task 2) → consumed by `_print_alarms` wiring (Task 2, via `target is None`) and by tests (Task 2/4) — consistent. `_build_alarms_ticket_lines` (Task 3) signature `(alarms: list[dict]) -> list[str]` matches its only call site in `_print_alarms` (Task 4). `ImpresionMenuView._client` attribute name matches what Task 4's tests patch (`view._client = MagicMock()`). View name `"impresion_menu"` is identical across `home.py` (Task 5), `ciclos.py` (Task 6), and `main_window.py`'s `views` dict (Task 6).

## Session Recovery Note (2026-07-15)

This plan file was reconstructed from conversation context after it was found deleted mid-execution
(it had never been committed — untracked file — and disappeared while another, unrelated parallel
session was active on the same working directory/branch). Tasks 1-4 above are marked DONE and their
commits/reviews are verified present in `git log` and in `.superpowers/sdd/progress.md`'s
`impresion-general-alarmas` ledger section. Tasks 5-6 steps are reproduced verbatim from the
original plan and have not been started yet.
