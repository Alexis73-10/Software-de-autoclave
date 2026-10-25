# tests/test_u11_cuentas_sistema.py
#
# U11 (tanda 11, D11-6): cuentas del sistema `Admin` e `Ingeniero`.
# - BD nuevas: nacen con Admin/Ingeniero (usuario y nombre) y la marca
#   persistente `cuenta_sistema`; contraseñas iniciales sin cambio.
# - Migración v11 sobre una BD anterior (admin/ingeniero): renombra solo las
#   filas semilla, conserva contraseña, debe_cambiar_clave y auditoría, agrega
#   `usuario_renombrado`, es idempotente y no renombra ante un choque.
# - Protección por la marca (no por el texto): 409 + auditoría al desactivar,
#   borrar, cambiar el rol o renombrar; sí se restablece / cambia la clave.
# - Inicio de sesión sin distinguir mayúsculas; unicidad al crear.
# - Regla del último ingeniero activo.

import json
import logging
import shutil
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from autoclave.backend.contrasenas import hash_password, verificar_password
from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.db_manager import DbManager

# Esquema de usuarios de la v10 y siembra tal como la hacía el código anterior
# a U11 (db_manager.py en c607dc4): usuario y nombre en minúsculas / Administrador.
_SEMILLA_V10 = (
    ("Administrador", "admin", "admin",
     "pbkdf2$600000$244c45ae5ee701d94ead2bfad6339db3$"
     "5abbc82ab1c70a268623cc8f2c774a1733f3851d9a30f9a3fcd835f3afc5a190"),
    ("Ingeniero", "ingeniero", "ingeniero",
     "pbkdf2$600000$dd26db607bc796ade9d097563e47d0e1$"
     "f8fa605e93fc5e4e035c60d0e07b23a96ca6390830855f36c14cb03a2d609019"),
)


def _seed_v10(self):
    with self._lock:
        if self._conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            for nombre, usuario, rol, hash_pw in _SEMILLA_V10:
                self._conn.execute(
                    "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo,"
                    " creado_por, creado_en, debe_cambiar_clave)"
                    " VALUES (?,?,?,?,1,'semilla',?,1)",
                    (nombre, usuario, hash_pw, rol, datetime.now().isoformat()))
            self._conn.commit()


def crear_bd_v10(ruta, monkeypatch, preparar=None):
    """BD con el esquema de la v10 (migraciones 1-10) y las semillas antiguas.
    `preparar(conn)` ajusta filas antes de cerrar (sin la v11 no hay triggers
    de cuenta del sistema)."""
    with monkeypatch.context() as m:
        m.setattr(dbm, "_MIGRACIONES", tuple(x for x in dbm._MIGRACIONES if x[0] <= 10))
        m.setattr(DbManager, "seed_admin_if_empty", _seed_v10)
        db = DbManager(db_path=ruta)
        assert db.get_version_esquema() == 10
        cols = {f[1] for f in db._conn.execute("PRAGMA table_info(usuarios)")}
        assert "cuenta_sistema" not in cols
        db.registrar_auditoria("login_ok", usuario="admin", rol="admin", entidad="/auth/login")
        db.registrar_auditoria("cambio_clave", usuario="admin", rol="admin")
        db.crear_usuario("Inés", "ines_ing", hash_password("clave1234"), "ingeniero")
        if preparar:
            with db._lock:
                preparar(db._conn)
                db._conn.commit()
        db.close()


def _fila(db, usuario):
    with db._lock:
        r = db._conn.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
    return dict(r) if r else None


def _auditoria(db):
    with db._lock:
        return [dict(r) for r in db._conn.execute("SELECT * FROM audit_log ORDER BY id")]


# ── BD nueva ───────────────────────────────────────────────────────────────

def test_bd_nueva_nace_con_admin_e_ingeniero_marcados(tmp_path):
    db = DbManager(db_path=tmp_path / "n.db")
    assert db.get_version_esquema() == dbm.ESQUEMA_VERSION >= 11
    for usuario, clave, rol in (("Admin", "admin1234", "admin"),
                                ("Ingeniero", "ingeniero1234", "ingeniero")):
        f = _fila(db, usuario)
        assert f["nombre"] == usuario and f["rol"] == rol and f["activo"] == 1
        assert f["cuenta_sistema"] == 1 and f["debe_cambiar_clave"] == 1
        assert f["creado_por"] == "semilla"
        assert verificar_password(clave, f["hash_pw"])
    assert _fila(db, "admin") is None and _fila(db, "ingeniero") is None
    assert not [a for a in _auditoria(db) if a["evento"] == "usuario_renombrado"]
    # un usuario creado después no queda marcado
    db.crear_usuario("Pepe", "pepe", "h", "tecnico")
    assert _fila(db, "pepe")["cuenta_sistema"] == 0
    db.close()


# ── migración v11 ──────────────────────────────────────────────────────────

def test_migracion_renombra_semillas_y_conserva_todo(tmp_path, monkeypatch):
    original = tmp_path / "f.db"

    def preparar(conn):
        # el admin ya cambió su contraseña (debe_cambiar_clave=0); el ingeniero no
        conn.execute("UPDATE usuarios SET hash_pw=?, debe_cambiar_clave=0 WHERE usuario='admin'",
                     (hash_password("propia5678"),))

    crear_bd_v10(original, monkeypatch, preparar)
    copia = tmp_path / "copia.db"
    shutil.copy(original, copia)

    with sqlite3.connect(copia) as c:
        antes = {r[0]: r for r in c.execute(
            "SELECT usuario, hash_pw, debe_cambiar_clave, activo, rol, id FROM usuarios")}
        auditoria_antes = c.execute("SELECT * FROM audit_log ORDER BY id").fetchall()

    db = DbManager(db_path=copia)
    assert db.get_version_esquema() >= 11
    for viejo, nuevo in (("admin", "Admin"), ("ingeniero", "Ingeniero")):
        f = _fila(db, nuevo)
        assert f is not None and _fila(db, viejo) is None
        assert f["nombre"] == nuevo and f["cuenta_sistema"] == 1
        _, hash_pw, debe, activo, rol, id_ = antes[viejo]
        assert (f["hash_pw"], f["debe_cambiar_clave"], f["activo"], f["rol"], f["id"]) == \
               (hash_pw, debe, activo, rol, id_)
    assert verificar_password("propia5678", _fila(db, "Admin")["hash_pw"])
    assert _fila(db, "Admin")["debe_cambiar_clave"] == 0
    assert _fila(db, "Ingeniero")["debe_cambiar_clave"] == 1
    assert _fila(db, "ines_ing")["cuenta_sistema"] == 0

    auditoria = _auditoria(db)
    # los registros históricos no se reescriben
    assert [tuple(a.values()) for a in auditoria[:len(auditoria_antes)]] \
        == [tuple(r) for r in auditoria_antes]
    assert auditoria[0]["usuario"] == "admin"
    renombres = [a for a in auditoria if a["evento"] == "usuario_renombrado"]
    assert len(renombres) == 2
    por_entidad = {a["entidad"]: a for a in renombres}
    assert json.loads(por_entidad["Admin"]["valor_anterior"]) == {"usuario": "admin",
                                                                   "nombre": "Administrador"}
    assert json.loads(por_entidad["Admin"]["valor_nuevo"]) == {"usuario": "Admin", "nombre": "Admin"}
    assert json.loads(por_entidad["Ingeniero"]["valor_anterior"])["usuario"] == "ingeniero"
    db.close()
    # el original no se tocó
    with sqlite3.connect(original) as c:
        assert {r[0] for r in c.execute("SELECT usuario FROM usuarios")} >= {"admin", "ingeniero"}


def test_migracion_dos_veces_sin_efecto(tmp_path, monkeypatch):
    ruta = tmp_path / "f.db"
    crear_bd_v10(ruta, monkeypatch)
    DbManager(db_path=ruta).close()
    with sqlite3.connect(ruta) as c:
        usuarios_1 = c.execute("SELECT * FROM usuarios ORDER BY id").fetchall()
        auditoria_1 = c.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    db = DbManager(db_path=ruta)                        # segundo arranque
    # y la función de la migración, llamada otra vez a mano, tampoco cambia nada
    with db._lock:
        db._conn.execute("BEGIN IMMEDIATE")
        dbm._migracion_v11(db._conn)
        db._conn.commit()
    db.close()
    with sqlite3.connect(ruta) as c:
        assert c.execute("SELECT * FROM usuarios ORDER BY id").fetchall() == usuarios_1
        assert c.execute("SELECT * FROM audit_log ORDER BY id").fetchall() == auditoria_1
    assert sum(1 for a in auditoria_1 if a[4] == "usuario_renombrado") == 2


def test_migracion_no_renombra_si_choca_sin_distinguir_mayusculas(tmp_path, monkeypatch, caplog):
    ruta = tmp_path / "f.db"

    def preparar(conn):
        # otro usuario (no semilla) que choca con el nombre nuevo de la semilla
        conn.execute("INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo, creado_por)"
                     " VALUES ('Otro', 'ADMIN', 'x', 'tecnico', 1, 'ines_ing')")

    crear_bd_v10(ruta, monkeypatch, preparar)
    with caplog.at_level(logging.WARNING):
        db = DbManager(db_path=ruta)
    semilla = _fila(db, "admin")
    assert semilla is not None and semilla["nombre"] == "Administrador"
    assert semilla["cuenta_sistema"] == 1                      # protegida por la marca
    assert _fila(db, "ADMIN")["cuenta_sistema"] == 0
    assert _fila(db, "Admin") is None
    assert _fila(db, "Ingeniero")["cuenta_sistema"] == 1        # la otra sí se renombra
    renombres = [a["entidad"] for a in _auditoria(db) if a["evento"] == "usuario_renombrado"]
    assert renombres == ["Ingeniero"]
    assert any("choca" in r.getMessage() and "ADMIN" in r.getMessage() for r in caplog.records)
    db.close()


def test_migracion_ignora_filas_no_semilla(tmp_path, monkeypatch):
    ruta = tmp_path / "f.db"

    def preparar(conn):
        # BD anterior a la columna creado_por: la fila no se reconoce como semilla
        conn.execute("UPDATE usuarios SET creado_por='' WHERE usuario='ingeniero'")

    crear_bd_v10(ruta, monkeypatch, preparar)
    db = DbManager(db_path=ruta)
    f = _fila(db, "ingeniero")
    assert f is not None and f["cuenta_sistema"] == 0 and _fila(db, "Ingeniero") is None
    assert _fila(db, "Admin")["cuenta_sistema"] == 1
    db.close()


# ── protección en la base (triggers) ───────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "UPDATE usuarios SET usuario='Jefe' WHERE usuario='Admin'",
    "UPDATE usuarios SET nombre='Jefe' WHERE usuario='Admin'",
    "UPDATE usuarios SET rol='tecnico' WHERE usuario='Ingeniero'",
    "UPDATE usuarios SET activo=0 WHERE usuario='Ingeniero'",
    "UPDATE usuarios SET cuenta_sistema=0 WHERE usuario='Admin'",
    "UPDATE usuarios SET cuenta_sistema=1 WHERE usuario='pepe'",
    "DELETE FROM usuarios WHERE usuario='Admin'",
    "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, cuenta_sistema, creado_por)"
    " VALUES ('X', 'x', 'h', 'admin', 1, 'Admin')",
])
def test_triggers_protegen_cuentas_sistema(tmp_path, sql):
    db = DbManager(db_path=tmp_path / "t.db")
    db.crear_usuario("Pepe", "pepe", "h", "tecnico")
    with pytest.raises(sqlite3.DatabaseError):
        with db._lock:
            db._conn.execute(sql)
    db._conn.rollback()
    assert _fila(db, "Admin")["activo"] == 1 and _fila(db, "Ingeniero")["rol"] == "ingeniero"
    db.close()


def test_clave_de_cuenta_sistema_si_se_cambia(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    db.actualizar_password("Admin", "nuevo_hash")
    assert _fila(db, "Admin")["hash_pw"] == "nuevo_hash"
    assert db.restablecer_password("Ingeniero", "temp_hash")
    assert _fila(db, "Ingeniero")["debe_cambiar_clave"] == 1
    assert db.fijar_activo_usuario("Admin", False, "ingeniero") == "cuenta_sistema"
    db.close()


# ── búsqueda sin distinguir mayúsculas y unicidad ──────────────────────────

def test_busqueda_sin_distinguir_mayusculas(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    for escrito in ("admin", "ADMIN", "Admin", "aDmIn"):
        assert db.get_usuario_by_username(escrito)["usuario"] == "Admin"
    assert db.get_usuario_by_username("INGENIERO")["usuario"] == "Ingeniero"
    assert db.get_usuario_by_username("nadie") is None
    with pytest.raises(sqlite3.IntegrityError):
        db.crear_usuario("Otro", "ADMIN", "h", "tecnico")
    db.crear_usuario("Pepe", "pepe", "h", "tecnico", activo=0)
    assert db.get_usuario_by_username("PEPE") is None           # inactivo
    db.close()


def test_busqueda_ambigua_no_elige(tmp_path, monkeypatch):
    ruta = tmp_path / "f.db"

    def preparar(conn):
        for u in ("ana", "ANA"):
            conn.execute("INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo)"
                         " VALUES ('Ana', ?, 'x', 'tecnico', 1)", (u,))

    crear_bd_v10(ruta, monkeypatch, preparar)
    db = DbManager(db_path=ruta)
    assert db.get_usuario_by_username("ana")["usuario"] == "ana"      # exacto
    assert db.get_usuario_by_username("ANA")["usuario"] == "ANA"
    assert db.get_usuario_by_username("Ana") is None                 # dos candidatos
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
                                 ("Inés", "ines_ing", "ingeniero")):
        db.crear_usuario(nombre, usuario, hash_password("clave1234"), rol)
    yield _cliente(db)
    db.close()


@pytest.mark.parametrize("escrito", ["admin", "ADMIN", "Admin"])
def test_login_sin_distinguir_mayusculas(api, escrito):
    client, srv, ctx, _ = api
    r = client.post("/auth/login", json={"usuario": escrito, "clave": "admin1234"})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"] == "Admin" and r.json()["nombre"] == "Admin"
    assert r.json()["debe_cambiar_clave"] is True
    assert ctx.db.get_auditoria(evento="login_ok")[0]["usuario"] == "Admin"


def test_login_otro_usuario_sin_distinguir_mayusculas(api):
    client, *_ = api
    r = client.post("/auth/login", json={"usuario": "TOMAS_TEC", "clave": "clave1234"})
    assert r.status_code == 200 and r.json()["usuario"] == "tomas_tec"
    assert client.post("/auth/login", json={"usuario": "ADMIN", "clave": "mala1234"}).status_code == 401


def test_lista_expone_la_marca(api):
    client, srv, ctx, cab = api
    r = client.get("/usuarios", headers=cab(srv, "ingeniero", usuario="ines_ing"))
    filas = {u["usuario"]: u for u in r.json()["usuarios"]}
    assert filas["Admin"]["cuenta_sistema"] is True and filas["Ingeniero"]["cuenta_sistema"] is True
    assert filas["ines_ing"]["cuenta_sistema"] is False


def _rechazos(ctx):
    return ctx.db.get_auditoria(evento="cuenta_sistema_rechazada")


@pytest.mark.parametrize("rol,yo", [("ingeniero", "ines_ing"), ("admin", "ana_admin")])
@pytest.mark.parametrize("objetivo", ["Admin", "Ingeniero"])
def test_409_desactivar_cuenta_sistema(api, rol, yo, objetivo):
    client, srv, ctx, cab = api
    r = client.put(f"/usuarios/{objetivo}/activo", json={"activo": False},
                   headers=cab(srv, rol, usuario=yo))
    assert r.status_code == 409 and r.json()["codigo"] == "cuenta_sistema"
    assert ctx.db.get_usuario_cualquiera(objetivo)["activo"] == 1
    fila = _rechazos(ctx)[0]
    assert fila["entidad"] == objetivo and fila["usuario"] == yo
    assert fila["detalle"]["accion"] == "desactivar"


@pytest.mark.parametrize("objetivo", ["Admin", "Ingeniero"])
@pytest.mark.parametrize("metodo,cuerpo,accion", [
    ("DELETE", None, "borrar"),
    ("PATCH", {"rol": "tecnico"}, "cambiar_rol"),
    ("PATCH", {"usuario": "Jefe"}, "renombrar"),
    ("PATCH", {"nombre": "Jefe"}, "renombrar"),
])
def test_409_borrar_cambiar_rol_renombrar_cuenta_sistema(api, objetivo, metodo, cuerpo, accion):
    client, srv, ctx, cab = api
    antes = ctx.db.get_usuario_cualquiera(objetivo)
    r = client.request(metodo, f"/usuarios/{objetivo}", json=cuerpo,
                       headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 409 and r.json()["codigo"] == "cuenta_sistema"
    assert ctx.db.get_usuario_cualquiera(objetivo) == antes
    fila = _rechazos(ctx)[0]
    assert fila["entidad"] == objetivo and fila["detalle"]["accion"] == accion


def test_borrar_o_modificar_otro_usuario_tampoco_disponible(api):
    client, srv, ctx, cab = api
    h = cab(srv, "ingeniero", usuario="ines_ing")
    r = client.delete("/usuarios/tomas_tec", headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "usuario_no_se_borra"
    r = client.patch("/usuarios/tomas_tec", json={"rol": "admin"}, headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "modificacion_no_disponible"
    assert ctx.db.get_usuario_cualquiera("tomas_tec")["rol"] == "tecnico"
    assert client.delete("/usuarios/nadie", headers=h).status_code == 404
    assert client.patch("/usuarios/Admin", json={"rol": "x"},
                        headers=cab(srv, "tecnico", usuario="tomas_tec")).status_code == 403
    assert client.delete("/usuarios/Admin").status_code == 401
    assert client.patch("/usuarios/Admin", json={"otro": 1}, headers=h).status_code == 422


def test_restablecer_y_cambiar_clave_de_cuenta_sistema_si(api):
    client, srv, ctx, cab = api
    r = client.post("/usuarios/Admin/restablecer_clave",
                    json={"clave": "temporal99", "confirmacion": "temporal99"},
                    headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 200
    token = client.post("/auth/login", json={"usuario": "admin", "clave": "temporal99"}).json()["token"]
    r = client.post("/auth/change_password",
                    json={"clave_actual": "temporal99", "clave_nueva": "nueva12345",
                          "confirmacion": "nueva12345"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert client.post("/auth/login", json={"usuario": "ADMIN", "clave": "nueva12345"}).status_code == 200


@pytest.mark.parametrize("nombre", ["admin", "ADMIN", "ingeniero", "TOMAS_TEC"])
def test_crear_rechaza_nombre_que_solo_difiere_en_mayusculas(api, nombre):
    client, srv, ctx, cab = api
    r = client.post("/usuarios", json={"nombre": "Copia", "usuario": nombre, "clave": "clave1234",
                                       "confirmacion": "clave1234", "rol": "tecnico"},
                    headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 409 and r.json()["codigo"] == "usuario_existe"


def test_regla_ultimo_ingeniero_activo_se_conserva(tmp_path, monkeypatch):
    # BD anterior con la semilla `ingeniero` desactivada: tras migrar sigue
    # inactiva y la regla protege a la última ingeniera activa
    ruta = tmp_path / "f.db"
    crear_bd_v10(ruta, monkeypatch,
                 lambda c: c.execute("UPDATE usuarios SET activo=0 WHERE usuario='ingeniero'"))
    db = DbManager(db_path=ruta)
    try:
        assert _fila(db, "Ingeniero")["activo"] == 0 and _fila(db, "Ingeniero")["cuenta_sistema"] == 1
        client, srv, ctx, cab = _cliente(db)
        h_otro = cab(srv, "ingeniero", usuario="otro_ing")
        assert db.fijar_activo_usuario("ines_ing", False, "ingeniero") == "ultimo_protegido"
        r = client.put("/usuarios/ines_ing/activo", json={"activo": False}, headers=h_otro)
        assert r.status_code == 409 and r.json()["codigo"] == "ultimo_ingeniero"
        assert _fila(db, "ines_ing")["activo"] == 1
        # reactivar la cuenta del sistema sí se permite; desactivarla de nuevo, no
        r = client.put("/usuarios/Ingeniero/activo", json={"activo": True}, headers=h_otro)
        assert r.status_code == 200 and _fila(db, "Ingeniero")["activo"] == 1
        r = client.put("/usuarios/Ingeniero/activo", json={"activo": False}, headers=h_otro)
        assert r.status_code == 409 and r.json()["codigo"] == "cuenta_sistema"
        # con Ingeniero activo, ines ya no es la última
        r = client.put("/usuarios/ines_ing/activo", json={"activo": False}, headers=h_otro)
        assert r.status_code == 200
    finally:
        db.close()


# ── UI de usuarios (controlador y pantalla) ────────────────────────────────

USUARIOS_UI = {
    "usuarios": [
        {"nombre": "Admin", "usuario": "Admin", "rol": "admin", "activo": True,
         "cuenta_sistema": True, "ultimo_ingreso": None},
        {"nombre": "Ingeniero", "usuario": "Ingeniero", "rol": "ingeniero", "activo": True,
         "cuenta_sistema": True, "ultimo_ingreso": None},
        {"nombre": "Tomás Gil", "usuario": "tomas_tec", "rol": "tecnico", "activo": True,
         "cuenta_sistema": False, "ultimo_ingreso": None},
    ],
    "gestionables": ["admin", "ingeniero", "tecnico"],
}


def test_controlador_expone_cuenta_sistema_y_mapea_error():
    import sys as _sys
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(_sys.argv)
    from autoclave.ui_qml.controllers.usuarios_controller import UsuariosController, mensaje_de
    from autoclave.ui_qml.sesion_backend import Resultado

    class S:
        def enviar(self, metodo, ruta, cuerpo=None):
            return Resultado("ok", USUARIOS_UI if ruta == "/usuarios" else {}, 200)

    c = UsuariosController(sesion=S())
    c.rol, c.usuarioActual = "ingeniero", "ines_ing"
    c.cargar()
    filas = {u["usuario"]: u for u in c.usuarios}
    assert filas["Admin"]["cuentaSistema"] is True and filas["tomas_tec"]["cuentaSistema"] is False
    assert c.motivoSobre("Admin") == ""                 # restablecer la clave sigue disponible
    assert mensaje_de("cuenta_sistema") == "gestion_usuarios.err_cuenta_sistema"


def test_pantalla_deshabilita_desactivar_cuenta_sistema():
    pytest.importorskip("PySide6")
    from tests.helpers.opciones_qml_doble import correr
    leer = [("botonRestablecerClave", "habilitado"), ("botonActivoUsuario", "habilitado"),
            ("motivoCuentaSistema", "visible")]
    r = correr("usuarios", "ingeniero", {"/usuarios": USUARIOS_UI, "/operadores": {"operadores": []}},
               usuario="ines_ing",
               pasos=[{"fijar": [("opcionesUsuarios", "seleccionado", "Admin")], "leer": leer},
                      {"fijar": [("opcionesUsuarios", "seleccionado", "tomas_tec")], "leer": leer}])
    assert r["avisos"] == []
    p_admin, p_tec = (p["props"] for p in r["pasos"])
    assert p_admin["botonActivoUsuario.habilitado"] is False
    assert p_admin["botonRestablecerClave.habilitado"] is True
    assert p_admin["motivoCuentaSistema.visible"] is True
    assert p_tec["botonActivoUsuario.habilitado"] is True
    assert p_tec["motivoCuentaSistema.visible"] is False
