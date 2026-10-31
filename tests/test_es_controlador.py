"""OPCIONES > Entradas / Salidas: controlador (lectura, modo prueba, calibracion)."""

import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

_CANALES = {
    "DI": [{"name": "paro_emergencia", "estado_key": "paro_emergencia",
            "i18n": "io.di.paro_emergencia", "id": "DI 11"}],
    "DO": [{"name": "vapor_camara", "estado_key": "vapor_camara", "i18n": "io.do.vapor_camara",
            "id": "DO 04", "momentanea": False, "bloqueada": False},
           {"name": "bomba_vacio", "estado_key": "bomba_vacio", "i18n": "io.do.bomba_vacio",
            "id": "DO 19", "momentanea": True, "bloqueada": False}],
    "temperature": [{"name": "temp_camara", "estado_key": "temp_camara",
                     "i18n": "io.ai.temp_camara", "id": "AI 01", "raw_index": 0}],
    "pressure": [{"name": "pres_camara", "estado_key": "pres_camara",
                  "i18n": "io.ai.pres_camara", "id": "AI 09", "raw_index": 8}],
}
_STATUS = {"machine_state": "PREPARADO", "estado_modulo_es": "ok", "card_connected": True,
           "test_mode_active": False,
           "sensors": {"digital_inputs": {"paro_emergencia": 1},
                       "digital_outputs": {"vapor_camara": 0, "bomba_vacio": 1},
                       "temperature": {"camara": 25.5}, "pressure": {"camara": 101.0},
                       "adc": {"temp_camara": 2000, "pres_camara": 2500}}}


class _Sesion:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        r = self.respuestas.get((metodo, ruta))
        return r() if callable(r) else (r or Resultado("error_generico"))


def _ok(datos=None):
    return Resultado("ok", datos or {}, 200)


def _ctrl(respuestas):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = _Sesion(respuestas)
    return EntradasSalidasController(sesion=s), s


def _con_datos(extra=None):
    resp = {("GET", "/io/channels"): _ok(_CANALES), ("GET", "/status"): _ok(_STATUS)}
    resp.update(extra or {})
    c, s = _ctrl(resp)
    c.cargarCanales()
    c.actualizar()
    return c, s


def test_lista_de_canales_y_estados():
    c, _ = _con_datos()
    assert [e["name"] for e in c.entradas] == ["paro_emergencia"]
    assert c.entradas[0]["activo"] is True
    assert [s["name"] for s in c.salidas] == ["vapor_camara", "bomba_vacio"]
    assert c.salidas[1]["encendida"] is True and c.salidas[1]["momentanea"] is True
    assert c.temperatura[0]["valor"] == 25.5 and c.temperatura[0]["adc"] == 2000
    assert c.presion[0]["valor"] == 101.0
    assert c.enlace is True


def test_sin_respuesta_todo_pasa_a_sin_datos():
    c, s = _con_datos()
    s.respuestas[("GET", "/status")] = Resultado(BACKEND_NO_RESPONDE)
    c.actualizar()
    assert c.entradas[0]["activo"] is None
    assert c.salidas[0]["encendida"] is None
    assert c.temperatura[0]["valor"] is None and c.temperatura[0]["valido"] is False
    assert c.enlace is False


def test_estado_del_modo_prueba_sale_del_backend():
    c, s = _con_datos()
    assert c.modoPrueba is False
    s.respuestas[("GET", "/status")] = _ok({**_STATUS, "test_mode_active": True})
    c.actualizar()
    assert c.modoPrueba is True


def test_entrar_modo_prueba_ok_y_rechazo_con_motivo():
    c, s = _con_datos({("POST", "/io/test/enter"): _ok({"ok": True})})
    assert c.entrarModoPrueba() is True and c.modoPrueba is True
    c2, _ = _con_datos({("POST", "/io/test/enter"): Resultado(
        "modo_prueba_rechazado", {"detail": "Paro de emergencia activo"}, 409)})
    assert c2.entrarModoPrueba() is False and c2.modoPrueba is False
    assert c2.mensaje == "io.err_rechazado" and "Paro" in c2.detalle


def test_salir_envia_la_causa_y_apaga_la_bandera():
    c, s = _con_datos({("POST", "/io/test/enter"): _ok(), ("POST", "/io/test/exit"): _ok()})
    c.entrarModoPrueba()
    assert c.salirModoPrueba("abandono de la sección") is True
    assert ("POST", "/io/test/exit", {"motivo": "abandono de la sección"}) in s.enviados
    assert c.modoPrueba is False


def test_salir_sin_modo_prueba_no_llama_al_backend():
    c, s = _con_datos()
    assert c.salirModoPrueba("x") is True
    assert not [e for e in s.enviados if e[1] == "/io/test/exit"]


def test_accionar_sostenida_y_momentanea():
    c, s = _con_datos({("PATCH", "/io/test/output/vapor_camara"): _ok(),
                       ("PATCH", "/io/test/output/bomba_vacio"): _ok()})
    assert c.accionar("vapor_camara", True, False) is True
    assert c.accionar("bomba_vacio", True, True) is True
    assert c.accionar("bomba_vacio", False, True) is True
    cuerpos = [e[2] for e in s.enviados if e[0] == "PATCH"]
    assert cuerpos == [{"value": True}, {"value": True, "momentanea": True}, {"value": False}]


def test_accionar_rechazado_muestra_motivo():
    c, _ = _con_datos({("PATCH", "/io/test/output/vapor_camara"): Resultado(
        "fuente_vapor_no_instalada", {"detail": "No la usa este equipo"}, 409)})
    assert c.accionar("vapor_camara", True, False) is False
    assert c.detalle == "No la usa este equipo"


def test_calibracion_carga_calcula_y_aplica_con_origen():
    cal = {"sensor": "pres_camara", "tipo": "pressure", "gain": 1.0, "offset": 0.0,
           "is_poly": False, "last_change": None}
    c, s = _con_datos({("GET", "/calibration/pressure/pres_camara"): _ok(cal),
                       ("PATCH", "/calibration/pressure/pres_camara"): _ok({"ok": True})})
    assert c.cargarCalibracion("presion", "pres_camara") is True
    r = c.calcular(12.0, 9.54, 322.0, 300.0)
    assert r["valido"] is True and r["gain"] == pytest.approx((300 - 9.54) / 310)
    assert c.calcular(5.0, 4.0, 5.0, 6.0)["valido"] is False
    assert c.aplicarPuntos(12.0, 9.54, 322.0, 300.0, "capturada", "escrita", False) is True
    cuerpo = [e[2] for e in s.enviados if e[0] == "PATCH"][0]
    assert cuerpo["origen_lectura"] == {"bajo": "capturada", "alto": "escrita"}
    assert "confirmar_fuera_de_rango" not in cuerpo


def test_calibracion_requiere_confirmacion_y_reenvio():
    cal = {"sensor": "pres_camara", "tipo": "pressure", "gain": 1.0, "offset": 0.0, "is_poly": False}
    c, s = _con_datos({("GET", "/calibration/pressure/pres_camara"): _ok(cal),
                       ("PATCH", "/calibration/pressure/pres_camara"): Resultado(
                           "CALIBRACION_REQUIERE_CONFIRMACION", {"detail": "fuera de rango"}, 409)})
    c.cargarCalibracion("presion", "pres_camara")
    assert c.aplicarPuntos(1.0, 2.0, 5.0, 9.0, "escrita", "escrita", False) is False
    assert c.requiereConfirmacion is True
    s.respuestas[("PATCH", "/calibration/pressure/pres_camara")] = _ok()
    assert c.aplicarPuntos(1.0, 2.0, 5.0, 9.0, "escrita", "escrita", True) is True
    assert [e[2] for e in s.enviados if e[0] == "PATCH"][-1]["confirmar_fuera_de_rango"] is True
    assert c.requiereConfirmacion is False


def test_restaurar_envia_destino():
    cal = {"sensor": "temp_camara", "tipo": "temperature", "gain": 1.1, "offset": 0.2, "is_poly": False}
    c, s = _con_datos({("GET", "/calibration/temperature/temp_camara"): _ok(cal),
                       ("POST", "/calibration/temperature/temp_camara/restaurar"): _ok()})
    c.cargarCalibracion("temperatura", "temp_camara")
    assert c.restaurar("defecto") is True
    assert ("POST", "/calibration/temperature/temp_camara/restaurar",
            {"destino": "defecto"}) in s.enviados


def test_permisos_siguen_rol_y_estado(monkeypatch):
    from autoclave.cliente.session_manager import SessionManager
    c, _ = _con_datos()
    monkeypatch.setattr(SessionManager, "current_user", staticmethod(lambda: {"rol": "tecnico"}))
    assert c.puedeProbar is True and c.puedeCalibrar is True
    monkeypatch.setattr(SessionManager, "current_user", staticmethod(lambda: {"rol": "admin"}))
    assert c.puedeProbar is False and c.puedeCalibrar is False
