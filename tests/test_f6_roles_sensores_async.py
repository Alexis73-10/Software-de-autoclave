# tests/test_f6_roles_sensores_async.py
#
# AJUSTES 2026-11-02, FASE 6 (P1): roles de sensores (PUT /cycle/sensor-roles)
# como operación crítica SIN optimismo. La asignación mostrada es la vigente
# del backend hasta el 200 o una relectura de GET /cycle/sensors que coincida;
# ya no hay relectura síncrona ni el atajo que daba por buena la asignación
# ante «sin respuesta».

import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


_PROGRAMAS = {"programas": [{"numero": 4, "cycle_id": "liquidos", "nombre": "Líquidos",
                             "editable": True, "danado": False, "secciones": []}]}
VIGENTE = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"}
NUEVA = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
NO_RESPONDE = Resultado(BACKEND_NO_RESPONDE)


def _sensores(asignacion):
    return Resultado("ok", {"asignacion": dict(asignacion), "editable": True,
                            "sensores": [{"id": k, "estado": "disponible"} for k in asignacion]}, 200)


class _Sesion:
    def __init__(self):
        self.generacion = 0
        self.vuelo = []
        self.enviados = []
        self.sincronos = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta))
        return Resultado("error_generico")

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        e = {"metodo": metodo, "ruta": ruta.split("?")[0], "cuerpo": cuerpo,
             "al_terminar": al_terminar, "al_tardio": al_tardio, "plazo_s": plazo_s}
        self.vuelo.append(e)
        self.enviados.append(e)
        return True

    def cancelar_envios(self, dueno):
        return 0

    def rutas(self, metodo=None):
        return [e["ruta"] for e in self.vuelo if metodo in (None, e["metodo"])]

    def entregar(self, metodo, ruta, r):
        i = next(i for i, e in enumerate(self.vuelo) if e["metodo"] == metodo and e["ruta"] == ruta)
        e = self.vuelo.pop(i)
        e["al_terminar"](r)
        return e


def _ctrl():
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    s = _Sesion()
    c = ParametrosCicloController(sesion=s)
    res = []
    c.operacionResuelta.connect(lambda *a: res.append(a))
    c.cargar()
    s.entregar("GET", "/programas", Resultado("ok", _PROGRAMAS, 200))
    c.cargarSensores()
    s.entregar("GET", "/cycle/sensors", _sensores(VIGENTE))
    assert c.asignacion == VIGENTE
    return c, s, res


def test_200_confirma_y_relee():
    c, s, res = _ctrl()
    assert c.guardarSensores(NUEVA) is True
    put = s.vuelo[-1]
    assert (put["metodo"], put["ruta"], put["plazo_s"]) == ("PUT", "/cycle/sensor-roles", 10.0)
    assert put["cuerpo"] == {"programa": 4, "asignacion": NUEVA,
                             "asignacion_anterior_esperada": VIGENTE}
    assert c.operacionEnCurso and c.estadoDe("sensores:4") == "enviando" and c._op.bloquea()
    assert c.asignacion == VIGENTE                         # sin optimismo
    s.entregar("PUT", "/cycle/sensor-roles", Resultado("ok", {"ok": True}, 200))
    assert res == [("sensores:4", "confirmada", "")] and c.mensaje == ""
    assert "/cycle/sensors" in s.rutas("GET") and "/programas" in s.rutas("GET")
    s.entregar("GET", "/cycle/sensors", _sensores(NUEVA))
    assert c.asignacion == NUEVA and s.sincronos == []


def test_rechazo_muestra_el_motivo_y_conserva_lo_vigente():
    c, s, res = _ctrl()
    c.guardarSensores(NUEVA)
    s.entregar("PUT", "/cycle/sensor-roles", Resultado("ROL_SONDA_NO_ACTIVA", {}, 422))
    assert res == [("sensores:4", "rechazada", "opciones.err_rol_sonda_no_activa")]
    assert c.mensaje == "opciones.err_rol_sonda_no_activa" and c.asignacion == VIGENTE
    s.entregar("GET", "/cycle/sensors", NO_RESPONDE)       # relectura fallida: no borra la vista
    assert c.asignacion == VIGENTE and c.mensaje == "opciones.err_rol_sonda_no_activa"


def test_sin_respuesta_relectura_que_coincide_confirma():
    c, s, res = _ctrl()
    c.guardarSensores(NUEVA)
    s.entregar("PUT", "/cycle/sensor-roles", NO_RESPONDE)
    assert c.estadoDe("sensores:4") == "verificando" and res == []
    s.entregar("GET", "/cycle/sensors", _sensores(NUEVA))
    assert res == [("sensores:4", "confirmada", "")] and c.asignacion == NUEVA


def test_sin_respuesta_relectura_que_no_coincide_queda_sin_confirmar():
    """MAYOR-3: lo releído aún viejo no es un rechazo; el 200 tardío se anuncia."""
    c, s, res = _ctrl()
    c.guardarSensores(NUEVA)
    put = s.entregar("PUT", "/cycle/sensor-roles", NO_RESPONDE)
    s.entregar("GET", "/cycle/sensors", _sensores(VIGENTE))
    assert res == [("sensores:4", "sin_confirmar", "opciones.err_sin_respuesta")]
    assert c.asignacion == VIGENTE and c.mensaje == "opciones.err_sin_respuesta"
    put["al_tardio"](Resultado("ok", {"ok": True}, 200))
    assert res[-1] == ("sensores:4", "confirmada", "operacion.confirmada_tarde")


def test_tardio_con_otro_guardado_vigente_no_se_anuncia():
    """MAYOR-1: con otro guardado de roles del mismo programa en vuelo, el 200
    tardío del anterior no se confunde con él: solo se relee."""
    c, s, res = _ctrl()
    c.guardarSensores(NUEVA)
    put = s.entregar("PUT", "/cycle/sensor-roles", NO_RESPONDE)
    s.entregar("GET", "/cycle/sensors", NO_RESPONDE)
    assert c.guardarSensores(NUEVA) is True
    put["al_tardio"](Resultado("ok", {"ok": True}, 200))
    assert [x[1] for x in res] == ["sin_confirmar"] and c.estadoDe("sensores:4") == "enviando"


def test_ya_no_existe_el_atajo_de_sin_respuesta():
    """Antes: sin respuesta y la vista ya igual a lo pedido -> True y mensaje
    vacío sin relectura. Ahora se relee y, sin lectura, queda sin confirmar."""
    from autoclave.ui_qml.controllers import parametros_ciclo_controller as pc
    assert not hasattr(pc.ParametrosCicloController, "_cargar_sensores_sincrono")
    c, s, res = _ctrl()
    c.guardarSensores(VIGENTE)                              # lo pedido ya es lo mostrado
    s.entregar("PUT", "/cycle/sensor-roles", NO_RESPONDE)
    assert res == [] and c.estadoDe("sensores:4") == "verificando"
    s.entregar("GET", "/cycle/sensors", NO_RESPONDE)
    assert res == [("sensores:4", "sin_confirmar", "operacion.sin_confirmar")]
    assert c.mensaje == "operacion.sin_confirmar"


def test_tardio_200_tras_sin_confirmar_notifica_y_relee():
    c, s, res = _ctrl()
    c.guardarSensores(NUEVA)
    put = s.entregar("PUT", "/cycle/sensor-roles", NO_RESPONDE)
    s.entregar("GET", "/cycle/sensors", NO_RESPONDE)
    while "/cycle/sensors" in s.rutas("GET"):
        s.entregar("GET", "/cycle/sensors", NO_RESPONDE)
    put["al_tardio"](Resultado("ok", {"ok": True}, 200))
    assert res[-1] == ("sensores:4", "confirmada", "operacion.confirmada_tarde")
    assert "/cycle/sensors" in s.rutas("GET")
    while "/cycle/sensors" in s.rutas("GET"):               # la última lectura manda
        s.entregar("GET", "/cycle/sensors", _sensores(NUEVA))
    assert c.asignacion == NUEVA


def test_doble_toque_sin_segundo_envio():
    c, s, _ = _ctrl()
    assert c.guardarSensores(NUEVA) is True
    assert c.guardarSensores(NUEVA) is False
    assert len([e for e in s.enviados if e["metodo"] == "PUT"]) == 1


def test_qml_bloquea_el_boton_durante_la_operacion():
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1]
           / "src/autoclave/ui_qml/qml/Pantallas/OpcionesParametrosCiclo.qml").read_text(encoding="utf-8")
    assert "control.estadoDe(control.claveSensores())" in qml
    assert "&& !control.operacionEnCurso" in qml
    assert "function onOperacionResuelta(clave, estado, mensaje)" in qml
