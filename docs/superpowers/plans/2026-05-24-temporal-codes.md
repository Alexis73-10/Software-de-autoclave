# Temporal Codes + Clock Guard + Web Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static HMAC activation code with two date-bound codes (installation + factory key) that expire automatically each day, add an anti-rollback clock guard, and create an internal web app to generate both codes.

**Architecture:** `activation.py` gains two independent HMAC functions — each uses a different secret and includes the ISO date in the message, so the same serial produces a different code every day and installation codes can never be used as factory keys. `clock_guard.py` is a single pure function that compares today's date against `profile.created_at`; it is injected into `bootstrap.py` so the main app raises a typed exception that shows a clear error dialog. The web app is a standalone FastAPI script (`tools/generador/app.py`) that imports from the same `activation.py`, so code generation logic lives in exactly one place.

**Tech Stack:** Python 3.14 · `hmac` / `hashlib` / `base64` (stdlib) · Tkinter (stdlib) · FastAPI + uvicorn (already installed) · pytest + monkeypatch (tests)

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| **Modify** | `src/autoclave/installation/activation.py` | Replace static code with `generate/validate_installation_code` + `generate/validate_factory_key` |
| **Create** | `src/autoclave/installation/clock_guard.py` | `check_system_clock(installed_at)` — raises `ClockTamperedError` if today < install date |
| **Modify** | `src/autoclave/installation/wizard.py` | `validate_code` → `validate_installation_code` |
| **Modify** | `src/autoclave/installation/bootstrap.py` | Call `check_system_clock` after loading profile; propagate `ClockTamperedError` |
| **Modify** | `src/autoclave/ui/main.py` | Catch `ClockTamperedError` at startup and show error dialog |
| **Create** | `src/autoclave/installation/factory_dialog.py` | Tkinter dialog that accepts and validates factory key |
| **Modify** | `tests/test_activation.py` | Replace old tests with new API tests (18 cases) |
| **Create** | `tests/test_clock_guard.py` | 4 tests for clock guard via monkeypatch |
| **Create** | `tools/generador/app.py` | FastAPI web app — login + serial form → both codes for today |

---

## Task 1: Rewrite `activation.py` with date-bound codes

**Files:**
- Modify: `src/autoclave/installation/activation.py`
- Test: `tests/test_activation.py`

- [ ] **Step 1: Write the failing tests (replace entire test file)**

```python
# tests/test_activation.py
from datetime import date
from autoclave.installation.activation import (
    generate_installation_code,
    validate_installation_code,
    generate_factory_key,
    validate_factory_key,
)

TODAY     = date(2026, 5, 24)
YESTERDAY = date(2026, 5, 23)
SERIAL    = "SN123456"

# --- Installation code ---

def test_installation_code_length():
    assert len(generate_installation_code(SERIAL, TODAY)) == 12

def test_installation_code_is_uppercase():
    assert generate_installation_code(SERIAL, TODAY).isupper()

def test_installation_code_deterministic_same_day():
    assert generate_installation_code(SERIAL, TODAY) == generate_installation_code(SERIAL, TODAY)

def test_installation_code_differs_by_day():
    assert generate_installation_code(SERIAL, TODAY) != generate_installation_code(SERIAL, YESTERDAY)

def test_installation_code_differs_by_serial():
    assert generate_installation_code(SERIAL, TODAY) != generate_installation_code("SN999999", TODAY)

def test_validate_installation_code_correct():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code(SERIAL, code, TODAY) is True

def test_validate_installation_code_wrong_day():
    code = generate_installation_code(SERIAL, YESTERDAY)
    assert validate_installation_code(SERIAL, code, TODAY) is False

def test_validate_installation_code_wrong_serial():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code("SN999999", code, TODAY) is False

def test_validate_installation_code_case_insensitive():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code("sn123456", code.lower(), TODAY) is True

def test_validate_installation_code_strips_whitespace():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code(SERIAL, f"  {code}  ", TODAY) is True

# --- Factory key ---

def test_factory_key_length():
    assert len(generate_factory_key(SERIAL, TODAY)) == 12

def test_factory_key_deterministic_same_day():
    assert generate_factory_key(SERIAL, TODAY) == generate_factory_key(SERIAL, TODAY)

def test_factory_key_differs_by_day():
    assert generate_factory_key(SERIAL, TODAY) != generate_factory_key(SERIAL, YESTERDAY)

def test_validate_factory_key_correct():
    key = generate_factory_key(SERIAL, TODAY)
    assert validate_factory_key(SERIAL, key, TODAY) is True

def test_validate_factory_key_wrong_day():
    key = generate_factory_key(SERIAL, YESTERDAY)
    assert validate_factory_key(SERIAL, key, TODAY) is False

# --- Cross-type: codes cannot be used interchangeably ---

def test_installation_code_rejected_as_factory_key():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_factory_key(SERIAL, code, TODAY) is False

def test_factory_key_rejected_as_installation_code():
    key = generate_factory_key(SERIAL, TODAY)
    assert validate_installation_code(SERIAL, key, TODAY) is False
```

- [ ] **Step 2: Run to verify all tests fail**

```
python -m pytest tests/test_activation.py -v
```

Expected: `ImportError` (old API names don't exist yet) — all 18 tests fail.

- [ ] **Step 3: Rewrite `activation.py`**

```python
# src/autoclave/installation/activation.py
import hmac
import hashlib
import base64
from datetime import date as _date

_SECRET_INSTALL = b"EspecifikaInstall\xf3\x9a\x11\x2c\x87\xde"
_SECRET_FACTORY = b"EspecifikaFabrica\x7e\x44\xb2\x9f\x13\xcc"


def _make_code(secret: bytes, serial: str, day: _date) -> str:
    message = f"{serial.strip().upper()}:{day.isoformat()}".encode()
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    return base64.b32encode(digest)[:12].decode()


def generate_installation_code(serial: str, day: _date | None = None) -> str:
    return _make_code(_SECRET_INSTALL, serial, day or _date.today())


def validate_installation_code(serial: str, code: str, day: _date | None = None) -> bool:
    expected = generate_installation_code(serial, day)
    return hmac.compare_digest(expected, code.strip().upper()[:12])


def generate_factory_key(serial: str, day: _date | None = None) -> str:
    return _make_code(_SECRET_FACTORY, serial, day or _date.today())


def validate_factory_key(serial: str, code: str, day: _date | None = None) -> bool:
    expected = generate_factory_key(serial, day)
    return hmac.compare_digest(expected, code.strip().upper()[:12])
```

- [ ] **Step 4: Run tests to verify all pass**

```
python -m pytest tests/test_activation.py -v
```

Expected: 18 passed.

- [ ] **Step 5: Commit**

```
git add tests/test_activation.py src/autoclave/installation/activation.py
git commit -m "feat: replace static HMAC code with date-bound installation code and factory key"
```

---

## Task 2: Create `clock_guard.py`

**Files:**
- Create: `src/autoclave/installation/clock_guard.py`
- Create: `tests/test_clock_guard.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clock_guard.py
import pytest
from datetime import datetime, timedelta
from autoclave.installation.clock_guard import check_system_clock, ClockTamperedError

INSTALLED_AT = datetime(2026, 5, 20, 10, 0, 0)


def test_clock_ok_when_today_is_after_install(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: (INSTALLED_AT + timedelta(days=4)).date(),
    )
    check_system_clock(INSTALLED_AT)  # should not raise


def test_clock_ok_same_day(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: INSTALLED_AT.date(),
    )
    check_system_clock(INSTALLED_AT)  # should not raise


def test_clock_tampered_when_today_is_before_install(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: (INSTALLED_AT - timedelta(days=1)).date(),
    )
    with pytest.raises(ClockTamperedError):
        check_system_clock(INSTALLED_AT)


def test_clock_tampered_message_contains_dates(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: (INSTALLED_AT - timedelta(days=1)).date(),
    )
    with pytest.raises(ClockTamperedError, match="2026-05-19"):
        check_system_clock(INSTALLED_AT)
```

- [ ] **Step 2: Run to verify all fail**

```
python -m pytest tests/test_clock_guard.py -v
```

Expected: `ModuleNotFoundError` — all 4 tests fail.

- [ ] **Step 3: Create `clock_guard.py`**

```python
# src/autoclave/installation/clock_guard.py
from datetime import datetime, date


class ClockTamperedError(Exception):
    pass


def _today() -> date:
    return date.today()


def check_system_clock(installed_at: datetime) -> None:
    today = _today()
    if today < installed_at.date():
        raise ClockTamperedError(
            f"Reloj del sistema ({today}) es anterior a la fecha de instalación "
            f"({installed_at.date()}). Verifique la fecha y hora del sistema."
        )
```

- [ ] **Step 4: Run tests to verify all pass**

```
python -m pytest tests/test_clock_guard.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full suite to check for regressions**

```
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```
git add src/autoclave/installation/clock_guard.py tests/test_clock_guard.py
git commit -m "feat: add clock guard — blocks startup if system clock precedes install date"
```

---

## Task 3: Update `wizard.py` to use the new installation code

**Files:**
- Modify: `src/autoclave/installation/wizard.py`

- [ ] **Step 1: Replace import**

In `src/autoclave/installation/wizard.py`, line 9, change:

```python
# before
from .activation import validate_code
```

```python
# after
from .activation import validate_installation_code
```

- [ ] **Step 2: Replace validation call and update error message**

In `ir_a_paso2()` (around line 62), change:

```python
# before
        if not validate_code(serial, code):
            err1.config(text="Código de activación incorrecto")
```

```python
# after
        if not validate_installation_code(serial, code):
            err1.config(text="Código de activación incorrecto o expirado")
```

- [ ] **Step 3: Run full suite to confirm no regressions**

```
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```
git add src/autoclave/installation/wizard.py
git commit -m "feat: wizard uses date-bound installation code"
```

---

## Task 4: Integrate clock guard into `bootstrap.py` and `main.py`

**Files:**
- Modify: `src/autoclave/installation/bootstrap.py`
- Modify: `src/autoclave/ui/main.py`

- [ ] **Step 1: Rewrite `bootstrap.py`**

```python
# src/autoclave/installation/bootstrap.py
import json
import logging
from .storage import exists, load
from .profile import ProfileValidationError
from .clock_guard import check_system_clock, ClockTamperedError

logger = logging.getLogger(__name__)


def get_installation_profile():
    """
    Return the InstallationProfile if valid, or None if the file doesn't exist
    or is corrupt. Raises ClockTamperedError if the system clock is before the
    installation date — callers must handle this explicitly.
    """
    if not exists():
        return None

    try:
        profile = load()
        check_system_clock(profile.created_at)
        return profile
    except ClockTamperedError:
        raise
    except (ProfileValidationError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Perfil de instalación corrupto o inválido: %s", e)
        return None
```

- [ ] **Step 2: Update `main.py` — add import and handle `ClockTamperedError`**

Add this import near the top of `src/autoclave/ui/main.py` (after the existing `bootstrap` import):

```python
from autoclave.installation.clock_guard import ClockTamperedError
```

Replace the startup block (the section starting at `profile = get_installation_profile()` around line 46) with:

```python
    # ── 1. Verificar instalación ───────────────────────────────────────────
    try:
        profile = get_installation_profile()
    except ClockTamperedError as e:
        import tkinter as tk
        from tkinter import messagebox
        _root = tk.Tk()
        _root.withdraw()
        messagebox.showerror(
            "Error de sistema",
            f"No se puede iniciar el software.\n\n{e}",
        )
        _root.destroy()
        sys.exit(1)

    if profile is None:
        logger.info("Perfil de instalación no encontrado o inválido — iniciando wizard")
        completed = launch_installation_wizard()
        if not completed:
            logger.error("Instalación requerida para continuar. Cerrando.")
            sys.exit(1)
        try:
            profile = get_installation_profile()
        except ClockTamperedError as e:
            logger.error("Reloj adulterado tras wizard: %s", e)
            sys.exit(1)
        if profile is None:
            logger.error("Error crítico: perfil sigue inválido tras wizard. Cerrando.")
            sys.exit(1)
```

- [ ] **Step 3: Run full suite**

```
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```
git add src/autoclave/installation/bootstrap.py src/autoclave/ui/main.py
git commit -m "feat: integrate clock guard into bootstrap — shows error dialog on tampered clock"
```

---

## Task 5: Create `factory_dialog.py`

**Files:**
- Create: `src/autoclave/installation/factory_dialog.py`

No automated tests — the Tkinter dialog requires a display. Use the manual test in Step 2.

- [ ] **Step 1: Create `factory_dialog.py`**

```python
# src/autoclave/installation/factory_dialog.py
import tkinter as tk
from tkinter import messagebox

from .activation import validate_factory_key


def launch_factory_dialog(serial_number: str) -> bool:
    """
    Show the factory key entry dialog for the given serial number.
    Returns True if a valid factory key was entered, False if cancelled.
    The factory key is valid only for today — it must be generated fresh each time.
    """
    result = {"granted": False}

    root = tk.Tk()
    root.title("Acceso de fabricante — Autoclave Especifika")
    root.resizable(False, False)
    root.grab_set()

    frame = tk.Frame(root, padx=30, pady=20)
    frame.pack()

    tk.Label(frame, text="Acceso de fabricante", font=("", 14, "bold")).pack(pady=(0, 16))
    tk.Label(frame, text=f"Serial: {serial_number}", fg="gray").pack(pady=(0, 12))

    tk.Label(frame, text="Clave de fabricante:", anchor="w").pack(fill="x")
    key_var = tk.StringVar()
    tk.Entry(frame, textvariable=key_var, width=30, show="*").pack(fill="x", pady=(0, 12))

    err_label = tk.Label(frame, text="", fg="red")
    err_label.pack()

    def verificar():
        key = key_var.get().strip()
        if not key:
            err_label.config(text="Ingrese la clave")
            return
        if validate_factory_key(serial_number, key):
            result["granted"] = True
            messagebox.showinfo("Acceso concedido", "Modo fabricante activado.")
            root.destroy()
        else:
            err_label.config(text="Clave incorrecta o expirada")

    tk.Button(frame, text="Verificar", command=verificar, width=20).pack(pady=(8, 4))
    tk.Button(frame, text="Cancelar", command=root.destroy, width=20).pack()

    root.mainloop()
    return result["granted"]
```

- [ ] **Step 2: Manual test from Python shell**

```python
from autoclave.installation.activation import generate_factory_key
from autoclave.installation.factory_dialog import launch_factory_dialog
from datetime import date

serial = "SN123456"
key = generate_factory_key(serial, date.today())
print(f"Clave de hoy para {serial}: {key}")
result = launch_factory_dialog(serial)
print("Acceso concedido:", result)
```

Verificar:
1. La ventana aparece con el serial en gris
2. Ingresar la clave correcta → messagebox "Acceso concedido", `result = True`
3. Cerrar y ejecutar de nuevo → ingresar clave incorrecta → mensaje de error en rojo
4. Ingresar el código de instalación (diferente) → también debe dar error

- [ ] **Step 3: Commit**

```
git add src/autoclave/installation/factory_dialog.py
git commit -m "feat: add factory key dialog (Tkinter) — daily code, placeholder for future manufacturer functions"
```

---

## Task 6: Create `tools/generador/app.py`

**Files:**
- Create: `tools/generador/app.py`

La app importa directamente desde `autoclave.installation.activation` — no hay duplicación de lógica.

- [ ] **Step 1: Create directory**

```
mkdir tools\generador
```

- [ ] **Step 2: Create `app.py`**

```python
# tools/generador/app.py
"""
Generador interno de códigos de instalación y claves de fábrica.

Correr:
    python tools/generador/app.py

Acceso local:    http://localhost:8080
Desde otra PC:   http://<ip-de-tu-maquina>:8080

Variables de entorno (opcionales):
    GENERADOR_USER  — usuario (default: especifika)
    GENERADOR_PASS  — contraseña (default: cambiar_esto_2026)
    GENERADOR_HOST  — host de escucha (default: 0.0.0.0)
    GENERADOR_PORT  — puerto (default: 8080)
"""
import os
import sys
import secrets
from datetime import date

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

# Permite importar el paquete sin instalarlo si se corre directamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from autoclave.installation.activation import generate_installation_code, generate_factory_key

# ── Configuración ────────────────────────────────────────────────────────────
_USER = os.environ.get("GENERADOR_USER", "especifika")
_PASS = os.environ.get("GENERADOR_PASS", "cambiar_esto_2026")
_HOST = os.environ.get("GENERADOR_HOST", "0.0.0.0")
_PORT = int(os.environ.get("GENERADOR_PORT", "8080"))

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(docs_url=None, redoc_url=None)
_sessions: set[str] = set()

_CSS = """
body{font-family:sans-serif;max-width:500px;margin:60px auto;padding:0 20px;background:#f5f5f5}
.card{background:#fff;border-radius:8px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
h1{margin-top:0;font-size:1.3rem;color:#2c3e50}
label{display:block;margin:14px 0 4px;font-size:.9rem;color:#555}
input[type=text],input[type=password]{width:100%;box-sizing:border-box;padding:10px;
  border:1px solid #ccc;border-radius:4px;font-size:1rem}
button{width:100%;margin-top:18px;padding:12px;background:#27ae60;color:#fff;
  border:none;border-radius:4px;font-size:1rem;cursor:pointer}
button:hover{background:#219653}
.error{color:#e74c3c;font-size:.9rem;margin-top:10px}
.result{margin-top:22px;padding:18px;background:#eaf6f0;border-radius:6px}
.chip-label{font-size:.75rem;color:#888;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 2px}
.code{font-family:monospace;font-size:1.25rem;letter-spacing:.12em;color:#2c3e50;font-weight:bold}
.date-note{font-size:.8rem;color:#888;margin-top:4px}
.logout{margin-top:20px;text-align:right}
.logout a{color:#aaa;font-size:.82rem;text-decoration:none}
.logout a:hover{color:#888}
"""


def _is_authenticated(request: Request) -> bool:
    return request.cookies.get("session", "") in _sessions


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse("/generar" if _is_authenticated(request) else "/login")


@app.get("/login", response_class=HTMLResponse)
async def login_get(error: str = ""):
    err = f'<p class="error">{error}</p>' if error else ""
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Generador — Login</title>
<style>{_CSS}</style></head><body><div class="card">
<h1>Generador de Códigos</h1>
<form method="POST" action="/login">
  <label>Usuario</label><input name="username" type="text" autofocus>
  <label>Contraseña</label><input name="password" type="password">
  <button type="submit">Entrar</button>
</form>{err}</div></body></html>""")


@app.post("/login")
async def login_post(username: str = Form(...), password: str = Form(...)):
    if username == _USER and password == _PASS:
        token = secrets.token_hex(32)
        _sessions.add(token)
        resp = RedirectResponse("/generar", status_code=303)
        resp.set_cookie("session", token, httponly=True, samesite="strict")
        return resp
    return RedirectResponse("/login?error=Usuario+o+contraseña+incorrectos", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    _sessions.discard(request.cookies.get("session", ""))
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp


@app.get("/generar", response_class=HTMLResponse)
async def generar_get(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")
    return HTMLResponse(_dashboard("", "", ""))


@app.post("/generar", response_class=HTMLResponse)
async def generar_post(request: Request, serial: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse("/login")
    serial = serial.strip().upper()
    if not serial:
        return HTMLResponse(_dashboard("", "", "El serial no puede estar vacío"))
    install_code = generate_installation_code(serial)
    factory_key  = generate_factory_key(serial)
    return HTMLResponse(_dashboard(serial, install_code, factory_key))


def _dashboard(serial: str, install_code: str, factory_key: str, error: str = "") -> str:
    today = date.today().isoformat()
    result = ""
    if install_code:
        result = f"""<div class="result">
  <div class="chip-label">Serial</div>
  <div class="code">{serial}</div>
  <div class="chip-label">Código de instalación</div>
  <div class="code">{install_code}</div>
  <div class="chip-label">Clave de fábrica</div>
  <div class="code">{factory_key}</div>
  <div class="date-note">Válidos solo el día de hoy: {today}</div>
</div>"""
    err = f'<p class="error">{error}</p>' if error else ""
    return f"""<!DOCTYPE html><html><head><title>Generador</title>
<style>{_CSS}</style></head><body><div class="card">
<h1>Generador de Códigos</h1>
<form method="POST" action="/generar">
  <label>Número de serie del equipo</label>
  <input name="serial" type="text" value="{serial}" placeholder="SN123456" autofocus>
  <button type="submit">Generar</button>
</form>{err}{result}
<div class="logout"><a href="/logout">Cerrar sesión</a></div>
</div></body></html>"""


if __name__ == "__main__":
    print(f"\nGenerador corriendo en http://localhost:{_PORT}")
    print(f"Desde otra máquina: http://<ip-de-esta-PC>:{_PORT}\n")
    uvicorn.run(app, host=_HOST, port=_PORT, log_level="warning")
```

- [ ] **Step 3: Smoke test**

```
python tools/generador/app.py
```

Abrir http://localhost:8080 y verificar:
1. Redirige a `/login`
2. Login con usuario/contraseña incorrectos → mensaje de error en rojo
3. Login con `especifika` / `cambiar_esto_2026` → llega al dashboard
4. Ingresar serial `SN123456` → aparecen ambos códigos con la fecha de hoy
5. Copiar el código de instalación → verificarlo en el wizard del software → debe pasar
6. Copiar la clave de fábrica → verificarla con `validate_factory_key` en Python shell → debe pasar
7. Usar el código de instalación como clave de fábrica → debe fallar
8. Cerrar sesión → redirige a login

- [ ] **Step 4: Commit**

```
git add tools/generador/app.py
git commit -m "feat: add internal web app for generating daily installation and factory codes"
```

---

## Verificación final

- [ ] **Correr el suite completo una última vez**

```
python -m pytest tests/ -v
```

Expected: 22 passed (18 activation + 4 clock guard).

- [ ] **Commit de cierre si todo verde**

```
git add .
git commit -m "chore: final test run — all 22 tests pass"
```

---

## Checklist de cobertura del spec

| Requisito | Tarea |
|---|---|
| Código de instalación expira cada día | Task 1 |
| Clave de fábrica expira cada día | Task 1 |
| Secretos distintos — códigos no intercambiables | Task 1 (tests de cross-type lo prueban) |
| Guardián del reloj bloquea si fecha retrocede | Task 2 + Task 4 |
| Wizard usa nuevo código de instalación | Task 3 |
| Diálogo de clave de fábrica en el software | Task 5 |
| App web con login | Task 6 |
| App web accesible desde otra máquina | Task 6 (`HOST=0.0.0.0`) |
| Credenciales hardcodeadas, migrables a env vars | Task 6 (`os.environ.get`) |
| Migración opción B — instalaciones existentes re-instalan | Old `generate_code`/`validate_code` eliminados en Task 1 |
| Tests actualizados | TDD en cada tarea |
