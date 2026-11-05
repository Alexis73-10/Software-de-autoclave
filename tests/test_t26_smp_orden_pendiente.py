"""Tanda 26 (SMP): orden pendiente por salida sostenida en el modo prueba y
relectura rápida del caché de /status mientras haya una orden pendiente.

Pruebas del prompt (§3.3): ON y un toque antes del /status -> se envía OFF;
un ON rechazado no queda pendiente; vencida la ventana manda el /status; con
el modo prueba sin confirmar, apagar sigue disponible."""

import os
import sys
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import Resultado

pytestmark = pytest.mark.req("HAZ-SMP-01")

_CANALES = {
    "DI": [],
    "DO": [{"name": "vapor_camara", "estado_key": "vapor_camara", "i18n": "io.do.vapor_camara",
            "id": "DO 04", "momentanea": False, "bloqueada": False},
           {"name": "bomba_vacio", "estado_key": "bomba_vacio", "i18n": "io.do.bomba_vacio",
            "id": "DO 19", "momentanea": True, "bloqueada": False}],
    "temperature": [], "pressure": [],
}


def _status(vapor=0, prueba=True):
    return {"machine_state": "PREPARADO", "estado_modulo_es": "ok", "card_connected": True,
            "test_mode_active": prueba,
            "sensors": {"digital_inputs": {}, "digital_outputs": {"vapor_camara": vapor,
                                                                  "bomba_vacio": 0},
                        "temperature": {}, "pressure": {}, "adc": {}}}


class _Sesion:
    def __init__(self):
        self.enviados = []
        self.patch = lambda cuerpo: Resultado("ok", {"ok": True, "value": cuerpo["value"]}, 200)

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "PATCH":
            return self.patch(cuerpo)
        return Resultado("error_generico")


class _Fuente:
    """Caché de /status con instante de envío controlado: t_envio fijo = un
    /status pedido ANTES de la orden (no la refleja)."""
    def __init__(self, status):
        self.status, self.t_envio = status, None

    def status_vigente(self):
        t = time.monotonic() if self.t_envio is None else self.t_envio
        return self.status, True, 0.1, t


@pytest.fixture
def ctrl():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s, f = _Sesion(), _Fuente(_status())
    c = EntradasSalidasController(sesion=s, fuente_estado=f)
    c._al_canales(Resultado("ok", _CANALES, 200))
    c.actualizar()
    assert c.modoPrueba is True and c.salidasHabilitadas is True
    c.sesion, c.fuente = s, f
    yield c
    c._timer_pendientes.stop()


def _vapor(c):
    return next(s for s in c.salidas if s["name"] == "vapor_camara")


def _patches(s):
    return [(r, b) for m, r, b in s.enviados if m == "PATCH"]


def _status_viejo(c):
    """El caché sigue con un /status pedido antes de la última orden."""
    c.fuente.t_envio = time.monotonic() - 10.0


def test_on_y_toque_antes_del_status_envia_off(ctrl):
    c = ctrl
    _status_viejo(c)
    assert c.alternar("vapor_camara") is True
    assert _patches(c.sesion)[-1] == ("/io/test/output/vapor_camara", {"value": True})
    c.actualizar()                               # /status viejo: sigue en OFF
    v = _vapor(c)
    assert v["encendida"] is False
    assert v["pendiente"] is True and v["apagar"] is True and v["claveBoton"] == "io.ui.apagar"
    assert c.ordenPendiente is True
    # segundo toque antes de que llegue el /status: el inverso de lo ORDENADO
    assert c.alternar("vapor_camara") is True
    assert _patches(c.sesion)[-1] == ("/io/test/output/vapor_camara", {"value": False})
    v = _vapor(c)
    assert v["pendiente"] is True and v["apagar"] is False and v["claveBoton"] == "io.ui.activar"


def test_status_nuevo_que_refleja_la_orden_la_resuelve(ctrl):
    c = ctrl
    _status_viejo(c)
    c.alternar("vapor_camara")
    # /status nuevo todavía sin el cambio (el lazo no ha publicado): sigue pendiente
    c.fuente.t_envio = None
    c.actualizar()
    assert _vapor(c)["pendiente"] is True
    c.fuente.status = _status(vapor=1)
    c.actualizar()
    v = _vapor(c)
    assert v["pendiente"] is False and v["encendida"] is True and v["apagar"] is True
    assert c.ordenPendiente is False
    assert not c._timer_pendientes.isActive()


def test_on_rechazado_no_queda_pendiente(ctrl):
    c = ctrl
    c.sesion.patch = lambda cuerpo: Resultado("salida_prueba_puerta_abierta", {}, 409)
    assert c.alternar("vapor_camara") is False
    assert _vapor(c)["pendiente"] is False and c.ordenPendiente is False
    assert c.mensaje                              # muestra el motivo
    # el siguiente toque vuelve a pedir ON (lo leído sigue en OFF)
    c.alternar("vapor_camara")
    assert _patches(c.sesion)[-1][1] == {"value": True}


def test_rechazo_no_borra_la_orden_aceptada_anterior(ctrl):
    c = ctrl
    _status_viejo(c)
    c.alternar("vapor_camara")                   # ON aceptado
    c.sesion.patch = lambda cuerpo: Resultado("paro_emergencia", {}, 409)
    assert c.alternar("vapor_camara") is False   # OFF rechazado
    v = _vapor(c)
    assert v["pendiente"] is True and v["apagar"] is True


def test_ventana_vencida_manda_el_status(ctrl, monkeypatch):
    from autoclave.ui_qml.controllers import entradas_salidas_controller as m
    c = ctrl
    _status_viejo(c)
    c.alternar("vapor_camara")
    assert _vapor(c)["pendiente"] is True
    base = time.monotonic()
    monkeypatch.setattr(m.time, "monotonic", lambda: base + m.PLAZO_ORDEN_PENDIENTE_S + 0.5)
    c.actualizar()                               # con el /status todavía viejo
    v = _vapor(c)
    assert v["pendiente"] is False and v["encendida"] is False and v["apagar"] is False
    assert c.ordenPendiente is False


def test_ventana_vencida_con_status_nuevo_distinto(ctrl, monkeypatch):
    """P. ej. ESG-02 cortó la salida: vencida la ventana, se ve lo leído."""
    from autoclave.ui_qml.controllers import entradas_salidas_controller as m
    c = ctrl
    c.alternar("vapor_camara")
    base = time.monotonic()
    monkeypatch.setattr(m.time, "monotonic", lambda: base + m.PLAZO_ORDEN_PENDIENTE_S + 0.5)
    c.fuente.t_envio = base + m.PLAZO_ORDEN_PENDIENTE_S + 0.4
    c.actualizar()
    v = _vapor(c)
    assert v["pendiente"] is False and v["encendida"] is False


def test_prueba_sin_confirmar_apagar_sigue_disponible(ctrl):
    c = ctrl
    _status_viejo(c)
    c.alternar("vapor_camara")                   # ON aceptado y pendiente
    # la salida del modo prueba queda sin confirmar: salidas deshabilitadas
    c._fijar_prueba(True, sin_salida=True)
    assert c.salidasHabilitadas is False and c.pruebaSinConfirmar is True
    v = _vapor(c)
    assert v["pendiente"] is True and v["apagar"] is True   # la pantalla ofrece apagar
    n = len(_patches(c.sesion))
    assert c.alternar("vapor_camara") is True
    assert _patches(c.sesion)[n:] == [("/io/test/output/vapor_camara", {"value": False})]
    # encender, en cambio, no sale sin el modo prueba confirmado
    n = len(_patches(c.sesion))
    assert c.alternar("vapor_camara") is False
    assert len(_patches(c.sesion)) == n


def test_apagar_con_modo_prueba_inactivo_cuenta_como_hecho(ctrl):
    c = ctrl
    c.sesion.patch = lambda cuerpo: Resultado("modo_prueba_inactivo", {}, 409)
    c._pendientes["vapor_camara"] = (True, time.monotonic())
    assert c.alternar("vapor_camara") is True
    assert _vapor(c)["apagar"] is False


def test_atrapamiento_toma_el_valor_respondido(ctrl):
    c = ctrl
    c.sesion.patch = lambda cuerpo: Resultado(
        "ok", {"ok": True, "value": False, "invertida": True}, 200)
    _status_viejo(c)
    c.alternar("vapor_camara")
    v = _vapor(c)
    assert v["pendiente"] is True and v["apagar"] is False


def test_momentaneas_sin_cambio(ctrl):
    c = ctrl
    assert c.accionar("bomba_vacio", True, True) is True
    assert _patches(c.sesion)[-1] == ("/io/test/output/bomba_vacio",
                                      {"value": True, "momentanea": True})
    b = next(s for s in c.salidas if s["name"] == "bomba_vacio")
    assert b["pendiente"] is False and b["claveBoton"] == "io.ui.mantener"
    assert "bomba_vacio" not in c._pendientes


def test_relectura_cada_200_ms_solo_con_orden_pendiente(ctrl):
    from autoclave.ui_qml.controllers import entradas_salidas_controller as m
    c = ctrl
    assert m.SONDEO_PENDIENTE_MS == 200 and c._timer_pendientes.interval() == 200
    assert not c._timer_pendientes.isActive()
    _status_viejo(c)
    c.alternar("vapor_camara")
    assert c._timer_pendientes.isActive()
    c.fuente.t_envio = None
    c.fuente.status = _status(vapor=1)
    c._timer_pendientes.timeout.emit()           # el tick de 200 ms relee el caché
    assert _vapor(c)["encendida"] is True and not c._timer_pendientes.isActive()


def test_salida_del_modo_prueba_confirmada_limpia_pendientes(ctrl):
    c = ctrl
    _status_viejo(c)
    c.alternar("vapor_camara")
    c._fijar_prueba(False)
    assert c.ordenPendiente is False and not c._timer_pendientes.isActive()


def test_claves_i18n_nuevas_en_es_y_en():
    import json
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    for idioma in ("es", "en"):
        datos = json.loads((raiz / f"{idioma}.json").read_text(encoding="utf-8"))
        assert datos["io"]["ui"]["orden_pendiente"].strip()


def test_qml_usa_el_armado_del_controlador():
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"
           / "Pantallas" / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    assert "control.alternar(" in qml
    assert "modelData.claveBoton" in qml and "modelData.pendiente" in qml
    assert "modelData.apagar === true" in qml
    # ya no decide el toque con el estado leído
    assert "encendida !== true, false)" not in qml
