# CambioClaveController (T-8; plan_t8_login_qml.md §3.3): validación local con
# las reglas de Nuevo usuario, errores del backend por campo y por clave de
# es.json, y bloqueo de escrituras sin conexión.

import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.ui_qml.controllers.cambio_clave_controller import CambioClaveController
from autoclave.ui_qml.sesion_backend import SesionVentana


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_pendiente():
    SessionManager.login({"nombre": "Admin", "usuario": "admin", "rol": "admin",
                          "debe_cambiar_clave": True}, token="tok")
    yield
    SessionManager.logout()
    _recolectar()


class Transporte:
    def __init__(self, respuesta=(200, {"ok": True})):
        self.respuesta = respuesta
        self.llamadas = []

    def __call__(self, metodo, ruta, cuerpo, token, plazo):
        self.llamadas.append(ruta)
        return self.respuesta


def _control(respuesta=(200, {"ok": True})):
    t = Transporte(respuesta)
    s = SesionVentana(transporte=t, ejecutar=lambda f: f())
    c = CambioClaveController(sesion=s)
    c.eventos = []
    c.claveCambiada.connect(lambda: c.eventos.append("cambiada"))
    c.sesionTerminada.connect(lambda: c.eventos.append("terminada"))
    return c, s, t


def _e(clave, **valores):
    return {"clave": clave, "valores": valores}


@pytest.mark.parametrize("args,errores", [
    (("", "nueva12345", "nueva12345"), {"clave_actual": _e("validacion.obligatorio")}),
    (("admin1234", "corta", "corta"), {"clave_nueva": _e("validacion.corta", min=8)}),
    (("admin1234", "a" * 65, "a" * 65), {"clave_nueva": _e("validacion.larga", max=64)}),
    (("admin1234", "admin1234", "admin1234"), {"clave_nueva": _e("validacion.igual_actual")}),
    (("admin1234", "nueva12345", "otra12345"), {"confirmacion": _e("validacion.no_coinciden")}),
])
def test_validacion_local_no_sale_a_la_red(args, errores):
    c, _, t = _control()
    assert not c.cambiar(*args)
    assert c.errores == errores and t.llamadas == []


def test_exito_quita_la_bandera():
    c, _, t = _control()
    assert c.cambiar("admin1234", "nueva12345", "nueva12345")
    assert c.eventos == ["cambiada"] and t.llamadas == ["/auth/change_password"]
    assert not SessionManager.debe_cambiar_clave()


def test_errores_del_backend_por_campo():
    c, _, _ = _control((422, {"codigo": "validacion", "errores": [
        {"campo": "clave_nueva", "codigo": "igual_actual"}]}))
    c.cambiar("admin1234", "nueva12345", "nueva12345")
    assert c.errores == {"clave_nueva": _e("validacion.igual_actual")}
    assert c.eventos == []


def test_clave_actual_incorrecta_en_su_campo():
    c, _, _ = _control((403, {"codigo": "clave_actual_incorrecta"}))
    c.cambiar("mala", "nueva12345", "nueva12345")
    assert c.errores == {"clave_actual": _e("sesion.clave_actual_incorrecta")}
    assert SessionManager.is_authenticated()


def test_codigo_desconocido_mensaje_generico():
    c, _, _ = _control((409, {"codigo": "otro"}))
    c.cambiar("admin1234", "nueva12345", "nueva12345")
    assert c.mensajeClave == "sesion.error_generico" and c.eventos == []


def test_sin_conexion_no_sale_a_la_red():
    c, s, t = _control()
    s.vigilar(False, True)
    assert not c.cambiar("admin1234", "nueva12345", "nueva12345")
    assert c.mensajeClave == "sesion.sin_conexion_escrituras" and t.llamadas == []


def test_abandonar_cierra_con_logout():
    c, _, t = _control()
    c.abandonar()
    assert not SessionManager.is_authenticated() and t.llamadas == ["/auth/logout"]


def _recolectar():
    """Destruye en un punto seguro los QObject de la prueba que quedaron en
    ciclos de referencias: si el recolector lo hace durante processEvents,
    mientras Qt despacha uno de sus timers, el proceso cae."""
    import gc
    gc.collect()
    QCoreApplication.processEvents()
