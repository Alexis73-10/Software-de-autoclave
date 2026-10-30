"""
Generador interno de códigos de instalación y claves de fábrica (Especifika).

Corre SOLO en el PC de Cristian, con su propia base (generador.db, no la del
software del autoclave); otros usuarios entran por navegador desde la red local
(G1, tanda 2). Usuarios individuales con rol admin/usuario.

Desarrollo:   python tools/generador/app.py      (usa la carpeta de datos, ver datos_generador.py)
Ejecutable:   GeneradorCodigos.exe (lanzador.py)

Acceso local:    http://localhost:<puerto>
Desde otra PC:   http://<ip-de-este-PC>:<puerto>   (se muestra en la pantalla de login)
"""
import html
import os
import socket
import sys
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
sys.path.insert(0, os.path.join(_AQUI, "..", "..", "src"))
from autoclave.installation.activation import generate_installation_code, generate_factory_key  # noqa: E402
from autoclave.installation import activation  # noqa: E402
from autoclave.installation import secretos as _secretos  # noqa: E402
from autoclave.backend.contrasenas import hash_password  # noqa: E402

import db as generador_db  # noqa: E402
import datos_generador  # noqa: E402
import seguridad_generador as seg  # noqa: E402

IDENTIDAD = "generador-especifika"
_COOKIE = "session"

_CSS = """
body{font-family:sans-serif;max-width:640px;margin:48px auto;padding:0 20px;background:#f5f5f5;color:#222}
.card{background:#fff;border-radius:8px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
h1{margin-top:0;font-size:1.3rem;color:#2c3e50} h2{font-size:1.05rem;color:#2c3e50;margin:24px 0 6px}
label{display:block;margin:14px 0 4px;font-size:.9rem;color:#555}
input[type=text],input[type=password],select{width:100%;box-sizing:border-box;padding:10px;
  border:1px solid #ccc;border-radius:4px;font-size:1rem}
button{width:100%;margin-top:18px;padding:12px;background:#27ae60;color:#fff;
  border:none;border-radius:4px;font-size:1rem;cursor:pointer}
button:hover{background:#219653}
button.warning{background:#e67e22} button.warning:hover{background:#ca6f1e}
button.chico{width:auto;margin:0;padding:6px 10px;font-size:.85rem}
.error{color:#c0392b;font-size:.9rem;margin-top:10px}
.ok{color:#1e8449;font-size:.9rem;margin-top:10px}
.nota{font-size:.82rem;color:#666;margin-top:10px}
.result{margin-top:22px;padding:18px;background:#eaf6f0;border-radius:6px}
.chip-label{font-size:.75rem;color:#888;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 2px}
.code{font-family:Consolas,"Cascadia Mono",monospace;font-size:1.25rem;letter-spacing:.12em;color:#2c3e50;font-weight:bold}
.date-note{font-size:.8rem;color:#888;margin-top:8px}
.menu{margin-top:20px;display:flex;justify-content:space-between;font-size:.85rem}
.menu a{color:#888;text-decoration:none} .menu a:hover{color:#555}
table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:6px}
th{text-align:left;color:#888;font-weight:normal;padding:2px 6px}
td{padding:4px 6px;border-top:1px solid #eee;vertical-align:middle}
form.enlinea{display:inline}
"""


def ip_local() -> str:
    """IP de este PC en la red local (sin enviar tráfico)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _pagina(titulo: str, cuerpo: str) -> HTMLResponse:
    return HTMLResponse(f"<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
                        f"<title>{html.escape(titulo)}</title><style>{_CSS}</style></head>"
                        f"<body><div class='card'>{cuerpo}</div></body></html>")


def motivo_sin_secretos() -> str:
    """LIC-01 (licencia L0): texto del motivo por el que el generador no
    arranca, o "" si hay secretos de activación."""
    if activation.secretos_disponibles():
        return ""
    return (f"No se encontró un archivo de secretos de activación válido en "
            f"{_secretos.ruta_archivo_secretos()} (o en la variable de entorno "
            f"{_secretos.VARIABLE_ENTORNO}). Ejecute tools\\secretos\\generar_secretos.py "
            f"o copie el archivo de secretos vigente y reinicie el generador.")


def app_sin_secretos(motivo: str) -> FastAPI:
    """Sin secretos el generador no arranca: toda ruta muestra el motivo."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/salud")
    async def salud():
        return JSONResponse({"app": IDENTIDAD, "sin_secretos": True})

    @app.api_route("/{ruta:path}", methods=["GET", "POST"])
    async def todo(ruta: str = ""):
        r = _pagina("Generador — Sin secretos",
                    f"<h1>Generador de Códigos</h1><p class='error'>El generador no arrancó.</p>"
                    f"<p>{html.escape(motivo)}</p>")
        r.status_code = 503
        return r
    return app


def create_app(datos: Path, conf: dict, sesiones: seg.Sesiones | None = None,
               iteraciones: int | None = None) -> FastAPI:
    """App del generador sobre la carpeta de datos `datos` (la base ya debe
    apuntar a datos/generador.db e inicializada). `iteraciones` solo en pruebas.
    Sin secretos de activación devuelve app_sin_secretos (LIC-01)."""
    motivo = motivo_sin_secretos()
    if motivo:
        return app_sin_secretos(motivo)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    sesiones = sesiones or seg.Sesiones(conf["inactividad_min"] * 60, conf["intentos_max"],
                                        conf["bloqueo_min"] * 60)
    kw_hash = {"iteraciones": iteraciones} if iteraciones else {}
    url_compartir = f"http://{ip_local()}:{conf['puerto']}"
    archivo_inicial = datos / seg.ARCHIVO_CLAVE_INICIAL

    def actual(request: Request) -> dict | None:
        return sesiones.usuario(request.cookies.get(_COOKIE))

    def menu(usuario: dict) -> str:
        admin = "<a href='/admin'>Usuarios</a> · " if usuario["rol"] == "admin" else ""
        return (f"<div class='menu'><span>{html.escape(usuario['usuario'])} ({usuario['rol']})</span>"
                f"<span>{admin}<a href='/cambiar_clave'>Cambiar contraseña</a> · "
                f"<a href='/logout'>Cerrar sesión</a></span></div>")

    def exigir(request: Request, admin: bool = False):
        """(usuario, None) o (None, redirección)."""
        u = actual(request)
        if u is None:
            return None, RedirectResponse("/login", status_code=303)
        if u["debe_cambiar"]:
            return None, RedirectResponse("/cambiar_clave", status_code=303)
        if admin and u["rol"] != "admin":
            return None, RedirectResponse("/generar", status_code=303)
        return u, None

    @app.get("/salud")
    async def salud():
        return JSONResponse({"app": IDENTIDAD})

    @app.get("/")
    async def raiz(request: Request):
        return RedirectResponse("/generar" if actual(request) else "/login", status_code=303)

    @app.get("/login")
    async def login_get(error: str = ""):
        err = f'<p class="error">{html.escape(error)}</p>' if error else ""
        inicial = ""
        if archivo_inicial.exists():
            inicial = (f"<p class='nota'>Primer arranque: la contraseña temporal del usuario "
                       f"<b>admin</b> está en <code>{html.escape(str(archivo_inicial))}</code> "
                       f"en el PC del generador.</p>")
        return _pagina("Generador — Ingreso", f"""<h1>Generador de Códigos</h1>
<form method="POST" action="/login">
  <label>Usuario</label><input name="username" type="text" autofocus autocomplete="username">
  <label>Contraseña</label><input name="password" type="password" autocomplete="current-password">
  <button type="submit">Entrar</button>
</form>{err}{inicial}
<p class="nota">Desde otro PC de la red: <code>{html.escape(url_compartir)}</code></p>""")

    @app.post("/login")
    async def login_post(username: str = Form(default=""), password: str = Form(default="")):
        username = username.strip()
        if not username or not password:
            return RedirectResponse("/login?error=Ingrese+usuario+y+contraseña", status_code=303)
        token, motivo = sesiones.autenticar(username, password)
        if token is None:
            from urllib.parse import quote_plus
            return RedirectResponse(f"/login?error={quote_plus(motivo)}", status_code=303)
        fila = generador_db.obtener_usuario(username)
        resp = RedirectResponse("/cambiar_clave" if fila["debe_cambiar"] else "/generar",
                                status_code=303)
        resp.set_cookie(_COOKIE, token, httponly=True, samesite="strict")
        return resp

    @app.get("/logout")
    async def logout(request: Request):
        sesiones.cerrar(request.cookies.get(_COOKIE))
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(_COOKIE)
        return resp

    def _form_clave(usuario: dict, error: str = "") -> HTMLResponse:
        obligatorio = ("<p class='nota'>Debe cambiar la contraseña antes de continuar.</p>"
                       if usuario["debe_cambiar"] else "")
        err = f'<p class="error">{html.escape(error)}</p>' if error else ""
        volver = "" if usuario["debe_cambiar"] else menu(usuario)
        return _pagina("Generador — Contraseña", f"""<h1>Cambiar contraseña</h1>{obligatorio}
<form method="POST" action="/cambiar_clave">
  <label>Contraseña actual</label><input name="actual" type="password" autocomplete="current-password">
  <label>Contraseña nueva (mínimo {seg.LONGITUD_MINIMA} caracteres)</label>
  <input name="nueva" type="password" autocomplete="new-password">
  <label>Confirmar contraseña nueva</label><input name="confirmacion" type="password" autocomplete="new-password">
  <button type="submit">Guardar</button>
</form>{err}{volver}""")

    @app.get("/cambiar_clave")
    async def cambiar_get(request: Request):
        u = actual(request)
        if u is None:
            return RedirectResponse("/login", status_code=303)
        return _form_clave(u)

    @app.post("/cambiar_clave")
    async def cambiar_post(request: Request, actual_: str = Form(default="", alias="actual"),
                           nueva: str = Form(default=""), confirmacion: str = Form(default="")):
        u = actual(request)
        if u is None:
            return RedirectResponse("/login", status_code=303)
        if not seg.verificar_password(actual_, u["hash"]):
            return _form_clave(u, "La contraseña actual no es correcta")
        motivo = seg.validar_clave_nueva(nueva, confirmacion)
        if motivo is None and nueva == actual_:
            motivo = "La contraseña nueva debe ser distinta de la actual"
        if motivo:
            return _form_clave(u, motivo)
        generador_db.fijar_clave(u["usuario"], hash_password(nueva, **kw_hash), debe_cambiar=False)
        if u["usuario"] == "admin" and archivo_inicial.exists():
            archivo_inicial.unlink(missing_ok=True)
        return RedirectResponse("/generar", status_code=303)

    # ── generar ──────────────────────────────────────────────────────────

    @app.get("/generar")
    async def generar_get(request: Request):
        u, redir = exigir(request)
        if redir:
            return redir
        return _pagina("Generador", _dashboard(u, menu(u), "", "", "", ya_instalado=False))

    @app.post("/generar")
    async def generar_post(request: Request, serial: str = Form(default="")):
        u, redir = exigir(request)
        if redir:
            return redir
        serial = serial.strip().upper()
        if not serial:
            return _pagina("Generador", _dashboard(u, menu(u), "", "", "",
                                                   error="El serial no puede estar vacío"))
        ya_instalado = generador_db.fue_instalado(serial)
        factory_key = generate_factory_key(serial)
        if ya_instalado:
            generador_db.log_codigo(serial, "fabrica", u["usuario"])
            return _pagina("Generador", _dashboard(u, menu(u), serial, "", factory_key,
                                                   ya_instalado=True,
                                                   history=generador_db.get_history(serial)))
        install_code = generate_installation_code(serial)
        generador_db.log_codigo(serial, "instalacion", u["usuario"])
        return _pagina("Generador", _dashboard(u, menu(u), serial, install_code, factory_key,
                                               history=generador_db.get_history(serial)))

    @app.post("/reinstalar")
    async def reinstalar_post(request: Request, serial: str = Form(default="")):
        u, redir = exigir(request)
        if redir:
            return redir
        serial = serial.strip().upper()
        if not serial:
            return _pagina("Generador", _dashboard(u, menu(u), "", "", "",
                                                   error="El serial no puede estar vacío"))
        install_code = generate_installation_code(serial)
        generador_db.log_codigo(serial, "reinstalacion", u["usuario"])
        return _pagina("Generador", _dashboard(u, menu(u), serial, install_code, "",
                                               ya_instalado=True, reinstalacion=True,
                                               history=generador_db.get_history(serial)))

    # ── administración de usuarios (solo admin) ──────────────────────────

    def _admin(u: dict, aviso: str = "", error: str = "") -> HTMLResponse:
        filas = []
        for x in generador_db.listar_usuarios():
            nombre = html.escape(x["usuario"])
            estado = "activo" if x["activo"] else "desactivado"
            accion = "desactivar" if x["activo"] else "activar"
            filas.append(
                f"<tr><td>{nombre}</td><td>{x['rol']}</td><td>{estado}"
                f"{' · debe cambiar' if x['debe_cambiar'] else ''}</td><td>"
                f"<form class='enlinea' method='POST' action='/admin/{accion}'>"
                f"<input type='hidden' name='usuario' value='{nombre}'>"
                f"<button class='chico warning' type='submit'>{accion.capitalize()}</button></form> "
                f"<form class='enlinea' method='POST' action='/admin/restablecer'>"
                f"<input type='hidden' name='usuario' value='{nombre}'>"
                f"<button class='chico' type='submit'>Restablecer contraseña</button></form>"
                f"</td></tr>")
        ok = f"<p class='ok'>{aviso}</p>" if aviso else ""
        err = f"<p class='error'>{html.escape(error)}</p>" if error else ""
        return _pagina("Generador — Usuarios", f"""<h1>Usuarios</h1>{ok}{err}
<table><tr><th>Usuario</th><th>Rol</th><th>Estado</th><th></th></tr>{''.join(filas)}</table>
<h2>Nuevo usuario</h2>
<form method="POST" action="/admin/crear">
  <label>Usuario</label><input name="usuario" type="text">
  <label>Rol</label><select name="rol"><option value="usuario">usuario</option>
  <option value="admin">admin</option></select>
  <button type="submit">Crear (con contraseña temporal)</button>
</form>
<p class="nota">La contraseña temporal se muestra una sola vez; el usuario debe cambiarla al ingresar.</p>
<p class="nota">Huella del secreto de instalación: <code>{html.escape(activation.huella_instalacion() or "-")}</code>
(debe coincidir con la que mostró la compilación del autoclave).</p>
{menu(u)}<p class='nota'><a href='/generar'>Volver al generador</a></p>""")

    def _aviso_clave(usuario: str, clave: str) -> str:
        return (f"Contraseña temporal de <b>{html.escape(usuario)}</b> (se muestra una sola vez): "
                f"<code>{html.escape(clave)}</code>")

    @app.get("/admin")
    async def admin_get(request: Request):
        u, redir = exigir(request, admin=True)
        return redir or _admin(u)

    @app.post("/admin/crear")
    async def admin_crear(request: Request, usuario: str = Form(default=""),
                          rol: str = Form(default="usuario")):
        u, redir = exigir(request, admin=True)
        if redir:
            return redir
        usuario = usuario.strip()
        if not usuario or len(usuario) > 40 or not usuario.replace(".", "").replace("_", "").isalnum():
            return _admin(u, error="Usuario inválido (letras, números, punto o guion bajo)")
        if rol not in generador_db.ROLES:
            return _admin(u, error="Rol inválido")
        if generador_db.obtener_usuario(usuario) is not None:
            return _admin(u, error="Ese usuario ya existe")
        clave = seg.clave_temporal()
        generador_db.crear_usuario(usuario, hash_password(clave, **kw_hash), rol, debe_cambiar=True)
        return _admin(u, aviso=_aviso_clave(usuario, clave))

    @app.post("/admin/restablecer")
    async def admin_restablecer(request: Request, usuario: str = Form(default="")):
        u, redir = exigir(request, admin=True)
        if redir:
            return redir
        if generador_db.obtener_usuario(usuario) is None:
            return _admin(u, error="Usuario inexistente")
        clave = seg.clave_temporal()
        generador_db.fijar_clave(usuario, hash_password(clave, **kw_hash), debe_cambiar=True)
        sesiones.cerrar_de(usuario)
        return _admin(u, aviso=_aviso_clave(usuario, clave))

    @app.post("/admin/desactivar")
    async def admin_desactivar(request: Request, usuario: str = Form(default="")):
        u, redir = exigir(request, admin=True)
        if redir:
            return redir
        fila = generador_db.obtener_usuario(usuario)
        if fila is None:
            return _admin(u, error="Usuario inexistente")
        if usuario == u["usuario"]:
            return _admin(u, error="No puede desactivarse a sí mismo")
        if fila["rol"] == "admin" and fila["activo"] and generador_db.contar_admins_activos() <= 1:
            return _admin(u, error="Debe quedar al menos un admin activo")
        generador_db.fijar_activo(usuario, False)
        sesiones.cerrar_de(usuario)
        return _admin(u, aviso=f"{html.escape(usuario)} desactivado")

    @app.post("/admin/activar")
    async def admin_activar(request: Request, usuario: str = Form(default="")):
        u, redir = exigir(request, admin=True)
        if redir:
            return redir
        if generador_db.obtener_usuario(usuario) is None:
            return _admin(u, error="Usuario inexistente")
        generador_db.fijar_activo(usuario, True)
        return _admin(u, aviso=f"{html.escape(usuario)} activado")

    return app


def _render_history(history: list[dict]) -> str:
    if not history:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(h['tipo'])}</td>"
        f"<td>{html.escape(h['fecha'])}</td>"
        f"<td>{html.escape(h['usuario'])}</td></tr>"
        for h in history
    )
    return (
        '<div class="result"><div class="chip-label">Historial</div>'
        "<table><tr><th>Tipo</th><th>Fecha</th><th>Usuario</th></tr>"
        f"{rows}</table></div>"
    )


def _dashboard(usuario: dict, menu_html: str, serial: str, install_code: str, factory_key: str,
               error: str = "", history: list[dict] | None = None,
               ya_instalado: bool = False, reinstalacion: bool = False) -> str:
    today = date.today().isoformat()
    safe_serial = html.escape(serial)
    result = ""
    reinstall_form = ""
    if install_code or factory_key:
        codes_html = ""
        if reinstalacion:
            codes_html += ('<div class="chip-label">Código de reinstalación</div>'
                           f'<div class="code">{html.escape(install_code)}</div>')
        elif not ya_instalado and install_code:
            codes_html += ('<div class="chip-label">Código de instalación</div>'
                           f'<div class="code">{html.escape(install_code)}</div>')
        if factory_key:
            codes_html += ('<div class="chip-label">Clave de fábrica</div>'
                           f'<div class="code">{html.escape(factory_key)}</div>')
        result = (f'<div class="result"><div class="chip-label">Serial</div>'
                  f'<div class="code">{safe_serial}</div>{codes_html}'
                  f'<div class="date-note">Válidos solo el día de hoy: {today}</div></div>')
    if ya_instalado and not reinstalacion:
        reinstall_form = (f'<form method="POST" action="/reinstalar" style="margin-top:8px">'
                          f'<input type="hidden" name="serial" value="{safe_serial}">'
                          f'<button class="warning" type="submit">Solicitar reinstalación</button></form>')
    err = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return (f"<h1>Generador de Códigos</h1>"
            f'<form method="POST" action="/generar">'
            f"  <label>Número de serie del equipo</label>"
            f'  <input name="serial" type="text" value="{safe_serial}" placeholder="SN123456" autofocus>'
            f'  <button type="submit">Generar</button>'
            f"</form>{err}{result}{reinstall_form}{_render_history(history or [])}{menu_html}")


if __name__ == "__main__":
    import lanzador
    lanzador.main(["--sin-navegador"])
