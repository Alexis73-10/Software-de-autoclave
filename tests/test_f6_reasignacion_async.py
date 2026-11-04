# tests/test_f6_reasignacion_async.py
#
# AJUSTES 2026-11-02, FASE 6 (P1): Reasignación de E/S sin HTTP síncrono en
# la GUI. Aplicar, restaurar fábrica y verificar son operaciones críticas SIN
# optimismo (OperacionCritica): nunca éxito sin un 200 o una relectura de
# GET /io/assignment que coincida; `reiniciando` solo tras la confirmación;
# una operación a la vez; bloquean la navegación; tardíos.

import copy
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


_FILAS = [
    {"funcion": "vapor_camara", "tipo": "DO", "grupo": "DO", "i18n": "io.do.vapor_camara",
     "puerto_actual": 4, "id_actual": "DO 04", "puerto_guardado": 4, "puerto_fabrica": 4,
     "critica": True, "reforzada": False, "temperatura": False},
    {"funcion": "paro_emergencia", "tipo": "DI", "grupo": "DI", "i18n": "io.di.paro_emergencia",
     "puerto_actual": 11, "id_actual": "DI 11", "puerto_guardado": 11, "puerto_fabrica": 11,
     "critica": True, "reforzada": True, "temperatura": False},
]
_DATOS = {
    "filas": _FILAS,
    "puertos": {"DI": list(range(1, 17)), "DO": list(range(1, 33)), "AI_TEMP": [], "AI_PRES": []},
    "ocupados": {"DI": {"11": "paro_emergencia"}, "DO": {"4": "vapor_camara"},
                 "AI_TEMP": {}, "AI_PRES": {}},
    "cambios_guardados": {}, "reinicio_pendiente": False, "error_archivo": "", "bloqueo": "",
    "pendientes": ["paro_emergencia"],
    "verificacion": {"estado": "pendiente", "funciones": {
        "paro_emergencia": {"estado": "trama_presente", "falta": ""}}},
    "editable": True, "motivo": "", "aviso_camara": False, "reinicio_disponible": True,
}
OK_REINICIO = Resultado("ok", {"ok": True, "reinicio": True}, 200)
NO_RESPONDE = Resultado(BACKEND_NO_RESPONDE)


def _datos(**cambios):
    d = copy.deepcopy(_DATOS)
    for funcion, puerto in cambios.items():
        next(f for f in d["filas"] if f["funcion"] == funcion)["puerto_guardado"] = puerto
    return d


class _Sesion:
    """enviar_async que guarda cada petición; la prueba entrega a mano."""

    def __init__(self):
        self.generacion = 0
        self.vuelo = []           # dicts: metodo, ruta, cuerpo, al_terminar, al_tardio, plazo_s
        self.enviados = []
        self.sincronos = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta))
        return Resultado("error_generico")

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        e = {"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo, "al_terminar": al_terminar,
             "al_tardio": al_tardio, "plazo_s": plazo_s}
        self.vuelo.append(e)
        self.enviados.append(e)
        return True

    def cancelar_envios(self, dueno):
        return 0

    def pendientes(self, metodo=None):
        return [(e["metodo"], e["ruta"]) for e in self.vuelo if metodo in (None, e["metodo"])]

    def entregar(self, metodo, ruta, r):
        i = next(i for i, e in enumerate(self.vuelo) if e["metodo"] == metodo and e["ruta"] == ruta)
        e = self.vuelo.pop(i)
        e["al_terminar"](r)
        return e


def _ctrl(inicial=None):
    from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController
    s = _Sesion()
    c = ReasignacionController(sesion=s)
    resueltos = []
    c.operacionResuelta.connect(lambda *a: resueltos.append(a))
    c.cargar()
    s.entregar("GET", "/io/assignment", Resultado("ok", inicial or _datos(), 200))
    return c, s, resueltos


def _aplicar(c):
    c.elegirPuerto("vapor_camara", 7)
    return c.aplicar("secreta")


# ── aplicar ─────────────────────────────────────────────────────────────────

def test_aplicar_200_confirma_y_solo_entonces_reinicia():
    c, s, res = _ctrl()
    assert _aplicar(c) is True
    post = s.vuelo[-1]
    assert (post["metodo"], post["ruta"], post["plazo_s"]) == ("POST", "/io/assignment", 30.0)
    assert c.operacionEnCurso and c.estadoDe("aplicar") == "enviando"
    assert c._op.bloquea()                                 # bloquea la navegación
    assert not c.reiniciando and c.cantidadCambios == 1    # sin optimismo
    s.entregar("POST", "/io/assignment", OK_REINICIO)
    assert res == [("aplicar", "confirmada", "")]
    assert c.reiniciando and c.mensaje == "reasignacion.reiniciando" and c.cantidadCambios == 0
    assert not c.operacionEnCurso and not c._op.bloquea() and s.sincronos == []


def test_aplicar_200_sin_reinicio():
    c, s, res = _ctrl()
    _aplicar(c)
    s.entregar("POST", "/io/assignment", Resultado("ok", {"ok": True, "reinicio": False}, 200))
    assert not c.reiniciando and c.mensaje == "reasignacion.guardado_sin_reinicio"


def test_aplicar_rechazo_conserva_los_cambios_y_relee():
    c, s, res = _ctrl()
    _aplicar(c)
    s.entregar("POST", "/io/assignment", Resultado("reautenticacion_fallida", {}, 403))
    assert res == [("aplicar", "rechazada", "reasignacion.err_clave")]
    assert c.mensaje == "reasignacion.err_clave" and not c.reiniciando
    assert c.cantidadCambios == 1 and s.pendientes("GET") == [("GET", "/io/assignment")]
    s.entregar("GET", "/io/assignment", NO_RESPONDE)       # la relectura falla: queda el motivo
    assert c.mensaje == "reasignacion.err_clave" and c.cargado


def test_aplicar_sin_respuesta_relectura_que_coincide_confirma_y_reinicia():
    c, s, res = _ctrl()
    _aplicar(c)
    s.entregar("POST", "/io/assignment", NO_RESPONDE)
    assert c.estadoDe("aplicar") == "verificando" and not c.reiniciando and res == []
    s.entregar("GET", "/io/assignment", Resultado("ok", _datos(vapor_camara=7), 200))
    assert res == [("aplicar", "confirmada", "")]
    assert c.reiniciando and c.mensaje == "reasignacion.reiniciando" and c.cantidadCambios == 0


def test_aplicar_sin_respuesta_relectura_que_no_coincide_queda_sin_confirmar():
    """MAYOR-3: lo releído aún viejo no es un rechazo (el POST puede seguir
    esperando el lock): sin confirmar, y el 200 tardío sí reinicia."""
    c, s, res = _ctrl()
    _aplicar(c)
    post = s.entregar("POST", "/io/assignment", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", Resultado("ok", _datos(), 200))
    assert res == [("aplicar", "sin_confirmar", "reasignacion.err_sin_respuesta")]
    assert not c.reiniciando and c.cantidadCambios == 1
    post["al_tardio"](OK_REINICIO)
    assert res[-1] == ("aplicar", "confirmada", "operacion.confirmada_tarde")
    assert c.reiniciando and c.cantidadCambios == 0


def test_200_tardio_con_otra_operacion_vigente_no_se_confunde():
    """MAYOR-1: aplicar A queda sin confirmar, se lanza restaurar fábrica; el
    200 tardío de A no activa `reiniciando` ni se anuncia: solo se relee."""
    c, s, res = _ctrl()
    _aplicar(c)
    post_a = s.entregar("POST", "/io/assignment", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", NO_RESPONDE)
    assert [x[1] for x in res] == ["sin_confirmar"]
    assert c.restaurarFabrica("secreta") is True
    gets = len(s.pendientes("GET"))
    post_a["al_tardio"](OK_REINICIO)
    assert [x[1] for x in res] == ["sin_confirmar"]             # nada nuevo anunciado
    assert not c.reiniciando and c.cantidadCambios == 1 and c.estadoDe("fabrica") == "enviando"
    assert len(s.pendientes("GET")) == gets + 1                 # solo la relectura
    s.entregar("POST", "/io/assignment/factory", Resultado("ok", {"ok": True, "reinicio": False}, 200))
    assert res[-1] == ("fabrica", "confirmada", "")
    assert c.mensaje == "reasignacion.guardado_sin_reinicio" and not c.reiniciando


def test_200_tardio_con_aplicar_de_nuevo_en_vuelo_no_pisa_su_respuesta():
    """MAYOR-1: misma clave; el 200 de la vigente usa SU cuerpo, no el del tardío."""
    c, s, res = _ctrl()
    _aplicar(c)
    post_a = s.entregar("POST", "/io/assignment", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", NO_RESPONDE)
    assert c.aplicar("secreta") is True
    post_a["al_tardio"](OK_REINICIO)
    assert not c.reiniciando and len(res) == 1
    s.entregar("POST", "/io/assignment", Resultado("ok", {"ok": True, "reinicio": False}, 200))
    assert res[-1] == ("aplicar", "confirmada", "")
    assert c.mensaje == "reasignacion.guardado_sin_reinicio" and not c.reiniciando


def test_aplicar_sin_lectura_queda_sin_confirmar_y_el_200_tardio_reinicia():
    c, s, res = _ctrl()
    _aplicar(c)
    post = s.entregar("POST", "/io/assignment", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", NO_RESPONDE)
    assert res == [("aplicar", "sin_confirmar", "operacion.sin_confirmar")]
    assert c.mensaje == "operacion.sin_confirmar" and not c.reiniciando
    assert c.cantidadCambios == 1 and not c.operacionEnCurso
    post["al_tardio"](OK_REINICIO)
    assert res[-1] == ("aplicar", "confirmada", "operacion.confirmada_tarde")
    assert c.reiniciando and c.cantidadCambios == 0


def test_aplicar_doble_toque_sin_segundo_envio():
    c, s, res = _ctrl()
    assert _aplicar(c) is True
    assert c.aplicar("secreta") is False
    assert c.restaurarFabrica("secreta") is False
    assert c.verificar("paro_emergencia", "secreta", "") is False
    assert len([e for e in s.enviados if e["metodo"] == "POST"]) == 1


def test_durante_el_envio_no_se_cambian_ni_descartan_los_cambios():
    c, s, _ = _ctrl()
    _aplicar(c)
    c.elegirPuerto("vapor_camara", 9)
    c.descartar()
    assert c.pendientes == {"vapor_camara": "DO 07"}
    c.cargar()                                              # una lectura en vuelo no los quita
    s.entregar("GET", "/io/assignment", Resultado("ok", _datos(vapor_camara=7), 200))
    assert c.cantidadCambios == 1


def test_lectura_anterior_al_desenlace_no_quita_reiniciando():
    c, s, _ = _ctrl()
    c.cargar()                                              # lectura en vuelo antes del POST
    _aplicar(c)
    s.entregar("POST", "/io/assignment", OK_REINICIO)
    s.entregar("GET", "/io/assignment", Resultado("ok", _datos(), 200))
    assert c.reiniciando


def test_plazo_total_sin_respuesta_libera_la_navegacion():
    c, s, res = _ctrl()
    _aplicar(c)
    op = c._op._ops["aplicar"]
    op.timer_total.timeout.emit()
    assert res == [("aplicar", "sin_confirmar", "operacion.sin_confirmar")]
    assert not c._op.bloquea() and not c.reiniciando


# ── restaurar fábrica ───────────────────────────────────────────────────────

def test_fabrica_200_reinicia():
    c, s, res = _ctrl()
    assert c.restaurarFabrica("secreta") is True
    assert s.vuelo[-1]["plazo_s"] == 30.0 and s.vuelo[-1]["cuerpo"] == {"clave": "secreta",
                                                                         "confirmar": True}
    assert not c.reiniciando
    s.entregar("POST", "/io/assignment/factory", OK_REINICIO)
    assert res == [("fabrica", "confirmada", "")] and c.reiniciando


_CAMBIADA = {**_datos(vapor_camara=7), "cambios_guardados": {"vapor_camara": [4, 7]}}


@pytest.mark.parametrize("leido,final", [
    (_datos(), "confirmada"),
    (_CAMBIADA, "sin_confirmar"),                                # MAYOR-3: no es rechazo
    ({**_datos(), "error_archivo": "archivo_ilegible"}, "sin_confirmar"),   # MAYOR-2
])
def test_fabrica_sin_respuesta_concilia_contra_fabrica(leido, final):
    c, s, res = _ctrl(copy.deepcopy(_CAMBIADA))
    c.restaurarFabrica("secreta")
    s.entregar("POST", "/io/assignment/factory", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", Resultado("ok", leido, 200))
    assert [x[1] for x in res] == [final]
    assert c.reiniciando is (final == "confirmada")


@pytest.mark.parametrize("inicial", [
    {**_datos(), "error_archivo": "archivo_ilegible"},           # el backend devuelve la de fábrica
    {**_datos(), "reinicio_pendiente": True},                    # fábrica guardada, sin reiniciar
    _datos(),                                                    # fábrica ya guardada
], ids=["archivo_danado", "reinicio_pendiente", "ya_de_fabrica"])
def test_fabrica_sin_respuesta_no_confirma_si_antes_ya_era_fabrica(inicial):
    """MAYOR-2: si al pedir ya se cumplía la condición de fábrica (o el
    archivo estaba dañado / con reinicio pendiente), la relectura no prueba
    nada: sin confirmar y sin `reiniciando`."""
    c, s, res = _ctrl(copy.deepcopy(inicial))
    c.restaurarFabrica("secreta")
    s.entregar("POST", "/io/assignment/factory", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", Resultado("ok", _datos(), 200))
    assert [x[1] for x in res] == ["sin_confirmar"] and not c.reiniciando


# ── verificar ───────────────────────────────────────────────────────────────

def test_verificar_200():
    c, s, res = _ctrl()
    assert c.verificar("paro_emergencia", "secreta", "Paro") is True
    assert s.vuelo[-1]["plazo_s"] == 10.0 and c.estadoDe("verificar") == "enviando"
    s.entregar("POST", "/io/assignment/verify", Resultado("ok", {"ok": True}, 200))
    assert res == [("verificar", "confirmada", "")] and c.mensaje == "reasignacion.verificada_ok"
    assert not c.reiniciando


@pytest.mark.parametrize("estado,final", [("verificada", "confirmada"),
                                          ("trama_presente", "sin_confirmar")])
def test_verificar_sin_respuesta_concilia(estado, final):
    c, s, res = _ctrl()
    c.verificar("paro_emergencia", "secreta", "Paro")
    s.entregar("POST", "/io/assignment/verify", NO_RESPONDE)
    leido = _datos()
    leido["verificacion"]["funciones"]["paro_emergencia"]["estado"] = estado
    s.entregar("GET", "/io/assignment", Resultado("ok", leido, 200))
    assert [x[1] for x in res] == [final]
    assert c.mensaje == ("reasignacion.verificada_ok" if final == "confirmada"
                         else "reasignacion.err_sin_respuesta")


def test_verificar_relectura_que_no_coincide_y_200_tardio():
    """MAYOR-3: sin confirmar tras la relectura vieja; el 200 tardío se anuncia."""
    c, s, res = _ctrl()
    c.verificar("paro_emergencia", "secreta", "Paro")
    post = s.entregar("POST", "/io/assignment/verify", NO_RESPONDE)
    s.entregar("GET", "/io/assignment", Resultado("ok", _datos(), 200))
    assert [x[1] for x in res] == ["sin_confirmar"]
    post["al_tardio"](Resultado("ok", {"ok": True}, 200))
    assert res[-1] == ("verificar", "confirmada", "operacion.confirmada_tarde")


def test_conciliadores_sin_datos_no_confirman():
    from autoclave.ui_qml.controllers import reasignacion_controller as rc
    assert rc.conciliar_aplicar({}, {"vapor_camara": 7}) == "sin_confirmar"
    assert rc.conciliar_aplicar(_datos(vapor_camara=7), {}) == "sin_confirmar"
    assert rc.conciliar_fabrica({"x": 1}) == "sin_confirmar"
    assert rc.conciliar_fabrica(_datos()) == ("sin_confirmar", "reasignacion.err_sin_respuesta")
    assert rc.conciliar_verificar({}, "paro_emergencia") == "sin_confirmar"


def test_qml_bloquea_botones_y_muestra_el_estado():
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1]
           / "src/autoclave/ui_qml/qml/Pantallas/OpcionesReasignacion.qml").read_text(encoding="utf-8")
    assert qml.count("!raiz._ocupado") >= 4
    assert "operacion.procesando" in qml and "operacion.verificando" in qml
    assert "function onOperacionResuelta(clave, estado, mensaje)" in qml
