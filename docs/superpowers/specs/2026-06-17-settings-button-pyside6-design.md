# Spec — Botón Settings abre menú PySide6

**Fecha:** 2026-06-17
**Estado:** Aprobado

## Contexto

La ventana principal `InterfazPrincipal` (tkinter/customtkinter) es el punto de entrada de la aplicación. Su footer ya contiene un botón de settings (ícono de engranaje) sin comando asignado. El menú PySide6 (`MainWindowFluent`) existe pero actualmente se lanza como ventana primaria en `main.py`, lo cual es incorrecto.

El objetivo es invertir los roles: tkinter es la ventana principal permanente, y el menú PySide6 se abre únicamente al presionar el botón de settings.

## Requisitos

- Tkinter `InterfazPrincipal` es el punto de entrada y ventana principal.
- El botón settings (engranaje) del footer lanza el menú PySide6.
- Al abrir el menú PySide6: tkinter se oculta (`withdraw()`).
- Al cerrar el menú PySide6: tkinter reaparece (`deiconify()`).
- El menú PySide6 debe ser pantalla completa sin barra de título (`FramelessWindowHint` + `showFullScreen()`).
- Si el operador hace doble click en settings mientras ya está abierto, el segundo click se ignora.

## Arquitectura

```
python -m autoclave.main
  └─ InterfazPrincipal (tkinter, pantalla completa, ventana principal)
        └─ botón settings
                ├─ withdraw() tkinter
                ├─ Popen("autoclave.ui_pyside.app")
                └─ poll() cada 500 ms
                      └─ proc terminó → deiconify() tkinter
```

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `src/autoclave/main.py` | Revertir bloque 3 — lanzar `InterfazPrincipal` (tkinter), eliminar arranque PySide6 |
| `src/autoclave/ui/window/main_window.py` | Agregar `_open_settings()`, `_poll_settings()`, wiring del botón settings |
| `src/autoclave/ui_pyside/main_window.py` | Eliminar parámetro `tkinter_proc`; `closeEvent` solo detiene reloj |
| `src/autoclave/ui_pyside/app.py` | **Nuevo** — entry point standalone PySide6 |

## Detalle por componente

### `main.py` — bloque 3 revertido

El bloque 3 de `main.py` vuelve a lanzar tkinter directamente (idéntico a `ui/main.py`):

```python
# ── 3. Arrancar UI (tkinter) ──────────────────────────────────────────────
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

### `InterfazPrincipal` — settings integration

En `__init__`, agregar:
```python
self._settings_proc = None
```

Nuevos métodos:
```python
def _open_settings(self):
    if self._settings_proc and self._settings_proc.poll() is None:
        return  # ya abierto, ignorar doble click
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

Wiring del botón settings en `_build_footer()`:
```python
ctk.CTkButton(pill, text="", image=self._img_settings,
              fg_color="transparent", hover_color="#406080",
              command=self._open_settings,           # ← agregar este parámetro
              width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)
```

`InterfazPrincipal` necesita `import subprocess` y `import sys` al nivel del módulo (ya presentes en `ui/main.py`, verificar en `main_window.py`).

### `ui_pyside/app.py` — nuevo entry point

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

### `MainWindowFluent` — simplificación

- Eliminar parámetro `tkinter_proc` de `__init__` (y toda su lógica de subprocess).
- Eliminar `_open_monitor()` y el botón "Monitor" del footer (ya no aplica).
- `closeEvent` simplificado:
  ```python
  def closeEvent(self, event) -> None:
      self._clock_timer.stop()
      event.accept()
  ```
- `setMinimumSize(800, 600)` puede eliminarse (es fullscreen).
- El `setWindowTitle` puede mantenerse (invisible con FramelessWindowHint pero no daña).

## Manejo de errores

| Caso | Comportamiento |
|---|---|
| Doble click en settings | `poll() is None` → segundo click ignorado silenciosamente |
| PySide6 cierra con crash | `poll()` devuelve código ≠ None → `deiconify()` igual |
| `Popen` lanza `OSError` | `except OSError` → `deiconify()` inmediato + `logger.error` |
| Tkinter cierra mientras settings abierto | `on_close()` puede llamar `self._settings_proc.terminate()` antes de `app.destroy()` |

## Testing

- Sin tests unitarios nuevos — el comportamiento es integración de procesos.
- Smoke test de import: `python -c "from autoclave.ui_pyside.app import main; print('OK')"`.
- Suite completa (221 tests) debe seguir pasando sin modificaciones.
- Verificación manual: abrir app → click settings → tkinter oculta → menú PySide6 pantalla completa → cerrar menú → tkinter reaparece.
