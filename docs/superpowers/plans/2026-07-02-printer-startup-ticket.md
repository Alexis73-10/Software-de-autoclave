# Printer Startup Ticket — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Imprimir automáticamente un ticket de arranque en la impresora térmica cada vez que el sistema inicia, mostrando datos del equipo, versión del software y horas de último apagado y encendido actual.

**Architecture:** Módulo `printer/` independiente en el proceso principal (UI). Un hilo daemon escribe un timestamp cada 30 s para sobrevivir apagados abruptos por interruptor eléctrico. Al estar la UI visible (500 ms después del render) se lee ese timestamp, se formatea el ticket y se envía a la impresora Windows via `win32print` RAW.

**Tech Stack:** Python stdlib (`threading`, `json`, `importlib.metadata`), `pywin32` (`win32print`), tkinter `after()`.

## Global Constraints

- Python ≥ 3.11
- Ningún error de impresora interrumpe el arranque del autoclave — todos los errores se loguean con `logger.warning` y la ejecución continúa
- Ancho máximo del ticket: 48 caracteres por línea (papel 58 mm, Generic/Text Only)
- Codificación de bytes para la impresora: `cp437` con `errors="replace"`
- Nombre de la impresora en Windows: `"Generic / Text Only"` (verificar nombre exacto en el equipo real antes de implementar)
- El timestamp de último apagado se persiste en `data/last_shutdown.json`
- Si `last_shutdown.json` no existe o es corrupto → mostrar `"Primer encendido"` en el ticket
- No añadir comentarios de código salvo que el motivo no sea obvio

---

## Mapa de archivos

| Acción | Ruta |
|---|---|
| Crear | `src/autoclave/devices/printer/__init__.py` |
| Crear | `src/autoclave/devices/printer/heartbeat.py` |
| Crear | `src/autoclave/devices/printer/startup_ticket.py` |
| Crear | `src/autoclave/devices/printer/win32_printer.py` |
| Crear | `tests/test_startup_ticket.py` |
| Crear | `tests/test_heartbeat.py` |
| Crear | `tests/test_win32_printer.py` |
| Modificar | `pyproject.toml` — agregar `pywin32` a `dependencies` |
| Modificar | `src/autoclave/main.py` — iniciar heartbeat + pasar `profile` a la UI |
| Modificar | `src/autoclave/ui/window/main_window.py` — recibir `profile`, disparar print en `after(500)` |

---

## Task 1: Dependencia pywin32 + esqueleto del paquete printer

**Files:**
- Modify: `pyproject.toml:16-27`
- Create: `src/autoclave/devices/printer/__init__.py`

**Interfaces:**
- Produces: paquete `autoclave.devices.printer` importable; `win32print` disponible en el entorno

- [ ] **Step 1: Agregar pywin32 a dependencias**

En `pyproject.toml`, dentro del bloque `dependencies`, añadir `"pywin32"` al final de la lista:

```toml
dependencies = [
  "pyserial",
  "tk",
  "pillow",
  "PyYAML",
  "SQLAlchemy",
  "pydantic",
  "PySide6",
  "PySide6-Fluent-Widgets[full]",
  "pyqtgraph",
  "keyring",
  "pywin32",
]
```

- [ ] **Step 2: Crear `__init__.py` vacío**

Crear `src/autoclave/devices/printer/__init__.py` con contenido vacío (solo el archivo, sin contenido).

- [ ] **Step 3: Instalar la dependencia**

```
pip install -e .
```

Expected: instalación exitosa, sin errores.

- [ ] **Step 4: Verificar que win32print importa**

```
python -c "import win32print; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```
git add pyproject.toml src/autoclave/devices/printer/__init__.py
git commit -m "feat: agregar pywin32 y esqueleto de paquete printer"
```

---

## Task 2: `startup_ticket.py` — formateador puro con TDD

**Files:**
- Create: `src/autoclave/devices/printer/startup_ticket.py`
- Test: `tests/test_startup_ticket.py`

**Interfaces:**
- Consumes: `InstallationProfile` de `autoclave.installation.profile` (campos: `model_id: str`, `serial_number: str`, `equipment_class: EquipmentClass`); `EquipmentClass` de `autoclave.installation.equipment`
- Produces: `format_startup_ticket(profile, version: str, last_shutdown: datetime | None, startup_time: datetime) -> str`

- [ ] **Step 1: Escribir los tests**

Crear `tests/test_startup_ticket.py`:

```python
from datetime import datetime
from unittest.mock import MagicMock
from autoclave.installation.equipment import EquipmentClass


def _profile():
    p = MagicMock()
    p.model_id = "MESA_B"
    p.serial_number = "AUT-2024-001"
    p.equipment_class = EquipmentClass.MESA_B
    return p


def test_ticket_contiene_modelo():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "MESA_B" in text


def test_ticket_contiene_serie():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "AUT-2024-001" in text


def test_ticket_contiene_version():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "0.4.0" in text


def test_ticket_contiene_hora_encendido():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "10:47:23" in text


def test_ticket_contiene_hora_apagado():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "10:15:08" in text


def test_ticket_primer_encendido_cuando_none():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        None,
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "Primer encendido" in text


def test_ninguna_linea_supera_48_chars():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    for linea in text.splitlines():
        assert len(linea) <= 48, f"Línea demasiado larga ({len(linea)}): {linea!r}"
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```
pytest tests/test_startup_ticket.py -v
```

Expected: `ImportError` o `ModuleNotFoundError` — el módulo aún no existe.

- [ ] **Step 3: Implementar `startup_ticket.py`**

Crear `src/autoclave/devices/printer/startup_ticket.py`:

```python
from datetime import datetime
from autoclave.installation.profile import InstallationProfile

_W   = 48
_SEP = "=" * _W
_DIV = "-" * _W


def format_startup_ticket(
    profile: InstallationProfile,
    version: str,
    last_shutdown: datetime | None,
    startup_time: datetime,
) -> str:
    apagado = (
        last_shutdown.strftime("%Y-%m-%d  %H:%M:%S")
        if last_shutdown is not None
        else "Primer encendido"
    )
    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE".center(_W),
        _SEP,
        f"{'Modelo:':<16}{profile.model_id}",
        f"{'Serie:':<16}{profile.serial_number}",
        f"{'Clase:':<16}{profile.equipment_class.value}",
        f"{'Software:':<16}v{version}",
        _DIV,
        f"{'ENCENDIDO':<16}{startup_time.strftime('%Y-%m-%d  %H:%M:%S')}",
        f"{'APAGADO':<16}{apagado}",
        _DIV,
        "Sistema listo".center(_W),
        _SEP,
        "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Ejecutar tests y verificar que pasan**

```
pytest tests/test_startup_ticket.py -v
```

Expected: 7 tests en PASSED.

- [ ] **Step 5: Commit**

```
git add src/autoclave/devices/printer/startup_ticket.py tests/test_startup_ticket.py
git commit -m "feat: agregar formateador de ticket de arranque con tests"
```

---

## Task 3: `heartbeat.py` — persistencia de timestamp

**Files:**
- Create: `src/autoclave/devices/printer/heartbeat.py`
- Test: `tests/test_heartbeat.py`

**Interfaces:**
- Produces:
  - `write_timestamp(path: Path = _DEFAULT_FILE) -> None`
  - `read_last_shutdown(path: Path = _DEFAULT_FILE) -> datetime | None`
  - `start(interval: int = 30, path: Path = _DEFAULT_FILE) -> None`

- [ ] **Step 1: Escribir tests**

Crear `tests/test_heartbeat.py`:

```python
import json
from datetime import datetime
from pathlib import Path


def test_write_timestamp_crea_archivo(tmp_path):
    from autoclave.devices.printer.heartbeat import write_timestamp
    p = tmp_path / "last_shutdown.json"
    write_timestamp(p)
    assert p.exists()


def test_write_timestamp_es_iso_valido(tmp_path):
    from autoclave.devices.printer.heartbeat import write_timestamp
    p = tmp_path / "last_shutdown.json"
    write_timestamp(p)
    data = json.loads(p.read_text())
    dt = datetime.fromisoformat(data["timestamp"])
    assert isinstance(dt, datetime)


def test_read_last_shutdown_parsea_fecha(tmp_path):
    from autoclave.devices.printer.heartbeat import read_last_shutdown
    p = tmp_path / "last_shutdown.json"
    p.write_text(json.dumps({"timestamp": "2026-07-02T10:15:08"}))
    dt = read_last_shutdown(p)
    assert dt == datetime(2026, 7, 2, 10, 15, 8)


def test_read_last_shutdown_ausente_retorna_none(tmp_path):
    from autoclave.devices.printer.heartbeat import read_last_shutdown
    p = tmp_path / "no_existe.json"
    assert read_last_shutdown(p) is None


def test_read_last_shutdown_corrupto_retorna_none(tmp_path):
    from autoclave.devices.printer.heartbeat import read_last_shutdown
    p = tmp_path / "last_shutdown.json"
    p.write_text("esto-no-es-json-{{{")
    assert read_last_shutdown(p) is None
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```
pytest tests/test_heartbeat.py -v
```

Expected: `ImportError` — módulo no existe.

- [ ] **Step 3: Implementar `heartbeat.py`**

Crear `src/autoclave/devices/printer/heartbeat.py`:

```python
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_FILE = Path(__file__).resolve().parents[4] / "data" / "last_shutdown.json"


def write_timestamp(path: Path = _DEFAULT_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"timestamp": datetime.now().isoformat()}),
        encoding="utf-8",
    )


def read_last_shutdown(path: Path = _DEFAULT_FILE) -> datetime | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return datetime.fromisoformat(data["timestamp"])
    except Exception:
        return None


def _tick(interval: int, path: Path) -> None:
    try:
        write_timestamp(path)
    except Exception as exc:
        logger.warning("heartbeat: error al escribir timestamp: %s", exc)
    finally:
        t = threading.Timer(interval, _tick, args=(interval, path))
        t.daemon = True
        t.start()


def start(interval: int = 30, path: Path = _DEFAULT_FILE) -> None:
    _tick(interval, path)
```

- [ ] **Step 4: Ejecutar tests y verificar que pasan**

```
pytest tests/test_heartbeat.py -v
```

Expected: 5 tests en PASSED.

- [ ] **Step 5: Commit**

```
git add src/autoclave/devices/printer/heartbeat.py tests/test_heartbeat.py
git commit -m "feat: agregar heartbeat de persistencia de timestamp de apagado"
```

---

## Task 4: `win32_printer.py` — driver RAW para Windows

**Files:**
- Create: `src/autoclave/devices/printer/win32_printer.py`
- Test: `tests/test_win32_printer.py`

**Interfaces:**
- Produces: `print_raw(text: str, printer_name: str = "Generic / Text Only") -> None`

- [ ] **Step 1: Escribir test del path de error (pywin32 ausente)**

Crear `tests/test_win32_printer.py`:

```python
import sys
import logging


def test_print_raw_sin_pywin32_loguea_warning(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "win32print", None)
    from autoclave.devices.printer.win32_printer import print_raw
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.win32_printer"):
        print_raw("texto de prueba")
    assert "win32print no disponible" in caplog.text
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

```
pytest tests/test_win32_printer.py -v
```

Expected: `ImportError` — módulo no existe.

- [ ] **Step 3: Implementar `win32_printer.py`**

Crear `src/autoclave/devices/printer/win32_printer.py`:

```python
import logging

logger = logging.getLogger(__name__)

PRINTER_NAME = "Generic / Text Only"


def print_raw(text: str, printer_name: str = PRINTER_NAME) -> None:
    try:
        import win32print
    except ImportError:
        logger.warning("win32print no disponible — impresión omitida")
        return

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        logger.warning("print_raw: no se pudo abrir impresora '%s': %s", printer_name, exc)
        return

    try:
        win32print.StartDocPrinter(handle, 1, ("Autoclave", None, "RAW"))
        win32print.WritePrinter(handle, text.encode("cp437", errors="replace"))
        win32print.EndDocPrinter(handle)
    except Exception as exc:
        logger.warning("print_raw: error al enviar datos: %s", exc)
    finally:
        win32print.ClosePrinter(handle)
```

- [ ] **Step 4: Ejecutar test y verificar que pasa**

```
pytest tests/test_win32_printer.py -v
```

Expected: 1 test en PASSED.

- [ ] **Step 5: Ejecutar toda la suite para detectar regresiones**

```
pytest --tb=short -q
```

Expected: todos los tests previos siguen en PASSED.

- [ ] **Step 6: Commit**

```
git add src/autoclave/devices/printer/win32_printer.py tests/test_win32_printer.py
git commit -m "feat: agregar driver win32 de impresion RAW con manejo de errores"
```

---

## Task 5: Integración — main.py + InterfazPrincipal

**Files:**
- Modify: `src/autoclave/main.py`
- Modify: `src/autoclave/ui/window/main_window.py`

**Interfaces:**
- Consumes:
  - `heartbeat.start(interval=30)` de `autoclave.devices.printer.heartbeat`
  - `heartbeat.read_last_shutdown()` de `autoclave.devices.printer.heartbeat`
  - `format_startup_ticket(profile, version, last_shutdown, startup_time)` de `autoclave.devices.printer.startup_ticket`
  - `print_raw(text)` de `autoclave.devices.printer.win32_printer`
  - `InstallationProfile` con campos `model_id`, `serial_number`, `equipment_class`

- [ ] **Step 1: Iniciar heartbeat en `main.py`**

En `src/autoclave/main.py`, añadir el import al inicio del bloque de imports existentes:

```python
from autoclave.devices.printer import heartbeat
```

Luego, inmediatamente después del bloque que llama a `wait_for_backend` (alrededor de la línea 98, antes de los imports de UI), agregar:

```python
    # ── 2b. Iniciar heartbeat de impresora ────────────────────────────────────
    heartbeat.start(interval=30)
```

El bloque queda así (extracto relevante del archivo):

```python
    # ── 2. Iniciar backend ────────────────────────────────────────────────
    backend_process = None
    if SOURCE_DOOR == 1:
        if is_backend_alive():
            logger.info("Backend ya estaba corriendo")
        else:
            logger.info("Iniciando backend...")
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "autoclave.backend.main"],
                stdout=subprocess.DEVNULL,
                stderr=None,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if not wait_for_backend(process=backend_process, max_wait=40):
                logger.error("Backend no respondió — la UI arrancará sin datos")
    else:
        logger.info("PC puerta 2 — esperando backend en red...")
        if not wait_for_backend(max_wait=40):
            logger.warning("Backend no disponible, la UI seguirá intentando...")

    # ── 2b. Iniciar heartbeat de impresora ────────────────────────────────────
    heartbeat.start(interval=30)

    # ── 3. Arrancar UI (tkinter) ────────────────────────────────────────────
    from autoclave.ui.service_ui.backend_client import BackendClient
    ...
```

- [ ] **Step 2: Pasar `profile` a `InterfazPrincipal` en `main.py`**

En `main.py`, cambiar la construcción de `InterfazPrincipal` (línea ~128) para añadir el parámetro `profile`:

```python
    app = InterfazPrincipal(
        ui_service=ui_service,
        door_commands=door_commands,
        on_shutdown=on_close,
        source_door=SOURCE_DOOR,
        profile=profile,
    )
```

- [ ] **Step 3: Agregar `profile` a `InterfazPrincipal.__init__`**

En `src/autoclave/ui/window/main_window.py`, cambiar la firma del `__init__` (línea 38):

```python
    def __init__(self, ui_service, door_commands, on_shutdown=None, source_door=1, profile=None):
```

Añadir inmediatamente después de `self._source_door = source_door` (línea 43):

```python
        self._profile = profile
```

- [ ] **Step 4: Disparar impresión con `after()`**

En `InterfazPrincipal.__init__`, añadir después de `self._schedule_update()` (línea 71):

```python
        self.after(500, self._print_startup_ticket)
```

- [ ] **Step 5: Implementar `_print_startup_ticket`**

Añadir el método a `InterfazPrincipal`, después del método `_schedule_update` (línea ~103):

```python
    def _print_startup_ticket(self):
        import importlib.metadata
        from datetime import datetime
        from autoclave.devices.printer.heartbeat import read_last_shutdown
        from autoclave.devices.printer.startup_ticket import format_startup_ticket
        from autoclave.devices.printer.win32_printer import print_raw

        try:
            version = importlib.metadata.version("autoclave")
            last_shutdown = read_last_shutdown()
            text = format_startup_ticket(
                self._profile, version, last_shutdown, datetime.now()
            )
            print_raw(text)
            logger.info("Ticket de arranque enviado a impresora")
        except Exception as exc:
            logger.warning("_print_startup_ticket: error inesperado: %s", exc)
```

- [ ] **Step 6: Verificar la suite de tests**

```
pytest --tb=short -q
```

Expected: todos los tests en PASSED, sin nuevas fallas.

- [ ] **Step 7: Verificación manual en el equipo**

1. Encender el autoclave
2. Esperar que la UI cargue completamente
3. Verificar que la impresora imprime el ticket con: modelo, serie, clase, versión, hora de encendido y hora de apagado (o "Primer encendido" en el primer arranque)
4. Apagar el equipo por el interruptor eléctrico
5. Encender de nuevo y verificar que ahora "APAGADO" muestra la hora aproximada del apagado anterior

> **Nota sobre el nombre de la impresora:** Si el ticket no sale, verificar el nombre exacto en Windows:
> Panel de Control → Dispositivos e impresoras → clic derecho en la impresora → Ver propiedades de impresora. El nombre que aparece en la barra de título es el que debe ir en `PRINTER_NAME` de `win32_printer.py`.

- [ ] **Step 8: Commit**

```
git add src/autoclave/main.py src/autoclave/ui/window/main_window.py
git commit -m "feat: integrar ticket de arranque en UI — heartbeat + print al encender"
```
