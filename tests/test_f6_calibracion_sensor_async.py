"""FASE 6 (AJUSTES 2026-11-02, paso 2): calibración de un sensor asíncrona y
SIN OPTIMISMO (OperacionCritica, claves cal_cargar / cal_puntos /
cal_restaurar).

- Los valores mostrados son los del backend: no cambian hasta el 200 (y
  entonces se releen) o hasta una relectura.
- PATCH sin respuesta: se relee GET /calibration; si ganancia y offset
  coinciden con lo que da calcular() -> confirmada; si no, sin confirmar con
  lo leído a la vista.
- Restaurar sin respuesta: sin confirmar, mostrando lo leído.
- Una operación a la vez; bloquea la navegación (plazo 10 s).
"""

import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from autoclave.ui_qml import sesion_backend as sb  # noqa: E402
from autoclave.ui_qml.operacion_critica import registro  # noqa: E402

NO_RESPONDE = sb.Resultado(sb.BACKEND_NO_RESPONDE)
RUTA = "/calibration/pressure/pres_camara"
CAL = {"sensor": "pres_camara", "tipo": "pressure", "gain": 1.0, "offset": 0.0,
       "is_poly": False, "last_change": None}
# puntos de la prueba: lectura 12 -> 9.54 y 322 -> 300 con la calibración neutra
PUNTOS = (12.0, 9.54, 322.0, 300.0)
G_ESP = (300 - 9.54) / 310
O_ESP = 9.54 - G_ESP * 12.0


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _ok(datos=None):
    return sb.Resultado("ok", datos or {"ok": True}, 200)


class SesionDoble:
    def __init__(self):
        self.generacion = 0
        self.envios = []
        self.sincronos = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        self.envios.append({"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo,
                            "al_terminar": al_terminar, "al_tardio": al_tardio,
                            "plazo_s": plazo_s})
        return True

    def enviar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta, cuerpo))
        return _ok()

    def ultimo(self, metodo, ruta):
        return [e for e in self.envios if e["metodo"] == metodo and e["ruta"] == ruta][-1]

    def contar(self, metodo, ruta):
        return len([e for e in self.envios if e["metodo"] == metodo and e["ruta"] == ruta])

    def responder(self, metodo, ruta, r):
        self.ultimo(metodo, ruta)["al_terminar"](r)


def _ctrl_cargado():
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = SesionDoble()
    c = EntradasSalidasController(sesion=s)
    res = []
    c.operacionResuelta.connect(lambda *a: res.append(a))
    assert c.cargarCalibracion("presion", "pres_camara") is True
    assert c.calibracion == {}                       # sin valores hasta la respuesta
    assert c.estadoDe("cal_cargar") == "enviando"
    s.responder("GET", RUTA, _ok(CAL))
    assert res == [("cal_cargar", "confirmada", "")]
    assert c.calibracion["gain"] == 1.0 and c.calibracion["offset"] == 0.0
    res.clear()
    return c, s, res


def _aplicar(c, confirmar=False):
    return c.aplicarPuntos(*PUNTOS, "capturada", "escrita", confirmar)


def test_cargar_sin_respuesta_no_abre_la_calibracion():
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = SesionDoble()
    c = EntradasSalidasController(sesion=s)
    res = []
    c.operacionResuelta.connect(lambda *a: res.append(a))
    c.cargarCalibracion("presion", "pres_camara")
    s.responder("GET", RUTA, NO_RESPONDE)
    assert res[-1][:2] == ("cal_cargar", "sin_confirmar") and c.calibracion == {}
    assert c.mensaje == res[-1][2] != ""
    assert c.cargarCalibracion("otra_cosa", "x") is False


def test_aplicar_valores_del_backend_hasta_el_200_y_luego_se_releen():
    c, s, res = _ctrl_cargado()
    assert _aplicar(c) is True
    patch = s.ultimo("PATCH", RUTA)
    assert patch["plazo_s"] == 10.0 and patch["cuerpo"]["origen_lectura"] == {
        "bajo": "capturada", "alto": "escrita"}
    assert c.estadoDe("cal_puntos") == "enviando" and c.operacionEnCurso is True
    assert c._op.bloquea() is True and registro.bloqueaNavegacion is True
    assert c.calibracion["gain"] == 1.0              # sin optimismo
    assert s.contar("GET", RUTA) == 1
    s.responder("PATCH", RUTA, _ok({"ok": True, "gain": G_ESP, "offset": O_ESP}))
    assert res == [("cal_puntos", "confirmada", "")]
    assert c.calibracion["gain"] == 1.0              # aún no releído
    assert s.contar("GET", RUTA) == 2                # relectura tras el 200
    s.responder("GET", RUTA, _ok({**CAL, "gain": G_ESP, "offset": O_ESP}))
    assert c.calibracion["gain"] == pytest.approx(G_ESP)
    assert c.operacionEnCurso is False and c._op.bloquea() is False
    assert s.sincronos == []                         # nada síncrono


def test_aplicar_sin_respuesta_relectura_que_coincide_confirma():
    c, s, res = _ctrl_cargado()
    _aplicar(c)
    s.responder("PATCH", RUTA, NO_RESPONDE)
    assert c.estadoDe("cal_puntos") == "verificando"
    assert s.contar("GET", RUTA) == 2
    s.responder("GET", RUTA, _ok({**CAL, "gain": G_ESP + 1e-9, "offset": O_ESP}))
    assert res == [("cal_puntos", "confirmada", "")]
    assert c.calibracion["gain"] == pytest.approx(G_ESP)


def test_aplicar_sin_respuesta_relectura_distinta_queda_sin_confirmar_con_lo_leido():
    c, s, res = _ctrl_cargado()
    _aplicar(c)
    s.responder("PATCH", RUTA, NO_RESPONDE)
    s.responder("GET", RUTA, _ok({**CAL, "gain": 1.0, "offset": 0.0}))
    assert res[-1] == ("cal_puntos", "sin_confirmar", "operacion.sin_confirmar")
    assert c.mensaje == "operacion.sin_confirmar"
    assert c.calibracion["gain"] == 1.0 and c.calibracion["offset"] == 0.0


def test_aplicar_sin_respuesta_y_relectura_fallida_queda_sin_confirmar():
    c, s, res = _ctrl_cargado()
    _aplicar(c)
    s.responder("PATCH", RUTA, NO_RESPONDE)
    s.responder("GET", RUTA, NO_RESPONDE)
    assert res[-1][:2] == ("cal_puntos", "sin_confirmar")
    assert c.calibracion["gain"] == 1.0


def test_una_operacion_a_la_vez():
    c, s, res = _ctrl_cargado()
    assert _aplicar(c) is True
    assert _aplicar(c) is False and c.mensaje == "operacion.procesando"
    assert c.restaurar("defecto") is False
    assert c.cargarCalibracion("presion", "pres_camara") is False
    assert s.contar("PATCH", RUTA) == 1
    assert s.contar("POST", RUTA + "/restaurar") == 0


def test_rechazo_que_pide_confirmacion():
    c, s, res = _ctrl_cargado()
    _aplicar(c)
    s.responder("PATCH", RUTA, sb.Resultado("CALIBRACION_REQUIERE_CONFIRMACION",
                                            {"detail": "fuera de rango"}, 409))
    assert res[-1][:2] == ("cal_puntos", "rechazada")
    assert c.requiereConfirmacion is True and c.detalle == "fuera de rango"
    assert _aplicar(c, confirmar=True) is True
    assert s.ultimo("PATCH", RUTA)["cuerpo"]["confirmar_fuera_de_rango"] is True


def test_restaurar_200_relee():
    c, s, res = _ctrl_cargado()
    assert c.restaurar("defecto") is True
    post = s.ultimo("POST", RUTA + "/restaurar")
    assert post["cuerpo"] == {"destino": "defecto"} and post["plazo_s"] == 10.0
    s.responder("POST", RUTA + "/restaurar", _ok())
    assert res == [("cal_restaurar", "confirmada", "")]
    s.responder("GET", RUTA, _ok({**CAL, "gain": 1.0, "offset": 0.0}))
    assert c.calibracion["gain"] == 1.0


def test_restaurar_sin_respuesta_sin_confirmar_mostrando_lo_leido():
    c, s, res = _ctrl_cargado()
    c.restaurar("ultimo")
    s.responder("POST", RUTA + "/restaurar", NO_RESPONDE)
    s.responder("GET", RUTA, _ok({**CAL, "gain": 1.05, "offset": -0.3}))
    assert res[-1] == ("cal_restaurar", "sin_confirmar", "operacion.sin_confirmar")
    assert c.calibracion["gain"] == 1.05 and c.calibracion["offset"] == -0.3


# ── C1 (revisión FASE 6): un 200 tardío de otro sensor ─────────────────────

RUTA_A = "/calibration/temperature/temp_camara"
CAL_A = {"sensor": "temp_camara", "tipo": "temperature", "gain": 2.0, "offset": 5.0,
         "is_poly": False, "last_change": None}


def _tardio(s, metodo, ruta, r):
    s.ultimo(metodo, ruta)["al_tardio"](r)


@pytest.mark.parametrize("tardio_antes_del_200_de_c", [True, False])
def test_c1_200_tardio_de_A_con_C_pedido_no_cambia_la_calibracion(tardio_antes_del_200_de_c):
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = SesionDoble()
    c = EntradasSalidasController(sesion=s)
    res = []
    c.operacionResuelta.connect(lambda *a: res.append(a))
    # A sin respuesta en 5 s: sin confirmar, la pantalla no se abre
    assert c.cargarCalibracion("temperatura", "temp_camara") is True
    s.responder("GET", RUTA_A, NO_RESPONDE)
    assert res[-1][:2] == ("cal_cargar", "sin_confirmar") and c.calibracion == {}
    # el técnico pide C
    assert c.cargarCalibracion("presion", "pres_camara") is True
    if tardio_antes_del_200_de_c:
        _tardio(s, "GET", RUTA_A, _ok(CAL_A))
        assert c.calibracion == {}                       # el de A no se fija
        s.responder("GET", RUTA, _ok(CAL))
    else:
        s.responder("GET", RUTA, _ok(CAL))
        _tardio(s, "GET", RUTA_A, _ok(CAL_A))
    # MAYOR-1 (segunda revisión): con C vigente (misma clave) el 200 tardío de A
    # no se anuncia (solo log y relectura); con C ya resuelto, sí
    tarde = ("cal_cargar", "confirmada", "operacion.confirmada_tarde")
    assert (tarde in res) is (not tardio_antes_del_200_de_c)
    assert ("cal_cargar", "confirmada", "") in res
    assert c.calibracion["sensor"] == "pres_camara" and c.calibracion["gain"] == 1.0
    assert c.calibracionEs("presion", "pres_camara") is True
    assert c.calibracionEs("temperatura", "temp_camara") is False
    # aplicar desde la pantalla de C escribe en C, nunca en A
    assert c.aplicarPuntos(*PUNTOS, "capturada", "escrita", False, "presion", "pres_camara") is True
    assert s.contar("PATCH", RUTA) == 1 and s.contar("PATCH", RUTA_A) == 0


def test_c1_tardio_del_mismo_pedido_si_se_fija():
    """Sin un pedido nuevo, el 200 tardío del vigente sí fija (no abre: lo
    descarta la QML por "confirmada_tarde")."""
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = SesionDoble()
    c = EntradasSalidasController(sesion=s)
    c.cargarCalibracion("temperatura", "temp_camara")
    s.responder("GET", RUTA_A, NO_RESPONDE)
    _tardio(s, "GET", RUTA_A, _ok(CAL_A))
    assert c.calibracionEs("temperatura", "temp_camara") is True


def test_c1_aplicar_y_restaurar_con_otro_sensor_se_rechazan_en_local():
    c, s, res = _ctrl_cargado()                          # cargada: presion / pres_camara
    for seg, sen in (("temperatura", "temp_camara"), ("presion", "pres_chaqueta"),
                     ("temperatura", "pres_camara"), ("", "")):
        assert c.aplicarPuntos(*PUNTOS, "capturada", "escrita", False, seg, sen) is False
        assert c.restaurar("defecto", seg, sen) is False
        assert c.mensaje == "operacion.sin_confirmar"
    assert s.contar("PATCH", RUTA) == 0 and s.contar("POST", RUTA + "/restaurar") == 0
    assert c.operacionEnCurso is False and res == []
    # con el sensor de la pantalla igual al cargado, sí sale
    assert c.restaurar("defecto", "presion", "pres_camara") is True
    assert s.contar("POST", RUTA + "/restaurar") == 1


def test_c1_qml_no_abre_con_tardia_y_pasa_el_sensor_de_la_pantalla():
    from pathlib import Path
    base = Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas"
    es = (base / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    cal = (base / "OpcionesCalibracionSensor.qml").read_text(encoding="utf-8")
    assert 'if (mensaje === "operacion.confirmada_tarde") return' in es
    assert "control.calibracionEs(raiz.calibracionPedidaTipo, raiz.calibracionPedidaSensor)" in es
    assert "origenBajo, origenAlto, confirmar, raiz.segmento, raiz.sensor)" in cal
    assert "restaurar(raiz.accionPendiente, raiz.segmento, raiz.sensor)" in cal


def test_qml_abre_y_limpia_solo_con_confirmada():
    from pathlib import Path
    base = Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas"
    es = (base / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    cal = (base / "OpcionesCalibracionSensor.qml").read_text(encoding="utf-8")
    assert "function onOperacionResuelta(clave, estado, mensaje)" in es
    assert 'clave !== "cal_cargar"' in es and 'estado === "confirmada"' in es
    assert "if (control.cargarCalibracion(" not in es
    assert "if (controlador.aplicarPuntos(" not in cal
    assert 'clave !== "cal_puntos"' in cal and 'estado === "confirmada"' in cal
    assert "operacion.procesando" in cal and "operacion.verificando" in cal


def test_h4_qml_confirmada_tarde_no_borra_los_puntos():
    """H4 (3.er ciclo de corrección): un 'confirmada' tardío de cal_puntos
    (puede ser de otro sensor o de puntos anteriores) no limpia lo escrito;
    el retorno va ANTES de la limpieza, dentro del manejador de cal_puntos."""
    from pathlib import Path
    base = Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas"
    cal = (base / "OpcionesCalibracionSensor.qml").read_text(encoding="utf-8")
    ini = cal.index("function onOperacionResuelta(clave, estado, mensaje)")
    cuerpo = cal[ini:cal.index("function editar(", ini)]
    i_clave = cuerpo.index('if (clave !== "cal_puntos") return')
    i_tarde = cuerpo.index('if (mensaje === "operacion.confirmada_tarde") return')
    i_limpia = cuerpo.index("raiz.realBajo = Number.NaN")
    assert i_clave < i_tarde < i_limpia
