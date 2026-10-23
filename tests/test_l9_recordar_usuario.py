# tests/test_l9_recordar_usuario.py
#
# D9-12 (H9, tanda 9): "Recordar usuario" en el inicio de sesión QML. Solo se
# recuerda el NOMBRE de usuario (nunca la contraseña ni el token), en un
# archivo local de preferencias de la interfaz, y solo tras credenciales
# válidas. Desmarcar la casilla y entrar borra el nombre guardado.

import json
import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.controllers.login_controller import LoginController
from autoclave.ui_qml.domain import recordar_usuario as ru
from tests.test_contrato_autenticacion import _backend_real
from tests.test_login_controller import transporte_de


# ── módulo de dominio ─────────────────────────────────────────────────

def test_sin_archivo_no_hay_usuario(tmp_path):
    assert ru.cargar(tmp_path / "no.json") == ""


def test_guardar_y_cargar(tmp_path):
    ruta = tmp_path / "sub" / "login.json"
    ru.guardar("tec1", ruta)
    assert ru.cargar(ruta) == "tec1"
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"usuario": "tec1"}


def test_olvidar_borra_el_archivo(tmp_path):
    ruta = tmp_path / "login.json"
    ru.guardar("tec1", ruta)
    ru.olvidar(ruta)
    assert not ruta.exists() and ru.cargar(ruta) == ""
    ru.olvidar(ruta)   # sin archivo: no falla


@pytest.mark.parametrize("contenido", [
    "no es json", "[]", '{"usuario": 5}', '{"usuario": "   "}',
    '{"usuario": "' + "x" * 31 + '"}', '{"usuario": "a\\nb"}', '{"otro": "tec1"}',
])
def test_archivo_danado_o_invalido_se_ignora(tmp_path, contenido):
    ruta = tmp_path / "login.json"
    ruta.write_text(contenido, encoding="utf-8")
    assert ru.cargar(ruta) == ""


def test_no_guarda_nombres_invalidos(tmp_path):
    ruta = tmp_path / "login.json"
    ru.guardar("   ", ruta)
    ru.guardar("x" * 31, ruta)
    assert not ruta.exists()


def test_guarda_solo_la_clave_usuario(tmp_path):
    ruta = tmp_path / "login.json"
    ru.guardar("  tec1  ", ruta)
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"usuario": "tec1"}


# ── controlador ───────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()
    import gc
    gc.collect()
    QCoreApplication.processEvents()


@pytest.fixture
def backend(tmp_path):
    return _backend_real(tmp_path)


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "prefs" / "login_recordado.json"


def _ctrl(backend, ruta):
    sesion = sb.SesionVentana(transporte=transporte_de(backend), ejecutar=lambda t: t())
    return LoginController(sesion=sesion, ruta_recordado=ruta)


def test_sin_recordado_casilla_desmarcada(backend, ruta):
    c = _ctrl(backend, ruta)
    assert c.usuarioRecordado == "" and c.recordarUsuario is False


def test_con_recordado_casilla_marcada_y_nombre(backend, ruta):
    ru.guardar("tec1", ruta)
    c = _ctrl(backend, ruta)
    assert c.usuarioRecordado == "tec1" and c.recordarUsuario is True


def test_marcado_y_login_valido_guarda_solo_el_nombre(backend, ruta):
    c = _ctrl(backend, ruta)
    c.fijarRecordarUsuario(True)
    c.iniciarSesion("  tec1 ", "clave1234")
    assert SessionManager.is_authenticated()
    texto = ruta.read_text(encoding="utf-8")
    assert json.loads(texto) == {"usuario": "tec1"}
    assert "clave1234" not in texto and SessionManager.token() not in texto


def test_marcado_y_login_fallido_no_guarda(backend, ruta):
    c = _ctrl(backend, ruta)
    c.fijarRecordarUsuario(True)
    c.iniciarSesion("tec1", "mala")
    c.iniciarSesion("nadie", "clave1234")
    assert not ruta.exists()


def test_login_fallido_no_borra_el_recordado(backend, ruta):
    ru.guardar("tec1", ruta)
    c = _ctrl(backend, ruta)
    c.fijarRecordarUsuario(False)
    c.iniciarSesion("tec1", "mala")
    assert ru.cargar(ruta) == "tec1"


def test_desmarcado_y_login_valido_olvida(backend, ruta):
    ru.guardar("tec1", ruta)
    c = _ctrl(backend, ruta)
    c.fijarRecordarUsuario(False)
    c.iniciarSesion("tec1", "clave1234")
    assert SessionManager.is_authenticated() and not ruta.exists()


def test_cambio_de_clave_obligatorio_tambien_recuerda(backend, ruta):
    # credenciales válidas, aunque deba cambiar la contraseña
    c = _ctrl(backend, ruta)
    c.fijarRecordarUsuario(True)
    c.iniciarSesion("admin", "admin1234")
    assert SessionManager.debe_cambiar_clave()
    assert ru.cargar(ruta) == "admin"


def test_cambiar_casilla_emite_y_no_escribe_hasta_entrar(backend, ruta):
    c = _ctrl(backend, ruta)
    cambios = []
    c.recordarUsuarioChanged.connect(lambda: cambios.append(c.recordarUsuario))
    c.fijarRecordarUsuario(True)
    c.fijarRecordarUsuario(True)
    assert cambios == [True] and not ruta.exists()


def test_ruta_por_defecto_en_data_de_la_app():
    from autoclave.utils.paths import app_root
    assert ru.ruta_por_defecto() == app_root() / "data" / "login_recordado.json"
