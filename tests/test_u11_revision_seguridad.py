# tests/test_u11_revision_seguridad.py
#
# Revisión de seguridad de U11 (tanda 11, D11-6):
# SAF-01: Unicode (NFKC + casefold) en unicidad, búsqueda, bloqueo y
#         simulador; caracteres permitidos al crear; `sistema`/`semilla` reservados.
# SAF-02: recursive_triggers y trigger que cubre id / creado_por.
# SAF-03: la semilla se reconoce también por su rol.
# SAF-04: PATCH con cuerpo vacío (422) y campos pedidos en la auditoría.
# Opcional: "Último ingreso" encuentra los ingresos previos al renombre.

import json
import logging
import sqlite3

import pytest

from autoclave.backend.contrasenas import hash_password
from autoclave.services.domain.logging.db_manager import DbManager
from tests.test_u11_cuentas_sistema import _cliente, _fila, _rechazos, api, crear_bd_v10  # noqa: F401

IMITACIONES = ["Αdmin",          # alfa griega
               "Ａdmin",          # A de ancho completo
               "Admin​",         # espacio de ancho cero (Cf)
               "Ad­min",         # guion suave (Cf)
               "Adm\x07in",           # control
               "Аdmin"]          # A cirílica


def _codigos(usuario):
    from autoclave.ui_pyside.services.validacion_usuario import codigos_nuevo_usuario
    return codigos_nuevo_usuario("N", usuario, "clave1234", "clave1234", "tecnico", lambda _u: False)


# ── SAF-01 ─────────────────────────────────────────────────────────────────

def test_normalizar_usuario_nfkc_y_casefold():
    from autoclave.core.runtime.nombre_usuario import normalizar_usuario
    assert normalizar_usuario("ＡDMIN") == normalizar_usuario("admin") == "admin"
    assert normalizar_usuario("PEÑA") == "peña"
    assert normalizar_usuario("Αdmin") != "admin"     # la alfa no es una A


@pytest.mark.parametrize("usuario", IMITACIONES + ["a b", "tab\tx", "ab<c>", "x@y"])
def test_validacion_rechaza_caracteres_no_permitidos(usuario):
    assert _codigos(usuario).get("usuario") == "formato"


@pytest.mark.parametrize("usuario", ["José.Ñandú_1-a", "peña", "PEÑA", "tec1", "ines_ing", "a.b-c"])
def test_validacion_acepta_latinas_digitos_y_signos(usuario):
    assert _codigos(usuario) == {}


@pytest.mark.parametrize("usuario", ["sistema", "SISTEMA", "Semilla", "semilla"])
def test_validacion_reserva_sistema_y_semilla(usuario):
    assert _codigos(usuario).get("usuario") == "reservado"


def test_textos_de_validacion_es_en():
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    for lang in ("es", "en"):
        v = json.loads((raiz / f"{lang}.json").read_text(encoding="utf-8"))["validacion"]
        assert v["reservado"] and "{min}" in v["formato"] and "{max}" in v["formato"]


def test_bd_normaliza_unicode(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    assert db.existe_usuario("Ａdmin") is True
    assert db.get_usuario_by_username("ＡDMIN")["usuario"] == "Admin"
    with pytest.raises(sqlite3.IntegrityError):
        db.crear_usuario("X", "Ａdmin", "h", "tecnico")
    assert db.get_usuario_by_username("Αdmin") is None
    db.close()


def test_contador_de_bloqueo_normaliza_unicode():
    from autoclave.backend.autenticacion import ControlIntentos
    c = ControlIntentos(max_intentos=2)
    c.reservar_intento("admin")
    c.reservar_intento("ＡDMIN")
    assert c.bloqueado("Admin")


@pytest.mark.parametrize("usuario,codigo", [(u, "formato") for u in IMITACIONES]
                         + [("sistema", "reservado"), ("SEMILLA", "reservado")])
def test_api_rechaza_imitaciones_y_reservados(api, usuario, codigo):  # noqa: F811
    client, srv, ctx, cab = api
    r = client.post("/usuarios", json={"nombre": "Copia", "usuario": usuario, "clave": "clave1234",
                                       "confirmacion": "clave1234", "rol": "tecnico"},
                    headers=cab(srv, "ingeniero", usuario="ines_ing"))
    assert r.status_code == 422
    assert {"campo": "usuario", "codigo": codigo} in r.json()["errores"]


def test_simulador_normaliza_y_valida():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from autoclave.simulador.autenticacion_simulada import registrar_autenticacion
    app = FastAPI()
    registrar_autenticacion(app)
    c = TestClient(app)
    r = c.post("/auth/login", json={"usuario": "ＡDMIN", "clave": "admin1234"})
    assert r.status_code == 200 and r.json()["usuario"] == "Admin"
    tok = c.post("/auth/login", json={"usuario": "ing1", "clave": "clave1234"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    cuerpo = {"nombre": "X", "clave": "clave1234", "confirmacion": "clave1234", "rol": "tecnico"}
    assert c.post("/usuarios", json={**cuerpo, "usuario": "Admin​"}, headers=h).status_code == 422
    assert c.post("/usuarios", json={**cuerpo, "usuario": "sistema"}, headers=h).status_code == 422


def test_usuario_existente_con_nombre_ya_no_valido_sigue_entrando(tmp_path, monkeypatch):
    ruta = tmp_path / "f.db"
    crear_bd_v10(ruta, monkeypatch, lambda c: c.execute(
        "INSERT INTO usuarios (nombre, usuario, hash_pw, rol, activo) VALUES ('Viejo', 'José Pérez', ?, "
        "'tecnico', 1)", (hash_password("clave1234"),)))
    db = DbManager(db_path=ruta)
    try:
        client, *_ = _cliente(db)
        r = client.post("/auth/login", json={"usuario": "josé pérez", "clave": "clave1234"})
        assert r.status_code == 200 and r.json()["usuario"] == "José Pérez"
    finally:
        db.close()


# ── SAF-02 ─────────────────────────────────────────────────────────────────

def test_recursive_triggers_activo(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    assert db._conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
    db.close()


@pytest.mark.parametrize("sql", [
    # REPLACE borra la fila en conflicto: con recursive_triggers dispara usuarios_sin_delete
    "INSERT OR REPLACE INTO usuarios (id, nombre, usuario, hash_pw, rol) "
    "SELECT id, 'X', 'x', 'h', 'tecnico' FROM usuarios WHERE usuario='Admin'",
    "REPLACE INTO usuarios (nombre, usuario, hash_pw, rol) VALUES ('X', 'Admin', 'h', 'tecnico')",
    "UPDATE OR REPLACE usuarios SET usuario='Admin' WHERE usuario='pepe'",
    "UPDATE usuarios SET id=999 WHERE usuario='Admin'",
    "UPDATE usuarios SET creado_por='otro' WHERE usuario='Ingeniero'",
])
def test_replace_e_id_creado_por_no_tocan_cuentas_sistema(tmp_path, sql):
    db = DbManager(db_path=tmp_path / "t.db")
    db.crear_usuario("Pepe", "pepe", "h", "tecnico")
    with pytest.raises(sqlite3.DatabaseError):
        with db._lock:
            db._conn.execute(sql)
    db._conn.rollback()
    a = _fila(db, "Admin")
    assert a is not None and a["cuenta_sistema"] == 1 and a["nombre"] == "Admin"
    assert _fila(db, "Ingeniero")["creado_por"] == "semilla"
    assert _fila(db, "pepe") is not None
    db.close()


# ── SAF-03 ─────────────────────────────────────────────────────────────────

def test_migracion_exige_el_rol_de_la_semilla(tmp_path, monkeypatch, caplog):
    ruta = tmp_path / "f.db"
    crear_bd_v10(ruta, monkeypatch,
                 lambda c: c.execute("UPDATE usuarios SET rol='tecnico' WHERE usuario='admin'"))
    with caplog.at_level(logging.WARNING):
        db = DbManager(db_path=ruta)
    f = _fila(db, "admin")
    assert f is not None and f["cuenta_sistema"] == 0 and _fila(db, "Admin") is None
    assert _fila(db, "Ingeniero")["cuenta_sistema"] == 1
    assert any("rol" in r.getMessage() and "'admin'" in r.getMessage() for r in caplog.records)
    db.close()


# ── SAF-04 ─────────────────────────────────────────────────────────────────

def test_patch_vacio_422_y_campos_en_auditoria(api):  # noqa: F811
    client, srv, ctx, cab = api
    h = cab(srv, "ingeniero", usuario="ines_ing")
    assert client.patch("/usuarios/Admin", json={}, headers=h).status_code == 422
    assert client.patch("/usuarios/Admin", json={"nombre": None}, headers=h).status_code == 422
    assert not _rechazos(ctx)
    r = client.patch("/usuarios/Admin", json={"rol": "tecnico", "nombre": "Jefe"}, headers=h)
    assert r.status_code == 409
    detalle = _rechazos(ctx)[0]["detalle"]
    assert detalle["accion"] == "cambiar_rol" and detalle["campos"] == ["nombre", "rol"]


# ── Opcional: último ingreso ───────────────────────────────────────────────

def test_ultimo_ingreso_encuentra_ingresos_previos_al_renombre(tmp_path, monkeypatch):
    ruta = tmp_path / "f.db"
    crear_bd_v10(ruta, monkeypatch)                     # trae un login_ok de `admin`
    db = DbManager(db_path=ruta)
    filas = {u["usuario"]: u for u in db.listar_usuarios()}
    assert filas["Admin"]["ultimo_ingreso"] is not None
    assert filas["Ingeniero"]["ultimo_ingreso"] is None
    db.close()
