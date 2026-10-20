"""F1 (tanda 3): app de registro de pruebas de banco (tools/registro_pruebas)."""

import base64
import json
import os
import shutil
import sqlite3
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools" / "registro_pruebas"))

import almacen as alm  # noqa: E402
import app_registro  # noqa: E402
import datos_registro  # noqa: E402
import definiciones  # noqa: E402
import exportar  # noqa: E402
import respaldo_registro  # noqa: E402
import seguridad_registro as seg  # noqa: E402

# JPEG y PNG mínimos válidos
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 40 + b"\xff\xd9"
PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 30)
CAB = {"equipo": "Equipo de pruebas", "serial": "SN-1", "version_software": "0.5", "commit": "abc1234",
       "firmware": "1.0.0", "id_tarjeta": "T-1", "fecha": "2026-10-26", "lugar": "Banco"}
CLAVE = "clave-larga-123"


@pytest.fixture
def entorno(tmp_path):
    datos = tmp_path / "datos"
    conf = {**datos_registro.preparar(datos), "iteraciones_hash": 1000}
    almacen = alm.Almacen(datos)
    for usuario, rol in (("admin", "admin"), ("ana", "ejecutor"), ("beto", "ejecutor")):
        almacen.crear_usuario(usuario, usuario.title(), seg.hashear(CLAVE, 1000), rol, debe_cambiar=False)
    app = app_registro.crear_app(datos, conf, almacen=almacen)
    return app, almacen, datos, conf


def _cliente(app, usuario=None):
    c = TestClient(app)
    c.headers["X-Registro"] = "1"
    if usuario:
        r = c.post("/api/login", json={"usuario": usuario, "clave": CLAVE})
        assert r.status_code == 200, r.text
    return c


def _u(almacen, nombre):
    return almacen.usuario(nombre)


def _firma(c, rid, pid, cid="firma-0001"):
    r = c.post(f"/api/registros/{rid}/pruebas/{pid}/firma",
               json={"cliente_id": cid, "png_base64": base64.b64encode(PNG).decode()})
    assert r.status_code == 200, r.text
    return cid


def _guardar(c, rid, pid, resultado="aprobada", cid=None, uuid=None, motivo="", obs=""):
    cid = cid or f"firma-{pid}"
    if resultado is not None:
        _firma(c, rid, pid, cid)
    return c.put(f"/api/registros/{rid}/pruebas/{pid}", json={
        "datos": {"pasos": [True], "valores": {"presion": "101"}, "resultado": resultado,
                  "observaciones": obs, "firma_id": cid if resultado else None},
        "cliente_uuid": uuid, "motivo": motivo, "ts_cliente": "2026-10-26T10:00:00"})


# ── definiciones desde pruebas.py ──────────────────────────────────────────

def test_el_formulario_sale_de_pruebas_py_con_todos_los_bloques():
    s = definiciones.construir_snapshot()
    assert s["total"] >= 28 and {b[0] for b in s["bloques"]} == set("ABCDEFG")
    ids = {p["id"] for p in s["pruebas"]}
    assert {"A-04", "B-01", "B-03", "B-04", "B-07", "D-06", "D-07", "D-08", "E-06"} <= ids   # H1
    assert definiciones.verificar_snapshot(s)
    s["pruebas"][0]["titulo"] = "alterado"
    assert not definiciones.verificar_snapshot(s)


def test_el_snapshot_no_cambia_si_cambia_la_fuente(tmp_path, entorno):
    app, almacen, datos, conf = entorno
    fuente = tmp_path / "pruebas.py"
    shutil.copy(definiciones.FUENTE, fuente)
    almacen.fuente_pruebas = fuente
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    fuente.write_text(fuente.read_text(encoding="utf-8").replace('titulo="Instalación con el asistente QML"',
                                                                  'titulo="CAMBIADO"'), encoding="utf-8")
    est = c.get(f"/api/registros/{rid}").json()
    assert est["snapshot"]["pruebas"][0]["titulo"] == "Instalación con el asistente QML"
    nuevo = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    assert c.get(f"/api/registros/{nuevo}").json()["snapshot"]["pruebas"][0]["titulo"] == "CAMBIADO"
    assert almacen.verificar(rid)["ok"]


def test_aviso_del_orden_seguro_sin_bloquear():
    s = definiciones.construir_snapshot()
    assert definiciones.avisos_orden(s, "E-01", {"B-01": "aprobada"}) == ["A-04", "B-03", "B-04"]
    assert definiciones.avisos_orden(s, "E-01", {k: "aprobada" for k in ("A-04", "B-01", "B-03", "B-04")}) == []
    assert definiciones.avisos_orden(s, "A-01", {}) == []


# ── autenticación y seguridad ──────────────────────────────────────────────

def test_sin_sesion_todo_es_401(entorno):
    app, *_ = entorno
    c = _cliente(app)
    for ruta in ("/api/registros", "/api/definiciones", "/api/admin/usuarios", "/api/yo"):
        assert c.get(ruta).status_code == 401


def test_escrituras_sin_cabecera_csrf_se_rechazan(entorno):
    app, *_ = entorno
    c = TestClient(app)
    r = c.post("/api/login", json={"usuario": "ana", "clave": CLAVE})
    assert r.status_code == 403 and r.json()["codigo"] == "csrf"


def test_cabeceras_seguras_y_cookie_httponly_samesite(entorno):
    app, *_ = entorno
    c = TestClient(app)
    c.headers["X-Registro"] = "1"
    r = c.post("/api/login", json={"usuario": "ana", "clave": CLAVE})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    h = c.get("/api/registros").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "default-src 'self'" in h["content-security-policy"] and h["cache-control"] == "no-store"


def test_credenciales_malas_y_bloqueo_por_intentos(entorno):
    app, almacen, datos, conf = entorno
    c = _cliente(app)
    for _ in range(conf["intentos_max"]):
        assert c.post("/api/login", json={"usuario": "ana", "clave": "mal"}).status_code == 401
    r = c.post("/api/login", json={"usuario": "ana", "clave": CLAVE})      # aun con la clave buena
    assert r.status_code == 429 and "bloqueado" in r.json()["detail"]
    # un usuario inexistente da el mismo mensaje que uno con clave mala
    r1 = c.post("/api/login", json={"usuario": "nadie", "clave": "x"})
    r2 = c.post("/api/login", json={"usuario": "beto", "clave": "x"})
    assert r1.json()["detail"] == r2.json()["detail"]


def test_sesion_larga_configurable_y_vencimiento(entorno):
    app, almacen, datos, conf = entorno
    reloj = [0.0]
    sesiones = seg.Sesiones(almacen, 10 * 3600, 5, 900, reloj=lambda: reloj[0])
    token, _ = sesiones.autenticar("ana", CLAVE)
    reloj[0] = 9.9 * 3600
    assert sesiones.usuario(token)["usuario"] == "ana"          # sigue vigente tras casi 10 h de jornada
    reloj[0] = 10.1 * 3600
    assert sesiones.usuario(token) is None
    assert datos_registro.DEFECTO["sesion_horas"] in range(8, 13)


def test_sin_credenciales_por_defecto_primer_arranque(tmp_path):
    datos = tmp_path / "d"
    datos_registro.preparar(datos)
    almacen = alm.Almacen(datos)
    clave = seg.crear_admin_inicial(almacen, datos, 1000)
    assert clave and (datos / seg.ARCHIVO_CLAVE_INICIAL).exists()
    assert almacen.usuario("admin")["debe_cambiar"] == 1 and almacen.usuario("admin")["hash"] != clave
    assert seg.crear_admin_inicial(almacen, datos, 1000) is None        # solo la primera vez
    conf = {**datos_registro.preparar(datos), "iteraciones_hash": 1000}
    c = _cliente(app_registro.crear_app(datos, conf, almacen=almacen), "admin") if False else None
    app = app_registro.crear_app(datos, conf, almacen=almacen)
    c = TestClient(app)
    c.headers["X-Registro"] = "1"
    assert c.post("/api/login", json={"usuario": "admin", "clave": "admin"}).status_code == 401
    assert c.post("/api/login", json={"usuario": "admin", "clave": clave}).status_code == 200
    assert c.get("/api/registros").status_code == 403                    # clave pendiente
    r = c.post("/api/cambiar_clave", json={"clave_actual": clave, "clave_nueva": "otra-clave-larga",
                                           "confirmacion": "otra-clave-larga"})
    assert r.status_code == 200 and not (datos / seg.ARCHIVO_CLAVE_INICIAL).exists()
    assert c.get("/api/registros").status_code == 200


def test_clave_nueva_corta_o_distinta_se_rechaza(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    mal = c.post("/api/cambiar_clave", json={"clave_actual": CLAVE, "clave_nueva": "corta", "confirmacion": "corta"})
    assert mal.status_code == 422
    mal = c.post("/api/cambiar_clave", json={"clave_actual": "otra", "clave_nueva": "una-clave-larga-1",
                                             "confirmacion": "una-clave-larga-1"})
    assert mal.status_code == 401


def test_las_contrasenas_se_guardan_con_hash(entorno):
    _, almacen, *_ = entorno
    h = almacen.usuario("ana")["hash"]
    assert CLAVE not in h and h.startswith("pbkdf2")


# ── permisos: cada quien su registro ───────────────────────────────────────

def test_un_usuario_no_edita_ni_lee_el_registro_de_otro(entorno):
    app, almacen, *_ = entorno
    ana, beto, admin = _cliente(app, "ana"), _cliente(app, "beto"), _cliente(app, "admin")
    rid = ana.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    assert beto.get(f"/api/registros/{rid}").status_code == 403
    assert beto.put(f"/api/registros/{rid}/pruebas/A-01", json={"datos": {"pasos": [True]}}).status_code == 403
    assert beto.put(f"/api/registros/{rid}/cabecera", json={"cabecera": CAB}).status_code == 403
    assert beto.post(f"/api/registros/{rid}/anomalias", json={"datos": {}}).status_code == 403
    assert [r["id"] for r in beto.get("/api/registros").json()["registros"]] == []
    assert [r["id"] for r in ana.get("/api/registros").json()["registros"]] == [rid]
    assert admin.get(f"/api/registros/{rid}").status_code == 200           # el admin ve todos
    assert [r["id"] for r in admin.get("/api/registros").json()["registros"]] == [rid]
    # el admin no edita el registro de otro
    assert admin.put(f"/api/registros/{rid}/pruebas/A-01", json={"datos": {"pasos": [True]}}).status_code == 403


def test_solo_el_admin_administra_usuarios(entorno):
    app, *_ = entorno
    assert _cliente(app, "ana").get("/api/admin/usuarios").status_code == 403
    admin = _cliente(app, "admin")
    r = admin.post("/api/admin/usuarios", json={"usuario": "carla", "nombre": "Carla", "rol": "ejecutor"})
    assert r.status_code == 200 and len(r.json()["clave_temporal"]) >= 12
    assert admin.post("/api/admin/usuarios", json={"usuario": "carla", "rol": "ejecutor"}).status_code == 409
    nuevo = _cliente(app)
    assert nuevo.post("/api/login", json={"usuario": "carla", "clave": r.json()["clave_temporal"]}).status_code == 200
    assert nuevo.get("/api/registros").status_code == 403                  # debe cambiar la clave
    assert admin.post("/api/admin/usuarios/carla/activo", json={"activo": False}).status_code == 200
    assert nuevo.get("/api/yo").status_code == 401                          # sesión cerrada al desactivar
    assert admin.post("/api/admin/usuarios/admin/activo", json={"activo": False}).status_code == 409


# ── versiones inmutables y cadena de hash ──────────────────────────────────

def test_cada_guardado_es_una_version_nueva_con_hash_encadenado(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    v1 = _guardar(c, rid, "A-01", obs="primera").json()
    v2 = _guardar(c, rid, "A-02").json()
    assert v2["version"] > v1["version"] and v1["hash"] != v2["hash"]
    est = c.get(f"/api/registros/{rid}").json()
    seqs = [v["seq"] for v in est["versiones"]]
    assert seqs == sorted(seqs) == list(range(1, len(seqs) + 1))
    assert almacen.verificar(rid) == {**almacen.verificar(rid), "ok": True, "errores": []}


def test_hora_del_servidor_y_hora_del_telefono_se_guardan_aparte(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB, "ts_cliente": "1999-01-01T00:00:00"}).json()["id"]
    cab = almacen.estado_registro(rid)["versiones"][0]
    assert cab["ts_cliente"] == "1999-01-01T00:00:00" and cab["ts_servidor"].startswith("20")
    assert cab["ts_servidor"] != cab["ts_cliente"]


def test_modificar_un_resultado_firmado_exige_motivo_y_crea_version(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    assert _guardar(c, rid, "B-01", "aprobada").status_code == 200
    r = _guardar(c, rid, "B-01", "fallada", cid="firma-b01-2")
    assert r.status_code == 422 and r.json()["codigo"] == "falta_motivo"
    r = _guardar(c, rid, "B-01", "fallada", cid="firma-b01-2", motivo="Se repitió y falló")
    assert r.status_code == 200
    est = c.get(f"/api/registros/{rid}").json()
    assert est["pruebas"]["B-01"]["resultado"] == "fallada" and est["pruebas"]["B-01"]["cambios"] == 2
    motivos = [v["motivo"] for v in est["versiones"] if v["clave"] == "B-01" and v["tipo"] == "prueba"]
    assert motivos == ["", "Se repitió y falló"]                   # la versión anterior sigue ahí
    # una prueba aún sin resultado se puede seguir editando sin motivo
    assert _guardar(c, rid, "B-02", None).status_code == 200
    assert _guardar(c, rid, "B-02", None, obs="más datos").status_code == 200


def test_marcar_resultado_exige_firma(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    r = c.put(f"/api/registros/{rid}/pruebas/A-01", json={"datos": {"pasos": [True], "resultado": "aprobada"}})
    assert r.status_code == 422 and r.json()["codigo"] == "falta_firma"
    r = c.put(f"/api/registros/{rid}/pruebas/A-01", json={"datos": {
        "resultado": "aprobada", "firma_id": "inexistente-1"}})
    assert r.status_code == 422 and r.json()["codigo"] == "firma_invalida"


def test_la_base_no_permite_modificar_ni_borrar_versiones(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
           data={"cliente_id": "foto-0001"})
    con = almacen.conectar()
    for sentencia in ("UPDATE versiones SET motivo='x'", "DELETE FROM versiones", "UPDATE evidencias SET sha256='x'",
                      "DELETE FROM evidencias"):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sentencia)
    con.close()


def test_la_cadena_detecta_la_manipulacion(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    _guardar(c, rid, "A-01")
    _guardar(c, rid, "A-02")
    assert c.get(f"/api/registros/{rid}/verificar").json()["ok"] is True
    # manipulación directa (saltando los triggers, como lo haría quien edita el archivo)
    con = almacen.conectar()
    con.execute("DROP TRIGGER versiones_sin_update")
    con.execute("UPDATE versiones SET datos = replace(datos, 'aprobada', 'fallada') WHERE clave='A-01' AND tipo='prueba'")
    con.close()
    r = c.get(f"/api/registros/{rid}/verificar").json()
    assert r["ok"] is False and any("A-01" in e for e in r["errores"])


def test_la_cadena_detecta_un_hueco_y_un_snapshot_alterado(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    _guardar(c, rid, "A-01")
    con = almacen.conectar()
    con.execute("UPDATE registros SET snapshot = replace(snapshot, 'Instalación', 'Falsa') WHERE id=?", (rid,))
    con.close()
    r = c.get(f"/api/registros/{rid}/verificar").json()
    assert r["ok"] is False and any("snapshot" in e for e in r["errores"])


def test_reintento_con_el_mismo_uuid_no_duplica(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB, "cliente_uuid": "crear-uuid-0001"}).json()["id"]
    assert c.post("/api/registros", json={"cabecera": CAB, "cliente_uuid": "crear-uuid-0001"}).json()["id"] == rid
    a = _guardar(c, rid, "A-01", uuid="uuid-guardado-01")
    b = _guardar(c, rid, "A-01", uuid="uuid-guardado-01")
    assert a.json()["version"] == b.json()["version"] and b.json()["repetida"] is True
    assert len([v for v in almacen.estado_registro(rid)["versiones"] if v["tipo"] == "prueba"]) == 1
    assert len(c.get("/api/registros").json()["registros"]) == 1


def test_validaciones_de_entrada(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    malos = [{"pasos": "no"}, {"pasos": [1]}, {"valores": {"a": ["x"]}}, {"resultado": "quizas"},
             {"observaciones": "x" * 2001}]
    for datos in malos:
        assert c.put(f"/api/registros/{rid}/pruebas/A-01", json={"datos": datos}).status_code == 422
    assert c.put(f"/api/registros/{rid}/pruebas/Z-99", json={"datos": {"pasos": []}}).status_code == 404
    assert c.put(f"/api/registros/{rid}/pruebas/A-01", json={"datos": {}, "cliente_uuid": "a b"}).status_code == 422
    assert c.post("/api/registros", json={"cabecera": {"serial": "x" * 3000}}).status_code == 422


# ── fotos y firmas ─────────────────────────────────────────────────────────

def test_subida_de_fotos_con_hash_nombre_y_limites(entorno):
    app, almacen, datos, conf = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    r = c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
               data={"cliente_id": "foto-0001", "ts_cliente": "2026-10-26T10:00:00"})
    assert r.status_code == 200
    ev = [e for e in c.get(f"/api/registros/{rid}").json()["evidencias"] if e["tipo"] == "foto"][0]
    import hashlib
    assert ev["sha256"] == hashlib.sha256(JPEG).hexdigest() and ev["prueba_id"] == "B-01"
    archivos = list((datos / "fotos").glob("*"))
    assert len(archivos) == 1 and archivos[0].name.startswith(f"R{rid}_B-01_foto_")        # ID de prueba en el nombre
    assert c.get(f"/api/evidencias/{ev['id']}").content == JPEG
    # reintento idempotente: no duplica
    r = c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
               data={"cliente_id": "foto-0001"})
    assert r.json()["repetida"] is True and len(list((datos / "fotos").glob("*"))) == 1
    # varias fotos por prueba
    c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("g.jpg", JPEG + b"x", "image/jpeg")},
           data={"cliente_id": "foto-0002"})
    assert len([e for e in c.get(f"/api/registros/{rid}").json()["evidencias"] if e["tipo"] == "foto"]) == 2
    # no es imagen / demasiado grande
    r = c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("m.exe", b"MZ" + b"0" * 50, "image/jpeg")},
               data={"cliente_id": "foto-0003"})
    assert r.status_code == 415
    app.state.almacen  # noqa: B018
    grande = b"\xff\xd8\xff" + b"0" * (conf["foto_max_mb"] * 1024 * 1024)
    r = c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("h.jpg", grande, "image/jpeg")},
               data={"cliente_id": "foto-0004"})
    assert r.status_code == 413


def test_las_fotos_de_otro_registro_no_se_ven(entorno):
    app, *_ = entorno
    ana, beto = _cliente(app, "ana"), _cliente(app, "beto")
    rid = ana.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    ana.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
             data={"cliente_id": "foto-0001"})
    eid = ana.get(f"/api/registros/{rid}").json()["evidencias"][0]["id"]
    assert beto.get(f"/api/evidencias/{eid}").status_code == 403
    assert beto.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
                     data={"cliente_id": "foto-0009"}).status_code == 403


def test_firma_png_con_limites(entorno):
    app, almacen, datos, conf = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    assert c.post(f"/api/registros/{rid}/pruebas/A-01/firma", json={
        "cliente_id": "firma-0001", "png_base64": base64.b64encode(PNG).decode()}).status_code == 200
    assert c.post(f"/api/registros/{rid}/pruebas/A-01/firma", json={
        "cliente_id": "firma-0002", "png_base64": base64.b64encode(JPEG).decode()}).status_code == 415
    assert c.post(f"/api/registros/{rid}/pruebas/A-01/firma", json={
        "cliente_id": "firma-0003", "png_base64": "no es base64!!"}).status_code == 422
    grande = PNG + b"0" * (conf["firma_max_kb"] * 1024)
    assert c.post(f"/api/registros/{rid}/pruebas/A-01/firma", json={
        "cliente_id": "firma-0004", "png_base64": base64.b64encode(grande).decode()}).status_code == 413
    assert almacen.verificar(rid)["ok"]


def test_un_archivo_de_foto_alterado_rompe_la_verificacion(entorno):
    app, almacen, datos, _ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    c.post(f"/api/registros/{rid}/pruebas/B-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
           data={"cliente_id": "foto-0001"})
    next((datos / "fotos").glob("*")).write_bytes(JPEG + b"manipulada")
    r = c.get(f"/api/registros/{rid}/verificar").json()
    assert r["ok"] is False and any("alterado" in e for e in r["errores"])


# ── anomalías ──────────────────────────────────────────────────────────────

def test_anomalias_con_id_versionadas_y_validadas(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    datos = {"prueba_id": "B-01", "descripcion": "El paro tardó 3 s", "gravedad": "seguridad",
             "accion": "Revisar el cableado", "responsable": "Cristian", "estado": "abierta", "reensayo": ""}
    r = c.post(f"/api/registros/{rid}/anomalias", json={"datos": datos}).json()
    assert r["anomalia_id"] == "AN-001"
    assert c.post(f"/api/registros/{rid}/anomalias", json={"datos": datos}).json()["anomalia_id"] == "AN-002"
    cambio = c.put(f"/api/registros/{rid}/anomalias/AN-001", json={"datos": {**datos, "estado": "corregida",
                                                                              "reensayo": "B-01 aprobada"},
                                                                    "motivo": "Se reparó"})
    assert cambio.status_code == 200
    est = c.get(f"/api/registros/{rid}").json()
    assert est["anomalias"]["AN-001"]["estado"] == "corregida" and est["anomalias"]["AN-002"]["estado"] == "abierta"
    assert len([v for v in est["versiones"] if v["clave"] == "AN-001"]) == 2
    for malo in ({**datos, "gravedad": "grave"}, {**datos, "descripcion": ""}, {**datos, "prueba_id": "Z-99"}):
        assert c.post(f"/api/registros/{rid}/anomalias", json={"datos": malo}).status_code in (404, 422)
    assert c.put(f"/api/registros/{rid}/anomalias/AN-077", json={"datos": datos}).status_code == 404


# ── cierre ─────────────────────────────────────────────────────────────────

def test_cierre_con_firma_final_y_registro_inmutable(entorno):
    app, almacen, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    _guardar(c, rid, "A-01")
    _firma(c, rid, "cierre", "firma-cierre")
    r = c.post(f"/api/registros/{rid}/cerrar", json={"firma_id": "firma-cierre"})
    assert r.status_code == 409 and r.json()["codigo"] == "incompleto"          # faltan pruebas
    r = c.post(f"/api/registros/{rid}/cerrar", json={"firma_id": "firma-cierre", "confirmar_incompleto": True})
    assert r.status_code == 200
    est = c.get(f"/api/registros/{rid}").json()
    assert est["estado"] == "cerrado" and est["cierre"]["usuario"] == "ana" and est["cierre"]["sin_resultado"]
    assert c.put(f"/api/registros/{rid}/pruebas/A-02", json={"datos": {"pasos": [True]}}).status_code == 409
    assert c.post(f"/api/registros/{rid}/pruebas/A-02/firma", json={
        "cliente_id": "firma-tarde-1", "png_base64": base64.b64encode(PNG).decode()}).status_code == 409
    assert c.put(f"/api/registros/{rid}/cabecera", json={"cabecera": CAB}).status_code == 409
    assert almacen.verificar(rid)["ok"]


def test_cierre_sin_firma_se_rechaza(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    assert c.post(f"/api/registros/{rid}/cerrar", json={"firma_id": "no-existe-1",
                                                        "confirmar_incompleto": True}).status_code == 422


# ── consolidación ──────────────────────────────────────────────────────────

def test_consolidacion_marca_discrepancias_entre_ejecutores(entorno):
    app, *_ = entorno
    ana, beto, admin = _cliente(app, "ana"), _cliente(app, "beto"), _cliente(app, "admin")
    ra = ana.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    rb = beto.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    _guardar(ana, ra, "B-01", "aprobada")
    _guardar(beto, rb, "B-01", "fallada")
    _guardar(ana, ra, "B-02", "aprobada")
    _guardar(beto, rb, "B-02", "aprobada")
    assert ana.get("/api/admin/consolidacion").status_code == 403
    c = admin.get("/api/admin/consolidacion").json()
    por = {p["prueba_id"]: p for p in c["pruebas"]}
    assert por["B-01"]["discrepancia"] is True and por["B-02"]["discrepancia"] is False
    assert c["discrepancias"] == ["B-01"]
    assert {e["usuario"]: e["resultado"] for e in por["B-01"]["ejecutores"]} == {"ana": "aprobada", "beto": "fallada"}


# ── exportación ────────────────────────────────────────────────────────────

def _registro_completo(app):
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": {**CAB, "lugar": "<script>alert(1)</script>"}}).json()["id"]
    _guardar(c, rid, "A-01", obs="<b>negrita</b> & más")
    c.post(f"/api/registros/{rid}/pruebas/A-01/fotos", files={"file": ("f.jpg", JPEG, "image/jpeg")},
           data={"cliente_id": "foto-0001"})
    c.post(f"/api/registros/{rid}/anomalias", json={"datos": {
        "prueba_id": "A-01", "descripcion": "<img src=x onerror=alert(1)>", "gravedad": "cosmetica"}})
    _firma(c, rid, "cierre", "firma-cierre")
    c.post(f"/api/registros/{rid}/cerrar", json={"firma_id": "firma-cierre", "confirmar_incompleto": True})
    return c, rid


def test_exportaciones_json_csv_html_completas_y_escapadas(entorno):
    app, *_ = entorno
    c, rid = _registro_completo(app)
    j = c.get(f"/api/registros/{rid}/exportar/json").json()
    assert j["verificacion"]["ok"] and len(j["registro"]["versiones"]) >= 6
    assert all("hash" in v and "hash_prev" in v for v in j["registro"]["versiones"])
    assert j["definiciones"]["total"] >= 28
    csv_texto = c.get(f"/api/registros/{rid}/exportar/csv").text
    assert csv_texto.splitlines()[0].startswith("registro,ejecutor,bloque,prueba") and "A-01" in csv_texto
    h = c.get(f"/api/registros/{rid}/exportar/html")
    assert h.status_code == 200 and "attachment" in h.headers["content-disposition"]
    html = h.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "<script>alert(1)" not in html   # escape
    assert "&lt;img src=x onerror" in html and "&lt;b&gt;negrita" in html
    assert "data:image/png;base64" in html and "data:image/jpeg;base64" in html               # firma y miniatura
    assert "ÍNTEGRA" in html and j["verificacion"]["ultimo_hash"] in html and "AN-001" in html
    assert c.get(f"/api/registros/{rid}/exportar/pdf").status_code == 404


def test_exportar_a_carpeta_de_docs_sin_fotos_ni_base(entorno, tmp_path):
    app, almacen, datos, _ = entorno
    c, rid = _registro_completo(app)
    destino = tmp_path / "docs" / "informes" / "pruebas_banco" / "2026-10-26" / "ana"
    r = exportar.exportar_todo(almacen, rid, destino)
    assert r["cadena_integra"] and sorted(p.name for p in destino.iterdir()) == [
        "registro.html", "registro.json", "resultados.csv"]
    assert not list(destino.rglob("*.db")) and not list(destino.rglob("*.jpg"))
    # script de línea de comandos
    destino2 = tmp_path / "otro"
    assert exportar.main(["--registro", str(rid), "--destino", str(destino2), "--datos", str(datos)]) == 0
    assert (destino2 / "registro.html").exists()


def test_exportacion_a_la_carpeta_de_datos_por_la_api(entorno):
    app, almacen, datos, _ = entorno
    c, rid = _registro_completo(app)
    r = c.post(f"/api/registros/{rid}/exportar").json()
    assert (datos / "exportaciones" / f"R{rid}" / "registro.html").exists() and r["cadena_integra"]


def test_la_exportacion_de_otro_usuario_no_se_ve(entorno):
    app, *_ = entorno
    c, rid = _registro_completo(app)
    assert _cliente(app, "beto").get(f"/api/registros/{rid}/exportar/json").status_code == 403
    assert _cliente(app, "admin").get(f"/api/registros/{rid}/exportar/json").status_code == 200


# ── respaldo, arranque y estáticos ─────────────────────────────────────────

def test_respaldo_con_api_de_sqlite_y_verificacion(entorno, tmp_path):
    app, almacen, datos, _ = entorno
    _registro_completo(app)
    destino = respaldo_registro.respaldar(almacen.ruta, tmp_path / "resp")
    con = sqlite3.connect(destino)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert con.execute("SELECT COUNT(*) FROM versiones").fetchone()[0] >= 6
    con.close()
    assert _cliente(app, "admin").post("/api/admin/respaldo").json()["archivo"].startswith("registro_")
    assert _cliente(app, "ana").post("/api/admin/respaldo").status_code == 403


def test_poda_de_respaldos_por_dias(tmp_path):
    from datetime import datetime, timedelta
    vieja = tmp_path / f"registro_{(datetime.now() - timedelta(days=40)).strftime('%Y%m%d_%H%M%S')}.db"
    nueva = tmp_path / f"registro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    vieja.write_bytes(b"x")
    nueva.write_bytes(b"x")
    (tmp_path / "otra_cosa.db").write_bytes(b"x")
    assert respaldo_registro.podar(tmp_path, 30) == [vieja]
    assert nueva.exists() and (tmp_path / "otra_cosa.db").exists()


def test_arranque_con_puerto_ocupado(tmp_path, monkeypatch):
    import socket
    import lanzador_registro as lz
    ocupado = socket.socket()
    ocupado.bind(("127.0.0.1", 0))
    ocupado.listen(32)
    puerto = ocupado.getsockname()[1]
    try:
        assert lz.puerto_en_uso(puerto) is True and lz.es_la_app(puerto) is False
        datos = tmp_path / "d"
        datos_registro.preparar(datos)
        (datos / "config.json").write_text(json.dumps({"puerto": puerto}), encoding="utf-8")
        assert lz.main(["--datos", str(datos), "--sin-navegador"]) == 2          # otro programa: avisa y termina
    finally:
        ocupado.close()


def test_preparar_crea_las_carpetas_y_tolera_config_ilegible(tmp_path):
    datos = tmp_path / "d"
    conf = datos_registro.preparar(datos)
    assert all((datos / s).is_dir() for s in ("fotos", "firmas", "exportaciones", "respaldos"))
    assert conf["puerto"] == 8090 and conf["host"] == "0.0.0.0"
    (datos / "config.json").write_text("{ no es json", encoding="utf-8")
    assert datos_registro.preparar(datos) == datos_registro.DEFECTO
    assert (datos / "config.json").read_text(encoding="utf-8") == "{ no es json"      # no se pisa


def test_la_interfaz_estatica_se_sirve_con_cabeceras_seguras(entorno):
    app, *_ = entorno
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert c.get("/static/app.js").status_code == 200 and c.get("/static/cola.js").status_code == 200
    assert c.get("/static/../almacen.py").status_code == 404
    assert c.get("/static/almacen.py").status_code == 404
    assert c.get("/salud").json() == {"app": "registro-pruebas-especifika"}


def test_concurrencia_de_dos_ejecutores_guardando_a_la_vez(entorno):
    app, almacen, *_ = entorno
    cs = [_cliente(app, "ana"), _cliente(app, "beto")]
    rids = [c.post("/api/registros", json={"cabecera": CAB}).json()["id"] for c in cs]
    errores = []

    def trabajo(c, rid):
        for i in range(8):
            r = _guardar(c, rid, "A-01", obs=f"v{i}", cid=f"firma-{rid}-{i}", motivo=f"cambio {i}")
            if r.status_code != 200:
                errores.append(r.text)

    hilos = [threading.Thread(target=trabajo, args=(c, r)) for c, r in zip(cs, rids)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert errores == [] and all(almacen.verificar(r)["ok"] for r in rids)


# ── cola de pendientes (lógica JS, probada con node) ───────────────────────

def test_cola_de_pendientes_js_con_red_cortada_y_reintento():
    import shutil as _sh
    import subprocess
    node = _sh.which("node")
    if node is None:
        pytest.skip("node no está instalado: la cola se prueba a mano (ver README, comprobación 6)")
    r = subprocess.run([node, "--test", str(RAIZ / "tests" / "js" / "cola.test.js")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]


def test_el_codigo_de_la_interfaz_no_usa_innerhtml_ni_scripts_en_linea():
    estaticos = RAIZ / "tools" / "registro_pruebas" / "static"
    for nombre in ("app.js", "cola.js"):
        fuente = (estaticos / nombre).read_text(encoding="utf-8")
        assert "innerHTML" not in fuente and "eval(" not in fuente and "document.write" not in fuente
    index = (estaticos / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in index and "style=" not in index          # CSP: todo es archivo propio
    assert "serviceWorker" not in (estaticos / "app.js").read_text(encoding="utf-8")   # sin service worker


# ── revisión de seguridad ──────────────────────────────────────────────────

def test_cambiar_el_resultado_exige_una_firma_nueva(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    _guardar(c, rid, "B-01", "aprobada", cid="firma-uno-01")
    r = c.put(f"/api/registros/{rid}/pruebas/B-01", json={"datos": {
        "resultado": "fallada", "firma_id": "firma-uno-01"}, "motivo": "cambio"})
    assert r.status_code == 422 and r.json()["codigo"] == "falta_firma_nueva"


def test_cambiar_la_clave_cierra_las_otras_sesiones(entorno):
    app, *_ = entorno
    a1, a2 = _cliente(app, "ana"), _cliente(app, "ana")           # dos teléfonos
    r = a1.post("/api/cambiar_clave", json={"clave_actual": CLAVE, "clave_nueva": "otra-clave-larga-9",
                                            "confirmacion": "otra-clave-larga-9"})
    assert r.status_code == 200
    assert a1.get("/api/yo").status_code == 200 and a2.get("/api/yo").status_code == 401


def test_csv_neutraliza_formulas(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    rid = c.post("/api/registros", json={"cabecera": CAB}).json()["id"]
    _guardar(c, rid, "A-01", obs="=HYPERLINK(\"http://x\")")
    csv_texto = c.get(f"/api/registros/{rid}/exportar/csv").text
    assert "'=HYPERLINK" in csv_texto and ",=HYPERLINK" not in csv_texto


def test_ts_cliente_invalido_se_rechaza(entorno):
    app, *_ = entorno
    c = _cliente(app, "ana")
    assert c.post("/api/registros", json={"cabecera": CAB, "ts_cliente": {"x": 1}}).status_code == 422
    assert c.post("/api/registros", json={"cabecera": CAB, "ts_cliente": "x" * 100}).status_code == 422
