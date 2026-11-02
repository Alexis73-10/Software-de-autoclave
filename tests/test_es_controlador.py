"""OPCIONES > Entradas / Salidas: controlador (lectura, modo prueba, calibracion)."""

import os
import sys
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import Resultado

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


class _Fuente:
    """Doble del caché de /status de UIServiceBackend (status_vigente)."""
    def __init__(self, status):
        self.status, self.conectado, self.edad = status, True, 0.1
        self.t_envio = None          # None: «nuevo» (posterior a cualquier orden)

    def status_vigente(self):
        t = time.monotonic() if self.t_envio is None else self.t_envio
        return self.status, self.conectado, self.edad, t


def _ok(datos=None):
    return Resultado("ok", datos or {}, 200)


def _ctrl(respuestas, status=None):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = _Sesion(respuestas)
    f = _Fuente(status if status is not None else _STATUS)
    c = EntradasSalidasController(sesion=s, fuente_estado=f)
    c.fuente = f
    return c, s


def _con_datos(extra=None):
    resp = {("GET", "/io/channels"): _ok(_CANALES)}
    resp.update(extra or {})
    c, s = _ctrl(resp)
    c.cargarCanales()
    c.actualizar()
    return c, s


def _sin_datos(c):
    assert c.entradas[0]["activo"] is None
    assert c.salidas[0]["encendida"] is None
    assert c.temperatura[0]["valor"] is None and c.temperatura[0]["valido"] is False
    assert c.enlace is False and c.presionCamara is None and c.avisosCorte == []


def test_lista_de_canales_y_estados():
    c, _ = _con_datos()
    assert [e["name"] for e in c.entradas] == ["paro_emergencia"]
    assert c.entradas[0]["activo"] is True
    assert [s["name"] for s in c.salidas] == ["vapor_camara", "bomba_vacio"]
    assert c.salidas[1]["encendida"] is True and c.salidas[1]["momentanea"] is True
    assert c.temperatura[0]["valor"] == 25.5 and c.temperatura[0]["adc"] == 2000
    assert c.presion[0]["valor"] == 101.0
    assert c.enlace is True


@pytest.mark.parametrize("caso", ["desconectado", "vacio", "vencido", "sin_edad", "error",
                                  "sin_servicio"])
def test_cache_sin_datos_vigentes_todo_pasa_a_sin_datos(caso, monkeypatch):
    """(d) Igual que un GET /status sin respuesta antes del cambio."""
    c, _ = _con_datos()
    assert c.enlace is True
    if caso == "desconectado":
        c.fuente.conectado = False
    elif caso == "vacio":
        c.fuente.status = {}
    elif caso == "vencido":
        from autoclave.ui_qml.controllers import entradas_salidas_controller as m
        c.fuente.edad = m.ANTIGUEDAD_MAX_S + 0.5
    elif caso == "sin_edad":
        c.fuente.edad = None
    elif caso == "error":
        def falla():
            raise RuntimeError("caché roto")
        c.fuente.status_vigente = falla
    else:
        from autoclave.cliente import ui_service_backend
        monkeypatch.setattr(ui_service_backend, "_servicio_activo", None)
        c._fuente_estado = None
    c.actualizar()
    _sin_datos(c)


def test_sin_fuente_inyectada_usa_el_servicio_del_proceso(monkeypatch):
    from autoclave.cliente import ui_service_backend
    c, _ = _con_datos()
    otra = _Fuente({**_STATUS, "machine_state": "FALLA"})
    monkeypatch.setattr(ui_service_backend, "_servicio_activo", otra)
    c._fuente_estado = None
    c.actualizar()
    assert c.estadoMaquina == "FALLA"


def test_el_sondeo_no_llama_a_enviar_para_status():
    """(a) El tick de 1 s no sale a la red desde el hilo de la GUI."""
    c, s = _con_datos()
    for _ in range(3):
        c.actualizar()
    assert not [e for e in s.enviados if e[1] == "/status"]
    assert [e[1] for e in s.enviados] == ["/io/channels"]


def test_sin_cambios_no_emite_y_con_cambios_si():
    """(b) y (c): cambioDatos solo cuando cambia algo visible."""
    c, _ = _con_datos()
    emitidas = []
    c.cambioDatos.connect(lambda: emitidas.append(1))
    c.fuente.status = {**_STATUS}          # mismo contenido, otro objeto
    c.actualizar()
    c.actualizar()
    assert emitidas == []
    c.fuente.status = {**_STATUS, "sensors": {**_STATUS["sensors"],
                                              "temperature": {"camara": 26.0}}}
    c.actualizar()
    assert emitidas == [1] and c.temperatura[0]["valor"] == 26.0
    c.actualizar()
    assert emitidas == [1]
    c.fuente.conectado = False             # pasar a "Sin datos" también es un cambio
    c.actualizar()
    assert emitidas == [1, 1]
    c.actualizar()
    assert emitidas == [1, 1]


def test_estado_del_modo_prueba_sale_del_backend():
    c, s = _con_datos()
    assert c.modoPrueba is False
    c.fuente.status = {**_STATUS, "test_mode_active": True}
    c.actualizar()
    assert c.modoPrueba is True


# ── /status pedido antes de la orden (corrección tras revisión, 2026-11-02) ──

def _viejo(c, **cambios):
    """El caché trae un /status cuya petición salió ANTES de la última orden."""
    c.fuente.status = {**_STATUS, **cambios}
    c.fuente.t_envio = c._t_orden - 0.05


def _nuevo(c, **cambios):
    c.fuente.status = {**_STATUS, **cambios}
    c.fuente.t_envio = time.monotonic() + 0.001


def test_entrar_sin_parpadeo_por_status_anterior_a_la_orden():
    c, _ = _con_datos({("POST", "/io/test/enter"): _ok()})
    cambios = []
    c.modoPruebaChanged.connect(lambda: cambios.append(c.modoPrueba))
    assert c.entrarModoPrueba() is True
    _viejo(c, test_mode_active=False)       # pedido antes del enter: se ignora
    c.actualizar()
    c.actualizar()
    assert c.modoPrueba is True and cambios == [True]
    _nuevo(c, test_mode_active=True)        # posterior: se acepta, sin cambio
    c.actualizar()
    assert c.modoPrueba is True and cambios == [True]


def test_salir_sin_parpadeo_ni_salidas_viejas():
    c, _ = _con_datos({("POST", "/io/test/enter"): _ok(), ("POST", "/io/test/exit"): _ok()})
    c.fuente.status = {**_STATUS, "test_mode_active": True}
    c.entrarModoPrueba()
    c.actualizar()
    assert c.salirModoPrueba("x") is True
    _viejo(c, test_mode_active=True)
    c.actualizar()
    assert c.modoPrueba is False
    _nuevo(c, test_mode_active=False)
    c.actualizar()
    assert c.modoPrueba is False


def test_status_anterior_a_accionar_conserva_lo_mostrado():
    c, _ = _con_datos({("PATCH", "/io/test/output/vapor_camara"): _ok()})
    assert c.salidas[0]["encendida"] is False
    assert c.accionar("vapor_camara", True, False) is True
    _viejo(c)                                # vapor_camara aún en 0: no es dato nuevo
    _viejo_salidas = c.salidas
    c.actualizar()
    assert c.salidas is _viejo_salidas and c.enlace is True   # no pasa a «Sin datos»
    sensores = {**_STATUS["sensors"],
                "digital_outputs": {"vapor_camara": 1, "bomba_vacio": 1}}
    _nuevo(c, sensors=sensores)              # posterior a la orden: se acepta
    c.actualizar()
    assert c.salidas[0]["encendida"] is True


@pytest.mark.parametrize("caso", ["desconectado", "vencido"])
def test_tras_una_orden_vencido_o_desconectado_sigue_dando_sin_datos(caso):
    from autoclave.ui_qml.controllers import entradas_salidas_controller as m
    c, _ = _con_datos({("PATCH", "/io/test/output/vapor_camara"): _ok()})
    c.accionar("vapor_camara", True, False)
    _viejo(c)
    if caso == "desconectado":
        c.fuente.conectado = False
    else:
        c.fuente.edad = m.ANTIGUEDAD_MAX_S + 0.5
    c.actualizar()
    _sin_datos(c)


def test_fuente_sin_instante_de_envio_se_acepta():
    """Un doble de 3 valores (sin envío) se acepta como antes."""
    class _Tres:
        def status_vigente(self):
            return {**_STATUS, "machine_state": "FALLA"}, True, 0.1
    c, _ = _con_datos({("PATCH", "/io/test/output/vapor_camara"): _ok()})
    c.accionar("vapor_camara", True, False)
    c._fuente_estado = _Tres()
    c.actualizar()
    assert c.estadoMaquina == "FALLA"


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
