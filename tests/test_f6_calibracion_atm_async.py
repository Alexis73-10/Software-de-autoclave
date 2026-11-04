# tests/test_f6_calibracion_atm_async.py
#
# FASE 6 (AJUSTES 2026-11-02, paso 2): órdenes de la calibración atmosférica e
# impresiones de Mantenimiento asíncronas y sin optimismo (OperacionCritica).
# Nunca se muestra éxito sin un 200 o una relectura con la fase esperada; una
# orden a la vez; las impresiones no se releen ni se reintentan.

import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from autoclave.ui_qml import sesion_backend as sb  # noqa: E402
from autoclave.ui_qml.operacion_critica import (  # noqa: E402
    CONFIRMADA, RECHAZADA, SIN_CONFIRMAR, VERIFICANDO)

RUTA = "/maintenance/atm-calibration"
OK_MIDIENDO = sb.Resultado("ok", {"estado": "midiendo", "muestras": 1}, 200)
NO_RESPONDE = sb.Resultado(sb.BACKEND_NO_RESPONDE)


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class SesionDoble:
    """enviar_async que guarda los callbacks; la prueba entrega. `_peticion`
    para el sondeo (no se usa: ejecutar no corre nada)."""
    sinConexion = False

    def __init__(self):
        self.generacion = 0
        self.envios = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        self.envios.append({"metodo": metodo, "ruta": ruta, "al_terminar": al_terminar,
                            "al_tardio": al_tardio, "plazo_s": plazo_s})
        return True

    def cancelar_envios(self, dueno):
        pass

    def _peticion(self, *a, **k):
        return lambda: None

    def tratar_rechazo_sesion(self, *a, **k):
        pass

    def de(self, metodo, ruta):
        return [e for e in self.envios if (e["metodo"], e["ruta"]) == (metodo, ruta)]


def _ctrl():
    from autoclave.ui_qml.controllers.calibracion_atm_controller import CalibracionAtmController
    s = SesionDoble()
    c = CalibracionAtmController(sesion=s, ejecutar=lambda t: None)
    res = []
    c.operacionResuelta.connect(lambda *a: res.append(a))
    return c, s, res


def test_orden_200_confirma_con_los_datos_de_la_respuesta():
    c, s, res = _ctrl()
    assert c.iniciar() is True
    envio = s.de("POST", RUTA + "/start")[0]
    assert envio["plazo_s"] == 10.0
    assert c.operacionEnCurso and c.bloqueaNavegacion and c.estadoDe("atm_start") == "enviando"
    assert c.estado == ""                                  # nada cambia antes del 200
    envio["al_terminar"](OK_MIDIENDO)
    assert c.midiendo and c.mensaje == ""
    assert res == [("atm_start", CONFIRMADA, "")] and not c.operacionEnCurso


def test_orden_rechazada_no_cambia_lo_mostrado_y_relee():
    c, s, res = _ctrl()
    c.iniciar()
    s.de("POST", RUTA + "/start")[0]["al_terminar"](sb.Resultado("precondicion", {}, 409))
    assert res == [("atm_start", RECHAZADA, "calibracion_atm.err_precondicion")]
    assert c.mensaje == "calibracion_atm.err_precondicion" and not c.midiendo


@pytest.mark.parametrize("accion,leido,final", [
    ("start", {"estado": "midiendo"}, CONFIRMADA),
    ("start", {"estado": "inactiva"}, SIN_CONFIRMAR),
    ("cancel", {"estado": "abortada", "motivo": "cancelada"}, CONFIRMADA),
    ("cancel", {"estado": "midiendo"}, SIN_CONFIRMAR),
    ("confirm", {"estado": "ok"}, CONFIRMADA),
    ("confirm", {"estado": "por_confirmar"}, SIN_CONFIRMAR),
    ("discard", {"estado": "rechazada", "motivo": "descartada"}, CONFIRMADA),
    ("discard", {"estado": "rechazada", "motivo": "fuera_de_rango"}, SIN_CONFIRMAR),
])
def test_sin_respuesta_relee_y_solo_la_fase_esperada_confirma(accion, leido, final):
    c, s, res = _ctrl()
    slot = {"start": c.iniciar, "cancel": c.cancelar, "confirm": c.confirmar,
            "discard": c.descartar}[accion]
    assert slot() is True
    s.de("POST", f"{RUTA}/{accion}")[0]["al_terminar"](NO_RESPONDE)
    clave = "atm_" + accion
    assert c.estadoDe(clave) == VERIFICANDO and res == []
    s.de("GET", RUTA)[-1]["al_terminar"](sb.Resultado("ok", leido, 200))
    assert res[-1][:2] == (clave, final)
    assert c.estado == leido["estado"]                     # se muestra lo releído


def test_sin_respuesta_y_relectura_fallida_es_sin_confirmar():
    c, s, res = _ctrl()
    c.iniciar()
    s.de("POST", RUTA + "/start")[0]["al_terminar"](NO_RESPONDE)
    s.de("GET", RUTA)[-1]["al_terminar"](NO_RESPONDE)
    assert res == [("atm_start", SIN_CONFIRMAR, "operacion.sin_confirmar")]
    assert c.mensaje == "operacion.sin_confirmar" and c.estado == ""


def test_doble_toque_y_otra_orden_en_vuelo_no_envian():
    c, s, _ = _ctrl()
    assert c.iniciar() is True
    assert c.iniciar() is False and c.cancelar() is False
    assert len([e for e in s.envios if e["metodo"] == "POST"]) == 1


def test_tardio_200_tras_sin_confirmar_avisa_y_solo_relee():
    """MENOR-7: el cuerpo del 200 tardío es viejo: no se aplica con
    _fijar_datos; se relee el estado y solo lo releído se muestra."""
    c, s, res = _ctrl()
    c.iniciar()
    post = s.de("POST", RUTA + "/start")[0]
    post["al_terminar"](NO_RESPONDE)
    s.de("GET", RUTA)[-1]["al_terminar"](sb.Resultado("ok", {"estado": "inactiva"}, 200))
    assert res[-1][1] == SIN_CONFIRMAR
    n = len(s.de("GET", RUTA))
    post["al_tardio"](sb.Resultado("ok", {"estado": "ok"}, 200))
    assert res[-1] == ("atm_start", CONFIRMADA, "operacion.confirmada_tarde")
    assert c.estado == "inactiva"                          # no aplica los datos viejos
    nuevas = s.de("GET", RUTA)[n:]
    assert nuevas                                          # relee
    for e in nuevas:
        e["al_terminar"](OK_MIDIENDO)
    assert c.midiendo                                      # lo releído sí se muestra


def test_tardio_con_otra_orden_vigente_no_se_anuncia():
    """MAYOR-1: un 200 tardío de start con cancel en vuelo no se confunde."""
    c, s, res = _ctrl()
    c.iniciar()
    post = s.de("POST", RUTA + "/start")[0]
    post["al_terminar"](NO_RESPONDE)
    s.de("GET", RUTA)[-1]["al_terminar"](NO_RESPONDE)
    assert c.cancelar() is True
    post["al_tardio"](OK_MIDIENDO)
    assert [x[1] for x in res] == [SIN_CONFIRMAR] and c.estadoDe("atm_cancel") == "enviando"


def test_sondeo_durante_la_orden_no_pisa_lo_mostrado():
    c, s, _ = _ctrl()
    c.iniciar()
    gen = c._gen
    c._al_recibir(gen, sb.Resultado("ok", {"estado": "inactiva"}, 200), "t")
    assert c.estado == ""                                  # en vuelo: se descarta
    s.de("POST", RUTA + "/start")[0]["al_terminar"](OK_MIDIENDO)
    c._al_recibir(gen, sb.Resultado("ok", {"estado": "inactiva"}, 200), "t")
    assert c.midiendo                                      # generación vieja: se descarta


# ── impresiones ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("slot,ruta,clave", [
    ("imprimirPrueba", "/printer/test-page", "imprimir_prueba"),
    ("imprimirGanancias", "/maintenance/print/calibration", "imprimir_ganancias"),
])
def test_impresion_200(slot, ruta, clave):
    c, s, res = _ctrl()
    assert getattr(c, slot)() is True
    # MENOR-8: la impresión en vuelo bloquea la navegación (como mucho su plazo)
    assert s.de("POST", ruta)[0]["plazo_s"] == 15.0 and c.bloqueaNavegacion
    s.de("POST", ruta)[0]["al_terminar"](sb.Resultado("ok", {}, 200))
    assert res == [(clave, CONFIRMADA, "calibracion_atm.impreso")]
    assert c.mensaje == "calibracion_atm.impreso" and not c.bloqueaNavegacion


@pytest.mark.parametrize("r,msg", [
    (sb.Resultado("error_generico", {}, 503), "calibracion_atm.err_impresora"),
    (sb.Resultado("estado_no_permitido", {}, 409), "calibracion_atm.err_impresion_ciclo"),
])
def test_impresion_rechazada(r, msg):
    c, s, res = _ctrl()
    c.imprimirGanancias()
    s.envios[0]["al_terminar"](r)
    assert res == [("imprimir_ganancias", RECHAZADA, msg)] and c.mensaje == msg


def test_impresion_sin_respuesta_sin_relectura_ni_reintento():
    c, s, res = _ctrl()
    c.imprimirPrueba()
    s.envios[0]["al_terminar"](NO_RESPONDE)
    assert res == [("imprimir_prueba", SIN_CONFIRMAR, "operacion.sin_confirmar")]
    assert [(e["metodo"], e["ruta"]) for e in s.envios] == [("POST", "/printer/test-page")]
    s.envios[0]["al_tardio"](sb.Resultado("ok", {}, 200))  # tardío: se informa, no se repite
    assert res[-1] == ("imprimir_prueba", CONFIRMADA, "calibracion_atm.impreso")
    assert len(s.envios) == 1


def test_impresion_doble_toque_no_envia_dos_veces():
    c, s, _ = _ctrl()
    assert c.imprimirPrueba() is True
    assert c.imprimirPrueba() is False
    assert len(s.envios) == 1


def test_impresion_en_vuelo_bloquea_la_navegacion_de_mantenimiento():
    """MENOR-8: salir de Mantenimiento con la impresión en vuelo crearía otra
    instancia que dejaría imprimir otra vez; se bloquea la navegación (el
    registro de proceso y la propiedad de la pantalla)."""
    from pathlib import Path
    from autoclave.ui_qml import operacion_critica as oc
    c, s, _ = _ctrl()
    c.imprimirPrueba()
    assert oc.registro.bloqueaNavegacion
    s.envios[0]["al_terminar"](sb.Resultado("ok", {}, 200))
    assert not c.bloqueaNavegacion
    qml = (Path(__file__).resolve().parents[1]
           / "src/autoclave/ui_qml/qml/Pantallas/OpcionesMantenimiento.qml").read_text(encoding="utf-8")
    i = qml.index("readonly property bool navegacionBloqueada")
    assert "|| impresiones.bloqueaNavegacion" in qml[i:i + 300]


def test_h5_relecturas_tardias_cruzadas_la_vieja_no_pisa_a_la_reciente():
    """H5 (3.er ciclo de corrección): dos 200 tardíos (start y luego cancel)
    lanzan dos relecturas; si la del primero llega después, se descarta."""
    c, s, res = _ctrl()
    c.iniciar()
    p_start = s.de("POST", RUTA + "/start")[0]
    p_start["al_terminar"](NO_RESPONDE)
    s.de("GET", RUTA)[-1]["al_terminar"](NO_RESPONDE)
    assert c.cancelar() is True
    p_cancel = s.de("POST", RUTA + "/cancel")[0]
    p_cancel["al_terminar"](NO_RESPONDE)
    s.de("GET", RUTA)[-1]["al_terminar"](NO_RESPONDE)
    assert [x[1] for x in res] == [SIN_CONFIRMAR, SIN_CONFIRMAR]

    n = len(s.de("GET", RUTA))
    p_start["al_tardio"](OK_MIDIENDO)
    r1 = s.de("GET", RUTA)[n]                  # relectura del 200 tardío de start
    n = len(s.de("GET", RUTA))
    p_cancel["al_tardio"](sb.Resultado("ok", {"estado": "abortada"}, 200))
    r2 = s.de("GET", RUTA)[n]                  # relectura del 200 tardío de cancel
    r2["al_terminar"](sb.Resultado("ok", {"estado": "abortada", "motivo": "cancelada"}, 200))
    assert c.estado == "abortada"
    r1["al_terminar"](OK_MIDIENDO)             # la vieja llega después: se descarta
    assert c.estado == "abortada" and not c.midiendo


def test_h5_orden_nueva_invalida_la_relectura_tardia_en_vuelo():
    c, s, _ = _ctrl()
    c.iniciar()
    post = s.de("POST", RUTA + "/start")[0]
    post["al_terminar"](NO_RESPONDE)
    s.de("GET", RUTA)[-1]["al_terminar"](NO_RESPONDE)
    n = len(s.de("GET", RUTA))
    post["al_tardio"](OK_MIDIENDO)
    r1 = s.de("GET", RUTA)[n]
    assert c.cancelar() is True
    s.de("POST", RUTA + "/cancel")[0]["al_terminar"](
        sb.Resultado("ok", {"estado": "abortada", "motivo": "cancelada"}, 200))
    r1["al_terminar"](OK_MIDIENDO)             # anterior a la orden: no la pisa
    assert c.estado == "abortada"
