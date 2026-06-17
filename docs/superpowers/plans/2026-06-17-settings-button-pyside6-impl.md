# Settings Button → PySide6 Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que el botón de settings del footer de `InterfazPrincipal` (tkinter) abra el menú PySide6 como subprocess fullscreen, ocultando tkinter mientras está abierto.

**Architecture:** Tkinter `InterfazPrincipal` es la ventana principal permanente. El botón settings lanza `autoclave.ui_pyside.app` como subprocess y sondea su estado cada 500ms. Al terminar el subprocess, tkinter reaparece. `MainWindowFluent` se simplifica: ya no gestiona procesos tkinter hijos.

**Tech Stack:** Python 3.14, tkinter, customtkinter, PySide6, qfluentwidgets, subprocess, Windows 11.

## Global Constraints

- Todas las pantallas PySide6 deben ser pantalla completa sin barra de título (`FramelessWindowHint` + `showFullScreen()`).
- Tkinter `InterfazPrincipal` es siempre la ventana principal; PySide6 es secundaria/on-demand.
- No modificar la lógica de ciclo, sensores, ni ningún otro módulo que no figure en la lista de archivos.
- Usar `python` (no `python3`) en Windows. PowerShell para comandos de terminal.
- Tests con `python -m pytest`.

## File Map

**Modificados:**
- `src/autoclave/main.py` — revertir bloque 3 a lanzar tkinter; agregar cleanup de `_settings_proc` en `on_close()`
- `src/autoclave/ui/window/main_window.py` — agregar `_open_settings()`, `_poll_settings()`, wiring del botón; agregar `import subprocess` y `import sys`
- `src/autoclave/ui_pyside/main_window.py` — eliminar `tkinter_proc`, `_open_monitor()`, botón Monitor; eliminar imports `subprocess`/`sys`

**Nuevos:**
- `src/autoclave/ui_pyside/app.py` — entry point standalone PySide6 fullscreen frameless

---

## Task 1: Revertir `main.py` — lanzar tkinter como ventana principal

**Files:**
- Modify: `src/autoclave/main.py`

**Interfaces:**
- Consumes: `InterfazPrincipal(ui_service, door_commands, on_shutdown, source_door)` de `autoclave.ui.window.main_window`
- Produces: `app` (instancia de `InterfazPrincipal`) accesible desde `on_close()` para limpiar `_settings_proc`

- [ ] **Step 1: Leer el archivo actual**

Leer `src/autoclave/main.py` para identificar el bloque `# ── 3. Arrancar UI (PySide6)` y todo lo que sigue hasta el final del archivo.

- [ ] **Step 2: Reemplazar bloque 3 con arranque tkinter**

Localizar desde `# ── 3. Arrancar UI (PySide6)` hasta el final de `main()` y reemplazar con:

```python
    # ── 3. Arrancar UI (tkinter) ────────────────────────────────────────────
    from autoclave.ui.service_ui.backend_client import BackendClient
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.services.domain.puertas.door_command_service import DoorCommandService
    from autoclave.ui.window.main_window import InterfazPrincipal

    backend       = BackendClient(BACKEND_URL)
    ui_service    = UIServiceBackend(backend)
    door_commands = DoorCommandService(backend_client=backend, source_door=SOURCE_DOOR)

    def on_close():
        logger.info("Cerrando aplicación...")
        try:
            ui_service.reset_outputs()
            logger.info("Salidas digitales apagadas")
        except Exception as e:
            logger.warning("No se pudieron apagar las salidas: %s", e)
        ui_service.stop()
        if hasattr(app, '_settings_proc') and app._settings_proc and app._settings_proc.poll() is None:
            app._settings_proc.terminate()
        if backend_process:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
        app.destroy()

    app = InterfazPrincipal(
        ui_service=ui_service,
        door_commands=door_commands,
        on_shutdown=on_close,
        source_door=SOURCE_DOOR,
    )
    logger.info("UI Autoclave iniciada")
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()
```

Nota: `subprocess` ya está importado al nivel del módulo en `main.py` — no agregar de nuevo.

- [ ] **Step 3: Verificar sintaxis**

```
python -c "import ast; ast.parse(open('src/autoclave/main.py').read()); print('sintaxis OK')"
```

Expected: `sintaxis OK`

- [ ] **Step 4: Ejecutar suite de tests para verificar sin regresiones**

```
python -m pytest tests/ -q --tb=short
```

Expected: `221 passed` (o el número actual), sin nuevos fallos.

- [ ] **Step 5: Commit**

```
git add src/autoclave/main.py
git commit -m "fix: revertir main.py — tkinter como ventana principal, PySide6 on-demand"
```

---

## Task 2: Crear `ui_pyside/app.py` — entry point standalone PySide6

**Files:**
- Create: `src/autoclave/ui_pyside/app.py`

**Interfaces:**
- Consumes: `MainWindowFluent()` de `autoclave.ui_pyside.main_window` (sin argumentos tras Task 3)
- Produces: módulo `autoclave.ui_pyside.app` invocable como `python -m autoclave.ui_pyside.app`

Nota: `MainWindowFluent` aún tiene `tkinter_proc=None` como parámetro con default en este punto — el archivo funciona igual sin pasarlo. Task 3 eliminará el parámetro. El orden no importa porque el default es `None`.

- [ ] **Step 1: Crear el archivo**

Crear `src/autoclave/ui_pyside/app.py` con este contenido exacto:

```python
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from autoclave.ui_pyside.main_window import MainWindowFluent


def main():
    app = QApplication(sys.argv)
    window = MainWindowFluent()
    window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
    )
    window.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test de import**

```
python -c "from autoclave.ui_pyside.app import main; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```
git add src/autoclave/ui_pyside/app.py
git commit -m "feat: app.py — entry point standalone PySide6 fullscreen frameless"
```

---

## Task 3: Simplificar `MainWindowFluent` — eliminar gestión de subprocess tkinter

**Files:**
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consumes: nada nuevo
- Produces: `MainWindowFluent()` sin parámetros; `closeEvent` solo detiene el reloj

- [ ] **Step 1: Leer el archivo actual**

Leer `src/autoclave/ui_pyside/main_window.py` para ver el estado exacto.

- [ ] **Step 2: Eliminar imports de subprocess y sys**

Localizar y eliminar estas dos líneas del inicio del archivo:
```python
import subprocess
import sys
```

- [ ] **Step 3: Cambiar firma de `__init__`**

Localizar:
```python
    def __init__(self, tkinter_proc=None):
        super().__init__()
        self._tkinter_proc = tkinter_proc
```

Reemplazar con:
```python
    def __init__(self):
        super().__init__()
```

- [ ] **Step 4: Eliminar `_open_monitor()` completo**

Localizar y eliminar el método completo:
```python
    # ── Monitor tkinter ──────────────────────────────────────────────

    def _open_monitor(self) -> None:
        if self._tkinter_proc is None or self._tkinter_proc.poll() is not None:
            self._tkinter_proc = subprocess.Popen(
                [sys.executable, "-m", "autoclave.ui.main"],
            )
```

- [ ] **Step 5: Reemplazar `_build_footer()` — eliminar botón Monitor**

Localizar el método `_build_footer` completo y reemplazarlo con:

```python
    # ── Footer ────────────────────────────────────────────────────────

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background-color: #5789a7;")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 0, 20, 0)

        btn_salir = PushButton("Salir")
        btn_salir.clicked.connect(self.close)
        layout.addWidget(btn_salir)

        layout.addStretch()

        lbl_ver = QLabel("v1.0")
        lbl_ver.setStyleSheet("color: white;")
        layout.addWidget(lbl_ver)

        return footer
```

- [ ] **Step 6: Smoke test de import**

```
python -c "import autoclave.ui_pyside.main_window; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 7: Verificar suite de tests sin regresiones**

```
python -m pytest tests/ -q --tb=short
```

Expected: misma cantidad de tests pasando, sin nuevos fallos.

- [ ] **Step 8: Commit**

```
git add src/autoclave/ui_pyside/main_window.py
git commit -m "refactor: MainWindowFluent — eliminar gestión subprocess tkinter y botón Monitor"
```

---

## Task 4: Cablear botón settings en `InterfazPrincipal`

**Files:**
- Modify: `src/autoclave/ui/window/main_window.py`

**Interfaces:**
- Consumes: `autoclave.ui_pyside.app` (lanzado como subprocess vía `python -m`)
- Produces: `InterfazPrincipal._open_settings()`, `InterfazPrincipal._poll_settings()` — invocados por el botón settings y por `self.after()` respectivamente

- [ ] **Step 1: Leer el archivo**

Leer `src/autoclave/ui/window/main_window.py` para identificar la posición exacta de los imports, `__init__`, y `_build_footer`.

- [ ] **Step 2: Agregar imports de subprocess y sys**

Al inicio del archivo, después de `import logging`, agregar:
```python
import subprocess
import sys
```

El archivo debe quedar así al inicio:
```python
import time
import subprocess
import sys
import tkinter as tk
import customtkinter as ctk
import PIL.Image as Image
from PIL import ImageTk
import logging
```

- [ ] **Step 3: Agregar `self._settings_proc = None` en `__init__`**

En `__init__`, localizar el bloque de estado interno:
```python
        self.cycle_name        = self.ui_service.get_cycle_param("name") or "Cargando..."
        self._prev_machine_state = ""
        self._cycle_win          = None
        self._toast_widget       = None
```

Agregar `self._settings_proc = None` al final de ese bloque:
```python
        self.cycle_name        = self.ui_service.get_cycle_param("name") or "Cargando..."
        self._prev_machine_state = ""
        self._cycle_win          = None
        self._toast_widget       = None
        self._settings_proc      = None
```

- [ ] **Step 4: Agregar métodos `_open_settings` y `_poll_settings`**

Después del método `apagar_equipo` (antes del bloque `# ══ LOOP DE ACTUALIZACIÓN`), agregar:

```python
    # ══════════════════════════════════════════════════════════════════════════
    # MENÚ DE CONFIGURACIÓN (PySide6 como subprocess)
    # ══════════════════════════════════════════════════════════════════════════

    def _open_settings(self):
        if self._settings_proc and self._settings_proc.poll() is None:
            return  # ya abierto — ignorar doble click
        try:
            self.withdraw()
            self._settings_proc = subprocess.Popen(
                [sys.executable, "-m", "autoclave.ui_pyside.app"]
            )
            self.after(500, self._poll_settings)
        except OSError as e:
            logger.error("No se pudo lanzar el menú de configuración: %s", e)
            self.deiconify()

    def _poll_settings(self):
        if self._settings_proc and self._settings_proc.poll() is not None:
            self._settings_proc = None
            self.deiconify()
        else:
            self.after(500, self._poll_settings)
```

- [ ] **Step 5: Cablear `command=self._open_settings` en el botón settings de `_build_footer`**

Localizar en `_build_footer` el botón del engranaje (actualmente sin `command`):
```python
        ctk.CTkButton(pill, text="", image=self._img_settings,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)
```

Reemplazar con:
```python
        ctk.CTkButton(pill, text="", image=self._img_settings,
                      fg_color="transparent", hover_color="#406080",
                      command=self._open_settings,
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)
```

- [ ] **Step 6: Verificar sintaxis**

```
python -c "import ast; ast.parse(open('src/autoclave/ui/window/main_window.py').read()); print('sintaxis OK')"
```

Expected: `sintaxis OK`

- [ ] **Step 7: Smoke test de import**

```
python -c "from autoclave.ui.window.main_window import InterfazPrincipal; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 8: Ejecutar suite completa**

```
python -m pytest tests/ -q --tb=short
```

Expected: misma cantidad de tests pasando, sin nuevos fallos.

- [ ] **Step 9: Commit**

```
git add src/autoclave/ui/window/main_window.py
git commit -m "feat: botón settings abre menú PySide6 fullscreen, tkinter se oculta/reaparece"
```

---

## Self-Review

### Spec coverage

| Requisito spec | Task |
|---|---|
| Tkinter es ventana principal | Task 1 |
| Botón settings abre PySide6 | Task 4 |
| Tkinter se oculta al abrir settings | Task 4 (`withdraw()`) |
| Tkinter reaparece al cerrar settings | Task 4 (`_poll_settings` + `deiconify()`) |
| PySide6 fullscreen sin barra título | Task 2 (`FramelessWindowHint` + `showFullScreen()`) |
| Doble click ignorado | Task 4 (guard `poll() is None`) |
| Crash de PySide6 → tkinter reaparece | Task 4 (`poll() is not None` → `deiconify()`) |
| `Popen` falla → tkinter reaparece | Task 4 (`except OSError → deiconify()`) |
| Cleanup de `_settings_proc` al cerrar app | Task 1 (`on_close()` con `hasattr` guard) |
| Eliminar Monitor button de PySide6 | Task 3 |
| Eliminar `tkinter_proc` de `MainWindowFluent` | Task 3 |
