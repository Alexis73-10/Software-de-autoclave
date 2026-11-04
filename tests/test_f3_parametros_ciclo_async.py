# tests/test_f3_parametros_ciclo_async.py
#
# AJUSTES 2026-11-02, paso 2 fase 3: Opciones › Parámetros del ciclo sin HTTP
# síncrono en el hilo de la GUI (ParametrosCicloController).
#   B  parámetro (PATCH /cycle/parameter, SAF-05): asíncrono SIN optimismo; no
#      vigente hasta el 200; conciliación tras sin respuesta; arrastres y aviso
#      del modo de descompresión; una sola relectura.
#   C  entradas mostradas (PUT /cycle/display-inputs): optimista con reversión.
#   D  lecturas asíncronas con `cargando`.
#   guardarSensores: desde la FASE 6, asíncrono sin optimismo (ver
#   tests/test_f6_roles_sensores_async.py).
# El doble entrega a mano (`entregar`), como lo haría la sesión real más tarde.

import os
import sys

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _ok(datos):
    return Resultado("ok", datos, 200)


_PROGRAMAS = {"programas": [{"numero": 4, "cycle_id": "liquidos", "nombre": "Líquidos",
                             "editable": True, "danado": False,
                             "secciones": [{"clave": "esterilizacion", "no_se_ejecuta": False},
                                           {"clave": "globals", "no_se_ejecuta": False}]}]}


def _seccion(valor):
    return {"editable": True, "parametros": [
        {"clave": "tiempo_esterilizacion", "path": ["tiempo_esterilizacion"], "tipo": "float",
         "valor": valor, "defecto": 15.0, "min": 1, "max": 9999, "unidad": "min", "opciones": [],
         "modificado": valor != 15.0, "ultima_modificacion": None}]}


def _globals(tipo):
    return {"editable": True, "parametros": [
        {"clave": "tipo_carga", "path": ["tipo_carga"], "tipo": "enum", "valor": tipo,
         "defecto": "liquido", "min": None, "max": None, "unidad": "",
         "opciones": ["solido", "liquido"], "modos": [], "modificado": False,
         "ultima_modificacion": None}]}


def _descompresion(modo):
    return {"editable": True, "parametros": [
        {"clave": "modo", "path": ["modo"], "tipo": "int", "valor": modo, "defecto": 4,
         "min": 0, "max": 5, "unidad": "", "opciones": [], "modos": [0, 1, 2, 3, 4, 5],
         "modificado": False, "ultima_modificacion": None}]}


class _SesionAsync:
    """Doble con `enviar_async`: guarda cada petición; `entregar` la resuelve
    con la respuesta configurada (o la dada) en el orden en que se pidió."""

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.en_vuelo = []          # [metodo, ruta, cuerpo, al_terminar, al_tardio]
        self.enviados = []
        self.sincronos = []
        self.cancelados = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None):
        self.enviados.append((metodo, ruta, cuerpo))
        self.en_vuelo.append([metodo, ruta, cuerpo, al_terminar, al_tardio])
        return True

    def enviar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta, cuerpo))
        return self._respuesta(metodo, ruta, cuerpo)

    def cancelar_envios(self, dueno):
        self.cancelados.append(dueno)
        return 0

    def _respuesta(self, metodo, ruta, cuerpo):
        r = self.respuestas.get((metodo, ruta.split("?")[0]))
        if callable(r):
            r = r(cuerpo)
        return r or Resultado("error_generico")

    def pendientes(self, metodo=None):
        return [(m, r) for m, r, *_ in self.en_vuelo if metodo is None or m == metodo]

    def entregar(self, metodo=None, ruta=None, resultado=None):
        i = next(i for i, (m, r, *_) in enumerate(self.en_vuelo)
                 if (metodo is None or m == metodo) and (ruta is None or r.split("?")[0] == ruta))
        m, r, c, al_terminar, al_tardio = self.en_vuelo.pop(i)
        al_terminar(resultado if resultado is not None else self._respuesta(m, r, c))
        return al_tardio

    def entregar_todo(self):
        while self.en_vuelo:
            self.entregar()


def _control(extra=None, seccion="esterilizacion"):
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    estado = {"valor": 15.0}
    resp = {("GET", "/programas"): _ok(_PROGRAMAS),
            ("GET", "/programas/4/seccion/esterilizacion"): lambda c: _ok(_seccion(estado["valor"]))}
    resp.update(extra or {})
    s = _SesionAsync(resp)
    c = ParametrosCicloController(sesion=s)
    resueltos = []
    c.cambioResuelto.connect(lambda k, ok, m: resueltos.append((k, ok, m)))
    c.cargar()
    s.entregar_todo()
    c.abrirSeccion(seccion)
    s.entregar_todo()
    s.enviados.clear()
    return c, s, estado, resueltos


_K = "param:4:esterilizacion:tiempo_esterilizacion"


# ── D: lecturas asíncronas ────────────────────────────────────────────────

def test_lecturas_asincronas_con_cargando():
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    s = _SesionAsync({("GET", "/programas"): _ok(_PROGRAMAS)})
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    assert c.cargando and c.programas == [] and s.sincronos == []
    s.entregar()
    assert not c.cargando and c.numero == 4


def test_lectura_vieja_de_la_seccion_no_pisa_una_posterior():
    c, s, estado, _ = _control()
    c.abrirSeccion("esterilizacion")
    c.abrirSeccion("esterilizacion")
    s.entregar(resultado=_ok(_seccion(99.0)))      # la primera, ya superada
    s.entregar(resultado=_ok(_seccion(16.0)))
    assert c.parametros[0]["valor"] == 16.0
    c.abrirSeccion("esterilizacion")
    s.entregar(resultado=_ok(_seccion(17.0)))
    assert c.parametros[0]["valor"] == 17.0


# ── B: parámetro asíncrono sin optimismo ──────────────────────────────────

def test_parametro_no_es_vigente_hasta_el_200():
    c, s, estado, resueltos = _control({("PATCH", "/cycle/parameter"): _ok({"ok": True})})
    assert c.guardar("tiempo_esterilizacion", 20.0) is True       # aceptado, en vuelo
    assert c.parametros[0]["valor"] == 15.0                        # sigue el vigente
    assert c.pendientes == {_K: "enviando"} and c.valoresPendientes == {_K: 20.0}
    assert s.pendientes() == [("PATCH", "/cycle/parameter")] and s.sincronos == []
    # edición de esa clave bloqueada mientras está pendiente
    assert c.guardar("tiempo_esterilizacion", 21.0) is False
    assert len(s.pendientes("PATCH")) == 1
    estado["valor"] = 20.0
    s.entregar("PATCH")
    # 200: una sola relectura de la sección y una de los programas
    assert sorted(s.pendientes()) == [("GET", "/programas"),
                                      ("GET", "/programas/4/seccion/esterilizacion")]
    assert c.parametros[0]["valor"] == 15.0 and _K in c.pendientes
    s.entregar_todo()
    assert c.parametros[0]["valor"] == 20.0 and c.pendientes == {}
    assert resueltos == [(_K, True, "")] and c.mensaje == ""
    assert s.en_vuelo == []


def test_rechazo_relee_una_vez_y_no_cambia_el_valor():
    c, s, estado, resueltos = _control({("PATCH", "/cycle/parameter"):
                                        Resultado("VALOR_CAMBIO", {"valor_actual": 18.0}, 409)})
    c.guardar("tiempo_esterilizacion", 20.0)
    estado["valor"] = 18.0
    s.entregar("PATCH")
    assert s.pendientes() == [("GET", "/programas/4/seccion/esterilizacion")]
    s.entregar()
    assert c.parametros[0]["valor"] == 18.0 and c.pendientes == {}
    assert c.mensaje == "opciones.err_valor_cambio" and c.detalleMensaje["valor"] == 18.0
    assert resueltos == [(_K, False, "opciones.err_valor_cambio")]
    assert s.en_vuelo == []


@pytest.mark.parametrize("aplicado", [True, False])
def test_sin_respuesta_concilia_releyendo(aplicado):
    c, s, estado, resueltos = _control({("PATCH", "/cycle/parameter"): Resultado(BACKEND_NO_RESPONDE)})
    c.guardar("tiempo_esterilizacion", 20.0)
    if aplicado:
        estado["valor"] = 20.0           # se aplicó, pero la respuesta no llegó
    s.entregar("PATCH")
    assert c.pendientes == {_K: "verificando"}
    assert s.pendientes() == [("GET", "/programas/4/seccion/esterilizacion")]
    s.entregar()
    assert c.pendientes == {} and s.en_vuelo == []
    if aplicado:
        assert resueltos == [(_K, True, "")] and c.mensaje == ""
        assert c.parametros[0]["valor"] == 20.0
    else:
        assert resueltos == [(_K, False, "opciones.err_sin_respuesta")]
        assert c.parametros[0]["valor"] == 15.0


@pytest.mark.parametrize("patch", [_ok({"ok": True}), Resultado(BACKEND_NO_RESPONDE)])
def test_callback_que_lanza_no_deja_la_clave_pendiente(patch):
    # Salvaguarda: _aplicar_seccion corre antes de al_leer; un cuerpo malformado
    # en la relectura (parametros no iterable) lanza y la sesión solo lo
    # registraría. La clave sale de _en_vuelo y se resuelve con fallo.
    c, s, _, resueltos = _control({("PATCH", "/cycle/parameter"): patch})
    c.guardar("tiempo_esterilizacion", 20.0)
    s.entregar("PATCH")
    assert c.parametroPendiente is True
    s.entregar("GET", "/programas/4/seccion/esterilizacion",
               _ok({"editable": True, "parametros": 5}))
    assert _K not in c._en_vuelo and c.pendientes == {}
    assert c.parametroPendiente is False
    assert resueltos == [(_K, False, "opciones.err_generico")]
    assert c.mensaje == "opciones.err_generico"
    s.entregar_todo()                                   # nada más resuelve esa clave
    assert len(resueltos) == 1
    # la clave vuelve a poder guardarse
    assert c.guardar("tiempo_esterilizacion", 21.0) is True


def test_respuesta_tardia_relee():
    c, s, estado, _ = _control({("PATCH", "/cycle/parameter"): Resultado(BACKEND_NO_RESPONDE)})
    c.guardar("tiempo_esterilizacion", 20.0)
    al_tardio = s.entregar("PATCH")
    s.entregar_todo()
    assert c.mensaje == "opciones.err_sin_respuesta"
    estado["valor"] = 20.0
    al_tardio(_ok({"ok": True}))
    s.entregar_todo()
    assert c.parametros[0]["valor"] == 20.0 and c.mensaje == ""


def _control_tipo_carga(patch):
    est = {"tipo": "liquido", "modo": 4}
    c, s, _, resueltos = _control({
        ("GET", "/programas/4/seccion/globals"): lambda _c: _ok(_globals(est["tipo"])),
        ("GET", "/programas/4/seccion/descompresion"): lambda _c: _ok(_descompresion(est["modo"])),
        ("PATCH", "/cycle/parameter"): lambda cuerpo: patch(est, cuerpo)}, seccion="globals")
    return c, s, resueltos


def test_tipo_carga_lee_el_modo_antes_y_avisa_del_arrastre():
    arrastre = [{"fase": "descompresion", "path": ["modo"], "clave": "modo", "anterior": 4, "nuevo": 1}]

    def patch(est, cuerpo):
        est.update(tipo="solido", modo=1)
        return _ok({"ok": True, "arrastres": arrastre})
    c, s, resueltos = _control_tipo_carga(patch)
    assert c.guardar("tipo_carga", "solido") is True
    # el modo previo se lee antes de enviar el PATCH (en orden)
    assert s.pendientes() == [("GET", "/programas/4/seccion/descompresion")]
    s.entregar()
    assert s.pendientes() == [("PATCH", "/cycle/parameter")]
    s.entregar_todo()
    assert c.aviso == "opciones.aviso_modo_solido" and c.detalleAviso["modo"] == 1
    assert resueltos == [("param:4:globals:tipo_carga", True, "")]


def test_tipo_carga_sin_respuesta_aplicado_tambien_avisa():
    def patch(est, cuerpo):
        est.update(tipo="solido", modo=1)             # se aplicó, la respuesta no llegó
        return Resultado(BACKEND_NO_RESPONDE)
    c, s, resueltos = _control_tipo_carga(patch)
    c.guardar("tipo_carga", "solido")
    s.entregar_todo()
    assert c.aviso == "opciones.aviso_modo_solido" and c.detalleAviso["modo"] == 1
    assert c.mensaje == "" and resueltos == [("param:4:globals:tipo_carga", True, "")]
    # una sola relectura de cada cosa: modo antes, PATCH, sección, modo después
    assert [r for m, r, _ in s.enviados] == ["/programas/4/seccion/descompresion", "/cycle/parameter",
                                             "/programas/4/seccion/globals",
                                             "/programas/4/seccion/descompresion"]


def test_compatible_con_dobles_que_solo_tienen_enviar():
    """Camino de compatibilidad: el resultado llega en el acto y el slot
    devuelve el ok real (las pruebas anteriores siguen valiendo)."""
    from tests.test_t12_opciones_parametros import _Sesion
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    s = _Sesion({("GET", "/programas"): _ok(_PROGRAMAS),
                 ("GET", "/programas/4/seccion/esterilizacion"): _ok(_seccion(15.0)),
                 ("PATCH", "/cycle/parameter"): Resultado("VALOR_INVALIDO", {}, 422)})
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    c.abrirSeccion("esterilizacion")
    assert c.guardar("tiempo_esterilizacion", 20.0) is False and c.pendientes == {}
    assert not c.cargando


# ── C: entradas mostradas optimistas ──────────────────────────────────────

def _control_entradas(put):
    lectura = {"entradas": ["temp_camara"]}
    c, s, _, resueltos = _control({
        ("GET", "/cycle/display-inputs"): lambda _c: _ok({
            "entradas": list(lectura["entradas"]), "editable": True,
            "habilitadas": ["temp_camara", "pres_camara"],
            "disponibles": ["temp_camara", "pres_camara"]}),
        ("PUT", "/cycle/display-inputs"): put})
    c.cargarEntradas()
    s.entregar_todo()
    s.enviados.clear()
    return c, s, lectura, resueltos


def test_entradas_optimistas_confirmadas():
    c, s, lectura, resueltos = _control_entradas(_ok({"ok": True}))
    assert c.guardarEntradas(["pres_camara", "temp_camara"]) is True
    assert c.entradas == ["pres_camara", "temp_camara"]            # en el acto
    assert c.pendientes == {"entradas:4": "enviando"}
    # una lectura que llega mientras tanto no pisa lo pendiente
    c.cargarEntradas()
    s.entregar("GET")
    assert c.entradas == ["pres_camara", "temp_camara"]
    s.entregar("PUT")
    assert c.pendientes == {} and resueltos == [("entradas:4", True, "")]
    assert c.entradas == ["pres_camara", "temp_camara"]


def test_entradas_rechazadas_revierten():
    c, s, lectura, resueltos = _control_entradas(Resultado("SENSOR_NO_DISPONIBLE", {}, 422))
    c.guardarEntradas(["pres_camara"])
    assert c.entradas == ["pres_camara"]
    s.entregar("PUT")
    assert c.entradas == ["temp_camara"] and c.pendientes == {}
    assert c.mensaje == "opciones.err_sensor" and c.mensajeRevertido
    assert resueltos == [("entradas:4", False, "opciones.err_sensor")]


def test_entradas_sin_respuesta_y_sin_lectura_revierten_y_recargan():
    c, s, lectura, resueltos = _control_entradas(Resultado(BACKEND_NO_RESPONDE))
    c.guardarEntradas(["pres_camara"])
    s.entregar("PUT")
    assert c.pendientes == {"entradas:4": "verificando"}
    s.entregar("GET", resultado=Resultado(BACKEND_NO_RESPONDE))     # relectura fallida
    assert c.entradas == ["temp_camara"] and c.mensaje == "opciones.cambio_sin_confirmar"
    assert resueltos[-1][1] is False
    assert s.pendientes() == [("GET", "/cycle/display-inputs?programa=4")]   # recarga


def test_entradas_sin_respuesta_pero_aplicadas_se_confirman():
    c, s, lectura, resueltos = _control_entradas(Resultado(BACKEND_NO_RESPONDE))
    c.guardarEntradas(["pres_camara"])
    lectura["entradas"] = ["pres_camara"]
    s.entregar_todo()
    assert c.entradas == ["pres_camara"] and resueltos == [("entradas:4", True, "")]


# ── sensores: FASE 6, asíncrono sin optimismo (detalle en
# tests/test_f6_roles_sensores_async.py) ───────────────────────────────────

def test_guardar_sensores_ya_no_es_sincrono():
    sensores = {"asignacion": {"temp_camara": "principal"}, "editable": True,
                "sensores": [{"id": "temp_camara"}]}
    c, s, _, _ = _control({("GET", "/cycle/sensors"): _ok(sensores),
                           ("PUT", "/cycle/sensor-roles"): _ok({"ok": True})})
    _plazo = s.enviar_async
    s.enviar_async = lambda *a, plazo_s=None, **kw: _plazo(*a, **kw)   # OperacionCritica pasa plazo_s
    assert c.guardarSensores({"temp_camara": "principal"}) is True
    assert s.sincronos == [] and ("PUT", "/cycle/sensor-roles") in s.pendientes()


def test_al_destruirse_cancela_los_envios():
    import shiboken6
    c, s, _, _ = _control()
    ident = id(c)
    shiboken6.delete(c)
    assert ident in s.cancelados


# ── revisión (M1, B1, B3): salida con un guardado en vuelo ────────────────

def test_parametro_pendiente_solo_con_un_patch_en_vuelo():
    c, s, estado, _ = _control({("PATCH", "/cycle/parameter"): _ok({"ok": True})})
    avisos = []
    c.pendientesChanged.connect(lambda: avisos.append(c.parametroPendiente))
    assert c.parametroPendiente is False
    c.guardar("tiempo_esterilizacion", 20.0)
    assert c.parametroPendiente is True and avisos[-1] is True
    estado["valor"] = 20.0
    s.entregar("PATCH")
    assert c.parametroPendiente is True          # sigue hasta la relectura
    s.entregar_todo()
    assert c.parametroPendiente is False and avisos[-1] is False


def test_entradas_pendientes_no_cuentan_como_parametro():
    c, s, lectura, _ = _control_entradas(_ok({"ok": True}))
    c.guardarEntradas(["pres_camara"])
    assert c.pendientes == {"entradas:4": "enviando"} and c.parametroPendiente is False


def test_b1_lectura_fallida_conserva_las_entradas_pendientes():
    c, s, lectura, resueltos = _control_entradas(_ok({"ok": True}))
    c.guardarEntradas(["pres_camara", "temp_camara"])
    c.cargarEntradas()
    s.entregar("GET", resultado=Resultado(BACKEND_NO_RESPONDE))
    assert c.entradas == ["pres_camara", "temp_camara"]
    s.entregar("PUT")
    assert resueltos == [("entradas:4", True, "")]
    assert c.entradas == ["pres_camara", "temp_camara"]
    assert s.pendientes() == []                  # no vacía: no hace falta releer


def test_b1_sin_pendiente_la_lectura_fallida_vacia():
    c, s, lectura, _ = _control_entradas(_ok({"ok": True}))
    c.cargarEntradas()
    s.entregar("GET", resultado=Resultado(BACKEND_NO_RESPONDE))
    assert c.entradas == []


def test_b1_confirmado_con_la_lista_vacia_relee():
    c, s, lectura, resueltos = _control_entradas(_ok({"ok": True}))
    c.guardarEntradas(["pres_camara"])
    c._entradas = []                             # p. ej. vaciada por otra vía
    lectura["entradas"] = ["pres_camara"]
    s.entregar("PUT")
    assert resueltos == [("entradas:4", True, "")]
    assert s.pendientes() == [("GET", "/cycle/display-inputs?programa=4")]
    s.entregar_todo()
    assert c.entradas == ["pres_camara"]


# Pantalla (QML): guardandoParametro, Cancelar, retroceder, cambiosPendientes
# y la ventana de ajuste que se refresca con la relectura (B3).

_GUION_QML = r'''
import json, sys
from PySide6.QtCore import QObject, QUrl, QMetaObject, Qt, Q_RETURN_ARG, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
import autoclave.ui_qml.bridge.i18n_qml
import autoclave.ui_qml.bridge.unidades_qml
import autoclave.ui_qml.controllers
from autoclave import i18n
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.sesion_backend import Resultado

cfg = json.loads(sys.argv[2])
i18n.cargar()
estado = {"valor": 15.0}

def seccion():
    v = estado["valor"]
    return {"editable": True, "parametros": [
        {"clave": "tiempo_esterilizacion", "path": ["tiempo_esterilizacion"], "tipo": "float",
         "valor": v, "defecto": 15.0, "min": 1, "max": 9999, "unidad": "min", "opciones": [],
         "modificado": v != 15.0, "ultima_modificacion": None}]}

class Sesion:
    def __init__(self):
        self.en_vuelo = []
    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None, al_tardio=None):
        self.en_vuelo.append((metodo, ruta.split("?")[0], al_terminar))
        return True
    def enviar(self, metodo, ruta, cuerpo=None):
        return Resultado("error_generico")
    def cancelar_envios(self, dueno):
        return 0
    def responder(self, metodo, ruta):
        if metodo == "PATCH":
            return Resultado("VALOR_CAMBIO", {"valor_actual": estado["valor"]}, 409)
        if ruta == "/programas":
            return Resultado("ok", cfg["programas"], 200)
        return Resultado("ok", seccion(), 200)
    def entregar(self, metodo=None):
        i = next(i for i, x in enumerate(self.en_vuelo) if metodo is None or x[0] == metodo)
        m, r, f = self.en_vuelo.pop(i)
        f(self.responder(m, r))
    def entregar_todo(self):
        while self.en_vuelo:
            self.entregar()

s = Sesion()
sesion_backend.instalar(s)
qml_dir = sys.argv[1]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(cfg["qml"].encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_f3.qml"))
ventana = comp.create()
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(100)
vista = ventana.findChild(QObject, "vista")
ctrl = vista.findChild(QObject, "parametrosCicloController")

def hijo(n, nodo=None):
    nodo = nodo or ventana.contentItem()
    for item in nodo.childItems():
        if item.objectName() == n:
            return item
        e = hijo(n, item)
        if e is not None:
            return e
    return None

def retroceder():
    return QMetaObject.invokeMethod(vista, "retroceder", Qt.DirectConnection,
                                    Q_RETURN_ARG("QVariant"))

s.entregar_todo()
ctrl.abrirSeccion("esterilizacion")
s.entregar_todo()
vista.setProperty("vista", "seccion")
ajuste = hijo("ventanaAjuste")
cancelar = hijo("cancelarAjuste")
QMetaObject.invokeMethod(ajuste, "abrir", Qt.DirectConnection,
                         Q_ARG("QVariant", ctrl.property("parametros")[0]))
ajuste.setProperty("nuevo", 20.0)
QTest.qWait(50)
r = {}
r["antes"] = [vista.property("guardandoParametro"), vista.property("cambiosPendientes"),
              cancelar.property("habilitado")]
ctrl.guardar("tiempo_esterilizacion", 20.0)
QTest.qWait(50)
r["en_vuelo"] = [vista.property("guardandoParametro"), vista.property("cambiosPendientes"),
                 cancelar.property("habilitado"), ajuste.property("abierto")]
r["retroceder_en_vuelo"] = retroceder()
r["abierto_tras_retroceder"] = ajuste.property("abierto")
estado["valor"] = 18.0          # rechazo VALOR_CAMBIO: otro valor vigente
s.entregar("PATCH")
s.entregar_todo()
QTest.qWait(50)
r["despues"] = [vista.property("guardandoParametro"), cancelar.property("habilitado"),
                ajuste.property("abierto"), ajuste.property("param")["valor"],
                vista.property("cambiosPendientes")]
r["avisos"] = avisos
print("RES=" + json.dumps(r, ensure_ascii=False, default=str))
'''


def test_pantalla_bloquea_la_salida_con_un_guardado_en_vuelo():
    import json
    import subprocess
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1]
    qml_dir = raiz / "src" / "autoclave" / "ui_qml" / "qml"
    qml = ('import QtQuick\nimport Tema\nimport "Pantallas"\n'
           'Window { width: 1088; height: 1500; visible: true\n'
           '  Binding { target: Escala; property: "factor"; value: 1 }\n'
           '  OpcionesParametrosCiclo { objectName: "vista"; anchors.fill: parent; '
           'edicionPermitida: true } }')
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(raiz / "src") + os.pathsep + str(raiz)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _GUION_QML, str(qml_dir),
                        json.dumps({"qml": qml, "programas": _PROGRAMAS})],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=raiz, timeout=120, env=env)
    linea = next((x for x in p.stdout.splitlines() if x.startswith("RES=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    r = json.loads(linea[4:])
    assert r["avisos"] == [], r["avisos"]
    assert r["antes"] == [False, True, True]
    # en vuelo: bloquea, ya no es un cambio sin guardar, Cancelar deshabilitado
    assert r["en_vuelo"] == [True, False, False, True]
    assert r["retroceder_en_vuelo"] is True and r["abierto_tras_retroceder"] is True
    # rechazo: desbloquea y la ventana toma el vigente releído (B3)
    assert r["despues"] == [False, True, True, 18.0, True]


def test_opciones_bloquea_navegacion_y_engranaje_con_un_guardado():
    from pathlib import Path
    texto = (Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"
             / "Pantallas" / "Opciones.qml").read_text(encoding="utf-8")
    assert "parametrosCiclo.itemActivo?.guardandoParametro" in texto
    assert "parametrosEquipo.itemActivo?.guardandoParametro" in texto
    assert "onEngranajePulsado: if (!raiz.navegacionBloqueada) raiz.menuPulsado()" in texto
