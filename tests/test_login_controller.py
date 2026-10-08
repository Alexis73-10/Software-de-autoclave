# LoginController contra el backend REAL (T-8; plan_t8_login_qml.md §3):
# POST /auth/login por la sesión de la ventana, con el transporte apuntando a
# un TestClient de autoclave.backend.server (BD SQLite temporal). El bloqueo,
# los intentos y la auditoría los pone el backend; aquí se comprueba que el
# controlador los refleja con claves de es.json y que la sesión queda en
# SessionManager con el token fuera del dict.

import logging
import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui_pyside.services.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.controllers.login_controller import LoginController
from tests.test_contrato_autenticacion import _backend_real


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()
    _recolectar()


def transporte_de(cliente):
    """Transporte de sesion_backend sobre un TestClient (sin red)."""
    def transporte(metodo, ruta, cuerpo, token, plazo):
        cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
        r = cliente.request(metodo, ruta, json=cuerpo, headers=cabeceras)
        return r.status_code, r.json()
    return transporte


@pytest.fixture
def backend(tmp_path):
    return _backend_real(tmp_path)


@pytest.fixture
def ctrl(backend):
    sesion = sb.SesionVentana(transporte=transporte_de(backend), ejecutar=lambda t: t())
    c = LoginController(sesion=sesion)
    c.emitidas = []
    c.sesionIniciada.connect(lambda u, r: c.emitidas.append((u, r)))
    c.cambioClaveRequerido.connect(lambda: c.emitidas.append(("cambio",)))
    return c


def test_credenciales_validas_abren_sesion_con_token(ctrl, backend):
    assert ctrl.iniciarSesion("tec1", "clave1234")
    assert ctrl.emitidas == [("tec1", "tecnico")]
    assert SessionManager.current_role() == "tecnico"
    token = SessionManager.token()
    assert backend.get("/auth/sesion", headers={"Authorization": f"Bearer {token}"}).json() == {
        "usuario": "tec1", "rol": "tecnico"}


def test_semilla_admin_obliga_a_cambiar_la_clave(ctrl):
    ctrl.iniciarSesion("admin", "admin1234")
    assert ctrl.emitidas == [("cambio",)]
    assert SessionManager.debe_cambiar_clave()


@pytest.mark.parametrize("usuario,clave", [("tec1", "mala"), ("nadie", "clave1234")])
def test_credenciales_invalidas_un_solo_mensaje(ctrl, usuario, clave):
    ctrl.iniciarSesion(usuario, clave)
    assert ctrl.mensajeClave == "sesion.credenciales_invalidas"
    assert not SessionManager.is_authenticated() and ctrl.emitidas == []


@pytest.mark.parametrize("usuario,clave", [("", "x"), ("tec1", ""), ("   ", "x")])
def test_campos_vacios(ctrl, usuario, clave):
    assert not ctrl.iniciarSesion(usuario, clave)
    assert ctrl.mensajeClave == "sesion.campos_vacios"


def test_usuario_con_espacios_alrededor(ctrl):
    ctrl.iniciarSesion("  tec1  ", "clave1234")
    assert SessionManager.current_user()["usuario"] == "tec1"


def test_mensaje_se_limpia_al_acertar(ctrl):
    ctrl.iniciarSesion("tec1", "mala")
    assert ctrl.mensajeClave
    ctrl.iniciarSesion("tec1", "clave1234")
    assert ctrl.mensajeClave == ""


def test_quinto_fallo_bloquea_con_cuenta_regresiva(ctrl):
    for _ in range(4):
        ctrl.iniciarSesion("bloq1", "mala")
        assert not ctrl.bloqueado
    ctrl.iniciarSesion("bloq1", "mala")
    assert ctrl.mensajeClave == "sesion.usuario_bloqueado"
    assert ctrl.bloqueado and ctrl.tiempoBloqueo == "5:00"


def test_intento_fallido_cierra_la_sesion_previa(ctrl, backend):
    ctrl.iniciarSesion("tec1", "clave1234")
    token = SessionManager.token()
    ctrl.iniciarSesion("tec1", "mala")
    assert not SessionManager.is_authenticated()
    # la sesión anterior también se cerró en el backend
    assert backend.get("/auth/sesion", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_cerrar_sesion_invalida_el_token(ctrl, backend):
    ctrl.iniciarSesion("tec1", "clave1234")
    token = SessionManager.token()
    ctrl.cerrarSesion()
    assert not SessionManager.is_authenticated()
    assert backend.get("/auth/sesion", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_ni_la_contrasena_ni_el_token_aparecen_en_logs(ctrl, caplog):
    with caplog.at_level(logging.DEBUG):
        ctrl.iniciarSesion("tec1", "clave1234")
        token = SessionManager.token()
        ctrl.iniciarSesion("tec1", "otra-mala")
    assert "clave1234" not in caplog.text and "otra-mala" not in caplog.text
    assert token not in caplog.text


def _recolectar():
    """Destruye en un punto seguro los QObject de la prueba que quedaron en
    ciclos de referencias: si el recolector lo hace durante processEvents,
    mientras Qt despacha uno de sus timers, el proceso cae."""
    import gc
    gc.collect()
    QCoreApplication.processEvents()
