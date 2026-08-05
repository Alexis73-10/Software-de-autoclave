# Selector de ciclo por click — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que el operador cambie el ciclo de usuario activo haciendo click en el número de ciclo (`_lbl_n_ciclo`) de la pantalla principal, propagando el cambio de forma segura al `ControlLoop` en vivo.

**Architecture:** Cadena de 4 capas, de adentro hacia afuera: (1) `ControlLoop.set_active_cycle()` reconstruye la `StateMachine` con el nuevo `Cycle` — solo permitido fuera del estado `CICLO`; (2) dos endpoints FastAPI nuevos (`GET /cycles`, `POST /cycle/select`) exponen esa capacidad vía HTTP; (3) `UIServiceBackend` agrega dos métodos delgados que envuelven esas llamadas HTTP; (4) `InterfazPrincipal` (tkinter) habilita/deshabilita el click según el estado de máquina y abre un diálogo modal para elegir el ciclo.

**Tech Stack:** Python, FastAPI + Pydantic (backend), tkinter + customtkinter (UI de planta), pytest + `fastapi.testclient.TestClient` + `unittest.mock`.

## Global Constraints

- Solo ciclos con `source == "user"` son seleccionables — ver spec, sección "Alcance".
- El cambio de ciclo solo se permite cuando el estado global de la máquina no es `CICLO` (`GlobalState.CICLO`). En cualquier otro estado (`PREPARACION`, `PREPARADO`, `FALLA`, `HIBERNACION`) debe estar permitido.
- El cambio es solo en memoria — no se persiste en disco. No modificar `context.py` ni el arranque con `"bowe_dick"`.
- No requiere sesión de usuario iniciada.
- Reutilizar `CycleManager.set_default_cycle()` tal cual existe hoy — no renombrar ni duplicar su lógica de validación.

Spec de referencia: `docs/superpowers/specs/2026-08-05-selector-ciclo-click-design.md`

---

### Task 1: `ControlLoop.set_active_cycle()`

**Files:**
- Modify: `src/autoclave/services/domain/loop/control_loop.py`
- Test: `tests/test_control_loop_set_active_cycle.py` (create)

**Interfaces:**
- Consumes: `autoclave.state_machine.machine.enum_global.GlobalState` (ya importado en el archivo), `autoclave.state_machine.state_machine.StateMachine` (ya importado como `StateMachine`, patcheado en tests vía `autoclave.services.domain.loop.control_loop.StateMachine`).
- Produces: `ControlLoop.set_active_cycle(cycle) -> tuple[bool, str]` — usado por Task 2. `ControlLoop.cap` (nuevo atributo de instancia).

Hoy `ControlLoop.__init__` recibe `cap` y lo pasa a `StateMachine(...)` pero no lo guarda como atributo — hace falta para poder reconstruir la `StateMachine` más tarde. El método sigue el mismo patrón `(ok, motivo)` que ya usa `enter_test_mode()` (ver `control_loop.py:212-225`).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_control_loop_set_active_cycle.py`:

```python
from unittest.mock import MagicMock, patch

from autoclave.state_machine.machine.enum_global import GlobalState


class _FakeEstado:
    """Estado mínimo que soporta la interfaz usada por ControlLoop/StateMachine."""

    def __init__(self):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self._state = GlobalState.PREPARACION
        self.sensores_di = {"paro_emergencia": 0, "suministro_electrico": 1}

    def get_machine_state(self):
        return self._state

    def set_machine_state(self, state):
        self._state = state

    def get_flag(self, name):
        return self._flags.get(name, False)

    def set_flag(self, name, value):
        self._flags[name] = value

    def update(self, data):
        pass


def _make_control_loop(estado=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    estado = estado or _FakeEstado()
    cycle_manager = MagicMock()
    initial_cycle = MagicMock(name="initial_cycle")
    cycle_manager.get_selected_cycle.return_value = initial_cycle

    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as mock_sm_cls:
        loop = ControlLoop(
            units=MagicMock(),
            door_service=MagicMock(),
            doors=[],
            estado=estado,
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
            cap="fake_cap",
        )
    return loop, mock_sm_cls, initial_cycle, estado


def test_set_active_cycle_permitido_fuera_de_ciclo_reconstruye_state_machine():
    loop, mock_sm_cls, _, _ = _make_control_loop()
    mock_sm_cls.reset_mock()
    new_cycle = MagicMock(name="new_cycle")

    ok, reason = loop.set_active_cycle(new_cycle)

    assert (ok, reason) == (True, "")
    assert loop.cycle is new_cycle
    mock_sm_cls.assert_called_once_with(
        io=loop.link, estado=loop.estado, set_do=loop.set_do,
        cycle=new_cycle, config=loop.config_manager, cap="fake_cap",
    )
    assert loop.state_machine is mock_sm_cls.return_value


def test_set_active_cycle_bloqueado_en_ciclo():
    estado = _FakeEstado()
    estado.set_machine_state(GlobalState.CICLO)
    loop, mock_sm_cls, initial_cycle, _ = _make_control_loop(estado)
    mock_sm_cls.reset_mock()
    new_cycle = MagicMock(name="new_cycle")

    ok, reason = loop.set_active_cycle(new_cycle)

    assert ok is False
    assert "ciclo" in reason.lower()
    assert loop.cycle is initial_cycle
    mock_sm_cls.assert_not_called()


def test_set_active_cycle_permitido_en_estados_no_ciclo():
    for state in (GlobalState.PREPARACION, GlobalState.PREPARADO,
                  GlobalState.FALLA, GlobalState.HIBERNACION):
        estado = _FakeEstado()
        estado.set_machine_state(state)
        loop, mock_sm_cls, _, _ = _make_control_loop(estado)
        mock_sm_cls.reset_mock()

        ok, _ = loop.set_active_cycle(MagicMock())

        assert ok is True, f"debería permitir cambio de ciclo en estado {state}"
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_control_loop_set_active_cycle.py -v`
Expected: FAIL con `AttributeError: 'ControlLoop' object has no attribute 'set_active_cycle'`

- [ ] **Step 3: Implementar**

En `src/autoclave/services/domain/loop/control_loop.py`, en `__init__` (alrededor de la línea 48, justo después de `self.realtime_printer = realtime_printer` y antes de construir `self.state_machine`), agregar:

```python
        self.cap             = cap
```

Al final de la clase, después del método `exit_test_mode` (alrededor de la línea 230), agregar:

```python
    # =========================================================================
    # CAMBIO DE CICLO ACTIVO
    # =========================================================================

    def set_active_cycle(self, cycle) -> tuple[bool, str]:
        """Reemplaza el ciclo activo y reconstruye la StateMachine para que el
        cambio se propague a todos los sub-estados y fases. Solo seguro fuera
        de CICLO: no hay fases en curso cuyo estado interno se pierda."""
        if self.estado.get_machine_state() == GlobalState.CICLO:
            return False, "No se puede cambiar de ciclo mientras hay uno en curso."

        self.cycle = cycle
        self.state_machine = StateMachine(
            io=self.link, estado=self.estado, set_do=self.set_do,
            cycle=cycle, config=self.config_manager, cap=self.cap,
        )
        return True, ""
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_control_loop_set_active_cycle.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Correr toda la suite de control_loop para descartar regresiones**

Run: `pytest tests/test_control_loop_test_mode.py tests/test_control_loop_connectivity_ticket.py tests/test_control_loop_resilience.py tests/test_control_loop_desconexion_ciclo.py -v`
Expected: todos PASSED (el nuevo atributo `self.cap` no debe romper ningún test existente, ya que `cap` ya era un parámetro opcional de `__init__`).

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/services/domain/loop/control_loop.py tests/test_control_loop_set_active_cycle.py
git commit -m "feat: agregar ControlLoop.set_active_cycle para cambiar el ciclo activo en vivo"
```

---

### Task 2: Endpoints `GET /cycles` y `POST /cycle/select`

**Files:**
- Modify: `src/autoclave/backend/server.py`
- Test: `tests/test_backend_cycle_select_endpoint.py` (create)

**Interfaces:**
- Consumes: `ControlLoop.set_active_cycle(cycle) -> tuple[bool, str]` (Task 1). `CycleManager.set_default_cycle(cycle_id)` (ya existe en `src/autoclave/core/managers/cycle_manager.py:106-111`, valida existencia y setea `selected_cycle`). `Cycle` (ya existe en `cycle_manager.py`, atributos `.id`, `.name`, `.source`).
- Produces: `GET /cycles` → `list[{"id": str, "name": str, "source": str}]`. `POST /cycle/select` body `{"cycle_id": str}` → `{"ok": True, "id": str, "name": str}` en éxito; usado por Task 3.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_backend_cycle_select_endpoint.py`:

```python
import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.state_machine.machine.enum_global import GlobalState


def _make_cycles():
    user_cycle = Cycle(cycle_id="bowe_dick", name="Bowe & Dick", parameters={})
    user_cycle.source = "user"
    factory_cycle = Cycle(cycle_id="fabrica_x", name="Fábrica X", parameters={})
    factory_cycle.source = "factory"
    return user_cycle, factory_cycle


@pytest.fixture
def select_client():
    user_cycle, factory_cycle = _make_cycles()

    mock_ctx = MagicMock()
    mock_ctx.cycle_manager.cycles = {"bowe_dick": user_cycle, "fabrica_x": factory_cycle}
    mock_ctx.control_loop.set_active_cycle.return_value = (True, "")

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx, user_cycle, factory_cycle


def test_list_cycles_incluye_todos_con_source(select_client):
    client, *_ = select_client
    resp = client.get("/cycles")
    assert resp.status_code == 200
    body = resp.json()
    assert {"id": "bowe_dick", "name": "Bowe & Dick", "source": "user"} in body
    assert {"id": "fabrica_x", "name": "Fábrica X", "source": "factory"} in body


def test_select_cycle_ok_llama_control_loop_y_sincroniza_cycle_manager(select_client):
    client, mock_ctx, user_cycle, _ = select_client
    resp = client.post("/cycle/select", json={"cycle_id": "bowe_dick"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "id": "bowe_dick", "name": "Bowe & Dick"}
    mock_ctx.control_loop.set_active_cycle.assert_called_once_with(user_cycle)
    mock_ctx.cycle_manager.set_default_cycle.assert_called_once_with("bowe_dick")


def test_select_cycle_404_si_no_existe(select_client):
    client, mock_ctx, *_ = select_client
    resp = client.post("/cycle/select", json={"cycle_id": "no_existe"})
    assert resp.status_code == 404
    mock_ctx.control_loop.set_active_cycle.assert_not_called()


def test_select_cycle_422_si_es_de_fabrica(select_client):
    client, mock_ctx, *_ = select_client
    resp = client.post("/cycle/select", json={"cycle_id": "fabrica_x"})
    assert resp.status_code == 422
    mock_ctx.control_loop.set_active_cycle.assert_not_called()


def test_select_cycle_409_si_control_loop_rechaza(select_client):
    client, mock_ctx, *_ = select_client
    mock_ctx.control_loop.set_active_cycle.return_value = (
        False, "No se puede cambiar de ciclo mientras hay uno en curso."
    )
    resp = client.post("/cycle/select", json={"cycle_id": "bowe_dick"})
    assert resp.status_code == 409
    assert "ciclo" in resp.json()["detail"].lower()
    mock_ctx.cycle_manager.set_default_cycle.assert_not_called()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_backend_cycle_select_endpoint.py -v`
Expected: FAIL con `404 Not Found` en las llamadas a `/cycles` y `/cycle/select` (rutas no existen todavía).

- [ ] **Step 3: Implementar**

En `src/autoclave/backend/server.py`, justo después del endpoint `GET /cycle` existente (líneas 179-190), agregar:

```python
@app.get("/cycles")
def list_cycles():
    return [
        {"id": c.id, "name": c.name, "source": getattr(c, "source", "user")}
        for c in context.cycle_manager.cycles.values()
    ]


class _SelectCycleBody(BaseModel):
    cycle_id: str


@app.post("/cycle/select")
def select_cycle(body: _SelectCycleBody):
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")
    if getattr(cycle, "source", "user") != "user":
        raise HTTPException(status_code=422, detail="Solo se pueden seleccionar ciclos de usuario")

    ok, reason = context.control_loop.set_active_cycle(cycle)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)

    context.cycle_manager.set_default_cycle(body.cycle_id)
    return {"ok": True, "id": cycle.id, "name": cycle.name}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_backend_cycle_select_endpoint.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Correr la suite completa de tests de backend/server para descartar regresiones**

Run: `pytest tests/test_backend_cycle_parameter_endpoint.py tests/test_patch_cycle_parameters.py -v`
Expected: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/backend/server.py tests/test_backend_cycle_select_endpoint.py
git commit -m "feat: agregar endpoints GET /cycles y POST /cycle/select"
```

---

### Task 3: `UIServiceBackend.list_user_cycles()` y `select_cycle()`

**Files:**
- Modify: `src/autoclave/ui/service_ui/ui_service_backend.py`
- Test: `tests/test_ui_service_backend_cycle_select.py` (create)

**Interfaces:**
- Consumes: `BackendClient.get(path) -> dict|list` y `BackendClient.post(path, body) -> dict` (ya existen en `src/autoclave/ui/service_ui/backend_client.py:33-46`, lanzan `requests.HTTPError`/`requests.RequestException` vía `raise_for_status()`).
- Produces: `UIServiceBackend.list_user_cycles() -> list[dict]`, `UIServiceBackend.select_cycle(cycle_id: str) -> tuple[bool, str]` — usados por Task 4.

Estos métodos solo usan `self.backend` (no tocan `self._cache`/`self._lock`), así que los tests pueden construir la instancia sin pasar por `__init__` (que arranca un hilo de fondo con polling cada 200 ms) — se usa `object.__new__` y se asigna `self.backend` directamente.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_ui_service_backend_cycle_select.py`:

```python
from unittest.mock import MagicMock
import requests

from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend


def _make_service(backend):
    service = object.__new__(UIServiceBackend)
    service.backend = backend
    return service


def test_list_user_cycles_filtra_solo_source_user():
    backend = MagicMock()
    backend.get.return_value = [
        {"id": "bowe_dick", "name": "Bowe & Dick", "source": "user"},
        {"id": "fabrica_x", "name": "Fábrica X", "source": "factory"},
    ]
    service = _make_service(backend)

    result = service.list_user_cycles()

    assert result == [{"id": "bowe_dick", "name": "Bowe & Dick", "source": "user"}]
    backend.get.assert_called_once_with(path="/cycles")


def test_list_user_cycles_retorna_vacio_si_falla_backend():
    backend = MagicMock()
    backend.get.side_effect = requests.RequestException("sin conexión")
    service = _make_service(backend)

    assert service.list_user_cycles() == []


def test_select_cycle_ok():
    backend = MagicMock()
    backend.post.return_value = {"ok": True, "id": "bowe_dick", "name": "Bowe & Dick"}
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert (ok, motivo) == (True, "")
    backend.post.assert_called_once_with(path="/cycle/select", body={"cycle_id": "bowe_dick"})


def test_select_cycle_error_http_extrae_detail():
    backend = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "detail": "No se puede cambiar de ciclo mientras hay uno en curso."
    }
    backend.post.side_effect = requests.HTTPError(response=response)
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert motivo == "No se puede cambiar de ciclo mientras hay uno en curso."


def test_select_cycle_error_conexion():
    backend = MagicMock()
    backend.post.side_effect = requests.RequestException("timeout")
    service = _make_service(backend)

    ok, motivo = service.select_cycle("bowe_dick")

    assert ok is False
    assert "backend" in motivo.lower()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_ui_service_backend_cycle_select.py -v`
Expected: FAIL con `AttributeError: 'UIServiceBackend' object has no attribute 'list_user_cycles'`

- [ ] **Step 3: Implementar**

En `src/autoclave/ui/service_ui/ui_service_backend.py`, agregar el import al inicio del archivo (junto a los otros imports, línea 3-4):

```python
import requests
```

Y agregar los dos métodos nuevos al final de la clase, después de `reset_outputs` (línea 267):

```python
    # ==============================
    # SELECCIÓN DE CICLO ACTIVO
    # ==============================

    def list_user_cycles(self) -> list[dict]:
        """Lista los ciclos de usuario disponibles para seleccionar."""
        try:
            cycles = self.backend.get(path="/cycles")
            return [c for c in cycles if c.get("source") == "user"]
        except Exception as e:
            logger.warning("list_user_cycles error: %s", e)
            return []

    def select_cycle(self, cycle_id: str) -> tuple[bool, str]:
        """Cambia el ciclo activo. Retorna (ok, motivo — vacío si ok)."""
        try:
            self.backend.post(path="/cycle/select", body={"cycle_id": cycle_id})
            return True, ""
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            return False, detail
        except requests.RequestException as e:
            return False, f"No se pudo contactar al backend: {e}"
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_ui_service_backend_cycle_select.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui/service_ui/ui_service_backend.py tests/test_ui_service_backend_cycle_select.py
git commit -m "feat: agregar UIServiceBackend.list_user_cycles y select_cycle"
```

---

### Task 4: UI — click en el número de ciclo abre el selector (`main_window.py`)

**Files:**
- Modify: `src/autoclave/ui/window/main_window.py`

**Interfaces:**
- Consumes: `self.ui_service.get_estado_global() -> str` (ya existe, patrón usado en `_upd_panel_izquierdo`). `self.ui_service.list_user_cycles() -> list[dict]` y `self.ui_service.select_cycle(cycle_id) -> tuple[bool, str]` (Task 3). `self.ui_service.get_cycle_param("id") -> str` (ya existe — `GET /cycle` ya devuelve `"id"`, no requiere cambios de backend). `self._mostrar_toast(mensaje: str)` (ya existe, línea 791).
- Produces: nada consumido por otras tareas — es la capa final.

**Nota sobre testing:** este archivo no tiene tests automatizados hoy (`InterfazPrincipal` es un `tk.Tk()` fullscreen real que arranca hilos de fondo y hace llamadas de red desde `__init__` — instanciarlo en pytest no es práctico, y ningún test existente en el repo lo hace). Se sigue el patrón establecido en el proyecto: verificación manual con la app corriendo (ver Step 5).

- [ ] **Step 1: Agregar estado inicial**

En `__init__`, después de la línea `self._toast_widget = None` (línea 58), agregar:

```python
        self._cycle_selector_habilitado = False
```

- [ ] **Step 2: Agregar el método de habilitación/deshabilitación del click**

Agregar este método nuevo, junto a `_upd_listo` (después de la línea 733, antes de `_actualizar_imagen_puerta`):

```python
    def _upd_cycle_selector_habilitado(self):
        habilitado = self.ui_service.get_estado_global() != "CICLO"
        if habilitado == self._cycle_selector_habilitado:
            return   # sin cambio

        self._cycle_selector_habilitado = habilitado
        if habilitado:
            self._lbl_n_ciclo.bind("<Button-1>", lambda e: self._abrir_selector_ciclo())
            self._lbl_n_ciclo.configure(cursor="hand2")
        else:
            self._lbl_n_ciclo.unbind("<Button-1>")
            self._lbl_n_ciclo.configure(cursor="")
```

- [ ] **Step 3: Enganchar la actualización al loop de UI**

En `_update_ui` (línea 630-636), agregar la llamada junto a `self._upd_listo()`:

```python
                if self._tick % 2 == 0:
                    self._upd_ciclo_nombre()
                    self._upd_params_ciclo()
                    self._upd_panel_izquierdo()
                    self._upd_listo()
                    self._upd_cycle_selector_habilitado()
                    self._upd_suministro()
                    self._actualizar_imagen_puerta()
```

En `_rebuild_layout` (línea 768-785), resetear el flag junto a `self._toast_widget = None` (línea 782) para forzar el rebind tras un cambio de orientación (los widgets viejos, incluido el bind, se destruyen):

```python
        self._toast_widget = None
        self._cycle_selector_habilitado = False
        self._build_ui()
```

- [ ] **Step 4: Agregar el diálogo selector y el manejador de selección**

Agregar estos dos métodos nuevos junto a `_upd_cycle_selector_habilitado`:

```python
    def _abrir_selector_ciclo(self):
        cycles = self.ui_service.list_user_cycles()
        if not cycles:
            self._mostrar_toast("No hay ciclos de usuario disponibles.")
            return

        current_id = self.ui_service.get_cycle_param("id")

        dlg = tk.Toplevel(self)
        dlg.overrideredirect(True)
        dlg.configure(bg=CLR_DARK)
        dlg.resizable(False, False)
        dlg.grab_set()

        self.update_idletasks()
        w = 440
        h = 130 + 60 * len(cycles)
        x = self.winfo_x() + (self.winfo_width()  - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        ctk.CTkLabel(
            dlg, text="Seleccionar ciclo",
            font=("Segoe UI", 22, "bold"),
            text_color=CLR_W, fg_color="transparent",
        ).pack(pady=(24, 16))

        for cycle in cycles:
            es_actual = cycle["id"] == current_id
            ctk.CTkButton(
                dlg,
                text=f"✓  {cycle['name']}" if es_actual else cycle["name"],
                font=("Segoe UI", 16, "bold" if es_actual else "normal"),
                fg_color="#1e8449" if es_actual else "#5789a7",
                hover_color="#155d32" if es_actual else "#406080",
                width=360, height=44,
                state="disabled" if es_actual else "normal",
                command=lambda cid=cycle["id"], name=cycle["name"]: self._seleccionar_ciclo(dlg, cid, name),
            ).pack(pady=6)

        ctk.CTkButton(
            dlg, text="Cancelar",
            font=("Segoe UI", 14),
            fg_color="#5789a7", hover_color="#406080",
            width=160, height=36,
            command=dlg.destroy,
        ).pack(pady=(16, 20))

    def _seleccionar_ciclo(self, dlg, cycle_id, name):
        dlg.destroy()
        ok, motivo = self.ui_service.select_cycle(cycle_id)
        if not ok:
            self._mostrar_toast(motivo)
            return
        # actualización optimista inmediata — no esperar el refresco de /cycle (~5 s)
        self.cycle_name = name
        self._lbl_ciclo_nombre.configure(text=self.cycle_name.upper())
```

- [ ] **Step 5: Verificación manual**

Usar la skill `run` para levantar el backend y la app de planta (`InterfazPrincipal`), o arrancarlos manualmente:

```bash
python -m autoclave.backend.server &
python -m autoclave.ui.main
```

Checklist manual (ambas orientaciones si es posible, o al menos landscape):

1. Con la máquina en `PREPARADO`, el cursor cambia a mano al pasar sobre el número de ciclo ("01").
2. Click sobre el número abre el diálogo "Seleccionar ciclo" con los ciclos de usuario (Bowe & Dick, Instrumental 134), el activo resaltado en verde y deshabilitado.
3. Click en un ciclo distinto al activo: el diálogo se cierra, el nombre del ciclo en pantalla cambia inmediatamente al nuevo, sin esperar varios segundos.
4. Reabrir el diálogo: el ciclo recién elegido ahora aparece resaltado como el activo.
5. Botón "Cancelar" cierra el diálogo sin cambiar nada.
6. Iniciar un ciclo (estado `CICLO`): el cursor vuelve a normal sobre el número y el click ya no hace nada.
7. Al terminar/abortar el ciclo y volver a `PREPARADO`, el click se rehabilita automáticamente (sin reiniciar la app).
8. Si aplica, forzar un cambio de orientación (rotar pantalla o redimensionar) y repetir el punto 1 — el click debe seguir funcionando tras el rebuild del layout.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui/window/main_window.py
git commit -m "feat: click en numero de ciclo abre selector de ciclo activo"
```

---

## Self-Review

**Cobertura del spec:**
- Solo ciclos `source=="user"` seleccionables → validado en backend (Task 2, 422) y filtrado en `list_user_cycles` (Task 3). ✓
- Gating por estado != CICLO → `ControlLoop.set_active_cycle` (Task 1) + gating de UI (Task 4, Step 2-3) + defensa en profundidad vía 409 en Task 2. ✓
- Sin persistencia en disco → no se toca `context.py`; `set_default_cycle` ya es puramente en memoria. ✓
- Sin requisito de sesión → ningún endpoint ni método nuevo consulta `SessionManager`. ✓
- Diálogo tipo lista de botones, estilo `_confirmar_abort` → Task 4, Step 4. ✓
- Actualización optimista del nombre tras seleccionar → Task 4, `_seleccionar_ciclo`. ✓
- Casos de error (ciclo en curso, sin ciclos, backend caído) → cubiertos por toasts en Task 4 y tests de Task 2/3. ✓

**Placeholders:** ninguno — cada step tiene código completo, no hay "TODO" ni "similar a Task N".

**Consistencia de tipos:** `set_active_cycle(cycle) -> tuple[bool, str]` (Task 1) es exactamente lo que consume Task 2 (`ok, reason = context.control_loop.set_active_cycle(cycle)`). `select_cycle(cycle_id) -> tuple[bool, str]` (Task 3) es exactamente lo que consume Task 4 (`ok, motivo = self.ui_service.select_cycle(cycle_id)`). `list_user_cycles() -> list[dict]` con claves `id`/`name`/`source` (Task 3) coincide con lo que itera Task 4 (`cycle["id"]`, `cycle["name"]`).
