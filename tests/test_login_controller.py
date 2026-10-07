# Validación provisional del Login QML (enmienda de planeacion_nuevo_usuario.md,
# 2026-10-01): LoginController autentica contra la tabla usuarios con el mismo
# hash que el login PySide (D-03), por acceso directo a SQLite (D-04), y abre
# la sesión en SessionManager. A qué pantalla lleva la sesión aún no está definido.

import logging

import pytest

from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.ui_pyside.services.session_manager import SessionManager, hash_password
from autoclave.ui_qml.controllers.login_controller import (
    CAMPOS_VACIOS, CREDENCIALES_INVALIDAS, LoginController,
)


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()


@pytest.fixture
def db(tmp_path):
    base = DbManager(db_path=tmp_path / "t.db")   # trae admin / admin1234 (seed)
    base.crear_usuario("Ana Ruiz", "anar", hash_password("clave1234"), "tecnico")
    base.crear_usuario("Inactivo", "inact", hash_password("clave1234"), "tecnico", activo=0)
    return base


@pytest.fixture
def ctrl(db):
    return LoginController(db_factory=lambda: db)


def test_credenciales_validas_abren_sesion(ctrl):
    emitidas = []
    ctrl.sesionIniciada.connect(lambda u, r: emitidas.append((u, r)))
    assert ctrl.iniciarSesion("anar", "clave1234") is True
    assert SessionManager.current_user()["usuario"] == "anar"
    assert SessionManager.current_role() == "tecnico"
    assert emitidas == [("anar", "tecnico")]
    assert ctrl.mensajeError == ""
    assert ctrl.nombreSesion == "Ana Ruiz"


def test_admin_del_seed(ctrl):
    assert ctrl.iniciarSesion("admin", "admin1234") is True
    assert SessionManager.current_role() == "admin"


@pytest.mark.parametrize("usuario,clave", [
    ("anar", "otra12345"),      # contraseña incorrecta
    ("fantasma", "clave1234"),  # no existe
    ("inact", "clave1234"),     # inactivo
    ("ANAR", "clave1234"),      # el login compara exacto (P-05)
])
def test_credenciales_invalidas(ctrl, usuario, clave):
    emitidas = []
    ctrl.sesionIniciada.connect(lambda u, r: emitidas.append(u))
    assert ctrl.iniciarSesion(usuario, clave) is False
    assert ctrl.mensajeError == CREDENCIALES_INVALIDAS
    assert SessionManager.is_authenticated() is False
    assert emitidas == []


@pytest.mark.parametrize("usuario,clave", [("", "clave1234"), ("anar", ""), ("   ", "x")])
def test_campos_vacios(ctrl, usuario, clave):
    assert ctrl.iniciarSesion(usuario, clave) is False
    assert ctrl.mensajeError == CAMPOS_VACIOS


def test_usuario_con_espacios_alrededor(ctrl):
    # igual que login.py: el nombre se recorta, la contraseña no
    assert ctrl.iniciarSesion("  anar ", "clave1234") is True


def test_error_se_limpia_al_acertar(ctrl):
    ctrl.iniciarSesion("anar", "mala")
    assert ctrl.mensajeError != ""
    ctrl.iniciarSesion("anar", "clave1234")
    assert ctrl.mensajeError == ""


def test_intento_fallido_cierra_sesion_previa(ctrl):
    ctrl.iniciarSesion("admin", "admin1234")
    ctrl.iniciarSesion("anar", "mala")
    assert SessionManager.is_authenticated() is False
    assert ctrl.nombreSesion == ""


def test_cerrar_sesion(ctrl):
    ctrl.iniciarSesion("anar", "clave1234")
    ctrl.cerrarSesion()
    assert SessionManager.is_authenticated() is False
    assert ctrl.nombreSesion == ""


def test_conserva_una_instancia_de_db(db):
    llamadas = []

    def fabrica():
        llamadas.append(1)
        return db

    c = LoginController(db_factory=fabrica)
    c.iniciarSesion("anar", "mala")
    c.iniciarSesion("anar", "clave1234")
    assert len(llamadas) == 1   # NU-07


def test_contrasena_no_aparece_en_logs(ctrl, caplog):
    with caplog.at_level(logging.DEBUG):
        ctrl.iniciarSesion("anar", "clave1234")
        ctrl.iniciarSesion("anar", "secreta999")
    assert "clave1234" not in caplog.text
    assert "secreta999" not in caplog.text
    assert hash_password("clave1234") not in caplog.text
