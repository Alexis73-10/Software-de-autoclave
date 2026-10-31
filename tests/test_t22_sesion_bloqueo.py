# TEC-ACC-05 (tanda 22): el cliente QML de la sesión (ui_qml/sesion_backend.py)
# reconoce los 403 de la reautenticación de Opciones avanzadas
# (reautenticacion_fallida / reautenticacion_requerida, sin cerrar la sesión ni
# registrar «Respuesta no reconocida») y, ante un 429 usuario_bloqueado en una
# escritura con token (`enviar`), cierra la sesión local de inmediato con el
# aviso de bloqueo y sus segundos, que el login muestra al abrirse.

import logging
import sys
import time

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.controllers.login_controller import LoginController
from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController

pytestmark = pytest.mark.req("TEC-ACC-05")

TOKEN = "tok-secreto-t22"
USUARIO_OK = {"token": TOKEN, "usuario": "ing1", "nombre": "Ing", "rol": "ingeniero",
              "debe_cambiar_clave": False}
NO_RECONOCIDA = "Respuesta no reconocida"
# Status real del backend (server_reasignacion._reautenticar)
STATUS_REAUT = 403


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


class Transporte:
    def __init__(self, respuestas=None):
        self.respuestas = respuestas or {}
        self.llamadas = []

    def __call__(self, metodo, ruta, cuerpo, token, plazo):
        self.llamadas.append((metodo, ruta, token))
        return self.respuestas.get((metodo, ruta), (200, {"ok": True}))

    def rutas(self):
        return [(m, r) for m, r, _ in self.llamadas]


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _sesion(transporte):
    return sb.SesionVentana(transporte=transporte, ejecutar=lambda t: t())


def _esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        QCoreApplication.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return condicion()


# ── Reautenticación: reconocida y sin cerrar la sesión ───────────────────────

@pytest.mark.parametrize("estado_http", [400, 401, STATUS_REAUT])
@pytest.mark.parametrize("codigo,clave", [
    ("reautenticacion_fallida", "reasignacion.err_clave"),
    ("reautenticacion_requerida", "reasignacion.err_clave_requerida"),
])
def test_interpretar_reconoce_la_reautenticacion(caplog, estado_http, codigo, clave):
    with caplog.at_level(logging.ERROR):
        r = sb.interpretar(estado_http, {"codigo": codigo, "detail": "x"}, "/io/assignment")
    assert r.causa == codigo and r.estado_http == estado_http
    assert sb.clave_mensaje(codigo) == clave
    assert NO_RECONOCIDA not in caplog.text


@pytest.mark.parametrize("ruta", ["/io/assignment", "/io/assignment/factory",
                                  "/io/assignment/verify"])
@pytest.mark.parametrize("codigo", ["reautenticacion_fallida", "reautenticacion_requerida"])
def test_enviar_con_reautenticacion_rechazada_no_cierra_la_sesion(caplog, ruta, codigo):
    t = Transporte({("POST", ruta): (STATUS_REAUT, {"codigo": codigo, "detail": "x"})})
    s = _sesion(t)
    invalidas = []
    s.sesionInvalida.connect(lambda: invalidas.append(True))
    SessionManager.login(USUARIO_OK, token=TOKEN)
    with caplog.at_level(logging.ERROR):
        r = s.enviar("POST", ruta, {"clave": "mala"})
    assert r.causa == codigo
    assert SessionManager.is_authenticated() and SessionManager.token() == TOKEN
    assert NO_RECONOCIDA not in caplog.text
    QCoreApplication.processEvents()
    assert invalidas == []
    assert s.tomar_aviso() is None                    # el login no tiene nada que mostrar
    assert ("POST", "/auth/logout") not in t.rutas()


def test_reasignacion_muestra_contrasena_incorrecta():
    """De punta a punta: antes la pantalla mostraba el error genérico."""
    t = Transporte({("POST", "/io/assignment/factory"): (
        STATUS_REAUT, {"codigo": "reautenticacion_fallida", "detail": "Contraseña incorrecta"})})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    c = ReasignacionController(sesion=s)
    assert not c.restaurarFabrica("mala")
    assert c.mensaje == "reasignacion.err_clave"
    assert SessionManager.is_authenticated()


# ── 429 usuario_bloqueado en una escritura con token ─────────────────────────

def test_enviar_429_bloqueado_cierra_la_sesion_con_el_aviso_y_los_segundos():
    t = Transporte({("POST", "/io/assignment"): (
        429, {"codigo": "usuario_bloqueado", "segundos_restantes": 240,
              "detail": "Usuario bloqueado"})})
    s = _sesion(t)
    invalidas = []
    s.sesionInvalida.connect(lambda: invalidas.append(True))
    SessionManager.login(USUARIO_OK, token=TOKEN)
    r = s.enviar("POST", "/io/assignment", {"clave": "mala"})
    assert r.causa == "usuario_bloqueado"
    assert not SessionManager.is_authenticated()           # de inmediato, sin esperar un 401
    assert ("POST", "/auth/logout") not in t.rutas()       # el backend ya invalidó el token
    assert invalidas == []                                 # en diferido, como el 401
    assert _esperar(lambda: invalidas == [True])
    c = LoginController(sesion=s, reloj=Reloj())
    assert c.mensajeClave == "sesion.usuario_bloqueado"
    assert c.bloqueado and c.tiempoBloqueo == "4:00" and c.usuarioBloqueado == "ing1"


def test_enviar_429_sin_segundos_avisa_sin_cuenta_regresiva():
    t = Transporte({("POST", "/io/assignment"): (429, {"codigo": "usuario_bloqueado"})})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.enviar("POST", "/io/assignment", {"clave": "mala"})
    assert not SessionManager.is_authenticated()
    c = LoginController(sesion=s, reloj=Reloj())
    assert c.mensajeClave == "sesion.usuario_bloqueado" and not c.bloqueado


def test_reasignacion_bloqueada_deja_la_sesion_cerrada_sin_mas_peticiones():
    t = Transporte({("POST", "/io/assignment/factory"): (
        429, {"codigo": "usuario_bloqueado", "segundos_restantes": 300})})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    c = ReasignacionController(sesion=s)
    assert not c.restaurarFabrica("mala")
    assert not SessionManager.is_authenticated()
    # la recarga posterior no sale a la red sin token
    assert t.rutas() == [("POST", "/io/assignment/factory")]


# ── Sin cambio en los casos existentes ───────────────────────────────────────

def test_enviar_401_sigue_igual():
    t = Transporte({("POST", "/usuarios"): (401, {"codigo": "sesion_invalida"})})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    assert s.enviar("POST", "/usuarios", {}).causa == "sesion_invalida"
    assert not SessionManager.is_authenticated()
    c = LoginController(sesion=s, reloj=Reloj())
    assert c.mensajeClave == "sesion.sesion_invalida" and not c.bloqueado


def test_enviar_otro_rechazo_no_cierra_la_sesion():
    t = Transporte({("POST", "/usuarios"): (403, {"codigo": "rol_sin_permiso"})})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    assert s.enviar("POST", "/usuarios", {}).causa == "rol_sin_permiso"
    assert SessionManager.is_authenticated()
