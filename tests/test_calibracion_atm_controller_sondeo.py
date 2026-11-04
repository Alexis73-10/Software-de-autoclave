"""Calibración atmosférica (O2f): el sondeo de 1 s va en un hilo de trabajo, no
en el de la GUI, y datosChanged solo se emite si el estado cambió
(AJUSTES 2026-11-02). Las órdenes van asíncronas desde la FASE 6
(tests/test_f6_calibracion_atm_async.py); este doble solo tiene `enviar`, así
que se resuelven en el acto."""

import os
import sys
import threading
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

RUTA = "/maintenance/atm-calibration"


def _estado(estado="inactiva", muestras=0):
    return {"estado": estado, "muestras": muestras, "muestras_total": 24,
            "transcurrido_s": 0.0, "duracion_s": 120.0, "condiciones": {}}


class _Sesion:
    """Doble de SesionVentana: `_peticion` (lo que corre en el hilo del
    sondeo), `enviar` (órdenes síncronas) y `tratar_rechazo_sesion`."""
    sinConexion = False

    def __init__(self):
        self.respuestas = {("GET", RUTA): Resultado("ok", _estado(), 200)}
        self.enviados = []
        self.hilos = []
        self.rechazos = []      # (causa, hilo) de tratar_rechazo_sesion

    def _responder(self, metodo, ruta):
        self.enviados.append((metodo, ruta))
        self.hilos.append(threading.current_thread())
        return self.respuestas.get((metodo, ruta)) or Resultado("error_generico")

    def _peticion(self, metodo, ruta, cuerpo=None, token=None, plazo=None):
        assert token == "TOK"
        return lambda: self._responder(metodo, ruta)

    def enviar(self, metodo, ruta, cuerpo=None):
        return self._responder(metodo, ruta)

    def tratar_rechazo_sesion(self, r, metodo, ruta, usuario=""):
        self.rechazos.append((r.causa, threading.current_thread()))


@pytest.fixture(autouse=True)
def _con_sesion(monkeypatch):
    from autoclave.cliente.session_manager import SessionManager
    monkeypatch.setattr(SessionManager, "_current_user",
                        {"nombre": "T", "usuario": "t", "rol": "tecnico"})
    monkeypatch.setattr(SessionManager, "_token", "TOK")


class _Diferido:
    """Ejecutor que guarda las tareas para correrlas cuando la prueba quiera."""
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self):
        t, self.tareas = self.tareas, []
        for x in t:
            x()


def _ctrl(ejecutar=lambda t: t()):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.calibracion_atm_controller import CalibracionAtmController
    s = _Sesion()
    c = CalibracionAtmController(sesion=s, ejecutar=ejecutar)
    emitidas = []
    c.datosChanged.connect(lambda: emitidas.append(c.estado))
    return c, s, emitidas


def test_el_sondeo_corre_fuera_del_hilo_de_la_gui():
    from PySide6.QtCore import QCoreApplication
    c, s, emitidas = _ctrl(ejecutar=lambda t: threading.Thread(target=t, daemon=True).start())
    c.cargar()
    app = QCoreApplication.instance()
    for _ in range(200):
        app.processEvents()
        if emitidas:
            break
        threading.Event().wait(0.01)
    assert emitidas == ["inactiva"]
    assert s.hilos and all(h is not threading.main_thread() for h in s.hilos)


def test_sin_cambios_no_emite_y_con_cambios_si():
    c, s, emitidas = _ctrl()
    c.cargar()
    assert emitidas == ["inactiva"]
    c.cargar()
    c.cargar()
    assert emitidas == ["inactiva"]
    s.respuestas[("GET", RUTA)] = Resultado("ok", _estado("midiendo", 3), 200)
    c.cargar()
    assert emitidas == ["inactiva", "midiendo"] and c.midiendo is True


def test_sin_respuesta_conserva_lo_ultimo_sin_emitir():
    c, s, emitidas = _ctrl()
    c.cargar()
    s.respuestas[("GET", RUTA)] = Resultado(BACKEND_NO_RESPONDE)
    c.cargar()
    assert c.estado == "inactiva" and emitidas == ["inactiva"]


def test_un_sondeo_en_vuelo_no_pisa_la_orden_confirmada():
    diferido = _Diferido()
    c, s, emitidas = _ctrl(ejecutar=diferido)
    c.cargar()                                   # en vuelo, aún con "inactiva"
    s.respuestas[("POST", RUTA + "/start")] = Resultado("ok", _estado("midiendo", 1), 200)
    assert c.iniciar() is True and c.midiendo is True
    diferido.correr()                            # llega la respuesta vieja: se descarta
    assert c.midiendo is True and emitidas == ["midiendo"]


def test_un_solo_get_en_vuelo_y_el_pedido_intermedio_se_repite():
    diferido = _Diferido()
    c, s, _ = _ctrl(ejecutar=diferido)
    c.activar()                                  # sondeo activo (temporizador en marcha)
    c.cargar()
    assert len(diferido.tareas) == 1
    diferido.correr()                            # al llegar, se lanza el pedido pendiente
    assert len(diferido.tareas) == 1
    diferido.correr()
    assert [e for e in s.enviados if e == ("GET", RUTA)] == [("GET", RUTA)] * 2
    c.desactivar()


def test_tras_desactivar_el_pendiente_no_se_relanza():
    diferido = _Diferido()
    c, s, _ = _ctrl(ejecutar=diferido)
    c.activar()
    c.cargar()                                   # queda pendiente
    c.desactivar()
    diferido.correr()                            # llega la respuesta en vuelo
    assert diferido.tareas == []
    assert [e for e in s.enviados if e == ("GET", RUTA)] == [("GET", RUTA)]


def test_sin_token_o_sin_conexion_no_sale_a_la_red(monkeypatch):
    from autoclave.cliente.session_manager import SessionManager
    diferido = _Diferido()
    c, s, _ = _ctrl(ejecutar=diferido)
    s.sinConexion = True
    c.cargar()
    s.sinConexion = False
    monkeypatch.setattr(SessionManager, "_token", None)
    c.cargar()
    assert diferido.tareas == [] and s.enviados == []


@pytest.mark.parametrize("causa", ["sesion_invalida", "usuario_bloqueado"])
def test_rechazo_de_sesion_se_trata_en_el_hilo_de_la_gui(causa):
    from PySide6.QtCore import QCoreApplication
    c, s, emitidas = _ctrl(ejecutar=lambda t: threading.Thread(target=t, daemon=True).start())
    s.respuestas[("GET", RUTA)] = Resultado(causa, {"segundos_restantes": 30}, 401)
    c.cargar()
    app = QCoreApplication.instance()
    for _ in range(200):
        app.processEvents()
        if s.rechazos:
            break
        threading.Event().wait(0.01)
    assert [x[0] for x in s.rechazos] == [causa]
    assert s.rechazos[0][1] is threading.main_thread()
    assert s.hilos[0] is not threading.main_thread() and emitidas == []


def _sesion_real(estado_http, codigo):
    from autoclave.ui_qml.sesion_backend import SesionVentana
    llamadas = []

    def transporte(metodo, ruta, cuerpo, token, plazo):
        llamadas.append(threading.current_thread())
        return estado_http, {"codigo": codigo, "segundos_restantes": 30}

    sv = SesionVentana(transporte=transporte, ejecutar=lambda t: t())
    cierres = []
    original = sv.cerrar_local

    def cerrar_local(aviso=None):
        cierres.append((aviso, threading.current_thread()))
        original(aviso)

    sv.cerrar_local = cerrar_local
    return sv, llamadas, cierres


@pytest.mark.parametrize("estado_http,codigo,clave", [
    (401, "sesion_invalida", "sesion.sesion_invalida"),
    (429, "usuario_bloqueado", "sesion.usuario_bloqueado"),
])
def test_con_sesion_real_el_hilo_no_cierra_y_la_gui_si(estado_http, codigo, clave):
    """El hilo de trabajo solo hace la petición; cerrar_local corre al volver
    el resultado, en el hilo de la GUI, como hacía `enviar`."""
    from PySide6.QtCore import QCoreApplication
    from autoclave.cliente.session_manager import SessionManager
    from autoclave.ui_qml.controllers.calibracion_atm_controller import CalibracionAtmController
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    sv, llamadas, cierres = _sesion_real(estado_http, codigo)
    diferido = _Diferido()
    c = CalibracionAtmController(sesion=sv, ejecutar=diferido)
    c.cargar()
    hilo = threading.Thread(target=diferido.correr)
    hilo.start()
    hilo.join(5)
    assert llamadas and llamadas[0] is hilo
    assert cierres == []                         # el hilo no cerró nada
    QCoreApplication.instance().processEvents()  # entrega encolada al hilo de la GUI
    assert len(cierres) == 1 and cierres[0][0][0] == clave
    assert cierres[0][1] is threading.main_thread()
    assert SessionManager.token() is None


def test_emitir_tras_destruir_el_controlador_no_falla():
    import gc
    diferido = _Diferido()
    c, s, _ = _ctrl(ejecutar=diferido)
    c.cargar()
    del c
    gc.collect()
    diferido.correr()                            # ni excepción ni emisión sobre un objeto muerto


def test_espera_lenta_solo_se_registra_en_el_hilo_principal(caplog):
    import logging
    from autoclave.ui_qml.sesion_backend import SesionVentana
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)

    def lento(metodo, ruta, cuerpo, token, plazo):
        time.sleep(0.15)
        return 200, {}

    sv = SesionVentana(transporte=lento, ejecutar=lambda t: t())
    with caplog.at_level(logging.WARNING, logger="autoclave.ui_qml.sesion_backend"):
        h = threading.Thread(target=lambda: sv._llamar_con_plazo("GET", RUTA, None, "TOK"))
        h.start()
        h.join(5)
        assert not [r for r in caplog.records if "Espera lenta" in r.getMessage()]
        sv._llamar_con_plazo("GET", RUTA, None, "TOK")
        assert [r for r in caplog.records if "Espera lenta" in r.getMessage()]


def test_la_orden_sigue_sincrona_y_confirmada():
    c, s, _ = _ctrl(ejecutar=lambda t: None)    # el sondeo nunca responde
    s.respuestas[("POST", RUTA + "/cancel")] = Resultado("ok", _estado("abortada"), 200)
    assert c.cancelar() is True and c.estado == "abortada"
    assert s.hilos[-1] is threading.main_thread()


# ── lector del caché de UIServiceBackend ────────────────────────────────────

def test_status_vigente_del_servicio(monkeypatch):
    from autoclave.cliente import ui_service_backend as m

    class _Backend:
        def get_status(self):
            return {"machine_state": "PREPARADO"}

        def get_config(self):
            return {}

        def get_cycle(self):
            return {}

    anterior = m.servicio_activo()
    try:
        svc = m.UIServiceBackend.__new__(m.UIServiceBackend)
        svc.backend, svc._lock = _Backend(), threading.Lock()
        svc._cache, svc._config, svc._cycle, svc.connected = {}, {}, {}, False
        svc._t_status = svc._t_envio_status = None
        assert svc.status_vigente() == ({}, False, None, None)
        antes = time.monotonic()
        svc._fetch_status()
        st, conectado, edad, t_envio = svc.status_vigente()
        assert st == {"machine_state": "PREPARADO"} and conectado is True and 0 <= edad < 1
        assert antes <= t_envio <= time.monotonic()
    finally:
        m.instalar_servicio(anterior)


def test_stop_quita_el_servicio_activo_solo_si_es_el_suyo():
    from autoclave.cliente import ui_service_backend as m

    class _Backend:
        def get_status(self):
            return {}

        def get_config(self):
            return {}

        def get_cycle(self):
            return {}

    anterior = m.servicio_activo()
    try:
        a = m.UIServiceBackend(_Backend())
        b = m.UIServiceBackend(_Backend())
        assert m.servicio_activo() is b
        a.stop()                                 # no es el activo: no lo quita
        assert m.servicio_activo() is b
        b.stop()
        assert m.servicio_activo() is None
    finally:
        m.instalar_servicio(anterior)
