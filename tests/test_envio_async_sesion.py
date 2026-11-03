# tests/test_envio_async_sesion.py
#
# SesionVentana.enviar_async (AJUSTES 2026-11-02, paso 2 fase 1): la petición
# va en un hilo de trabajo y el resultado, el trato de 401 / 429 y los
# callbacks llegan en el hilo de la GUI; plazo vigilado al vaciar la cola;
# dueño destruido o cancelado sin caer; generación de sesión. Y el piloto
# UsuariosController con una SesionVentana real (cambio optimista, B y D).

import sys
import threading
import time
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QApplication

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend as sb

TOKEN = "tok-async-1"


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()


def _login(usuario="ana_admin", rol="admin"):
    SessionManager.login({"usuario": usuario, "nombre": "Ana", "rol": rol}, token=TOKEN)


class Transporte:
    def __init__(self, respuestas=None):
        self.respuestas = dict(respuestas or {})
        self.llamadas = []
        self.hilos = []

    def __call__(self, metodo, ruta, cuerpo, token, plazo):
        self.llamadas.append((metodo, ruta, cuerpo))
        self.hilos.append(threading.current_thread())
        r = self.respuestas.get((metodo, ruta), (200, {"ok": True}))
        if isinstance(r, Exception):
            raise r
        return r


class Diferido:
    """Guarda las tareas; `correr()` las ejecuta, cada una en su hilo."""
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self, cuantas=None):
        n = len(self.tareas) if cuantas is None else cuantas
        tareas, self.tareas = self.tareas[:n], self.tareas[n:]
        for t in tareas:
            h = threading.Thread(target=t)
            h.start()
            h.join(5)


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _sesion(transporte=None, **kw):
    d = Diferido()
    kw.setdefault("reloj", Reloj())
    s = sb.SesionVentana(transporte=transporte or Transporte(), ejecutar=d, **kw)
    return s, d


def _procesar(veces=5):
    for _ in range(veces):
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class Registro:
    def __init__(self):
        self.resultados, self.hilos = [], []

    def __call__(self, r):
        self.resultados.append(r)
        self.hilos.append(threading.current_thread())

    @property
    def causas(self):
        return [r.causa for r in self.resultados]


# ── despachador ─────────────────────────────────────────────────────────────

def test_no_bloquea_y_entrega_en_el_hilo_de_la_gui():
    _login()
    t = Transporte({("PUT", "/x"): (200, {"v": 1})})
    s, d = _sesion(t)
    reg = Registro()
    assert s.enviar_async("PUT", "/x", {"a": 1}, reg) is True
    assert reg.resultados == [] and t.llamadas == []      # nada en el acto
    d.correr()
    assert t.hilos[0] is not threading.main_thread()      # la petición, en otro hilo
    assert reg.resultados == []                           # el hilo no entrega
    s._envios._vaciar()
    assert reg.causas == ["ok"] and reg.resultados[0].datos == {"v": 1}
    assert reg.hilos == [threading.main_thread()]


def test_con_hilos_reales_el_callback_corre_en_la_gui():
    _login()
    s = sb.SesionVentana(transporte=Transporte(), ejecutar=sb._en_hilo)
    reg = Registro()
    s.enviar_async("GET", "/y", None, reg)
    limite = time.monotonic() + 3
    while not reg.resultados and time.monotonic() < limite:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert reg.causas == ["ok"] and reg.hilos == [threading.main_thread()]


def test_sin_token_y_sin_conexion_entregan_en_diferido_sin_salir_a_la_red():
    t = Transporte()
    s, d = _sesion(t)
    reg = Registro()
    assert s.enviar_async("PUT", "/x", None, reg) is False
    assert reg.resultados == []                           # nunca dentro de la llamada
    _procesar()
    assert reg.causas == ["sesion_invalida"] and d.tareas == [] and t.llamadas == []
    _login()
    s.vigilar(False, True)
    assert s.sinConexion
    reg2 = Registro()
    s.enviar_async("PUT", "/x", None, reg2)
    _procesar()
    assert reg2.causas == [sb.BACKEND_NO_RESPONDE] and d.tareas == []
    assert SessionManager.is_authenticated()              # no cierra nada


def test_401_en_dos_peticiones_cierra_y_avisa_una_sola_vez_en_la_gui():
    _login()
    t = Transporte({("PUT", "/a"): (401, {"codigo": "sesion_invalida"}),
                    ("PUT", "/b"): (401, {"codigo": "sesion_invalida"})})
    s, d = _sesion(t)
    avisos = []
    s.sesionInvalida.connect(lambda: avisos.append(threading.current_thread()))
    r1, r2 = Registro(), Registro()
    s.enviar_async("PUT", "/a", None, r1)
    s.enviar_async("PUT", "/b", None, r2)
    d.correr()
    s._envios._vaciar()
    _procesar()
    assert r1.causas == ["sesion_invalida"] and r2.causas == ["sesion_invalida"]
    assert not SessionManager.is_authenticated()
    assert avisos == [threading.main_thread()]
    assert s.tomar_aviso() == ("sesion.sesion_invalida", None)


def test_429_bloqueo_cierra_con_el_aviso_de_bloqueo():
    _login(usuario="tomas_tec")
    t = Transporte({("POST", "/z"): (429, {"codigo": "usuario_bloqueado", "segundos_restantes": 60})})
    s, d = _sesion(t)
    avisos = []
    s.sesionInvalida.connect(lambda: avisos.append(1))
    reg = Registro()
    s.enviar_async("POST", "/z", None, reg)
    d.correr()
    s._envios._vaciar()
    _procesar()
    assert reg.causas == ["usuario_bloqueado"] and avisos == [1]
    assert s.tomar_aviso() == ("sesion.usuario_bloqueado", 60, "tomas_tec")


def test_sesion_cerrada_con_peticion_en_vuelo_entrega_sesion_invalida_sin_volver_a_cerrar():
    _login()
    t = Transporte({("PUT", "/a"): (401, {"codigo": "sesion_invalida"})})
    s, d = _sesion(t)
    avisos = []
    s.sesionInvalida.connect(lambda: avisos.append(1))
    reg = Registro()
    s.enviar_async("PUT", "/a", None, reg)
    s.cerrar_local()
    _login()                                              # otra sesión ya abierta
    d.correr()
    s._envios._vaciar()
    _procesar()
    assert reg.causas == ["sesion_invalida"]
    assert SessionManager.is_authenticated() and avisos == []


def test_m2_sesion_cerrada_con_peticion_en_vuelo_un_200_se_entrega_tal_cual():
    _login()
    t = Transporte({("PUT", "/a"): (200, {"v": 7})})
    s, d = _sesion(t)
    reg = Registro()
    s.enviar_async("PUT", "/a", None, reg)
    s.cerrar_local()
    _login()
    d.correr()
    s._envios._vaciar()
    assert reg.causas == ["ok"] and reg.resultados[0].datos == {"v": 7}


def test_m2_respuesta_tardia_de_otra_sesion_ok_se_entrega_y_error_es_sesion_invalida():
    _login()
    reloj = Reloj()
    t = Transporte({("PUT", "/a"): (200, {}), ("PUT", "/b"): (409, {"codigo": "x"})})
    s, d = _sesion(t, reloj=reloj, plazo_s=5.0)
    ra, rb, ta, tb = Registro(), Registro(), Registro(), Registro()
    s.enviar_async("PUT", "/a", None, ra, al_tardio=ta)
    s.enviar_async("PUT", "/b", None, rb, al_tardio=tb)
    reloj.t += 5.0
    s._envios._vaciar()
    s.cerrar_local()
    _login()
    d.correr()
    s._envios._vaciar()
    assert ta.causas == ["ok"] and tb.causas == ["sesion_invalida"]


def test_plazo_vencido_entrega_sin_respuesta_y_la_tardia_va_a_al_tardio():
    _login()
    reloj = Reloj()
    s, d = _sesion(Transporte(), reloj=reloj, plazo_s=5.0)
    reg, tardio = Registro(), Registro()
    s.enviar_async("PUT", "/x", None, reg, al_tardio=tardio)
    s._envios._vaciar()
    assert reg.resultados == []
    reloj.t += 5.0
    s._envios._vaciar()
    assert reg.causas == [sb.BACKEND_NO_RESPONDE] and tardio.resultados == []
    assert s._envios.en_vuelo() == 0
    d.correr()
    s._envios._vaciar()
    assert reg.causas == [sb.BACKEND_NO_RESPONDE] and tardio.causas == ["ok"]
    assert tardio.hilos == [threading.main_thread()]


def test_dueno_destruido_con_peticion_en_vuelo_no_cae():
    _login()
    s, d = _sesion()
    dueno = QObject()
    llamados = []
    s.enviar_async("PUT", "/x", None, lambda r: llamados.append(dueno.objectName()), dueno=dueno)
    dueno.deleteLater()
    _procesar()
    d.correr()
    s._envios._vaciar()
    assert llamados == []


def test_cancelar_envios_del_dueno():
    _login()
    s, d = _sesion()
    dueno, otro = QObject(), QObject()
    a, b = Registro(), Registro()
    s.enviar_async("PUT", "/x", None, a, dueno=dueno)
    s.enviar_async("PUT", "/y", None, b, dueno=otro)
    assert s.cancelar_envios(dueno) == 1
    d.correr()
    s._envios._vaciar()
    assert a.resultados == [] and b.causas == ["ok"]


def test_tope_de_peticiones_en_vuelo():
    _login()
    s, d = _sesion()
    regs = [Registro() for _ in range(sb.MAX_ENVIOS_EN_VUELO + 1)]
    lanzadas = [s.enviar_async("GET", f"/r{i}", None, r) for i, r in enumerate(regs)]
    assert lanzadas == [True] * sb.MAX_ENVIOS_EN_VUELO + [False]
    _procesar()
    assert regs[-1].causas == [sb.ERROR_GENERICO]
    d.correr()
    s._envios._vaciar()
    assert all(r.causas == ["ok"] for r in regs[:-1])


def test_enviar_sincrono_sigue_igual():
    _login()
    s = sb.SesionVentana(transporte=Transporte({("PUT", "/x"): (200, {"v": 2})}))
    r = s.enviar("PUT", "/x")
    assert r.ok and r.datos == {"v": 2}


def test_funcion_de_modulo_compatible_con_dobles_de_solo_enviar():
    class Doble:
        def __init__(self):
            self.enviados = []

        def enviar(self, metodo, ruta, cuerpo=None):
            self.enviados.append((metodo, ruta, cuerpo))
            return sb.Resultado("ok", {}, 200)
    doble, reg = Doble(), Registro()
    assert sb.enviar_async(doble, "PUT", "/x", {"a": 1}, reg) is True
    assert reg.causas == ["ok"] and doble.enviados == [("PUT", "/x", {"a": 1})]
    m = MagicMock()
    m.enviar.return_value = sb.Resultado("ok")
    reg2 = Registro()
    sb.enviar_async(m, "GET", "/y", None, reg2)
    assert reg2.causas == ["ok"] and not m.enviar_async.called
    sb.cancelar_envios(Doble(), object())                  # sin cancelar_envios: no falla


# ── piloto: UsuariosController con una SesionVentana real ───────────────────

USUARIOS = {"usuarios": [
    {"nombre": "Ana", "usuario": "ana_admin", "rol": "admin", "activo": True},
    {"nombre": "Tomás", "usuario": "tomas_tec", "rol": "tecnico", "activo": True}],
    "gestionables": ["admin", "tecnico"]}
OPERADORES = {"operadores": [{"id": 2, "nombre": "Marta", "activo": False}]}


def _con_estado(activo_tomas):
    u = {"usuarios": [dict(x) for x in USUARIOS["usuarios"]], "gestionables": USUARIOS["gestionables"]}
    u["usuarios"][1]["activo"] = activo_tomas
    return (200, u)


def _ctrl(respuestas=None, **kw):
    from autoclave.ui_qml.controllers.usuarios_controller import UsuariosController
    _login()
    base = {("GET", "/usuarios"): (200, USUARIOS), ("GET", "/operadores"): (200, OPERADORES)}
    base.update(respuestas or {})
    t = Transporte(base)
    s, d = _sesion(t, **kw)
    c = UsuariosController(sesion=s)
    c.rol, c.usuarioActual = "admin", "ana_admin"
    c.cargar()
    assert c.cargando is True and c.usuarios == []
    d.correr()
    s._envios._vaciar()
    assert c.cargando is False and len(c.usuarios) == 2
    return c, s, d, t


def _activo(c, usuario):
    return next(u["activo"] for u in c.usuarios if u["usuario"] == usuario)


def test_piloto_la_casilla_cambia_antes_de_la_respuesta_y_se_confirma():
    c, s, d, t = _ctrl()
    resueltos = []
    c.cambioResuelto.connect(lambda *a: resueltos.append(a))
    assert c.fijarActivo("tomas_tec", False) is True        # aceptado, en vuelo
    assert _activo(c, "tomas_tec") is False
    assert c.pendientes == {"usuario:tomas_tec": "enviando"}
    d.correr()
    s._envios._vaciar()
    assert c.pendientes == {} and _activo(c, "tomas_tec") is False
    assert resueltos == [("usuario:tomas_tec", True, "")]
    assert ("PUT", "/usuarios/tomas_tec/activo", {"activo": False}) in t.llamadas


def test_piloto_409_revierte_con_mensaje():
    c, s, d, t = _ctrl({("PUT", "/usuarios/tomas_tec/activo"): (409, {"codigo": "rol_sin_permiso"})})
    c.fijarActivo("tomas_tec", False)
    assert _activo(c, "tomas_tec") is False
    d.correr()
    s._envios._vaciar()
    assert _activo(c, "tomas_tec") is True
    assert c.mensaje == "gestion_usuarios.err_rol" and c.mensajeRevertido is True


@pytest.mark.parametrize("leido,final,mensaje", [
    (False, False, ""),                                      # coincide: en silencio
    (True, True, "opciones.err_sin_respuesta"),              # no coincide: revierte
])
def test_piloto_plazo_vencido_relee_y_concilia(leido, final, mensaje):
    reloj = Reloj()
    c, s, d, t = _ctrl(reloj=reloj)
    c.fijarActivo("tomas_tec", False)
    put = d.tareas.pop()                                     # el PUT no vuelve a tiempo
    reloj.t += sb.PLAZO_S
    s._envios._vaciar()
    assert c.pendientes == {"usuario:tomas_tec": "verificando"}
    assert _activo(c, "tomas_tec") is False                  # mientras verifica
    t.respuestas[("GET", "/usuarios")] = _con_estado(leido)
    d.correr()
    s._envios._vaciar()
    assert c.pendientes == {} and _activo(c, "tomas_tec") is final
    assert c.mensaje == mensaje
    threading.Thread(target=put).start()                     # respuesta tardía: solo log


def test_piloto_plazo_vencido_sin_lectura_vuelve_a_lo_confirmado():
    reloj = Reloj()
    c, s, d, t = _ctrl(reloj=reloj)
    c.fijarActivo("tomas_tec", False)
    d.tareas.pop()
    reloj.t += sb.PLAZO_S
    s._envios._vaciar()
    t.respuestas[("GET", "/usuarios")] = ConnectionError("caído")
    d.correr()
    s._envios._vaciar()
    assert _activo(c, "tomas_tec") is True and c.mensaje == "opciones.cambio_sin_confirmar"
    assert c.mensajeRevertido is False


def test_m1_put_tardio_recarga_y_corrige_la_reversion():
    reloj = Reloj()
    c, s, d, t = _ctrl(reloj=reloj)
    c.fijarActivo("tomas_tec", False)
    put = d.tareas.pop()                                     # el PUT tarda más de PLAZO_S
    reloj.t += sb.PLAZO_S
    s._envios._vaciar()
    t.respuestas[("GET", "/usuarios")] = _con_estado(True)   # el GET llega antes de que se aplique
    d.correr()
    s._envios._vaciar()
    assert _activo(c, "tomas_tec") is True                   # revertido (lectura vieja)
    t.respuestas[("PUT", "/usuarios/tomas_tec/activo")] = (200, {"ok": True})
    t.respuestas[("GET", "/usuarios")] = _con_estado(False)  # ya aplicado
    h = threading.Thread(target=put)
    h.start()
    h.join(5)
    s._envios._vaciar()                                      # la tardía llama a cargar()
    d.correr()
    s._envios._vaciar()
    assert _activo(c, "tomas_tec") is False


def test_m3_sin_confirmar_recarga_la_lista():
    reloj = Reloj()
    c, s, d, t = _ctrl(reloj=reloj)
    c.fijarActivo("tomas_tec", False)
    d.tareas.pop()
    reloj.t += sb.PLAZO_S
    s._envios._vaciar()
    t.respuestas[("GET", "/usuarios")] = ConnectionError("caído")
    d.correr()
    s._envios._vaciar()
    assert c.mensaje == "opciones.cambio_sin_confirmar"
    t.respuestas[("GET", "/usuarios")] = _con_estado(False)  # el equipo volvió
    n = len([x for x in t.llamadas if x[0] == "GET"])
    d.correr()
    s._envios._vaciar()
    assert len([x for x in t.llamadas if x[0] == "GET"]) > n   # cargar() lanzó GET
    assert _activo(c, "tomas_tec") is False


def test_b1_codigos_de_usuarios_solo_en_sus_rutas():
    from autoclave.ui_qml.sesion_backend import codigos_conocidos
    for cod in ("ultimo_ingeniero", "autodesactivacion", "cuenta_sistema", "operador_existe"):
        assert cod in codigos_conocidos("/usuarios/x/activo")
        assert cod in codigos_conocidos("/operadores")
        assert cod not in codigos_conocidos("/cycle/start")
        assert cod not in codigos_conocidos()
        assert sb.interpretar(409, {"codigo": cod}, "/usuarios/x/activo").causa == cod


def test_piloto_dos_toques_rapidos_llegan_en_orden():
    c, s, d, t = _ctrl()
    c.fijarActivoOperador(2, True)
    c.fijarActivoOperador(2, False)
    c.fijarActivoOperador(2, True)
    assert [x for x in t.llamadas if x[0] == "PUT"] == []
    d.correr()
    s._envios._vaciar()
    d.correr()
    s._envios._vaciar()
    puts = [x[2]["activo"] for x in t.llamadas if x[0] == "PUT"]
    assert puts == [True, True] and c.pendientes == {}
    assert c.operadores[0]["activo"] is True


def test_piloto_accion_b_bloquea_hasta_el_200_y_recarga():
    c, s, d, t = _ctrl()
    assert c.agregarOperador("Luz") is True
    assert c.pendientes == {"nuevo_operador": "enviando"}
    assert c.agregarOperador("Otra") is False                # bloqueada mientras tanto
    assert len(c.operadores) == 1
    t.respuestas[("GET", "/operadores")] = (200, {"operadores": OPERADORES["operadores"]
                                                  + [{"id": 3, "nombre": "Luz", "activo": True}]})
    d.correr()
    s._envios._vaciar()                                      # 200 -> recarga
    assert c.pendientes == {} and c.cargando is True
    d.correr()
    s._envios._vaciar()
    assert [o["nombre"] for o in c.operadores] == ["Marta", "Luz"]


def test_piloto_lectura_vieja_no_pisa_un_cambio():
    c, s, d, t = _ctrl()
    c.cargar()                                               # GET con tomas activo
    c.fijarActivo("tomas_tec", False)
    tareas = list(d.tareas)
    d.tareas = tareas[2:]
    d.tareas_get = tareas[:2]
    d.correr()                                               # vuelve primero el PUT
    s._envios._vaciar()
    d.tareas = d.tareas_get
    d.correr()                                               # luego el GET viejo
    s._envios._vaciar()
    assert _activo(c, "tomas_tec") is False


def test_piloto_controlador_destruido_con_peticion_en_vuelo():
    c, s, d, t = _ctrl()
    c.fijarActivo("tomas_tec", False)
    c.deleteLater()
    _procesar()
    d.correr()
    s._envios._vaciar()                                      # no cae ni entrega
    assert s._envios.en_vuelo() == 0
