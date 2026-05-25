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
import html
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
.date-note{font-size:.8rem;color:#888;margin-top:8px}
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
    safe_serial = html.escape(serial)
    safe_error  = html.escape(error)
    result = ""
    if install_code:
        result = f"""<div class="result">
  <div class="chip-label">Serial</div>
  <div class="code">{safe_serial}</div>
  <div class="chip-label">Código de instalación</div>
  <div class="code">{install_code}</div>
  <div class="chip-label">Clave de fábrica</div>
  <div class="code">{factory_key}</div>
  <div class="date-note">Válidos solo el día de hoy: {today}</div>
</div>"""
    err = f'<p class="error">{safe_error}</p>' if error else ""
    return f"""<!DOCTYPE html><html><head><title>Generador</title>
<style>{_CSS}</style></head><body><div class="card">
<h1>Generador de Códigos</h1>
<form method="POST" action="/generar">
  <label>Número de serie del equipo</label>
  <input name="serial" type="text" value="{safe_serial}" placeholder="SN123456" autofocus>
  <button type="submit">Generar</button>
</form>{err}{result}
<div class="logout"><a href="/logout">Cerrar sesión</a></div>
</div></body></html>"""


if __name__ == "__main__":
    print(f"\nGenerador corriendo en http://localhost:{_PORT}")
    print(f"Desde otra máquina: http://<ip-de-esta-PC>:{_PORT}\n")
    uvicorn.run(app, host=_HOST, port=_PORT, log_level="warning")
