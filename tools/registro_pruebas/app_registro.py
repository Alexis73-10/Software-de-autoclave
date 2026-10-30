"""
App de registro de pruebas de banco (F1, tanda 3), para el teléfono (Android,
Chrome) por la red Wi-Fi local del banco. FastAPI + SQLite + HTML/JS sin
frameworks. Corre en el PC de Cristian; 2 personas, cada una con su usuario y su
propio registro; fotos como evidencia; firma en pantalla; versiones inmutables
con hash encadenado.

Desarrollo:   python tools/registro_pruebas/lanzador_registro.py
Acceso:       http://<ip-del-PC>:8090   (la IP aparece en la pantalla de login)

Seguridad: solo red local (firewall: abrir_firewall.ps1), sin credenciales por
defecto, contraseñas con hash, bloqueo por intentos, sesión larga configurable,
límites de subida, escape de HTML (la interfaz usa textContent; las exportaciones
escapan), cabecera personalizada obligatoria en escrituras + cookie SameSite
Strict (CSRF), y cabeceras seguras.
"""

import base64
import binascii
import os
import socket
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)

import almacen as alm  # noqa: E402
import definiciones  # noqa: E402
import exportar  # noqa: E402
import respaldo_registro  # noqa: E402
import seguridad_registro as seg  # noqa: E402

IDENTIDAD = "registro-pruebas-especifika"
COOKIE = "session"
CABECERA_CSRF = "x-registro"
ESTATICOS = Path(_AQUI) / "static"
TIPOS_ESTATICOS = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                   "cola.js": "text/javascript; charset=utf-8", "app.css": "text/css; charset=utf-8"}
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")


def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _tipo_imagen(datos: bytes) -> tuple[str, str] | None:
    if datos[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", ".png"
    return None


def crear_app(datos: Path, conf: dict, almacen: alm.Almacen | None = None,
              sesiones: seg.Sesiones | None = None, fuente_pruebas: Path | None = None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    almacen = almacen or alm.Almacen(datos, fuente_pruebas)
    sesiones = sesiones or seg.Sesiones(almacen, conf["sesion_horas"] * 3600, conf["intentos_max"],
                                        conf["bloqueo_min"] * 60)
    iteraciones = int(conf.get("iteraciones_hash") or 0)
    max_foto = int(conf["foto_max_mb"]) * 1024 * 1024
    max_firma = int(conf["firma_max_kb"]) * 1024
    url = f"http://{ip_local()}:{conf['puerto']}"
    app.state.almacen, app.state.sesiones = almacen, sesiones

    # ── cabeceras seguras y CSRF ─────────────────────────────────────────
    @app.middleware("http")
    async def seguridad(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/"):
            if request.headers.get(CABECERA_CSRF) != "1":
                return JSONResponse({"codigo": "csrf", "detail": "Petición no permitida"}, status_code=403)
        respuesta = await call_next(request)
        respuesta.headers["Content-Security-Policy"] = CSP
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta

    @app.exception_handler(alm.ErrorRegistro)
    async def _error(_r: Request, e: alm.ErrorRegistro):
        return JSONResponse({"codigo": e.codigo, "detail": e.motivo}, status_code=e.estado)

    # ── autenticación ────────────────────────────────────────────────────
    def actual(request: Request) -> dict | None:
        return sesiones.usuario(request.cookies.get(COOKIE))

    def exigir(request: Request, admin: bool = False, permitir_cambio: bool = False) -> dict:
        u = actual(request)
        if u is None:
            raise alm.ErrorRegistro("sesion_invalida", "Sesión no válida o vencida: inicie sesión", 401)
        if u["debe_cambiar"] and not permitir_cambio:
            raise alm.ErrorRegistro("clave_pendiente", "Debe cambiar la contraseña", 403)
        if admin and u["rol"] != "admin":
            raise alm.ErrorRegistro("solo_admin", "Solo el administrador", 403)
        return u

    def publico(u: dict) -> dict:
        return {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"],
                "debe_cambiar": bool(u["debe_cambiar"])}

    @app.get("/salud")
    async def salud():
        return {"app": IDENTIDAD}

    @app.get("/api/info")
    async def info():
        return {"app": IDENTIDAD, "url": url}

    @app.post("/api/login")
    async def login(request: Request, cuerpo: dict):
        usuario = str(cuerpo.get("usuario", "")).strip()
        clave = str(cuerpo.get("clave", ""))
        if not usuario or not clave:
            raise alm.ErrorRegistro("validacion", "Ingrese usuario y contraseña", 422)
        token, motivo = sesiones.autenticar(usuario, clave)
        if token is None:
            raise alm.ErrorRegistro("credenciales", motivo, 429 if "bloqueado" in motivo else 401)
        u = almacen.usuario(usuario)
        r = JSONResponse(publico(u))
        r.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/",
                     max_age=int(conf["sesion_horas"] * 3600))
        return r

    @app.post("/api/logout")
    async def logout(request: Request):
        sesiones.cerrar(request.cookies.get(COOKIE))
        r = JSONResponse({"ok": True})
        r.delete_cookie(COOKIE, path="/")
        return r

    @app.get("/api/yo")
    async def yo(request: Request):
        return publico(exigir(request, permitir_cambio=True))

    @app.post("/api/cambiar_clave")
    async def cambiar_clave(request: Request, cuerpo: dict):
        u = exigir(request, permitir_cambio=True)
        if not sesiones.verificar_clave(u["usuario"], str(cuerpo.get("clave_actual", ""))):
            raise alm.ErrorRegistro("credenciales", "La contraseña actual no es correcta", 401)
        motivo = seg.validar_clave_nueva(str(cuerpo.get("clave_nueva", "")), str(cuerpo.get("confirmacion", "")))
        if motivo:
            raise alm.ErrorRegistro("validacion", motivo, 422)
        almacen.fijar_clave(u["usuario"], seg.hashear(str(cuerpo["clave_nueva"]), iteraciones), False)
        sesiones.cerrar_de(u["usuario"], excepto=request.cookies.get(COOKIE))   # REG-02
        if u["usuario"] == "admin":
            (datos / seg.ARCHIVO_CLAVE_INICIAL).unlink(missing_ok=True)
        return {"ok": True}

    # ── definiciones y registros ─────────────────────────────────────────
    @app.get("/api/definiciones")
    async def get_definiciones(request: Request):
        exigir(request)
        s = definiciones.construir_snapshot(almacen.fuente_pruebas)
        return {"hash": s["hash"], "total": s["total"], "bloques": s["bloques"], "pruebas": s["pruebas"]}

    @app.get("/api/registros")
    async def listar(request: Request):
        return {"registros": almacen.listar_registros(exigir(request))}

    @app.post("/api/registros")
    async def crear(request: Request, cuerpo: dict):
        u = exigir(request)
        rid = almacen.crear_registro(u["usuario"], cuerpo.get("cabecera") or {}, cuerpo.get("ts_cliente"),
                                     cuerpo.get("cliente_uuid"))
        return {"id": rid}

    @app.get("/api/registros/{rid}")
    async def ver(request: Request, rid: int):
        almacen.acceso(rid, exigir(request))
        e = almacen.estado_registro(rid)
        # la UI no necesita el JSON completo de cada versión: se deja un resumen
        e["versiones"] = [{k: v[k] for k in ("seq", "clave", "tipo", "usuario", "ts_servidor", "motivo")}
                          for v in e["versiones"]]
        return e

    @app.put("/api/registros/{rid}/cabecera")
    async def cabecera(request: Request, rid: int, cuerpo: dict):
        u = exigir(request)
        v = almacen.guardar_cabecera(rid, u, cuerpo.get("cabecera") or {}, cuerpo.get("ts_cliente"),
                                     cuerpo.get("cliente_uuid"), str(cuerpo.get("motivo", "")))
        return {"ok": True, "version": v["seq"], "repetida": bool(v.get("repetida"))}

    @app.put("/api/registros/{rid}/pruebas/{pid}")
    async def prueba(request: Request, rid: int, pid: str, cuerpo: dict):
        u = exigir(request)
        v = almacen.guardar_prueba(rid, u, pid, cuerpo.get("datos") or {}, cuerpo.get("ts_cliente"),
                                   cuerpo.get("cliente_uuid"), str(cuerpo.get("motivo", "")))
        return {"ok": True, "version": v["seq"], "hash": v["hash"], "repetida": bool(v.get("repetida"))}

    @app.post("/api/registros/{rid}/pruebas/{pid}/fotos")
    async def foto(request: Request, rid: int, pid: str, file: UploadFile = File(...),
                   cliente_id: str = Form(...), ts_cliente: str = Form(default="")):
        u = exigir(request)
        contenido = await file.read(max_foto + 1)
        if len(contenido) > max_foto:
            raise alm.ErrorRegistro("demasiado_grande", f"La foto supera {conf['foto_max_mb']} MB", 413)
        tipo = _tipo_imagen(contenido)
        if tipo is None:
            raise alm.ErrorRegistro("tipo_invalido", "La foto debe ser JPEG o PNG", 415)
        r = almacen.guardar_evidencia(rid, u, pid, "foto", cliente_id, contenido, tipo[1], ts_cliente or None)
        return {"ok": True, "id": r["id"], "sha256": r["sha256"], "repetida": bool(r.get("repetida"))}

    @app.post("/api/registros/{rid}/pruebas/{pid}/firma")
    async def firma(request: Request, rid: int, pid: str, cuerpo: dict):
        u = exigir(request)
        try:
            contenido = base64.b64decode(str(cuerpo.get("png_base64", "")), validate=True)
        except (binascii.Error, ValueError):
            raise alm.ErrorRegistro("validacion", "Firma inválida", 422)
        if len(contenido) > max_firma:
            raise alm.ErrorRegistro("demasiado_grande", f"La firma supera {conf['firma_max_kb']} KB", 413)
        if _tipo_imagen(contenido) != ("image/png", ".png"):
            raise alm.ErrorRegistro("tipo_invalido", "La firma debe ser PNG", 415)
        r = almacen.guardar_evidencia(rid, u, pid, "firma", str(cuerpo.get("cliente_id", "")), contenido,
                                      ".png", cuerpo.get("ts_cliente"))
        return {"ok": True, "id": r["id"], "sha256": r["sha256"], "repetida": bool(r.get("repetida"))}

    @app.get("/api/evidencias/{eid}")
    async def evidencia(request: Request, eid: int):
        u = exigir(request)
        ev = almacen.evidencia(eid)
        if ev is None:
            raise alm.ErrorRegistro("no_existe", "La evidencia no existe", 404)
        almacen.acceso(ev["registro_id"], u)
        ruta = (almacen.datos / ev["archivo"]).resolve()
        if not str(ruta).startswith(str(almacen.datos.resolve())) or not ruta.is_file():
            raise alm.ErrorRegistro("no_existe", "Archivo no disponible", 404)
        return FileResponse(ruta, media_type="image/png" if ruta.suffix == ".png" else "image/jpeg")

    @app.post("/api/registros/{rid}/anomalias")
    async def anomalia_nueva(request: Request, rid: int, cuerpo: dict):
        u = exigir(request)
        v = almacen.guardar_anomalia(rid, u, cuerpo.get("datos") or {}, None, cuerpo.get("ts_cliente"),
                                     cuerpo.get("cliente_uuid"))
        return {"ok": True, "anomalia_id": v.get("anomalia_id") or v["clave"], "repetida": bool(v.get("repetida"))}

    @app.put("/api/registros/{rid}/anomalias/{an}")
    async def anomalia_cambia(request: Request, rid: int, an: str, cuerpo: dict):
        u = exigir(request)
        v = almacen.guardar_anomalia(rid, u, cuerpo.get("datos") or {}, an, cuerpo.get("ts_cliente"),
                                     cuerpo.get("cliente_uuid"), str(cuerpo.get("motivo", "")))
        return {"ok": True, "anomalia_id": an, "repetida": bool(v.get("repetida"))}

    @app.post("/api/registros/{rid}/cerrar")
    async def cerrar(request: Request, rid: int, cuerpo: dict):
        u = exigir(request)
        v = almacen.cerrar_registro(rid, u, str(cuerpo.get("firma_id", "")),
                                    cuerpo.get("confirmar_incompleto") is True, cuerpo.get("ts_cliente"),
                                    cuerpo.get("cliente_uuid"))
        return {"ok": True, "hash": v["hash"]}

    @app.get("/api/registros/{rid}/verificar")
    async def verificar(request: Request, rid: int):
        almacen.acceso(rid, exigir(request))
        return almacen.verificar(rid)

    @app.get("/api/registros/{rid}/exportar/{formato}")
    async def exportar_descarga(request: Request, rid: int, formato: str):
        almacen.acceso(rid, exigir(request))
        estado, ver = almacen.estado_registro(rid), almacen.verificar(rid)
        if formato == "json":
            cuerpo, tipo = exportar.exportar_json(estado, ver), "application/json"
        elif formato == "csv":
            cuerpo, tipo = exportar.exportar_csv(estado), "text/csv; charset=utf-8"
        elif formato == "html":
            cuerpo, tipo = exportar.exportar_html(estado, ver, almacen.datos), "text/html; charset=utf-8"
        else:
            raise alm.ErrorRegistro("formato", "Formato: json, csv o html", 404)
        return Response(cuerpo, media_type=tipo,
                        headers={"Content-Disposition": f'attachment; filename="registro_{rid}.{formato}"'})

    @app.post("/api/registros/{rid}/exportar")
    async def exportar_a_carpeta(request: Request, rid: int):
        almacen.acceso(rid, exigir(request))
        return exportar.exportar_todo(almacen, rid)

    # ── administración ───────────────────────────────────────────────────
    @app.get("/api/admin/usuarios")
    async def usuarios(request: Request):
        exigir(request, admin=True)
        return {"usuarios": almacen.listar_usuarios()}

    @app.post("/api/admin/usuarios")
    async def usuario_nuevo(request: Request, cuerpo: dict):
        exigir(request, admin=True)
        temporal = seg.clave_temporal()
        almacen.crear_usuario(str(cuerpo.get("usuario", "")).strip(), str(cuerpo.get("nombre", "")),
                              seg.hashear(temporal, iteraciones), str(cuerpo.get("rol", "ejecutor")))
        return {"ok": True, "clave_temporal": temporal}

    @app.post("/api/admin/usuarios/{usuario}/activo")
    async def usuario_activo(request: Request, usuario: str, cuerpo: dict):
        exigir(request, admin=True)
        activo = cuerpo.get("activo") is True
        fila = almacen.usuario(usuario)
        if fila is None:
            raise alm.ErrorRegistro("no_existe", "El usuario no existe", 404)
        if not activo and fila["rol"] == "admin" and almacen.admins_activos() <= 1:
            raise alm.ErrorRegistro("ultimo_admin", "No se puede desactivar al único administrador", 409)
        almacen.fijar_activo(usuario, activo)
        if not activo:
            sesiones.cerrar_de(usuario)
        return {"ok": True}

    @app.post("/api/admin/usuarios/{usuario}/clave")
    async def usuario_clave(request: Request, usuario: str):
        exigir(request, admin=True)
        if almacen.usuario(usuario) is None:
            raise alm.ErrorRegistro("no_existe", "El usuario no existe", 404)
        temporal = seg.clave_temporal()
        almacen.fijar_clave(usuario, seg.hashear(temporal, iteraciones), True)
        sesiones.cerrar_de(usuario)
        return {"ok": True, "clave_temporal": temporal}

    @app.get("/api/admin/consolidacion")
    async def consolidacion(request: Request):
        exigir(request, admin=True)
        return almacen.consolidar()

    @app.post("/api/admin/respaldo")
    async def respaldo(request: Request):
        exigir(request, admin=True)
        destino = respaldo_registro.respaldar(almacen.ruta, almacen.datos / "respaldos")
        if destino is None:
            raise alm.ErrorRegistro("respaldo_fallido", "No se pudo respaldar la base", 500)
        return {"ok": True, "archivo": destino.name}

    # ── interfaz estática ────────────────────────────────────────────────
    @app.get("/")
    async def raiz():
        return FileResponse(ESTATICOS / "index.html", media_type=TIPOS_ESTATICOS["index.html"],
                            headers={"Cache-Control": "no-store"})

    @app.get("/static/{nombre}")
    async def estatico(nombre: str):
        if nombre not in TIPOS_ESTATICOS:
            return JSONResponse({"codigo": "no_existe", "detail": "No existe"}, status_code=404)
        return FileResponse(ESTATICOS / nombre, media_type=TIPOS_ESTATICOS[nombre],
                            headers={"Cache-Control": "no-store"})

    return app
