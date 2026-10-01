# tests/test_ciclo_controller.py
#
# Puente QObject entre domain/pantalla_ciclo.py y Pantallas/Ciclo.qml. Las
# pruebas alimentan las respuestas REST directamente (aplicar_ciclo /
# aplicar_status / marcar_sin_conexion) con iniciar=False, sin red real.

import sys

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy

from autoclave.ui_qml.controllers.ciclo_controller import CicloController
from autoclave.ui_qml.domain.pantalla_ciclo import SIN_DATO


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _ciclo(temp=134.0, t_ester=3.5, t_secado=15.0):
    return {
        "name": "Bowe & Dick",
        "parameters": {
            "esterilizacion": {
                "temperatura_esterilizacion": {"value": temp},
                "tiempo_esterilizacion": {"value": t_ester},
            },
            "secado": {"tiempo_secado": {"value": t_secado}},
        },
    }


def _status(temp=85.0, pres=100.8):
    return {"sensors": {"temperature": {"camara": temp}, "pressure": {"camara": pres}}}


def _controller():
    return CicloController(iniciar=False)


def test_estado_inicial_sin_datos_y_sin_conexion():
    c = _controller()
    assert c.tempEsterilizacion == SIN_DATO
    assert c.tempCamara == SIN_DATO
    assert c.programa == SIN_DATO
    assert c.conectado is False


def test_aplicar_ciclo_publica_consignas():
    c = _controller()
    c.aplicar_ciclo(_ciclo())
    assert c.programa == "BOWE & DICK"
    assert c.tempEsterilizacion == "134.0"
    assert c.tiempoEsterilizacion == "3.5"
    assert c.tiempoSecado == "15"


def test_cambio_de_consigna_en_backend_se_refleja():
    c = _controller()
    c.aplicar_ciclo(_ciclo(temp=134.0))
    c.aplicar_ciclo(_ciclo(temp=121.0))
    assert c.tempEsterilizacion == "121.0"


def test_aplicar_status_publica_lecturas_y_marca_conectado():
    c = _controller()
    c.aplicar_status(_status())
    assert c.tempCamara == "085.0"
    assert c.presionCamara == "100.8"
    assert c.conectado is True


def test_datos_changed_se_emite_solo_si_algo_cambio():
    c = _controller()
    spy = QSignalSpy(c.datosChanged)
    c.aplicar_status(_status())
    c.aplicar_status(_status())
    assert spy.count() == 1


def test_sin_ciclo_seleccionado_muestra_sin_dato():
    c = _controller()
    c.aplicar_ciclo(_ciclo())
    c.aplicar_ciclo(None)
    assert c.tempEsterilizacion == SIN_DATO
    assert c.programa == SIN_DATO


def test_perdida_de_conexion_congela_valores_y_baja_conectado():
    # §6.4: congelar los valores mostrados y marcarlos como no vigentes
    c = _controller()
    c.aplicar_status(_status())
    c.aplicar_ciclo(_ciclo())
    spy = QSignalSpy(c.conectadoChanged)
    c.marcar_sin_conexion()
    assert c.conectado is False
    assert c.tempCamara == "085.0"
    assert c.tempEsterilizacion == "134.0"
    assert spy.count() == 1


def test_reconexion_vuelve_a_marcar_conectado():
    c = _controller()
    c.aplicar_status(_status())
    c.marcar_sin_conexion()
    c.aplicar_status(_status(temp=90.0))
    assert c.conectado is True
    assert c.tempCamara == "090.0"


# ── transporte REST real contra un servidor HTTP local ───────────────────

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import QEventLoop, QTimer


def _servidor(respuestas):
    """HTTPServer en un hilo; respuestas = {ruta: (codigo, cuerpo_dict)}."""
    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self):
            codigo, cuerpo = respuestas.get(self.path, (404, {"detail": "no"}))
            datos = json.dumps(cuerpo).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _esperar(condicion, ms=3000):
    loop = QEventLoop()
    reloj = QTimer()
    reloj.setInterval(20)
    reloj.timeout.connect(lambda: loop.quit() if condicion() else None)
    reloj.start()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    return condicion()


def test_sondeo_http_lee_status_y_cycle_del_backend():
    srv = _servidor({"/status": (200, _status(temp=120.5)), "/cycle": (200, _ciclo(temp=121.0))})
    try:
        c = CicloController(url_base=f"http://127.0.0.1:{srv.server_port}", intervalo_ms=100)
        assert _esperar(lambda: c.tempCamara == "120.5" and c.tempEsterilizacion == "121.0")
        assert c.conectado is True
    finally:
        srv.shutdown()


def test_sondeo_http_sin_ciclo_seleccionado_404_da_sin_dato_pero_conectado():
    srv = _servidor({"/status": (200, _status())})
    try:
        c = CicloController(url_base=f"http://127.0.0.1:{srv.server_port}", intervalo_ms=100)
        assert _esperar(lambda: c.conectado)
        assert c.tempEsterilizacion == SIN_DATO
    finally:
        srv.shutdown()


def test_sondeo_http_backend_caido_queda_sin_conexion():
    srv = _servidor({})
    puerto = srv.server_port
    srv.shutdown()
    srv.server_close()
    c = CicloController(url_base=f"http://127.0.0.1:{puerto}", intervalo_ms=100)
    c.aplicar_status(_status())          # venía conectado
    assert _esperar(lambda: not c.conectado)
    assert c.tempCamara == "085.0"       # valor congelado
