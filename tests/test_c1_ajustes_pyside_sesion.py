"""C1 (tanda 3): las ventanas PySide del engrane (calibración, entradas y
salidas, parámetros) se autentican contra el backend y llevan el token: sin él
el backend las rechaza (401) y nada se escribe."""

import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_pyside.services import auth_backend


@pytest.fixture(autouse=True)
def limpia_sesion():
    SessionManager.logout()
    yield
    SessionManager.logout()


def _resp(estado, datos=None):
    r = MagicMock()
    r.status_code = estado
    r.json.return_value = datos if datos is not None else {}
    return r


# ── cliente con token ──────────────────────────────────────────────────────

def test_el_cliente_pyside_envia_el_token_de_la_sesion():
    from autoclave.ui_pyside.services.backend_client import BackendClient
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK123")
    r = MagicMock()
    r.json.return_value = {}
    with patch("requests.patch", return_value=r) as p, patch("requests.get", return_value=r) as g, \
            patch("requests.post", return_value=r) as po:
        c = BackendClient("http://x:8000")
        c.patch("/calibration/temperature/temp_camara", {"a": 1})
        c.get("/status")
        c.post("/io/test/enter")
    for llamada in (p, g, po):
        assert llamada.call_args.kwargs["headers"] == {"Authorization": "Bearer TOK123"}


def test_sin_sesion_no_envia_cabecera():
    from autoclave.ui_pyside.services.backend_client import BackendClient
    r = MagicMock()
    r.json.return_value = {}
    with patch("requests.patch", return_value=r) as p:
        BackendClient("http://x:8000").patch("/calibration/x/y", {})
    assert "headers" not in p.call_args.kwargs


def test_cliente_base_sin_proveedor_no_cambia_el_comportamiento():
    from autoclave.cliente.backend_client import BackendClient
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    r = MagicMock()
    r.json.return_value = {}
    with patch("requests.get", return_value=r) as g:
        BackendClient("http://x:8000").get("/status")
    assert g.call_args.kwargs == {"timeout": 0.8}


def test_todas_las_vistas_pyside_usan_el_cliente_con_token():
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_pyside" / "views"
    for ruta in raiz.rglob("*.py"):
        assert "from autoclave.cliente.backend_client import BackendClient" not in \
            ruta.read_text(encoding="utf-8"), ruta


# ── login contra el backend ────────────────────────────────────────────────

def test_login_ok_guarda_token_y_rol():
    post = MagicMock(return_value=_resp(200, {"token": "T1", "usuario": "tec", "nombre": "Tec Uno",
                                              "rol": "tecnico", "debe_cambiar_clave": False}))
    r = auth_backend.iniciar_sesion("tec", "x", post=post)
    assert r.estado == auth_backend.OK
    assert SessionManager.token() == "T1" and SessionManager.current_role() == "tecnico"
    assert post.call_args.kwargs["json"] == {"usuario": "tec", "clave": "x"}


@pytest.mark.parametrize("estado, datos, esperado", [
    (401, {}, auth_backend.CREDENCIALES),
    (429, {"segundos_restantes": 120}, auth_backend.BLOQUEADO),
    (503, {}, auth_backend.SIN_BD),
    (500, {}, auth_backend.ERROR)])
def test_login_rechazado_no_deja_sesion(estado, datos, esperado):
    r = auth_backend.iniciar_sesion("tec", "x", post=MagicMock(return_value=_resp(estado, datos)))
    assert r.estado == esperado and not SessionManager.is_authenticated()
    if estado == 429:
        assert r.segundos == 120


def test_login_sin_backend():
    r = auth_backend.iniciar_sesion("tec", "x", post=MagicMock(side_effect=requests.ConnectionError()))
    assert r.estado == auth_backend.SIN_CONEXION and not SessionManager.is_authenticated()


def test_login_con_cambio_de_clave_pendiente_no_deja_sesion_y_cierra_el_token():
    posts = []

    def post(url, **kw):
        posts.append(url)
        return _resp(200, {"token": "T2", "usuario": "u", "nombre": "U", "rol": "tecnico",
                           "debe_cambiar_clave": True})

    r = auth_backend.iniciar_sesion("u", "x", post=post)
    assert r.estado == auth_backend.CAMBIO_CLAVE and not SessionManager.is_authenticated()
    assert posts[0].endswith("/auth/login")


def test_cerrar_sesion_invalida_el_token_y_limpia():
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    post = MagicMock()
    auth_backend.cerrar_sesion(post=post)
    assert post.call_args.args[0].endswith("/auth/logout")
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer TOK"}
    assert not SessionManager.is_authenticated() and SessionManager.token() is None


def test_cerrar_sesion_sin_backend_igual_limpia():
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    auth_backend.cerrar_sesion(post=MagicMock(side_effect=requests.ConnectionError()))
    assert not SessionManager.is_authenticated()


# ── vista de calibración: 401/403 no se muestra como fallo de conexión ──────

def _vista():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication(sys.argv)
    from autoclave.ui_pyside.views.entrdas_salidas.calibracion_sensor import CalibracionSensorView
    return CalibracionSensorView(nav_callback=lambda *a, **k: None)


@pytest.mark.parametrize("estado", [401, 403])
def test_calibracion_sin_sesion_o_sin_permiso_lo_dice(estado):
    v = _vista()
    exc = requests.HTTPError()
    exc.response = _resp(estado, {"detail": "Sesión no válida o vencida"})
    assert v._resolver_rechazo(exc, {}) is None
    assert "Sesión vencida o sin permiso" in v._lbl_info.text()
    assert "conectar" not in v._lbl_info.text()


# ── el backend rechaza sin token (nada se escribe) ──────────────────────────

def test_el_backend_rechaza_calibracion_y_salidas_sin_token():
    from fastapi.testclient import TestClient
    from tests.backend_doble import cargar_servidor
    ctx = MagicMock()
    srv, _ = cargar_servidor(ctx)
    c = TestClient(srv.app)
    body = {"shown_low": 20, "real_low": 20, "shown_high": 130, "real_high": 131}
    assert c.patch("/calibration/temperature/temp_camara", json=body).status_code == 401
    assert c.post("/io/test/enter").status_code == 401
    assert c.patch("/io/test/output/vapor_camara", json={"value": True}).status_code == 401
    ctx.setdo.set_output.assert_not_called()


# ── revisión de seguridad: sesión huérfana y rechazos visibles ──────────────

def test_login_cierra_antes_la_sesion_anterior():
    SessionManager.login({"nombre": "A", "usuario": "a", "rol": "tecnico"}, "VIEJO")
    urls = []

    def post(url, **kw):
        urls.append((url.rsplit("/", 1)[-1], kw.get("headers")))
        return _resp(200, {"token": "NUEVO", "usuario": "b", "nombre": "B", "rol": "tecnico",
                           "debe_cambiar_clave": False})

    auth_backend.iniciar_sesion("b", "x", post=post)
    assert urls[0] == ("logout", {"Authorization": "Bearer VIEJO"}) and urls[1][0] == "login"
    assert SessionManager.token() == "NUEVO"


def test_logout_reintenta_una_vez():
    SessionManager.login({"nombre": "A", "usuario": "a", "rol": "tecnico"}, "T")
    post = MagicMock(side_effect=[requests.ConnectionError(), _resp(200)])
    auth_backend.cerrar_sesion(post=post)
    assert post.call_count == 2 and not SessionManager.is_authenticated()


def test_cerrar_la_ventana_invalida_el_token():
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication(sys.argv)
    from autoclave.ui_pyside.main_window import MainWindowFluent
    SessionManager.login({"nombre": "A", "usuario": "a", "rol": "tecnico"}, "T")
    w = MainWindowFluent()
    with patch.object(auth_backend, "cerrar_sesion") as cerrar:
        w.closeEvent(QCloseEvent())
    cerrar.assert_called_once()


def test_salida_rechazada_no_cambia_la_tarjeta():
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication(sys.argv)
    from autoclave.ui_pyside.views.entrdas_salidas.io_do import SalidasDigitalesView
    v = SalidasDigitalesView(nav_callback=lambda *a, **k: None)
    exc = requests.HTTPError()
    exc.response = _resp(401, {"detail": "x"})
    v._client = MagicMock()
    v._client.patch.side_effect = exc
    with patch.object(QMessageBox, "warning") as aviso:
        assert v._toggle_output("vapor_camara", True) is False
    assert "Sesión vencida" in aviso.call_args.args[2]
