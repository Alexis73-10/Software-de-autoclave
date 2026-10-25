# tests/test_o2b_usuarios.py
#
# O2b (tanda 6): gestión de usuarios y operadores. Listar sin hashes,
# desactivar/reactivar (nunca borrar), restablecer contraseña con cambio
# obligatorio, operadores (tabla aparte, sin contraseña), matriz por rol
# (decisión 1.9 + ROLES_CREABLES), autodesactivación, último ingeniero,
# cierre de sesiones y auditoría.

import json
import sqlite3
from unittest.mock import MagicMock

import pytest

from autoclave.backend.contrasenas import hash_password
from tests.backend_doble import parchear_en_backend


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    for nombre, usuario, rol in (("Ana", "ana_admin", "admin"), ("Tomás", "tomas_tec", "tecnico"),
                                 ("Inés", "ines_ing", "ingeniero"), ("Iván", "ivan_ing", "ingeniero"),
                                 ("Adán", "adan_admin", "admin")):
        ctx.db.crear_usuario(nombre, usuario, hash_password("clave1234"), rol)
    srv, _ = cargar_servidor(ctx)
    ctx.control_loop.test_mode_active = False
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


def _h(srv, cab, rol, usuario=None):
    usuario = usuario or {"admin": "ana_admin", "tecnico": "tomas_tec", "ingeniero": "ines_ing"}.get(rol)
    return cab(srv, rol, usuario=usuario)


ROLES = ["operador", "admin", "tecnico", "ingeniero"]


# ── base de datos ──────────────────────────────────────────────────────────

def test_migracion_v9_crea_operadores_y_prohibe_borrar(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(db_path=tmp_path / "m.db")
    assert db.get_version_esquema() >= 9
    db.crear_usuario("X", "x", "h", "tecnico")
    db.crear_operador("Pedro")
    for sql in ("DELETE FROM usuarios", "DELETE FROM operadores"):
        with pytest.raises(sqlite3.DatabaseError):
            with db._lock:
                db._conn.execute(sql)
    db.close()


def test_listar_sin_hash_y_ultimo_ingreso(api):
    client, srv, ctx, cab = api
    assert client.post("/auth/login", json={"usuario": "tomas_tec", "clave": "clave1234"}).status_code == 200
    r = client.get("/usuarios", headers=_h(srv, cab, "admin"))
    assert r.status_code == 200
    filas = {u["usuario"]: u for u in r.json()["usuarios"]}
    assert "hash_pw" not in json.dumps(r.json())
    assert filas["tomas_tec"]["ultimo_ingreso"] and filas["ana_admin"]["ultimo_ingreso"] is None
    assert r.json()["gestionables"] == ["admin", "tecnico"]


@pytest.mark.parametrize("rol,esperado", [("operador", 403), ("admin", 200), ("tecnico", 200),
                                          ("ingeniero", 200)])
def test_matriz_listar(api, rol, esperado):
    client, srv, ctx, cab = api
    assert client.get("/usuarios", headers=_h(srv, cab, rol)).status_code == esperado


def test_sin_token_401(api):
    client, *_ = api
    assert client.get("/usuarios").status_code == 401
    assert client.put("/usuarios/tomas_tec/activo", json={"activo": False}).status_code == 401
    assert client.post("/usuarios/tomas_tec/restablecer_clave",
                       json={"clave": "nueva1234", "confirmacion": "nueva1234"}).status_code == 401
    assert client.post("/operadores", json={"nombre": "Pedro"}).status_code == 401


# ── desactivar / reactivar: matriz completa ───────────────────────────────

# (rol que actúa, usuario objetivo, código esperado)
MATRIZ_ACTIVO = [
    ("operador", "tomas_tec", 403),
    ("tecnico", "tomas_tec", 403), ("tecnico", "adan_admin", 403), ("tecnico", "ivan_ing", 403),
    ("admin", "tomas_tec", 200), ("admin", "adan_admin", 200), ("admin", "ivan_ing", 403),
    ("ingeniero", "tomas_tec", 200), ("ingeniero", "adan_admin", 200), ("ingeniero", "ivan_ing", 200),
]


@pytest.mark.parametrize("rol,objetivo,esperado", MATRIZ_ACTIVO)
def test_matriz_desactivar(api, rol, objetivo, esperado):
    client, srv, ctx, cab = api
    r = client.put(f"/usuarios/{objetivo}/activo", json={"activo": False}, headers=_h(srv, cab, rol))
    assert r.status_code == esperado
    activo = ctx.db.get_usuario_cualquiera(objetivo)["activo"]
    assert activo == (0 if esperado == 200 else 1)
    if esperado == 200:
        fila = ctx.db.get_auditoria(evento="usuario_desactivado")[0]
        assert fila["entidad"] == objetivo and json.loads(fila["valor_nuevo"]) == {"activo": False}
        # reactivar con el mismo rol
        r = client.put(f"/usuarios/{objetivo}/activo", json={"activo": True}, headers=_h(srv, cab, rol))
        assert r.status_code == 200 and ctx.db.get_usuario_cualquiera(objetivo)["activo"] == 1
        assert ctx.db.get_auditoria(evento="usuario_reactivado")


def test_desactivado_no_puede_ingresar(api):
    client, srv, ctx, cab = api
    client.put("/usuarios/tomas_tec/activo", json={"activo": False}, headers=_h(srv, cab, "admin"))
    assert client.post("/auth/login", json={"usuario": "tomas_tec", "clave": "clave1234"}).status_code == 401


@pytest.mark.parametrize("rol", ["admin", "ingeniero"])
def test_nadie_se_desactiva_a_si_mismo(api, rol):
    client, srv, ctx, cab = api
    yo = {"admin": "ana_admin", "ingeniero": "ines_ing"}[rol]
    r = client.put(f"/usuarios/{yo}/activo", json={"activo": False}, headers=_h(srv, cab, rol))
    assert r.status_code == 409 and r.json()["codigo"] == "autodesactivacion"
    assert ctx.db.get_usuario_cualquiera(yo)["activo"] == 1


def test_no_deja_sin_ingeniero_activo(api):
    client, srv, ctx, cab = api
    h = _h(srv, cab, "ingeniero")                      # ines_ing
    otros = [u["usuario"] for u in ctx.db.listar_usuarios()
             if u["rol"] == "ingeniero" and u["usuario"] != "ines_ing"
             and not u["cuenta_sistema"]]              # ivan
    for u in otros:
        assert client.put(f"/usuarios/{u}/activo", json={"activo": False}, headers=h).status_code == 200
    # U11 (D11-6): la cuenta del sistema Ingeniero no se desactiva (409). Para
    # probar la regla del último ingeniero activo se apaga aquí sin pasar por los
    # triggers (como en una BD antigua con la semilla inactiva; la versión con
    # una BD migrada está en test_u11_cuentas_sistema.py)
    r = client.put("/usuarios/Ingeniero/activo", json={"activo": False}, headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "cuenta_sistema"
    with ctx.db._lock:
        ctx.db._conn.execute("DROP TRIGGER usuarios_cuenta_sistema_protegida")
        ctx.db._conn.execute("UPDATE usuarios SET activo=0 WHERE usuario='Ingeniero'")
        ctx.db._conn.commit()
    # ines sería la última; otro ingeniero (sesión de ivan, ya inactivo) no cuenta
    db = ctx.db
    assert db.fijar_activo_usuario("ines_ing", False, "ingeniero") == "ultimo_protegido"
    h2 = cab(srv, "ingeniero", usuario="otro_ing")
    r = client.put("/usuarios/ines_ing/activo", json={"activo": False}, headers=h2)
    assert r.status_code == 409 and r.json()["codigo"] == "ultimo_ingeniero"
    assert db.get_usuario_cualquiera("ines_ing")["activo"] == 1


def test_desactivar_cierra_sus_sesiones(api):
    client, srv, ctx, cab = api
    token = client.post("/auth/login", json={"usuario": "tomas_tec", "clave": "clave1234"}).json()["token"]
    assert client.get("/usuarios", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    client.put("/usuarios/tomas_tec/activo", json={"activo": False}, headers=_h(srv, cab, "admin"))
    assert client.get("/usuarios", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_usuario_inexistente_404(api):
    client, srv, ctx, cab = api
    assert client.put("/usuarios/nadie/activo", json={"activo": False},
                      headers=_h(srv, cab, "ingeniero")).status_code == 404


def test_activo_estricto_bool(api):
    client, srv, ctx, cab = api
    assert client.put("/usuarios/tomas_tec/activo", json={"activo": "no"},
                      headers=_h(srv, cab, "ingeniero")).status_code == 422


# ── restablecer contraseña ─────────────────────────────────────────────────

@pytest.mark.parametrize("rol,objetivo,esperado", MATRIZ_ACTIVO)
def test_matriz_restablecer(api, rol, objetivo, esperado):
    client, srv, ctx, cab = api
    r = client.post(f"/usuarios/{objetivo}/restablecer_clave",
                    json={"clave": "temporal99", "confirmacion": "temporal99"}, headers=_h(srv, cab, rol))
    assert r.status_code == esperado
    login = client.post("/auth/login", json={"usuario": objetivo, "clave": "temporal99"})
    if esperado == 200:
        assert login.status_code == 200 and login.json()["debe_cambiar_clave"] is True
        assert ctx.db.get_auditoria(evento="clave_restablecida")[0]["entidad"] == objetivo
    else:
        assert login.status_code == 401


def test_restablecer_valida_y_no_audita_la_clave(api):
    client, srv, ctx, cab = api
    h = _h(srv, cab, "ingeniero")
    r = client.post("/usuarios/tomas_tec/restablecer_clave", json={"clave": "ab", "confirmacion": "xy"},
                    headers=h)
    assert r.status_code == 422
    assert {e["campo"] for e in r.json()["errores"]} == {"clave", "confirmacion"}
    client.post("/usuarios/tomas_tec/restablecer_clave",
                json={"clave": "secreta123", "confirmacion": "secreta123"}, headers=h)
    volcado = json.dumps(ctx.db.get_auditoria(limite=1000))
    assert "secreta123" not in volcado


def test_restablecer_propia_409(api):
    client, srv, ctx, cab = api
    r = client.post("/usuarios/ines_ing/restablecer_clave",
                    json={"clave": "temporal99", "confirmacion": "temporal99"}, headers=_h(srv, cab, "ingeniero"))
    assert r.status_code == 409 and r.json()["codigo"] == "usar_cambio_clave"


def test_restablecer_cierra_sesiones(api):
    client, srv, ctx, cab = api
    token = client.post("/auth/login", json={"usuario": "tomas_tec", "clave": "clave1234"}).json()["token"]
    client.post("/usuarios/tomas_tec/restablecer_clave",
                json={"clave": "temporal99", "confirmacion": "temporal99"}, headers=_h(srv, cab, "admin"))
    assert client.get("/usuarios", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ── operadores ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rol,esperado", [("operador", 403), ("admin", 200), ("tecnico", 403),
                                          ("ingeniero", 200)])
def test_matriz_operadores(api, rol, esperado):
    client, srv, ctx, cab = api
    h = _h(srv, cab, rol)
    r = client.post("/operadores", json={"nombre": "  Pedro   Pérez "}, headers=h)
    assert r.status_code == esperado
    if esperado == 200:
        id_ = r.json()["id"]
        assert r.json()["nombre"] == "Pedro Pérez"
        assert ctx.db.get_auditoria(evento="operador_creado")
        assert client.put(f"/operadores/{id_}/activo", json={"activo": False}, headers=h).status_code == 200
        assert ctx.db.get_auditoria(evento="operador_desactivado")
        assert client.get("/operadores", params={"activos": True}).json()["operadores"] == []
        assert client.get("/operadores").json()["operadores"][0]["activo"] is False
    else:
        ctx.db.crear_operador("Luz")
        id_ = ctx.db.listar_operadores()[0]["id"]
        assert client.put(f"/operadores/{id_}/activo", json={"activo": False}, headers=h).status_code == 403
        assert ctx.db.listar_operadores()[0]["activo"] is True


def test_operador_duplicado_y_validacion(api):
    client, srv, ctx, cab = api
    h = _h(srv, cab, "ingeniero")
    assert client.post("/operadores", json={"nombre": "Ñandú"}, headers=h).status_code == 200
    r = client.post("/operadores", json={"nombre": "ñANDÚ"}, headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "operador_existe"
    assert client.post("/operadores", json={"nombre": "   "}, headers=h).status_code == 422
    assert client.post("/operadores", json={"nombre": "x" * 41}, headers=h).status_code == 422
    assert client.put("/operadores/999/activo", json={"activo": False}, headers=h).status_code == 404


# ── permisos de la pantalla (técnico deshabilitado con motivo) ─────────────

@pytest.mark.parametrize("rol,ve,motivo", [("admin", True, ""), ("ingeniero", True, ""),
                                           ("tecnico", True, "rol"), ("operador", False, "rol"),
                                           ("", False, "rol")])
def test_permisos_ui(rol, ve, motivo):
    from autoclave.ui_qml.domain import permisos_opciones as p
    assert p.puede_ver("usuarios", rol) is ve
    assert p.motivo_gestion_usuarios(rol) == motivo


def test_seccion_inicial_del_tecnico_no_cambia():
    from autoclave.ui_qml.domain import permisos_opciones as p
    assert p.seccion_inicial("tecnico") == "parametros_ciclo"
    assert p.seccion_inicial("admin") == "usuarios"


# ── controlador y pantalla ─────────────────────────────────────────────────

USUARIOS_UI = {
    "usuarios": [
        {"nombre": "Ana Ruiz", "usuario": "ana_admin", "rol": "admin", "activo": True,
         "ultimo_ingreso": "2026-10-20T08:15:00"},
        {"nombre": "Tomás Gil", "usuario": "tomas_tec", "rol": "tecnico", "activo": True,
         "ultimo_ingreso": "2026-10-19T17:02:11"},
        {"nombre": "Inés Mora", "usuario": "ines_ing", "rol": "ingeniero", "activo": True,
         "ultimo_ingreso": None},
        {"nombre": "Luis Paz", "usuario": "luis_tec", "rol": "tecnico", "activo": False,
         "ultimo_ingreso": "2026-09-01T10:00:00"},
    ],
    "gestionables": ["admin", "tecnico"],
}
OPERADORES_UI = {"operadores": [{"id": 1, "nombre": "Pedro Pérez", "activo": True},
                                {"id": 2, "nombre": "Marta Ríos", "activo": False}]}


class _SesionUI:
    def __init__(self, causa="ok"):
        from autoclave.ui_qml.sesion_backend import Resultado
        self.R, self.causa, self.enviados = Resultado, causa, []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            return self.R("ok", {"/usuarios": USUARIOS_UI, "/operadores": OPERADORES_UI}.get(ruta, {}), 200)
        return self.R(self.causa, {}, 200)


def _ctrl(rol="admin", yo="ana_admin", causa="ok"):
    import sys as _sys
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(_sys.argv)
    from autoclave.ui_qml.controllers.usuarios_controller import UsuariosController
    s = _SesionUI(causa)
    c = UsuariosController(sesion=s)
    c.rol, c.usuarioActual = rol, yo
    c.cargar()
    return c, s


def test_controlador_lista_y_motivos():
    c, _ = _ctrl()
    assert [u["usuario"] for u in c.usuarios][:2] == ["ana_admin", "tomas_tec"]
    assert c.usuarios[0]["ultimoIngreso"] == "2026-10-20 08:15"
    assert c.motivo == "" and c.motivoSobre("tomas_tec") == ""
    assert c.motivoSobre("ana_admin") == "propio"
    assert c.motivoSobre("ines_ing") == "rol_objetivo"
    t, _ = _ctrl("tecnico", "tomas_tec")
    assert t.motivo == "rol" and t.motivoSobre("luis_tec") == "rol"


def test_controlador_envia_y_mapea_errores():
    c, s = _ctrl()
    assert c.fijarActivo("tomas_tec", False)
    assert ("PUT", "/usuarios/tomas_tec/activo", {"activo": False}) in s.enviados
    assert c.restablecer("tomas_tec", "temporal99", "temporal99")
    assert c.agregarOperador("Ana") and ("POST", "/operadores", {"nombre": "Ana"}) in s.enviados
    assert c.fijarActivoOperador(2, True)
    assert not c.agregarOperador("   ") and c.mensaje == "gestion_usuarios.err_validacion"
    c2, _ = _ctrl("ingeniero", "ines_ing", causa="ultimo_ingeniero")
    assert not c2.fijarActivo("x", False) and c2.mensaje == "gestion_usuarios.err_ultimo_ingeniero"


def test_textos_es_en():
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    es = json.loads((raiz / "es.json").read_text(encoding="utf-8"))["gestion_usuarios"]
    en = json.loads((raiz / "en.json").read_text(encoding="utf-8"))["gestion_usuarios"]
    assert set(es) == set(en) and all(es.values()) and all(en.values())
    from autoclave.ui_qml.controllers.usuarios_controller import _MENSAJES
    for clave in _MENSAJES.values():
        if clave.startswith("gestion_usuarios."):
            assert clave.split(".", 1)[1] in es


_LEER = [("botonRestablecerClave", "habilitado"), ("botonActivoUsuario", "habilitado"),
         ("botonNuevoUsuario", "habilitado"), ("avisoMotivoUsuarios", "visible"),
         ("motivoSeleccionado", "visible")]


@pytest.mark.parametrize("rol,yo,habilitado", [("admin", "ana_admin", True),
                                               ("ingeniero", "ines_ing", True),
                                               ("tecnico", "tomas_tec", False)])
def test_pantalla_por_rol(rol, yo, habilitado):
    pytest.importorskip("PySide6")
    from tests.opciones_qml_doble import correr
    r = correr("usuarios", rol, {"/usuarios": USUARIOS_UI, "/operadores": OPERADORES_UI}, usuario=yo,
               pasos=[{"leer": _LEER, "captura": f"O2b_1_usuarios_{rol}.png" if rol != "ingeniero" else ""},
                      {"fijar": [("opcionesUsuarios", "seleccionado", "luis_tec")], "leer": _LEER,
                       "captura": "O2b_2_seleccionado_admin.png" if rol == "admin" else ""},
                      {"fijar": [("opcionesUsuarios", "seleccionado", yo)], "leer": _LEER},
                      {"fijar": [("opcionesUsuarios", "pestana", "operadores")],
                       "leer": [("botonAgregarOperador", "habilitado")],
                       "captura": f"O2b_3_operadores_{rol}.png" if rol != "ingeniero" else ""}])
    assert r["avisos"] == []
    p0, p1, p2, p3 = (p["props"] for p in r["pasos"])
    textos = r["pasos"][0]["textos"]
    assert any("Ana Ruiz" in t for t in textos) and "Desactivado" in textos
    assert p0["botonNuevoUsuario.habilitado"] is habilitado
    assert p0["avisoMotivoUsuarios.visible"] is (not habilitado)
    assert p0["botonRestablecerClave.habilitado"] is False          # sin selección
    assert p1["botonActivoUsuario.habilitado"] is habilitado
    assert p1["botonRestablecerClave.habilitado"] is habilitado
    if habilitado:
        assert p2["botonActivoUsuario.habilitado"] is False and p2["motivoSeleccionado.visible"] is True
    assert p3["botonAgregarOperador.habilitado"] is habilitado
    assert any("Pedro Pérez" in t for t in r["pasos"][3]["textos"])


def test_login_no_emite_si_cambio_la_clave_durante_la_verificacion(api, monkeypatch):
    """H-01 (safety-reviewer): restablecer entre la lectura y la emisión del token."""
    client, srv, ctx, cab = api
    original = srv.verificar_password

    def lenta(clave, h):
        ok = original(clave, h)
        ctx.db.restablecer_password("tomas_tec", hash_password("otra_clave9"))
        return ok
    parchear_en_backend(monkeypatch, "verificar_password", lenta)
    assert client.post("/auth/login", json={"usuario": "tomas_tec", "clave": "clave1234"}).status_code == 401


def test_operadores_sin_metadatos_publicos(api):
    client, srv, ctx, cab = api
    ctx.db.crear_operador("Luz", "ana_admin")
    assert set(client.get("/operadores").json()["operadores"][0]) == {"id", "nombre", "activo"}
