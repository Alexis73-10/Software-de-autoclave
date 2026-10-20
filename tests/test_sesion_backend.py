# Sesión de la ventana QML contra el backend (T-8; plan_t8_login_qml.md §3):
# capa pura (causas y claves), operación en hilo con plazo total, login,
# cambio de contraseña, logout, escrituras con token y vigilancia de conexión.
# Los casos de timeout usan hilos reales y un plazo reducido; el transporte
# falso se bloquea en un threading.Event.

import logging
import socket
import sys
import threading
import time

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui.service_ui.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.controllers.login_controller import LoginController

TOKEN = "tok-secreto-123"
USUARIO_OK = {"token": TOKEN, "usuario": "tec1", "nombre": "Tec", "rol": "tecnico",
              "debe_cambiar_clave": False}


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()
    _recolectar()


class Transporte:
    """Respuestas por (método, ruta); opcionalmente se bloquea hasta `soltar`."""
    def __init__(self, respuestas=None, bloquear=()):
        self.respuestas = respuestas or {}
        self.bloquear = set(bloquear)
        self.soltar = threading.Event()
        self.llamadas = []

    def __call__(self, metodo, ruta, cuerpo, token, plazo):
        self.llamadas.append((metodo, ruta, token))
        if (metodo, ruta) in self.bloquear:
            self.soltar.wait(5)
        r = self.respuestas.get((metodo, ruta), (200, {"ok": True}))
        if isinstance(r, Exception):
            raise r
        return r

    def rutas(self):
        return [(m, r) for m, r, _ in self.llamadas]


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _sincrono(t):
    t()


def _sesion(transporte, **kw):
    kw.setdefault("ejecutar", _sincrono)
    return sb.SesionVentana(transporte=transporte, **kw)


def _esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        QCoreApplication.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return condicion()


# ── Capa pura ─────────────────────────────────────────────────────────────────

def test_interpretar_codigos_conocidos_y_desconocidos(caplog):
    assert sb.interpretar(200, {"x": 1}).ok
    r = sb.interpretar(429, {"codigo": "usuario_bloqueado", "segundos_restantes": 9})
    assert r.causa == "usuario_bloqueado" and r.datos["segundos_restantes"] == 9
    assert sb.interpretar(422, {"codigo": "validacion", "errores": []}).causa == "validacion"
    with caplog.at_level(logging.ERROR):
        assert sb.interpretar(409, {"codigo": "otro_codigo"}, "/x").causa == "error_generico"
        assert sb.interpretar(422, {"detail": [{"loc": ["body"]}]}).causa == "error_generico"
        assert sb.interpretar(500, "no json").causa == "error_generico"
    assert "HTTP 409 en /x" in caplog.text


def test_llamar_sin_respuesta_no_registra_el_token(caplog):
    def caido(*_a):
        raise ConnectionError(f"http://127.0.0.1:8000 {TOKEN}")
    with caplog.at_level(logging.DEBUG):
        r = sb.llamar(caido, "POST", "/auth/login", token=TOKEN)
    assert r.causa == sb.BACKEND_NO_RESPONDE
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("segundos,texto", [(300, "5:00"), (61, "1:01"), (0.2, "0:01"),
                                             (0, "0:00"), (-3, "0:00")])
def test_formato_tiempo(segundos, texto):
    assert sb.formato_tiempo(segundos) == texto


def test_clave_mensaje():
    assert sb.clave_mensaje("credenciales_invalidas") == "sesion.credenciales_invalidas"
    assert sb.clave_mensaje("usuario_existe") == "usuarios.usuario_existe"
    assert sb.clave_mensaje("cualquier_otro") == "sesion.error_generico"


# ── Token en SessionManager ───────────────────────────────────────────────────

def test_login_guarda_el_token_fuera_del_dict_de_sesion(caplog):
    t = Transporte({("POST", "/auth/login"): (200, USUARIO_OK)})
    s = _sesion(t)
    with caplog.at_level(logging.DEBUG):
        assert s.iniciar_sesion("tec1", "clave1234", lambda r: None)
    assert SessionManager.token() == TOKEN
    usuario = SessionManager.current_user()
    assert usuario["usuario"] == "tec1" and usuario["id"] is None
    assert "token" not in usuario
    assert TOKEN not in repr(usuario) and TOKEN not in str(usuario)
    assert TOKEN not in caplog.text and "clave1234" not in caplog.text


# ── LoginController ───────────────────────────────────────────────────────────

def _login(transporte, reloj=None, **kw):
    s = _sesion(transporte, **kw)
    c = LoginController(sesion=s, reloj=reloj or Reloj())
    eventos = []
    c.sesionIniciada.connect(lambda u, r: eventos.append(("ok", u, r)))
    c.cambioClaveRequerido.connect(lambda: eventos.append(("cambio",)))
    return s, c, eventos


def test_login_correcto_y_cambio_obligatorio():
    s, c, eventos = _login(Transporte({("POST", "/auth/login"): (200, USUARIO_OK)}))
    assert c.iniciarSesion("  tec1 ", "clave1234")
    assert eventos == [("ok", "tec1", "tecnico")] and c.mensajeClave == ""

    t = Transporte({("POST", "/auth/login"): (200, {**USUARIO_OK, "debe_cambiar_clave": True})})
    s, c, eventos = _login(t)
    c.iniciarSesion("admin", "admin1234")
    assert eventos == [("cambio",)] and SessionManager.debe_cambiar_clave()


def test_login_campos_vacios_no_sale_a_la_red():
    t = Transporte()
    _, c, _ = _login(t)
    assert not c.iniciarSesion("", "x")
    assert c.mensajeClave == "sesion.campos_vacios" and t.llamadas == []


def test_credenciales_invalidas():
    t = Transporte({("POST", "/auth/login"): (401, {"codigo": "credenciales_invalidas"})})
    _, c, _ = _login(t)
    c.iniciarSesion("tec1", "mala")
    assert c.mensajeClave == "sesion.credenciales_invalidas"
    assert not SessionManager.is_authenticated() and not c.bloqueado


def test_bloqueo_con_cuenta_regresiva_local():
    reloj = Reloj()
    t = Transporte({("POST", "/auth/login"): (
        429, {"codigo": "usuario_bloqueado", "segundos_restantes": 300})})
    _, c, _ = _login(t, reloj=reloj)
    c.iniciarSesion("tec1", "mala")
    assert c.mensajeClave == "sesion.usuario_bloqueado"
    assert c.bloqueado and c.tiempoBloqueo == "5:00"
    assert not c.iniciarSesion("TEC1", "clave1234")      # botón deshabilitado para ese usuario
    assert len(t.llamadas) == 1                           # sin consultas al backend
    assert c.usuarioBloqueado == "tec1"
    assert c.iniciarSesion("otro", "x")                   # el bloqueo es por usuario
    assert c.bloqueado and len(t.llamadas) == 2
    reloj.t += 299.5
    c._tic_bloqueo()
    assert c.bloqueado and c.tiempoBloqueo == "0:01"
    reloj.t += 0.5
    c._tic_bloqueo()
    assert not c.bloqueado and c.tiempoBloqueo == "0:00"
    assert c.mensajeClave == "sesion.usuario_bloqueado"   # solo se habilita el botón


def test_un_intento_nuevo_cierra_la_sesion_previa_con_logout():
    t = Transporte({("POST", "/auth/login"): (200, USUARIO_OK)})
    _, c, _ = _login(t)
    c.iniciarSesion("tec1", "clave1234")
    c.iniciarSesion("tec1", "clave1234")
    assert t.rutas() == [("POST", "/auth/login"), ("POST", "/auth/logout"),
                         ("POST", "/auth/login")]


# ── Timeouts (plazo total; hilos reales) ──────────────────────────────────────

def test_login_vencido_no_abre_sesion_ni_muestra_bloqueo():
    t = Transporte({("POST", "/auth/login"): (200, USUARIO_OK)}, bloquear={("POST", "/auth/login")})
    s, c, eventos = _login(t, ejecutar=sb._en_hilo, plazo_s=0.2)
    assert c.iniciarSesion("tec1", "clave1234")
    assert c.ocupado
    assert not c.iniciarSesion("tec1", "clave1234")       # una sola operación en vuelo
    assert _esperar(lambda: not c.ocupado)
    assert c.mensajeClave == "sesion.backend_no_responde" and not c.bloqueado
    assert not SessionManager.is_authenticated() and SessionManager.token() is None
    assert eventos == [] and t.rutas() == [("POST", "/auth/login")]


def test_login_que_responde_tarde_se_descarta_e_invalida_su_token():
    t = Transporte({("POST", "/auth/login"): (200, USUARIO_OK)}, bloquear={("POST", "/auth/login")})
    _, c, eventos = _login(t, ejecutar=sb._en_hilo, plazo_s=0.2)
    c.iniciarSesion("tec1", "clave1234")
    assert _esperar(lambda: not c.ocupado)
    t.soltar.set()
    assert _esperar(lambda: ("POST", "/auth/logout", TOKEN) in t.llamadas)
    assert not SessionManager.is_authenticated() and eventos == []


def test_logout_vencido_cierra_local_y_queda_en_el_log(caplog):
    t = Transporte({("POST", "/auth/logout"): TimeoutError("lectura vencida")})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    with caplog.at_level(logging.WARNING):
        s.cerrar_sesion()
    assert not SessionManager.is_authenticated() and SessionManager.token() is None
    assert "Cierre de sesión sin confirmar" in caplog.text
    assert TOKEN not in caplog.text


def test_cambio_de_clave_vencido_sin_reintento_cierra_sesion_y_avisa():
    t = Transporte(bloquear={("POST", "/auth/change_password")})
    s = _sesion(t, ejecutar=sb._en_hilo, plazo_s=0.2)
    SessionManager.login({**USUARIO_OK, "debe_cambiar_clave": True}, token=TOKEN)
    resultados = []
    assert s.cambiar_clave("admin1234", "nueva12345", "nueva12345", resultados.append)
    assert _esperar(lambda: resultados)
    assert resultados[0].causa == sb.BACKEND_NO_RESPONDE
    assert not SessionManager.is_authenticated()
    assert t.rutas().count(("POST", "/auth/change_password")) == 1   # sin reintento
    c = LoginController(sesion=s)
    assert c.mensajeClave == "sesion.clave_pudo_cambiar"


def test_transporte_real_respeta_el_plazo(monkeypatch):
    """Servidor local que acepta la conexión y nunca responde."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    monkeypatch.setenv("AUTOCLAVE_BACKEND_URL", f"http://127.0.0.1:{servidor.getsockname()[1]}")
    try:
        inicio = time.monotonic()
        r = sb.llamar(sb.transporte_http, "POST", "/auth/login",
                      {"usuario": "x", "clave": "y"}, plazo=0.3)
        assert r.causa == sb.BACKEND_NO_RESPONDE
        assert time.monotonic() - inicio < 2.0
    finally:
        servidor.close()


# ── Cambio de contraseña: bloqueo y sesión inválida ───────────────────────────

def test_cambio_de_clave_bloqueado_cierra_sin_logout_y_avisa_con_segundos():
    t = Transporte({("POST", "/auth/change_password"): (
        429, {"codigo": "usuario_bloqueado", "segundos_restantes": 120})})
    s = _sesion(t)
    SessionManager.login({**USUARIO_OK, "debe_cambiar_clave": True}, token=TOKEN)
    s.cambiar_clave("mala", "nueva12345", "nueva12345", lambda r: None)
    assert not SessionManager.is_authenticated()
    assert ("POST", "/auth/logout") not in t.rutas()      # el backend ya lo invalidó
    c = LoginController(sesion=s, reloj=Reloj())
    assert c.mensajeClave == "sesion.usuario_bloqueado"
    assert c.bloqueado and c.tiempoBloqueo == "2:00" and c.usuarioBloqueado == "tec1"


def test_cambio_de_clave_exitoso_quita_la_bandera():
    s = _sesion(Transporte())
    SessionManager.login({**USUARIO_OK, "debe_cambiar_clave": True}, token=TOKEN)
    s.cambiar_clave("admin1234", "nueva12345", "nueva12345", lambda r: None)
    assert SessionManager.is_authenticated() and not SessionManager.debe_cambiar_clave()


# ── Escrituras con token ──────────────────────────────────────────────────────

def test_enviar_pone_el_token_y_un_401_cierra_la_sesion():
    t = Transporte({("POST", "/usuarios"): (401, {"codigo": "sesion_invalida"})})
    s = _sesion(t)
    invalidas = []
    s.sesionInvalida.connect(lambda: invalidas.append(True))
    SessionManager.login(USUARIO_OK, token=TOKEN)
    r = s.enviar("POST", "/usuarios", {"x": 1})
    assert r.causa == "sesion_invalida" and t.llamadas == [("POST", "/usuarios", TOKEN)]
    assert not SessionManager.is_authenticated()
    assert invalidas == []                       # en diferido, fuera del slot que llamó
    assert _esperar(lambda: invalidas == [True])
    assert LoginController(sesion=s).mensajeClave == "sesion.sesion_invalida"


def test_enviar_sin_token_no_sale_a_la_red():
    t = Transporte()
    assert _sesion(t).enviar("POST", "/usuarios").causa == "sesion_invalida"
    assert t.llamadas == []


def test_cerrar_al_salir_hace_logout_sincrono():
    t = Transporte()
    s = _sesion(t, ejecutar=lambda _t: pytest.fail("no debe ir a otro hilo"))
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.cerrar_al_salir()
    assert t.llamadas == [("POST", "/auth/logout", TOKEN)]
    assert not SessionManager.is_authenticated()


# ── Vigilancia de conexión (§3.7) ─────────────────────────────────────────────

def _vigilada(transporte, reloj, **usuario):
    s = _sesion(transporte, reloj=reloj)
    SessionManager.login({**USUARIO_OK, **usuario}, token=TOKEN)
    cierres = []
    s.cierrePorDesconexion.connect(cierres.append)
    return s, cierres


def test_sin_conexion_bloquea_escrituras_y_cuenta_15_s():
    reloj, t = Reloj(), Transporte()
    s, cierres = _vigilada(t, reloj)
    s.vigilar(False, True)
    assert s.sinConexion and s.tiempoParaCierre == "0:15"
    assert s.enviar("POST", "/usuarios").causa == sb.BACKEND_NO_RESPONDE
    assert t.llamadas == []                                # sin salir a la red
    reloj.t += 5.2
    s._revisar_conexion()
    assert s.tiempoParaCierre == "0:10" and cierres == []
    reloj.t += 10
    s._revisar_conexion()
    assert cierres == ["principal"] and not SessionManager.is_authenticated()
    assert not s.sinConexion
    s.vigilar(True, False)                                 # al volver: logout del token
    assert t.llamadas == [("POST", "/auth/logout", TOKEN)]


def test_reconexion_antes_de_15_s_valida_el_token_una_vez():
    reloj, t = Reloj(), Transporte({("GET", "/auth/sesion"): (200, {"usuario": "tec1"})})
    s, cierres = _vigilada(t, reloj)
    s.vigilar(False, True)
    reloj.t += 8
    s.vigilar(True, True)
    assert not s.sinConexion and SessionManager.is_authenticated()
    s.vigilar(True, True)                                  # sin sondeo periódico
    assert t.rutas() == [("GET", "/auth/sesion")] and cierres == []


def test_reconexion_con_401_cierra_la_sesion():
    t = Transporte({("GET", "/auth/sesion"): (401, {"codigo": "sesion_invalida"})})
    s, _ = _vigilada(t, Reloj())
    invalidas = []
    s.sesionInvalida.connect(lambda: invalidas.append(True))
    s.vigilar(False, True)
    s.vigilar(True, True)
    assert not SessionManager.is_authenticated() and invalidas == [True]


def test_cambio_obligatorio_sin_conexion_descarta_el_token_sin_enviar_nada(caplog):
    reloj, t = Reloj(), Transporte()
    s, cierres = _vigilada(t, reloj, debe_cambiar_clave=True)
    s.vigilar(False, True)
    reloj.t += 15
    with caplog.at_level(logging.WARNING):
        s._revisar_conexion()
    assert cierres == ["login"] and not SessionManager.is_authenticated()
    s.vigilar(True, False)
    assert t.llamadas == []
    assert "Token descartado sin conexión" in caplog.text and TOKEN not in caplog.text


def test_fuera_de_pantallas_con_token_no_se_vigila():
    s, _ = _vigilada(Transporte(), Reloj())
    s.vigilar(False, False)
    assert not s.sinConexion
    s.vigilar(False, True)
    assert s.sinConexion
    s.vigilar(False, False)                                # salió de OPCIONES: deja de contar
    assert not s.sinConexion and SessionManager.is_authenticated()


# ── Correcciones de la revisión (TMG-xx temporización, SAF-xx seguridad) ──────

def test_tmg01_cerrar_sesion_cancela_el_login_en_vuelo_e_invalida_su_token():
    """Standby o salida del Login con la petición en vuelo: no se abre sesión."""
    t = Transporte({("POST", "/auth/login"): (200, USUARIO_OK)}, bloquear={("POST", "/auth/login")})
    s = _sesion(t, ejecutar=sb._en_hilo, plazo_s=3.0)
    terminados = []
    s.iniciar_sesion("tec1", "clave1234", terminados.append)
    s.cerrar_sesion()                           # p. ej. standby
    assert not s.ocupado
    t.soltar.set()
    assert _esperar(lambda: ("POST", "/auth/logout", TOKEN) in t.llamadas)
    assert not SessionManager.is_authenticated() and terminados == []


def test_tmg01_cancelar_solo_la_operacion_nombrada():
    t = Transporte(bloquear={("POST", "/auth/change_password")})
    s = _sesion(t, ejecutar=sb._en_hilo, plazo_s=3.0)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.cambiar_clave("a", "nueva12345", "nueva12345", lambda r: None)
    s.operacion.cancelar({"login"})
    assert s.ocupado
    s.operacion.cancelar({"cambio_clave"})
    assert not s.ocupado
    t.soltar.set()


def test_tmg10_login_rechazado_por_ocupado_no_cierra_la_sesion_previa():
    t = Transporte(bloquear={("POST", "/auth/change_password")})
    s = _sesion(t, ejecutar=sb._en_hilo, plazo_s=3.0)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.cambiar_clave("a", "nueva12345", "nueva12345", lambda r: None)
    assert not s.iniciar_sesion("otro", "x", lambda r: None)
    assert SessionManager.is_authenticated()
    t.soltar.set()


def test_tmg04_logout_sin_respuesta_se_reintenta_al_reconectar():
    t = Transporte({("POST", "/auth/logout"): ConnectionError("caído")})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.vigilar(False, False)
    s.cerrar_sesion()
    t.respuestas[("POST", "/auth/logout")] = (200, {"ok": True})
    s.vigilar(True, False)
    assert t.llamadas.count(("POST", "/auth/logout", TOKEN)) == 2


def test_tmg03_cerrar_al_salir_respeta_el_plazo_total_y_envia_pendientes():
    t = Transporte(bloquear={("POST", "/auth/logout")})
    s = _sesion(t)
    s._tokens_por_invalidar.append("tok-pendiente")
    SessionManager.login(USUARIO_OK, token=TOKEN)
    inicio = time.monotonic()
    s.cerrar_al_salir(plazo_s=0.3)
    assert time.monotonic() - inicio < 1.0
    assert {tok for _, _, tok in t.llamadas} == {TOKEN, "tok-pendiente"}
    assert not SessionManager.is_authenticated()
    t.soltar.set()


def test_tmg07_la_validacion_no_compite_con_el_login():
    t = Transporte({("GET", "/auth/sesion"): (200, {})}, bloquear={("POST", "/auth/login")})
    s = _sesion(t, ejecutar=sb._en_hilo, plazo_s=3.0)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.operacion.iniciar(lambda: t("POST", "/auth/login", {}, None, 1) and sb.Resultado("ok"),
                        lambda r: None, nombre="login")
    s.vigilar(False, False)
    s.vigilar(True, False)
    assert _esperar(lambda: ("GET", "/auth/sesion", TOKEN) in t.llamadas)
    t.soltar.set()


def test_saf02_toda_reconexion_con_sesion_valida_el_token():
    t = Transporte({("GET", "/auth/sesion"): (401, {"codigo": "sesion_invalida"})})
    s = _sesion(t)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.vigilar(False, False)                    # fuera de pantallas con token
    s.vigilar(True, False)
    assert not SessionManager.is_authenticated()


def test_saf04_el_repr_del_resultado_no_lleva_el_token():
    assert TOKEN not in repr(sb.Resultado("ok", {"token": TOKEN}))


def test_saf05_escritura_con_plazo_total():
    t = Transporte(bloquear={("POST", "/usuarios")})
    s = _sesion(t, plazo_s=0.3)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    inicio = time.monotonic()
    assert s.enviar("POST", "/usuarios", {}).causa == sb.BACKEND_NO_RESPONDE
    assert time.monotonic() - inicio < 1.0
    t.soltar.set()


def test_saf06_un_rechazo_no_registra_el_usuario_tecleado(caplog):
    t = Transporte({("POST", "/auth/login"): (401, {"codigo": "credenciales_invalidas"})})
    s = _sesion(t)
    with caplog.at_level(logging.DEBUG):
        s.iniciar_sesion("MiClaveSecreta99", "x", lambda r: None)
    assert "MiClaveSecreta99" not in caplog.text


# ── Inactividad de la sesión (SAF-01, decisión de Cristian 2026-10-08) ────────

def test_saf01_cinco_minutos_sin_actividad_cierran_la_sesion_con_logout():
    reloj, t = Reloj(), Transporte()
    s = _sesion(t, reloj=reloj)
    assert sb.SESION_INACTIVIDAD_S == 300
    SessionManager.login(USUARIO_OK, token=TOKEN)
    cierres = []
    s.cierrePorInactividad.connect(lambda: cierres.append(True))
    reloj.t += 299
    s._revisar_inactividad()
    assert SessionManager.is_authenticated() and cierres == []
    reloj.t += 1
    s._revisar_inactividad()
    assert not SessionManager.is_authenticated() and cierres == [True]
    assert t.llamadas == [("POST", "/auth/logout", TOKEN)]
    assert LoginController(sesion=s).mensajeClave == "sesion.sesion_expirada"


def test_saf01_la_actividad_de_esta_ventana_reinicia_el_conteo():
    from PySide6.QtCore import QEvent

    class Evento:   # el filtro solo mira type(); un QMouseEvent real cae al liberarse aquí
        def __init__(self, tipo):
            self._tipo = tipo

        def type(self):
            return self._tipo

    reloj = Reloj()
    s = _sesion(Transporte(), reloj=reloj)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    reloj.t += 290
    assert s.eventFilter(None, Evento(QEvent.Type.Paint)) is False
    s._revisar_inactividad()
    assert SessionManager.is_authenticated()            # un repintado no cuenta
    assert s.eventFilter(None, Evento(QEvent.Type.MouseButtonPress)) is False   # no lo consume
    reloj.t += 290
    s._revisar_inactividad()
    assert SessionManager.is_authenticated()


def test_saf01_fuera_de_las_pantallas_con_sesion_los_toques_no_la_prolongan():
    """Revisión de U2 (tanda 2, SAF-01 Alto): tras salir con Atrás/Home la
    sesión sigue viva, pero los toques en la preciclo o el ciclo en curso (de
    cualquiera) no la prolongan: vence a los 5 min del último uso con token."""
    from PySide6.QtCore import QEvent

    class Evento:
        def __init__(self, tipo):
            self._tipo = tipo

        def type(self):
            return self._tipo

    reloj = Reloj()
    t = Transporte()
    s = _sesion(t, reloj=reloj)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.vigilar(True, True)                    # OPCIONES a la vista
    reloj.t += 100
    s.eventFilter(None, Evento(QEvent.Type.MouseButtonPress))
    s.vigilar(True, False)                   # Home: preciclo, sesión abierta
    for _ in range(4):
        reloj.t += 70
        s.eventFilter(None, Evento(QEvent.Type.MouseButtonPress))
        s._revisar_inactividad()
    assert SessionManager.is_authenticated()  # 280 s desde el último uso con token
    reloj.t += 20
    s._revisar_inactividad()
    assert not SessionManager.is_authenticated()


def test_saf01_volver_a_una_pantalla_con_sesion_cuenta_como_actividad():
    reloj = Reloj()
    s = _sesion(Transporte(), reloj=reloj)
    SessionManager.login(USUARIO_OK, token=TOKEN)
    s.vigilar(True, False)
    reloj.t += 299
    s.vigilar(True, True)                    # el avatar abre OPCIONES
    reloj.t += 200
    s._revisar_inactividad()
    assert SessionManager.is_authenticated()


def test_saf01_el_login_reinicia_el_conteo():
    reloj = Reloj()
    t = Transporte({("POST", "/auth/login"): (200, USUARIO_OK)})
    s = _sesion(t, reloj=reloj)
    reloj.t += 1000                                     # ventana sin uso antes del login
    s.iniciar_sesion("tec1", "clave1234", lambda r: None)
    s._revisar_inactividad()
    assert SessionManager.is_authenticated()


def _recolectar():
    """Destruye en un punto seguro los QObject de la prueba que quedaron en
    ciclos de referencias: si el recolector lo hace durante processEvents,
    mientras Qt despacha uno de sus timers, el proceso cae."""
    import gc
    gc.collect()
    QCoreApplication.processEvents()
