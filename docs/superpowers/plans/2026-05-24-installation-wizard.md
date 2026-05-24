# Installation Wizard & Profile Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete installation wizard (Tkinter) that validates an offline activation code, collects machine data, and stores a locked profile; detect and reject missing or corrupt profiles on every startup.

**Architecture:** The wizard is a standalone `tk.Tk()` window launched in `ui/main.py` before the backend process starts. Activation codes are 12-char HMAC-SHA256 tokens derived from the serial number + an embedded secret. The profile is validated on every `load()` call; a `ProfileValidationError` is raised on corruption, and `bootstrap.py` surfaces it to the startup flow. `SOURCE_DOOR` in `ui/main.py` is replaced by `profile.door_id` so the profile is the single source of truth.

**Tech Stack:** Python stdlib (`hmac`, `hashlib`, `base64`, `json`, `dataclasses`), `tkinter` + `ttk` for wizard UI, `pytest` for tests.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/autoclave/installation/activation.py` | **CREATE** | HMAC code generation and validation |
| `src/autoclave/installation/profile.py` | **MODIFY** | Add `door_type`, `equipment_type`; add `ProfileValidationError` + `validate_profile_data()` |
| `src/autoclave/installation/storage.py` | **MODIFY** | Call `validate_profile_data()` on `load()`; handle `ProfileCorruptError` |
| `src/autoclave/installation/wizard.py` | **REPLACE** | Real Tkinter 2-step wizard |
| `src/autoclave/installation/bootstrap.py` | **MODIFY** | Return `None` on corrupt profile (with log), not just missing |
| `src/autoclave/ui/main.py` | **MODIFY** | Call bootstrap at startup; launch wizard if needed; use `profile.door_id` |
| `tests/test_activation.py` | **CREATE** | Tests for code generation and validation |
| `tests/test_profile_validation.py` | **CREATE** | Tests for validation and corruption detection |

---

## Task 1: Activation Code Module

**Files:**
- Create: `src/autoclave/installation/activation.py`
- Create: `tests/test_activation.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_activation.py
from autoclave.installation.activation import generate_code, validate_code

def test_generate_code_is_deterministic():
    assert generate_code("SN123456") == generate_code("SN123456")

def test_generate_code_length():
    assert len(generate_code("SN123456")) == 12

def test_validate_code_correct():
    code = generate_code("SN123456")
    assert validate_code("SN123456", code) is True

def test_validate_code_wrong_code():
    assert validate_code("SN123456", "WRONGCODE123") is False

def test_validate_code_case_insensitive():
    code = generate_code("SN123456")
    assert validate_code("sn123456", code.lower()) is True

def test_validate_code_different_serial():
    code = generate_code("SN123456")
    assert validate_code("SN999999", code) is False

def test_validate_code_strips_whitespace():
    code = generate_code("SN123456")
    assert validate_code("SN123456", f"  {code}  ") is True
```

- [ ] **Step 2: Run to confirm FAIL**

```
pytest tests/test_activation.py -v
```
Expected: `ModuleNotFoundError: No module named 'autoclave.installation.activation'`

- [ ] **Step 3: Create `activation.py`**

```python
# src/autoclave/installation/activation.py
import hmac
import hashlib
import base64

_SECRET = b"EspecifikaAutoclave\xf3\x9a\x11\x2c\x87\xde"

def generate_code(serial_number: str) -> str:
    """Return a 12-char uppercase activation code for the given serial number."""
    key = serial_number.strip().upper().encode()
    digest = hmac.new(_SECRET, key, hashlib.sha256).digest()
    return base64.b32encode(digest)[:12].decode()

def validate_code(serial_number: str, code: str) -> bool:
    """Return True if code is the valid activation code for serial_number."""
    expected = generate_code(serial_number)
    return hmac.compare_digest(expected, code.strip().upper()[:12])
```

- [ ] **Step 4: Run to confirm PASS**

```
pytest tests/test_activation.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/autoclave/installation/activation.py tests/test_activation.py
git commit -m "feat: add offline HMAC activation code system"
```

---

## Task 2: Profile Schema + Validation

**Files:**
- Modify: `src/autoclave/installation/profile.py`
- Create: `tests/test_profile_validation.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_profile_validation.py
import pytest
from autoclave.installation.profile import validate_profile_data, ProfileValidationError

VALID_DATA = {
    "machine_id": "ACV-2026-SN001",
    "model_id": "MX-500",
    "serial_number": "SN001",
    "door_count": 2,
    "door_type": "advanced",
    "equipment_type": "horizontal",
    "drying_type": "vacuum",
    "door_id": 1,
    "role": "operator_front",
    "created_at": "2026-01-01T00:00:00",
    "locked": True,
}

def test_valid_profile_returns_no_errors():
    assert validate_profile_data(VALID_DATA) == []

def test_missing_field_reported():
    data = {**VALID_DATA}
    del data["serial_number"]
    errors = validate_profile_data(data)
    assert any("serial_number" in e for e in errors)

def test_wrong_type_reported():
    data = {**VALID_DATA, "door_count": "dos"}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)

def test_invalid_door_count():
    data = {**VALID_DATA, "door_count": 5}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)

def test_invalid_door_type():
    data = {**VALID_DATA, "door_type": "giratoria"}
    errors = validate_profile_data(data)
    assert any("door_type" in e for e in errors)

def test_invalid_equipment_type():
    data = {**VALID_DATA, "equipment_type": "diagonal"}
    errors = validate_profile_data(data)
    assert any("equipment_type" in e for e in errors)

def test_invalid_drying_type():
    data = {**VALID_DATA, "drying_type": "solar"}
    errors = validate_profile_data(data)
    assert any("drying_type" in e for e in errors)

def test_profile_validation_error_contains_messages():
    errors = ["campo faltante: 'serial_number'"]
    exc = ProfileValidationError(errors)
    assert "serial_number" in str(exc)
    assert exc.errors == errors
```

- [ ] **Step 2: Run to confirm FAIL**

```
pytest tests/test_profile_validation.py -v
```
Expected: `ImportError` — `validate_profile_data` and `ProfileValidationError` don't exist yet.

- [ ] **Step 3: Update `profile.py`**

Replace the full file:

```python
# src/autoclave/installation/profile.py
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class Role(Enum):
    OPERATOR_FRONT = "operator_front"
    OPERATOR_BACK  = "operator_back"
    SERVICE        = "service"


class ProfileValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Perfil de instalación inválido: {'; '.join(errors)}")


@dataclass
class InstallationProfile:
    machine_id:     str
    model_id:       str
    serial_number:  str
    door_count:     int
    door_type:      str       # "simple" | "advanced"
    equipment_type: str       # "horizontal" | "vertical"
    drying_type:    str       # "vacuum" | "gravity"
    door_id:        int       # which door this PC controls (1 or 2)
    role:           Role
    created_at:     datetime
    locked:         bool = True


_REQUIRED_TYPES: dict[str, type] = {
    "machine_id":     str,
    "model_id":       str,
    "serial_number":  str,
    "door_count":     int,
    "door_type":      str,
    "equipment_type": str,
    "drying_type":    str,
    "door_id":        int,
    "role":           str,
    "created_at":     str,
    "locked":         bool,
}

_VALID_VALUES: dict[str, set] = {
    "door_count":     {1, 2},
    "door_type":      {"simple", "advanced"},
    "equipment_type": {"horizontal", "vertical"},
    "drying_type":    {"vacuum", "gravity"},
}


def validate_profile_data(data: dict) -> list[str]:
    """
    Validate raw profile dict. Returns a list of error strings.
    Empty list means the data is valid.
    """
    errors: list[str] = []

    for field, expected_type in _REQUIRED_TYPES.items():
        if field not in data:
            errors.append(f"campo faltante: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"tipo incorrecto en '{field}': "
                f"esperado {expected_type.__name__}, "
                f"recibido {type(data[field]).__name__}"
            )

    for field, valid in _VALID_VALUES.items():
        if field in data and isinstance(data[field], (str, int)) and data[field] not in valid:
            errors.append(f"valor inválido en '{field}': '{data[field]}' no está en {valid}")

    return errors
```

- [ ] **Step 4: Run to confirm PASS**

```
pytest tests/test_profile_validation.py -v
```
Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/autoclave/installation/profile.py tests/test_profile_validation.py
git commit -m "feat: add profile schema (door_type, equipment_type) and validation"
```

---

## Task 3: Storage + Bootstrap with Corruption Detection

**Files:**
- Modify: `src/autoclave/installation/storage.py`
- Modify: `src/autoclave/installation/bootstrap.py`

- [ ] **Step 1: Update `storage.py`** to validate on `load()` and handle new fields

```python
# src/autoclave/installation/storage.py
import json
import logging
from pathlib import Path
from datetime import datetime
from .profile import InstallationProfile, Role, ProfileValidationError, validate_profile_data

logger = logging.getLogger(__name__)

INSTALLATION_FILE = Path(__file__).resolve().parents[3] / "installation_profile.json"


def exists() -> bool:
    return INSTALLATION_FILE.exists()


def load() -> InstallationProfile:
    """
    Load and validate the installation profile.
    Raises ProfileValidationError if the file is missing fields or has bad values.
    Raises json.JSONDecodeError if the file is not valid JSON.
    """
    data = json.loads(INSTALLATION_FILE.read_text(encoding="utf-8"))

    errors = validate_profile_data(data)
    if errors:
        raise ProfileValidationError(errors)

    return InstallationProfile(
        machine_id=data["machine_id"],
        model_id=data["model_id"],
        serial_number=data["serial_number"],
        door_count=data["door_count"],
        door_type=data["door_type"],
        equipment_type=data["equipment_type"],
        drying_type=data["drying_type"],
        door_id=data["door_id"],
        role=Role(data["role"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        locked=data["locked"],
    )


def save(profile: InstallationProfile):
    if profile.locked and exists():
        raise RuntimeError("El perfil de instalación está bloqueado y no puede modificarse")

    INSTALLATION_FILE.write_text(json.dumps({
        "machine_id":     profile.machine_id,
        "model_id":       profile.model_id,
        "serial_number":  profile.serial_number,
        "door_count":     profile.door_count,
        "door_type":      profile.door_type,
        "equipment_type": profile.equipment_type,
        "drying_type":    profile.drying_type,
        "door_id":        profile.door_id,
        "role":           profile.role.value,
        "created_at":     profile.created_at.isoformat(),
        "locked":         profile.locked,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 2: Update `bootstrap.py`** to handle corrupt profiles

```python
# src/autoclave/installation/bootstrap.py
import json
import logging
from .storage import exists, load
from .profile import ProfileValidationError

logger = logging.getLogger(__name__)


def get_installation_profile():
    """
    Return the InstallationProfile if valid, or None if:
    - the file doesn't exist (new installation needed)
    - the file is corrupt or missing fields (re-installation needed)
    Logs a warning in the corrupt case.
    """
    if not exists():
        return None

    try:
        return load()
    except (ProfileValidationError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Perfil de instalación corrupto o inválido: %s", e)
        return None
```

- [ ] **Step 3: Run existing tests to verify nothing broke**

```
pytest tests/test_activation.py tests/test_profile_validation.py -v
```
Expected: all PASS.

- [ ] **Step 4: Commit**

```
git add src/autoclave/installation/storage.py src/autoclave/installation/bootstrap.py
git commit -m "feat: validate profile on load, return None on corrupt file"
```

---

## Task 4: Installation Wizard UI

**Files:**
- Replace: `src/autoclave/installation/wizard.py`

- [ ] **Step 1: Replace `wizard.py` with the real Tkinter wizard**

```python
# src/autoclave/installation/wizard.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from .profile import InstallationProfile, Role
from .storage import save
from .activation import validate_code

logger = logging.getLogger(__name__)


def launch_installation_wizard() -> bool:
    """
    Show the two-step installation wizard.
    Returns True if installation completed successfully, False if cancelled.
    """
    result = {"done": False}

    root = tk.Tk()
    root.title("Instalación — Autoclave Especifika")
    root.resizable(False, False)
    root.grab_set()

    # ── Variables ──────────────────────────────────────────────────────────
    serial_var         = tk.StringVar()
    code_var           = tk.StringVar()
    model_var          = tk.StringVar()
    door_count_var     = tk.IntVar(value=2)
    door_type_var      = tk.StringVar(value="advanced")
    equipment_type_var = tk.StringVar(value="horizontal")
    drying_type_var    = tk.StringVar(value="vacuum")
    door_id_var        = tk.IntVar(value=1)

    # ── PASO 1: Código de activación ───────────────────────────────────────
    frame1 = tk.Frame(root, padx=30, pady=20)

    tk.Label(
        frame1, text="Instalación del equipo",
        font=("", 14, "bold")
    ).pack(pady=(0, 20))

    tk.Label(frame1, text="Número de serie del equipo:", anchor="w").pack(fill="x")
    tk.Entry(frame1, textvariable=serial_var, width=35).pack(fill="x", pady=(0, 12))

    tk.Label(frame1, text="Código de activación:", anchor="w").pack(fill="x")
    tk.Entry(frame1, textvariable=code_var, width=35).pack(fill="x", pady=(0, 16))

    err1 = tk.Label(frame1, text="", fg="red")
    err1.pack()

    def ir_a_paso2():
        serial = serial_var.get().strip()
        code   = code_var.get().strip()
        if not serial:
            err1.config(text="Ingrese el número de serie")
            return
        if not code:
            err1.config(text="Ingrese el código de activación")
            return
        if not validate_code(serial, code):
            err1.config(text="Código de activación incorrecto")
            logger.warning("Intento de instalación con código inválido para serie '%s'", serial)
            return
        err1.config(text="")
        frame1.pack_forget()
        frame2.pack()

    tk.Button(frame1, text="Siguiente →", command=ir_a_paso2, width=20).pack(pady=(10, 0))

    # ── PASO 2: Datos del equipo ───────────────────────────────────────────
    frame2 = tk.Frame(root, padx=30, pady=20)

    tk.Label(
        frame2, text="Datos del equipo",
        font=("", 14, "bold")
    ).pack(pady=(0, 16))

    def fila(label_text, widget_factory):
        f = tk.Frame(frame2)
        tk.Label(f, text=label_text, width=22, anchor="w").pack(side="left")
        w = widget_factory(f)
        w.pack(side="left", fill="x", expand=True)
        f.pack(fill="x", pady=4)

    fila("Modelo:", lambda p: tk.Entry(p, textvariable=model_var))
    fila("N° de puertas:", lambda p: ttk.Spinbox(
        p, from_=1, to=2, textvariable=door_count_var, width=6, state="readonly"))
    fila("Tipo de puerta:", lambda p: ttk.Combobox(
        p, textvariable=door_type_var,
        values=["simple", "advanced"], state="readonly"))
    fila("Tipo de equipo:", lambda p: ttk.Combobox(
        p, textvariable=equipment_type_var,
        values=["horizontal", "vertical"], state="readonly"))
    fila("Tipo de secado:", lambda p: ttk.Combobox(
        p, textvariable=drying_type_var,
        values=["vacuum", "gravity"], state="readonly"))
    fila("Puerta de este PC (1/2):", lambda p: ttk.Spinbox(
        p, from_=1, to=2, textvariable=door_id_var, width=6, state="readonly"))

    err2 = tk.Label(frame2, text="", fg="red")
    err2.pack(pady=(10, 0))

    def instalar():
        model = model_var.get().strip()
        if not model:
            err2.config(text="El modelo es obligatorio")
            return

        serial = serial_var.get().strip().upper()
        profile = InstallationProfile(
            machine_id=f"ACV-{datetime.utcnow().strftime('%Y')}-{serial}",
            model_id=model,
            serial_number=serial,
            door_count=door_count_var.get(),
            door_type=door_type_var.get(),
            equipment_type=equipment_type_var.get(),
            drying_type=drying_type_var.get(),
            door_id=door_id_var.get(),
            role=Role.OPERATOR_FRONT,
            created_at=datetime.utcnow(),
            locked=True,
        )

        try:
            save(profile)
        except Exception as e:
            err2.config(text=f"Error al guardar: {e}")
            logger.error("Error guardando perfil de instalación: %s", e)
            return

        result["done"] = True
        logger.info("Instalación completada para serie '%s'", serial)
        messagebox.showinfo(
            "Instalación completada",
            "El equipo ha sido registrado correctamente.\n"
            "Reinicie el software para continuar."
        )
        root.destroy()

    tk.Button(
        frame2, text="Instalar", command=instalar,
        width=20, bg="#27ae60", fg="white", font=("", 10, "bold")
    ).pack(pady=(14, 0))

    frame1.pack()
    root.mainloop()

    return result["done"]
```

- [ ] **Step 2: Commit**

```
git add src/autoclave/installation/wizard.py
git commit -m "feat: replace wizard stub with real Tkinter 2-step installation wizard"
```

---

## Task 5: Startup Integration

**Files:**
- Modify: `src/autoclave/ui/main.py`

- [ ] **Step 1: Update `ui/main.py`** — add bootstrap check at the start of `main()` and replace hardcoded `SOURCE_DOOR` with `profile.door_id`

Replace the top of `main.py` — the `BACKEND_URL` / `SOURCE_DOOR` block and the beginning of `main()`:

```python
# src/autoclave/ui/main.py
import logging
import subprocess
import sys
import os
import time
import requests

from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.wizard import launch_installation_wizard
from autoclave.ui.window.main_window import InterfazPrincipal
from autoclave.ui.service_ui.backend_client import BackendClient
from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
from autoclave.services.domain.puertas.door_command_service import DoorCommandService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000"


def is_backend_alive(timeout=1):
    try:
        r = requests.get(f"{BACKEND_URL}/status", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def wait_for_backend(process=None, max_wait=40):
    logger.info("Esperando backend...")
    start = time.time()
    while time.time() - start < max_wait:
        if process is not None and process.poll() is not None:
            logger.error("El backend terminó inesperadamente (código %s)", process.returncode)
            return False
        if is_backend_alive():
            logger.info("Backend disponible (%.1fs)", time.time() - start)
            return True
        time.sleep(0.5)
    logger.error("Backend no respondió en %ds", max_wait)
    return False


def main():
    # ── 1. Verificar instalación ───────────────────────────────────────────
    profile = get_installation_profile()
    if profile is None:
        logger.info("Perfil de instalación no encontrado o inválido — iniciando wizard")
        completed = launch_installation_wizard()
        if not completed:
            logger.error("Instalación requerida para continuar. Cerrando.")
            sys.exit(1)
        profile = get_installation_profile()
        if profile is None:
            logger.error("Error crítico: perfil sigue inválido tras wizard. Cerrando.")
            sys.exit(1)

    SOURCE_DOOR = profile.door_id
    logger.info("Perfil cargado — serie: %s | puerta: %s", profile.serial_number, SOURCE_DOOR)

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

    # ── 3. Arrancar UI ────────────────────────────────────────────────────
    backend      = BackendClient(BACKEND_URL)
    ui_service   = UIServiceBackend(backend)
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
            logger.info("Deteniendo backend...")
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


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to make sure nothing regressed**

```
pytest tests/test_activation.py tests/test_profile_validation.py -v
```
Expected: all PASS.

- [ ] **Step 3: Commit**

```
git add src/autoclave/ui/main.py
git commit -m "feat: integrate installation check at startup, SOURCE_DOOR from profile"
```

---

## Self-Review Checklist

- [x] **Activation code**: Task 1 — `generate_code` + `validate_code` with HMAC-SHA256
- [x] **Profile fields**: Task 2 — added `door_type`, `equipment_type` to `InstallationProfile`
- [x] **Validation**: Task 2 — `validate_profile_data()` checks types, presence, and allowed values
- [x] **Corruption detection**: Task 3 — `load()` raises `ProfileValidationError`; `bootstrap` catches it and returns `None`
- [x] **Wizard UI**: Task 4 — 2-step Tkinter wizard with step 1 (code) and step 2 (data)
- [x] **Startup wiring**: Task 5 — `ui/main.py` checks profile before backend
- [x] **SOURCE_DOOR from profile**: Task 5 — `profile.door_id` replaces hardcoded constant
- [x] **Type consistency**: `InstallationProfile.door_type` and `equipment_type` defined in Task 2 and used in Tasks 3 and 4
- [x] **No placeholders**: all steps contain real code
