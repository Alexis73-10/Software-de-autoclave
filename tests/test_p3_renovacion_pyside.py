"""P3 (tanda 5): renovación del token en la UI PySide y reintento tras 401."""

import pytest
import requests

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_pyside.services import auth_backend
from autoclave.ui_pyside.services import renovacion_sesion as rs


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def sesion():
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    yield
    SessionManager.logout()


def _renovador(estado=200):
    reloj, consultas, caducadas = Reloj(), [], []

    def consultar(token):
        consultas.append(token)
        return estado
    r = rs.RenovadorSesion(consultar=consultar, reloj=reloj, al_caducar=lambda: caducadas.append(1))
    return r, reloj, consultas, caducadas


def test_en_uso_renueva_cada_30_s_como_maximo(sesion):
    r, reloj, consultas, _ = _renovador()
    r.actividad()
    assert r.tick() and consultas == ["TOK"]
    reloj.t += 10
    r.actividad()
    assert not r.tick()
    reloj.t += 25
    r.actividad()
    assert r.tick() and len(consultas) == 2


def test_sin_actividad_mayor_al_plazo_no_renueva(sesion):
    r, reloj, consultas, _ = _renovador()
    r.actividad()
    r.tick()
    reloj.t += rs.SESION_INACTIVIDAD_S + 1
    assert not r.tick() and consultas == ["TOK"]


def test_sin_sesion_o_sin_actividad_no_consulta():
    r, _, consultas, _ = _renovador()
    r.actividad()
    assert not r.tick()
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    try:
        r2, _, c2, _ = _renovador()
        assert not r2.tick() and c2 == []
    finally:
        SessionManager.logout()
    assert consultas == []


def test_401_en_la_renovacion_cierra_la_sesion_local(sesion):
    r, _, _, caducadas = _renovador(estado=401)
    r.actividad()
    r.tick()
    assert SessionManager.token() is None and caducadas == [1]


def test_backend_sin_respuesta_no_cierra_la_sesion(sesion):
    r, _, _, caducadas = _renovador(estado=None)
    r.actividad()
    r.tick()
    assert SessionManager.token() == "TOK" and caducadas == []


class _Resp:
    def __init__(self, codigo):
        self.status_code = codigo


def _http(codigo):
    return requests.HTTPError(response=_Resp(codigo))


def test_401_con_reintento_exitoso_guarda_lo_editado():
    datos = {"valor": 134.5}
    llamadas = []

    def guardar():
        llamadas.append(dict(datos))
        if len(llamadas) == 1:
            raise _http(401)
        return "ok"
    res = rs.guardar_con_reintento(guardar, lambda: ("t", "clave"),
                                   iniciar_sesion=lambda u, c: auth_backend.ResultadoLogin(auth_backend.OK))
    assert res.estado == rs.GUARDADO and res.valor == "ok"
    assert llamadas == [datos, datos]          # mismos datos, sin perder lo editado


def test_401_cancelado_no_guarda_y_dice_el_motivo():
    llamadas = []

    def guardar():
        llamadas.append(1)
        raise _http(401)
    res = rs.guardar_con_reintento(guardar, lambda: None,
                                   iniciar_sesion=lambda u, c: pytest.fail("no debe iniciar"))
    assert res.estado == rs.CANCELADO and llamadas == [1]
    assert "NO se guardó" in rs.mensaje_de(res)


def test_401_con_login_fallido_no_guarda():
    llamadas = []

    def guardar():
        llamadas.append(1)
        raise _http(401)
    res = rs.guardar_con_reintento(
        guardar, lambda: ("t", "mala"),
        iniciar_sesion=lambda u, c: auth_backend.ResultadoLogin(auth_backend.CREDENCIALES))
    assert res.estado == rs.LOGIN_FALLIDO and llamadas == [1]
    assert "NO se guardó" in rs.mensaje_de(res)


def test_otros_errores_se_propagan_sin_pedir_login():
    def guardar():
        raise _http(422)
    with pytest.raises(requests.HTTPError):
        rs.guardar_con_reintento(guardar, lambda: pytest.fail("no debe pedir login"))


def test_reingreso_de_otro_usuario_no_guarda(sesion):
    llamadas = []

    def guardar():
        llamadas.append(1)
        raise _http(401)
    res = rs.guardar_con_reintento(guardar, lambda: ("otro", "clave"),
                                   iniciar_sesion=lambda u, c: pytest.fail("no debe iniciar"))
    assert res.estado == rs.LOGIN_FALLIDO and res.login == rs.OTRO_USUARIO
    assert llamadas == [1] and "mismo usuario" in rs.mensaje_de(res)
