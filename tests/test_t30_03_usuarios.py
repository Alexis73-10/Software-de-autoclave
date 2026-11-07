# tests/test_t30_03_usuarios.py
#
# T30-03 (tanda 30): usuarios — eliminar, cambiar el rol y cambiar la propia
# contraseña. Reemplaza en parte U11 (tanda 11): el rol sí se cambia; nombre y
# usuario siguen sin editarse.
# - Base: migración v13 (columna `eliminado`, triggers: no se restaura, una
#   cuenta del sistema no se elimina); el eliminado no se lista, no inicia
#   sesión, no cuenta en las reglas, pero su nombre no se reutiliza.
# - API: DELETE /usuarios/{u} elimina; PATCH /usuarios/{u} con `rol` cambia el
#   rol; mismas reglas que desactivar; cierran sesiones; bitácora.
# - Cliente: códigos con ruta y texto (es/en); controlador; pantalla; cambio
#   voluntario de la contraseña desde Opciones › Usuarios (sin logout).

import ast
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.backend.contrasenas import hash_password
from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.db_manager import DbManager

RAIZ = Path(__file__).resolve().parents[1]
_I18N = RAIZ / "src" / "autoclave" / "i18n"


def _fila(db, usuario):
    with db._lock:
        r = db._conn.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
    return dict(r) if r else None


# ── base de datos ──────────────────────────────────────────────────────────

def test_migracion_v13_sobre_bd_v12(tmp_path, monkeypatch):
    ruta = tmp_path / "v12.db"
    with monkeypatch.context() as m:
        m.setattr(dbm, "_MIGRACIONES", tuple(x for x in dbm._MIGRACIONES if x[0] <= 12))
        db = DbManager(db_path=ruta)
        assert db.get_version_esquema() == 12
        assert "eliminado" not in {f[1] for f in db._conn.execute("PRAGMA table_info(usuarios)")}
        db.crear_usuario("Pepe", "pepe", "h", "tecnico")
        db.close()
    db = DbManager(db_path=ruta)
    try:
        assert db.get_version_esquema() == dbm.ESQUEMA_VERSION == 13
        assert _fila(db, "pepe")["eliminado"] == 0 and _fila(db, "Admin")["eliminado"] == 0
        assert [u["usuario"] for u in db.listar_usuarios()].count("pepe") == 1
    finally:
        db.close()
    # idempotente: reabrir no cambia nada
    db = DbManager(db_path=ruta)
    assert db.get_version_esquema() == 13
    db.close()


@pytest.mark.parametrize("sql", [
    "UPDATE usuarios SET eliminado=0 WHERE usuario='pepe'",          # no se restaura
    "UPDATE usuarios SET activo=1 WHERE usuario='pepe'",             # ni se reactiva
    "UPDATE usuarios SET usuario='otro' WHERE usuario='pepe'",       # el nombre queda
    "UPDATE usuarios SET eliminado=1 WHERE usuario='Admin'",         # cuenta del sistema
    "UPDATE usuarios SET eliminado=1 WHERE usuario='Ingeniero'",
    "DELETE FROM usuarios WHERE usuario='pepe'",                     # nunca se borra la fila
])
def test_triggers_v13(tmp_path, sql):
    db = DbManager(db_path=tmp_path / "t.db")
    db.crear_usuario("Pepe", "pepe", "h", "tecnico")
    assert db.eliminar_usuario("pepe", "ingeniero") == "ok"
    with pytest.raises(sqlite3.DatabaseError):
        with db._lock:
            db._conn.execute(sql)
    db._conn.rollback()
    assert _fila(db, "pepe")["eliminado"] == 1 and _fila(db, "pepe")["activo"] == 0
    assert _fila(db, "Admin")["eliminado"] == 0
    db.close()


def test_eliminado_fuera_de_listas_login_y_reglas_pero_nombre_reservado(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    db.crear_usuario("Pepe", "pepe", "h", "tecnico")
    assert db.eliminar_usuario("pepe", "ingeniero") == "ok"
    assert "pepe" not in [u["usuario"] for u in db.listar_usuarios()]
    assert db.get_usuario_cualquiera("pepe") is None
    assert db.get_usuario_by_username("pepe") is None and db.get_usuario_by_username("PEPE") is None
    assert db.existe_usuario("PEPE")                                  # no se reutiliza
    with pytest.raises(sqlite3.IntegrityError):
        db.crear_usuario("Otro", "Pepe", "h", "tecnico")
    assert db.fijar_activo_usuario("pepe", True, "ingeniero") == "no_existe"
    assert db.restablecer_password("pepe", "x") is False
    assert db.cambiar_rol_usuario("pepe", "admin", "ingeniero") == ("no_existe", None)
    assert db.eliminar_usuario("pepe", "ingeniero") == "no_existe"
    db.close()


def test_reglas_de_la_base(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    db.crear_usuario("Pepe", "pepe", "h", "tecnico")
    db.crear_usuario("Lu", "lu", "h", "tecnico")
    assert db.eliminar_usuario("Admin", "ingeniero") == "cuenta_sistema"
    assert db.cambiar_rol_usuario("Ingeniero", "admin", "ingeniero") == ("cuenta_sistema", "ingeniero")
    assert db.eliminar_usuario("pepe", "ingeniero", {"admin"}) == "rol_no_gestionable"
    assert db.cambiar_rol_usuario("pepe", "ingeniero", "ingeniero", {"admin", "tecnico"}) \
        == ("rol_no_gestionable", "tecnico")
    assert db.cambiar_rol_usuario("pepe", "tecnico", "ingeniero") == ("sin_cambio", "tecnico")
    # regla del último activo con un rol protegido de prueba (el Ingeniero del
    # sistema está siempre activo y no se puede usar aquí)
    assert db.eliminar_usuario("lu", "tecnico") == "ok"
    assert db.eliminar_usuario("pepe", "tecnico") == "ultimo_protegido"      # lu ya no cuenta
    assert db.cambiar_rol_usuario("pepe", "admin", "tecnico") == ("ultimo_protegido", "tecnico")
    assert db.fijar_activo_usuario("pepe", False, "tecnico") == "ultimo_protegido"
    assert db.cambiar_rol_usuario("pepe", "admin", "ingeniero") == ("ok", "tecnico")
    assert _fila(db, "pepe")["rol"] == "admin"
    db.close()


# ── API ────────────────────────────────────────────────────────────────────

def _cliente(db):
    from fastapi.testclient import TestClient
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.control_loop.test_mode_active = False
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    return TestClient(srv.app), srv, ctx, cabecera


@pytest.fixture
def api(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    for nombre, usuario, rol in (("Ana", "ana_admin", "admin"), ("Tomás", "tomas_tec", "tecnico"),
                                 ("Inés", "ines_ing", "ingeniero"), ("Iván", "ivan_ing", "ingeniero"),
                                 ("Adán", "adan_admin", "admin")):
        db.crear_usuario(nombre, usuario, hash_password("clave1234"), rol)
    yield _cliente(db)
    db.close()


def _login(client, usuario, clave="clave1234"):
    return client.post("/auth/login", json={"usuario": usuario, "clave": clave})


def test_eliminar_ok(api):
    client, srv, ctx, cab = api
    token = _login(client, "tomas_tec").json()["token"]
    h = cab(srv, "ingeniero", usuario="ines_ing")
    r = client.delete("/usuarios/tomas_tec", headers=h)
    assert r.status_code == 200 and r.json()["eliminado"] is True
    # sale de la lista, la fila sigue en la base (marcada)
    lista = client.get("/usuarios", headers=h).json()["usuarios"]
    assert "tomas_tec" not in [u["usuario"] for u in lista]
    assert _fila(ctx.db, "tomas_tec")["eliminado"] == 1
    # su sesión quedó cerrada y ya no inicia sesión (tampoco en mayúsculas)
    assert client.get("/auth/sesion", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    for escrito in ("tomas_tec", "TOMAS_TEC"):
        r = _login(client, escrito)
        assert r.status_code == 401 and r.json()["codigo"] == "credenciales_invalidas"
    # el nombre no se reutiliza
    r = client.post("/usuarios", json={"nombre": "Otro", "usuario": "Tomas_Tec", "clave": "clave1234",
                                       "confirmacion": "clave1234", "rol": "tecnico"}, headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "usuario_existe"
    # no se reactiva, ni se restablece, ni se vuelve a eliminar, ni cambia de rol
    assert client.put("/usuarios/tomas_tec/activo", json={"activo": True}, headers=h).status_code == 404
    assert client.post("/usuarios/tomas_tec/restablecer_clave",
                       json={"clave": "temporal99", "confirmacion": "temporal99"},
                       headers=h).status_code == 404
    assert client.delete("/usuarios/tomas_tec", headers=h).status_code == 404
    assert client.patch("/usuarios/tomas_tec", json={"rol": "admin"}, headers=h).status_code == 404
    # bitácora
    fila = ctx.db.get_auditoria(evento="usuario_eliminado")[0]
    assert fila["usuario"] == "ines_ing" and fila["entidad"] == "tomas_tec"
    assert json.loads(fila["valor_anterior"]) == {"rol": "tecnico", "activo": True}
    assert fila["detalle"] == {"sesiones_cerradas": 1}


@pytest.mark.parametrize("rol,yo,objetivo,status,codigo", [
    ("ingeniero", "ines_ing", "ines_ing", 409, "autoeliminacion"),
    ("admin", "ana_admin", "ana_admin", 409, "autoeliminacion"),
    ("ingeniero", "ines_ing", "Admin", 409, "cuenta_sistema"),
    ("admin", "ana_admin", "Ingeniero", 409, "cuenta_sistema"),
    ("admin", "ana_admin", "ines_ing", 403, "rol_no_gestionable"),
    ("tecnico", "tomas_tec", "adan_admin", 403, "rol_sin_permiso"),
])
def test_eliminar_rechazos(api, rol, yo, objetivo, status, codigo):
    client, srv, ctx, cab = api
    r = client.delete(f"/usuarios/{objetivo}", headers=cab(srv, rol, usuario=yo))
    assert r.status_code == status and r.json()["codigo"] == codigo
    assert _fila(ctx.db, objetivo)["eliminado"] == 0
    assert not ctx.db.get_auditoria(evento="usuario_eliminado")


def test_admin_elimina_admin_y_tecnico(api):
    client, srv, ctx, cab = api
    h = cab(srv, "admin", usuario="ana_admin")
    assert client.delete("/usuarios/adan_admin", headers=h).status_code == 200
    assert client.delete("/usuarios/tomas_tec", headers=h).status_code == 200


def test_cambiar_rol_ok(api):
    client, srv, ctx, cab = api
    token = _login(client, "tomas_tec").json()["token"]
    h = cab(srv, "ingeniero", usuario="ines_ing")
    r = client.patch("/usuarios/tomas_tec", json={"rol": "admin"}, headers=h)
    assert r.status_code == 200 and r.json()["rol"] == "admin"
    assert ctx.db.get_usuario_cualquiera("tomas_tec")["rol"] == "admin"
    assert client.get("/auth/sesion", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert _login(client, "tomas_tec").json()["rol"] == "admin"      # el nuevo ingreso trae el rol nuevo
    fila = ctx.db.get_auditoria(evento="usuario_rol_cambiado")[0]
    assert fila["entidad"] == "tomas_tec" and fila["usuario"] == "ines_ing"
    assert json.loads(fila["valor_anterior"]) == {"rol": "tecnico"}
    assert json.loads(fila["valor_nuevo"]) == {"rol": "admin"}
    assert fila["detalle"] == {"sesiones_cerradas": 1}
    # el mismo rol: 200 sin cambios, sin bitácora
    r = client.patch("/usuarios/tomas_tec", json={"rol": "admin"}, headers=h)
    assert r.status_code == 200 and r.json()["sin_cambio"] is True
    assert len(ctx.db.get_auditoria(evento="usuario_rol_cambiado")) == 1


@pytest.mark.parametrize("rol,yo,objetivo,cuerpo,status,codigo", [
    ("ingeniero", "ines_ing", "ines_ing", {"rol": "admin"}, 409, "autocambio_rol"),
    ("admin", "ana_admin", "ana_admin", {"rol": "tecnico"}, 409, "autocambio_rol"),
    ("admin", "ana_admin", "tomas_tec", {"rol": "ingeniero"}, 403, "rol_no_gestionable"),
    ("admin", "ana_admin", "ines_ing", {"rol": "tecnico"}, 403, "rol_no_gestionable"),
    ("ingeniero", "ines_ing", "Admin", {"rol": "tecnico"}, 409, "cuenta_sistema"),
    ("ingeniero", "ines_ing", "tomas_tec", {"rol": "operador"}, 422, "validacion"),
    ("ingeniero", "ines_ing", "tomas_tec", {"rol": "admin", "nombre": "X"}, 409,
     "modificacion_no_disponible"),
    ("ingeniero", "ines_ing", "tomas_tec", {"usuario": "x"}, 409, "modificacion_no_disponible"),
    ("tecnico", "tomas_tec", "adan_admin", {"rol": "tecnico"}, 403, "rol_sin_permiso"),
])
def test_cambiar_rol_rechazos(api, rol, yo, objetivo, cuerpo, status, codigo):
    client, srv, ctx, cab = api
    antes = ctx.db.get_usuario_cualquiera(objetivo)
    r = client.patch(f"/usuarios/{objetivo}", json=cuerpo, headers=cab(srv, rol, usuario=yo))
    assert r.status_code == status and r.json()["codigo"] == codigo
    assert ctx.db.get_usuario_cualquiera(objetivo) == antes
    assert not ctx.db.get_auditoria(evento="usuario_rol_cambiado")


def test_ultimo_ingeniero_activo_al_eliminar_y_cambiar_rol(tmp_path, monkeypatch):
    # BD anterior con la semilla `ingeniero` inactiva (U11): ines es la única
    # ingeniera activa; ni eliminarla ni pasarla a otro rol
    from tests.test_u11_cuentas_sistema import crear_bd_v10
    ruta = tmp_path / "f.db"
    crear_bd_v10(ruta, monkeypatch,
                 lambda c: c.execute("UPDATE usuarios SET activo=0 WHERE usuario='ingeniero'"))
    db = DbManager(db_path=ruta)
    try:
        client, srv, ctx, cab = _cliente(db)
        h = cab(srv, "ingeniero", usuario="otro_ing")
        r = client.delete("/usuarios/ines_ing", headers=h)
        assert r.status_code == 409 and r.json()["codigo"] == "ultimo_ingeniero"
        r = client.patch("/usuarios/ines_ing", json={"rol": "admin"}, headers=h)
        assert r.status_code == 409 and r.json()["codigo"] == "ultimo_ingeniero"
        assert _fila(db, "ines_ing")["rol"] == "ingeniero" and _fila(db, "ines_ing")["eliminado"] == 0
        # un segundo ingeniero activo la libera; un ingeniero eliminado no cuenta
        db.crear_usuario("Rita", "rita_ing", hash_password("clave1234"), "ingeniero")
        assert client.delete("/usuarios/rita_ing", headers=h).status_code == 200
        r = client.delete("/usuarios/ines_ing", headers=h)
        assert r.status_code == 409 and r.json()["codigo"] == "ultimo_ingeniero"
        db.crear_usuario("Saúl", "saul_ing", hash_password("clave1234"), "ingeniero")
        assert client.patch("/usuarios/ines_ing", json={"rol": "tecnico"}, headers=h).status_code == 200
    finally:
        db.close()


def test_cambiar_mi_clave_desde_cualquier_rol(api):
    client, srv, ctx, cab = api
    token = _login(client, "tomas_tec").json()["token"]
    r = client.post("/auth/change_password",
                    json={"clave_actual": "clave1234", "clave_nueva": "nueva12345",
                          "confirmacion": "nueva12345"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert _login(client, "tomas_tec", "nueva12345").status_code == 200


def test_openapi_sin_cambios_en_las_rutas_de_usuarios(api):
    client, *_ = api
    rutas = client.get("/openapi.json").json()["paths"]["/usuarios/{usuario}"]
    assert set(rutas) == {"delete", "patch"}
    assert rutas["delete"]["operationId"].startswith("borrar_usuario")
    assert rutas["patch"]["operationId"].startswith("modificar_usuario")


# ── cliente: códigos con ruta y texto ──────────────────────────────────────

_RECHAZOS = {"RechazoApi", "_rechazar"}
# Funciones de rutas/usuarios.py que sirven DELETE y PATCH /usuarios/{u}
_FUNCIONES = {"borrar_usuario", "modificar_usuario", "_rechazar_resultado",
              "_objetivo_existente", "_objetivo_gestionable", "_rechazar_cuenta_sistema"}
# Sin texto propio a propósito: `no_existe` no puede ser código de /usuarios
# (test_t25_codigos_rutas_async lo prohíbe: es de /global_params) y
# `modificacion_no_disponible` (nombre/usuario) la pantalla no lo envía nunca.
_SIN_TEXTO = {"no_existe", "modificacion_no_disponible"}


def _codigos_de_rutas() -> set:
    fuente = (RAIZ / "src" / "autoclave" / "backend" / "rutas" / "usuarios.py").read_text(encoding="utf-8")
    salida = set()
    for f in ast.walk(ast.parse(fuente)):
        if isinstance(f, ast.FunctionDef) and f.name in _FUNCIONES:
            for n in ast.walk(f):
                if isinstance(n, ast.Call):
                    nombre = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                    if nombre in _RECHAZOS and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
                        salida.add(n.args[1].value)
    return salida


def test_codigos_de_eliminar_y_rol_llegan_con_texto():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml import sesion_backend as sb
    from autoclave.ui_qml.controllers import usuarios_controller as uc
    codigos = _codigos_de_rutas()
    assert {"autoeliminacion", "autocambio_rol", "rol_no_gestionable", "ultimo_ingeniero",
            "cuenta_sistema"} <= codigos
    es = json.loads((_I18N / "es.json").read_text(encoding="utf-8"))
    en = json.loads((_I18N / "en.json").read_text(encoding="utf-8"))
    for cod in codigos - _SIN_TEXTO:
        for ruta in ("/usuarios/x", "/usuarios/x?y=1"):
            assert cod in sb.codigos_conocidos(ruta), cod
            assert sb.interpretar(409, {"codigo": cod}, ruta).causa == cod
        clave = uc._MENSAJES.get(cod)
        assert clave, cod
        sec, k = clave.split(".", 1)
        assert es[sec][k] and en[sec][k], clave
    for cod in ("autoeliminacion", "autocambio_rol", "rol_no_gestionable"):
        assert cod not in sb.codigos_conocidos("/cycle/start") and cod not in sb.codigos_conocidos()


def test_textos_nuevos_es_en_y_qml():
    es = json.loads((_I18N / "es.json").read_text(encoding="utf-8"))
    en = json.loads((_I18N / "en.json").read_text(encoding="utf-8"))
    assert set(es["usuarios_cuenta"]) == set(en["usuarios_cuenta"])
    for lang in (es, en):
        for ev in ("usuario_eliminado", "usuario_rol_cambiado"):
            assert lang["bitacora"]["ev"][ev] and lang["bitacora"]["tipo"][ev]
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas"
    import re
    usados = set()
    for nombre in ("OpcionesUsuarios.qml", "CambioClave.qml"):
        usados |= set(re.findall(r'"usuarios_cuenta\.([a-z_]+)"', (qml / nombre).read_text(encoding="utf-8")))
    assert usados and usados <= set(es["usuarios_cuenta"])
    texto = (qml / "OpcionesUsuarios.qml").read_text(encoding="utf-8")
    assert "elide" not in texto                          # D8-5.4


def test_bitacora_clasifica_los_eventos():
    from autoclave.core.runtime import bitacora
    for ev in ("usuario_eliminado", "usuario_rol_cambiado"):
        assert ev in bitacora.EVENTOS_REGISTRADOS and bitacora.categoria_de(ev) == "usuarios_sesion"


# ── controlador ────────────────────────────────────────────────────────────

USUARIOS_UI = {
    "usuarios": [
        {"nombre": "Admin", "usuario": "Admin", "rol": "admin", "activo": True,
         "cuenta_sistema": True, "ultimo_ingreso": None},
        {"nombre": "Inés", "usuario": "ines_ing", "rol": "ingeniero", "activo": True,
         "cuenta_sistema": False, "ultimo_ingreso": None},
        {"nombre": "Iván", "usuario": "ivan_ing", "rol": "ingeniero", "activo": True,
         "cuenta_sistema": False, "ultimo_ingreso": None},
        {"nombre": "Tomás Gil", "usuario": "tomas_tec", "rol": "tecnico", "activo": True,
         "cuenta_sistema": False, "ultimo_ingreso": None},
    ],
    "gestionables": ["admin", "ingeniero", "tecnico"],
}


def _ctrl(rol="ingeniero", yo="ines_ing", causa="ok", gestionables=None):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.usuarios_controller import UsuariosController
    from autoclave.ui_qml.sesion_backend import Resultado
    datos = dict(USUARIOS_UI)
    if gestionables is not None:
        datos["gestionables"] = gestionables

    class S:
        def __init__(self):
            self.enviados = []

        def enviar(self, metodo, ruta, cuerpo=None):
            self.enviados.append((metodo, ruta, cuerpo))
            if metodo == "GET":
                return Resultado("ok", datos if ruta == "/usuarios" else {"operadores": []}, 200)
            return Resultado(causa, {"ok": True} if causa == "ok" else {}, 200 if causa == "ok" else 409)

    s = S()
    c = UsuariosController(sesion=s)
    c.rol, c.usuarioActual = rol, yo
    c.cargar()
    return c, s


def test_controlador_roles_destino():
    c, _ = _ctrl()
    assert c.rolesDestino("tomas_tec") == ["admin", "ingeniero"]
    assert c.rolesDestino("ivan_ing") == ["admin", "tecnico"]
    assert c.rolesDestino("Admin") == []                 # cuenta del sistema
    assert c.rolesDestino("ines_ing") == []              # uno mismo
    a, _ = _ctrl("admin", "ana_admin", gestionables=["admin", "tecnico"])
    assert a.rolesDestino("tomas_tec") == ["admin"]
    assert a.rolesDestino("ivan_ing") == []              # rol no gestionable
    t, _ = _ctrl("tecnico", "tomas_tec", gestionables=[])
    assert t.rolesDestino("ivan_ing") == []


def test_controlador_envia_eliminar_y_rol():
    c, s = _ctrl()
    assert c.eliminar("tomas_tec")
    assert ("DELETE", "/usuarios/tomas_tec", None) in s.enviados
    assert c.cambiarRol("ivan_ing", "tecnico")
    assert ("PATCH", "/usuarios/ivan_ing", {"rol": "tecnico"}) in s.enviados
    n = len(s.enviados)
    assert not c.cambiarRol("ivan_ing", "ingeniero")     # mismo rol: no sale
    assert not c.cambiarRol("Admin", "tecnico")          # cuenta del sistema: no sale
    assert len(s.enviados) == n and c.mensaje == "gestion_usuarios.err_rol_objetivo"


@pytest.mark.parametrize("accion,causa,clave", [
    ("eliminar", "autoeliminacion", "usuarios_cuenta.err_propio_eliminar"),
    ("eliminar", "ultimo_ingeniero", "gestion_usuarios.err_ultimo_ingeniero"),
    ("eliminar", "cuenta_sistema", "gestion_usuarios.err_cuenta_sistema"),
    ("rol", "autocambio_rol", "usuarios_cuenta.err_propio_rol"),
    ("rol", "rol_no_gestionable", "gestion_usuarios.err_rol_objetivo"),
    ("rol", "validacion", "usuarios_cuenta.err_rol_invalido"),
])
def test_controlador_mapea_rechazos(accion, causa, clave):
    c, _ = _ctrl(causa=causa)
    ok = c.eliminar("tomas_tec") if accion == "eliminar" else c.cambiarRol("tomas_tec", "admin")
    assert ok is False and c.mensaje == clave


# ── pantalla (QML) ─────────────────────────────────────────────────────────

_GET = {"/usuarios": USUARIOS_UI, "/operadores": {"operadores": []}}
_LEER = [("botonCambiarRol", "habilitado"), ("botonEliminarUsuario", "habilitado"),
         ("botonCambiarMiClave", "habilitado"), ("botonCambiarMiClave", "visible"),
         ("notaUsuarios", "text")]


def test_pantalla_botones_por_seleccion_y_rol():
    pytest.importorskip("PySide6")
    from tests.helpers.opciones_qml_doble import correr
    r = correr("usuarios", "ingeniero", _GET, usuario="ines_ing", pasos=[
        {"fijar": [("opcionesUsuarios", "seleccionado", "tomas_tec")], "leer": _LEER},
        {"fijar": [("opcionesUsuarios", "seleccionado", "Admin")], "leer": _LEER},
        {"fijar": [("opcionesUsuarios", "seleccionado", "ines_ing")], "leer": _LEER},
        {"fijar": [("opcionesUsuarios", "seleccionado", "tomas_tec"), ("elegirRol", "visible", True)],
         "leer": [("opcionesUsuarios", "rolesDestino"), ("elegirRol", "visible")]},
    ])
    assert r["avisos"] == []
    tec, admin, propio, elegir = (p["props"] for p in r["pasos"])
    assert tec["botonCambiarRol.habilitado"] is True and tec["botonEliminarUsuario.habilitado"] is True
    assert admin["botonCambiarRol.habilitado"] is False and admin["botonEliminarUsuario.habilitado"] is False
    assert propio["botonCambiarRol.habilitado"] is False and propio["botonEliminarUsuario.habilitado"] is False
    for p in (tec, admin, propio):
        assert p["botonCambiarMiClave.habilitado"] is True and p["botonCambiarMiClave.visible"] is True
    assert "eliminado" in tec["notaUsuarios.text"]
    # el selector ofrece los roles gestionables menos el actual (tecnico)
    assert elegir["elegirRol.visible"] is True
    roles = elegir["opcionesUsuarios.rolesDestino"]
    assert "admin" in roles and "ingeniero" in roles and "tecnico" not in roles


def test_pantalla_tecnico_solo_cambia_su_clave():
    pytest.importorskip("PySide6")
    from tests.helpers.opciones_qml_doble import correr
    r = correr("usuarios", "tecnico", _GET, usuario="tomas_tec", pasos=[
        {"fijar": [("opcionesUsuarios", "seleccionado", "ivan_ing")], "leer": _LEER},
    ])
    assert r["avisos"] == []
    p = r["pasos"][0]["props"]
    assert p["botonCambiarRol.habilitado"] is False and p["botonEliminarUsuario.habilitado"] is False
    assert p["botonCambiarMiClave.habilitado"] is True and p["botonCambiarMiClave.visible"] is True


def test_pantalla_eliminar_y_rol_envian_desde_qml():
    pytest.importorskip("PySide6")
    from tests.helpers.opciones_qml_doble import correr
    r = correr("usuarios", "ingeniero", _GET, usuario="ines_ing", pasos=[
        {"llamar": [("usuariosController", "eliminar", ["tomas_tec"]),
                    ("usuariosController", "cambiarRol", ["ivan_ing", "tecnico"])],
         "leer": []},
    ])
    assert r["avisos"] == []
    assert ["DELETE", "/usuarios/tomas_tec", None] in r["enviados"]
    assert ["PATCH", "/usuarios/ivan_ing", {"rol": "tecnico"}] in r["enviados"]


# ── cambio voluntario de la contraseña (Main.qml) ──────────────────────────

_SCRIPT_VOLUNTARIO = textwrap.dedent(r"""
    import json
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml import sesion_backend
    from autoclave.cliente.session_manager import SessionManager
    from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

    llamadas = []
    def transporte(metodo, ruta, cuerpo, token, plazo):
        llamadas.append([metodo, ruta])
        if ruta == "/auth/login":
            return 200, {"token": f"tok-{len(llamadas)}", "usuario": "tec1", "nombre": "tec1",
                         "rol": "tecnico", "debe_cambiar_clave": False}
        if ruta == "/usuarios":
            return 200, {"usuarios": [], "gestionables": []}
        if ruta == "/operadores":
            return 200, {"operadores": []}
        return 200, {"ok": True}

    qapp = QGuiApplication([])
    sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                          cierre_s=0.8, intervalo_ms=50)
    sesion_backend.instalar(sesion)
    puente_nu = NuevoUsuarioBridge(sesion=sesion)
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: f not in ("PARO_EMERGENCIA", "PARO_REAL")
    ui.get_cycle.return_value = {"name": "Bowie & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "sesion": sesion, "puenteNuevoUsuario": puente_nu})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.show()

    def buscar(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]
    def visible(tipo):
        return any(o.property("visible") for o in buscar(tipo))
    def esperar(ms=700):
        QTest.qWait(ms)
    def pantalla():
        for t in ("CambioClave", "NuevoUsuario", "Opciones", "Login", "PantallaPreciclo"):
            if buscar(t) and visible(t):
                return t
        return "?"
    def rutas():
        return [r for _, r in llamadas]
    def abrir_cambio():
        QMetaObject.invokeMethod(buscar("Opciones")[0], "cambiarMiClavePulsado")
        esperar()

    r = {}
    QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
    esperar()
    QMetaObject.invokeMethod(buscar("PantallaPreciclo")[0], "avatarPulsado")
    esperar()
    login = buscar("Login")[0]
    login.setProperty("usuario", "tec1")
    login.setProperty("clave", "clave1234")
    QMetaObject.invokeMethod(login, "iniciarSesion")
    esperar()
    r["tras_login"] = pantalla()

    abrir_cambio()
    c = [o for o in buscar("CambioClave") if o.property("visible")][0]
    r["abre"] = [pantalla(), c.property("voluntario"),
                 c.findChild(QObject, "avisoCambioObligatorio").property("text")]
    QMetaObject.invokeMethod(c, "atras")
    esperar()
    r["atras"] = [pantalla(), SessionManager.is_authenticated(), rutas().count("/auth/logout")]

    abrir_cambio()
    c = [o for o in buscar("CambioClave") if o.property("visible")][0]
    for k, v in (("clave_actual", "clave1234"), ("clave_nueva", "nueva12345"),
                 ("confirmacion", "nueva12345")):
        c.setProperty(k, v)
    QMetaObject.invokeMethod(c, "cambiar")
    esperar()
    r["cambiada"] = [pantalla(), SessionManager.is_authenticated(),
                     rutas().count("/auth/change_password"), rutas().count("/auth/logout")]

    abrir_cambio()
    c = [o for o in buscar("CambioClave") if o.property("visible")][0]
    QMetaObject.invokeMethod(c, "inicio")
    esperar()
    r["inicio"] = [pantalla(), SessionManager.is_authenticated(), rutas().count("/auth/logout")]
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


@pytest.fixture(scope="module")
def voluntario():
    pytest.importorskip("PySide6")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT_VOLUNTARIO], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=180, cwd=RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout[-3000:] + proc.stderr[-3000:]
    return json.loads(linea[0][len("RESULTADO="):])


def test_voluntario_sin_avisos_qml(voluntario):
    assert voluntario["avisos"] == []


def test_voluntario_abre_desde_usuarios_con_aviso_propio(voluntario):
    assert voluntario["tras_login"] == "Opciones"
    pantalla, es_voluntario, aviso = voluntario["abre"]
    assert pantalla == "CambioClave" and es_voluntario is True
    es = json.loads((_I18N / "es.json").read_text(encoding="utf-8"))
    assert aviso == es["usuarios_cuenta"]["aviso_voluntario"]


def test_voluntario_atras_conserva_la_sesion(voluntario):
    assert voluntario["atras"] == ["Opciones", True, 0]


def test_voluntario_cambia_y_vuelve_a_opciones(voluntario):
    assert voluntario["cambiada"] == ["Opciones", True, 1, 0]


def test_voluntario_inicio_conserva_la_sesion(voluntario):
    assert voluntario["inicio"] == ["PantallaPreciclo", True, 0]
