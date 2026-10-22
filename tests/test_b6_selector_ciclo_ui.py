"""B6 (tanda 4): puente SelectorCiclo y recuadro "Programa" de Preciclo."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import requests

RAIZ = Path(__file__).resolve().parents[1]


class _Resp:
    def __init__(self, estado, datos):
        self.status_code = estado
        self._d = datos

    def json(self):
        return self._d


class _Backend:
    def __init__(self, lista=None, rechazo=None, cae=False):
        self.lista, self.rechazo, self.cae = lista, rechazo, cae
        self.llamadas = []

    def get(self, path, **kw):
        self.llamadas.append(("GET", path, None))
        if self.cae:
            raise requests.ConnectionError()
        return self.lista

    def post(self, path, body=None, **kw):
        self.llamadas.append(("POST", path, body))
        if self.cae:
            raise requests.ConnectionError()
        if self.rechazo:
            raise requests.HTTPError(response=_Resp(409, {"detail": self.rechazo}))
        return {"ok": True}


_LISTA = {"seleccionable": True, "motivo": "", "programas": [
    {"numero": 3, "cycle_id": "instrumental_121", "nombre": "Instrumental 121", "temperatura": 121.0,
     "tiempo": 15.0, "mas_usado": True, "seleccionado": False},
    {"numero": 2, "cycle_id": "instrumental_134", "nombre": "Instrumental 134", "temperatura": 134.0,
     "tiempo": 3.5, "mas_usado": False, "seleccionado": True}]}


def _selector(backend, door=1):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.bridge.selector_ciclo import SelectorCiclo
    return SelectorCiclo(backend, door=door, ejecutar=lambda t: t())     # síncrono


def test_cargar_presenta_las_filas_con_parametros_y_marcas():
    s = _selector(_Backend(_LISTA))
    s.cargar()
    filas = s.programas
    assert [f["numero"] for f in filas] == ["3", "2"]
    assert filas[0]["parametros"] == "121 °C · 15 min" and filas[0]["masUsado"] is True
    assert filas[1]["seleccionado"] is True and s.seleccionable is True and s.sinConexion is False


def test_no_seleccionable_muestra_el_motivo_del_backend():
    s = _selector(_Backend({**_LISTA, "seleccionable": False, "motivo": "No se puede cambiar de ciclo mientras hay uno en curso."}))
    s.cargar()
    assert s.seleccionable is False and "en curso" in s.mensaje


def test_backend_caido_es_sin_conexion_y_lista_vacia():
    s = _selector(_Backend(cae=True))
    s.cargar()
    assert s.programas == [] and s.sinConexion is True and s.seleccionable is False


def test_elegir_usa_el_mismo_endpoint_con_el_origen_de_la_puerta():
    b = _Backend(_LISTA)
    s = _selector(b, door=2)
    elegidos = []
    s.elegido.connect(lambda: elegidos.append(1))
    s.elegir("instrumental_121")
    assert ("POST", "/cycle/select", {"cycle_id": "instrumental_121", "origen": "puerta_2"}) in b.llamadas
    assert elegidos == [1] and s.mensaje == "" and s.ocupado is False


def test_rechazo_del_backend_muestra_su_motivo_no_un_fallo_generico():
    s = _selector(_Backend(_LISTA, rechazo="No se puede cambiar de ciclo mientras hay uno en curso."))
    elegidos = []
    s.elegido.connect(lambda: elegidos.append(1))
    s.elegir("instrumental_121")
    assert elegidos == [] and "en curso" in s.mensaje and s.sinConexion is False


def test_elegir_sin_respuesta_es_sin_conexion():
    s = _selector(_Backend(_LISTA, cae=True))
    s.elegir("instrumental_121")
    assert s.sinConexion is True and s.mensaje == ""


def test_respuesta_vieja_se_descarta():
    s = _selector(_Backend(_LISTA), )
    s._pedido = 5
    s._al_recibir_lista(4, _LISTA)
    assert s.programas == []


def test_filas_mal_formadas_se_descartan():
    s = _selector(_Backend({"seleccionable": True, "programas": [{"x": 1}, "y", _LISTA["programas"][0]]}))
    s.cargar()
    assert [f["numero"] for f in s.programas] == ["3"]


# ── pantalla ────────────────────────────────────────────────────────────────

_GUION = r"""
import json, sys
sys.path.insert(0, "src")
from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml.bridge.selector_ciclo import SelectorCiclo
qml_dir, captura = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
app = QGuiApplication([])
from autoclave.ui_qml.app import _cargar_fuentes
_cargar_fuentes()

SIN_HISTORIAL = len(sys.argv) > 3 and sys.argv[3] == "sin_historial"

class Backend:
    def get(self, path, **kw):
        filas = [
            {"numero": 3, "cycle_id": "i121", "nombre": "Instrumental 121", "temperatura": 121.0, "tiempo": 15.0, "mas_usado": True, "seleccionado": False},
            {"numero": 2, "cycle_id": "i134", "nombre": "Instrumental 134", "temperatura": 134.0, "tiempo": 3.5, "mas_usado": True, "seleccionado": True},
            {"numero": 1, "cycle_id": "bd", "nombre": "Bowie & Dick", "temperatura": 134.0, "tiempo": 3.5, "mas_usado": False, "seleccionado": False},
            {"numero": 4, "cycle_id": "liq", "nombre": "Líquidos", "temperatura": 121.0, "tiempo": 15.0, "mas_usado": False, "seleccionado": False}]
        if SIN_HISTORIAL:
            filas = sorted(filas, key=lambda f: f["numero"])
            for f in filas: f["mas_usado"] = False
        return {"seleccionable": True, "motivo": "", "programas": filas}
    def post(self, path, body=None, **kw):
        self.ultimo = body
        return {"ok": True}

backend = Backend()
selector = SelectorCiclo(backend, door=1, ejecutar=lambda t: t())
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
QML_SRC = b'''import QtQuick
import "Pantallas"
Item {
    id: p
    width: 1196; height: 1917
    QtObject { id: pf
        objectName: "puenteFalso"
        property bool connected: true
        property string machineState: "PREPARADO"
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property bool paroActivo: false
        property bool modoPrueba: false
        property string programa: "INSTRUMENTAL 134"
        property string cicloActivo: "02"
    }
    PantallaPreciclo { id: pre; objectName: "pantallaPre"; anchors.fill: parent; puente: pf }
}'''
c.setData(QML_SRC, QUrl.fromLocalFile(qml_dir + "/prueba_selector.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
pre = raiz.findChild(QObject, "pantallaPre")
pf = raiz.findChild(QObject, "puenteFalso")
pre.setProperty("selectorCiclo", selector)
r = {}
zona = pre.findChild(QObject, "zonaProgramaTocable")
ayuda = pre.findChild(QObject, "ayudaCambiarCiclo")
ventana = pre.findChild(QObject, "ventanaSelectorCiclo")
numero = pre.findChild(QObject, "zonaNumeroTocable")
aviso = pre.findChild(QObject, "avisoSelectorCiclo")
r["tocable_en_preparado"] = bool(pre.property("programaTocable")) and bool(zona.property("enabled")) and bool(ayuda.property("visible"))
r["numero_tocable"] = numero is not None and bool(numero.property("enabled"))
r["ventana_cerrada"] = not ventana.property("visible")
# D8-5.1 (tanda 8): sin datos vigentes y en FALLA SÍ se puede cambiar
for nombre, cambios in (("sin_conexion", {"connected": False}), ("falla", {"machineState": "FALLA"})):
    previos = {k: pf.property(k) for k in cambios}
    for k, v in cambios.items(): pf.setProperty(k, v)
    r["permitido_" + nombre] = bool(pre.property("programaTocable")) and bool(ayuda.property("visible"))
    for k, v in previos.items(): pf.setProperty(k, v)
# estados donde NO se puede cambiar: la zona sigue respondiendo y la ventana
# muestra el motivo del catálogo (nunca silencio)
for nombre, cambios in (("ciclo", {"machineState": "CICLO"}), ("estado_seguro", {"estadoSeguroActivo": True}),
                        ("confirmar_seguro", {"estadoSeguroRequiereConfirmacion": True}),
                        ("paro", {"paroActivo": True}), ("prueba", {"modoPrueba": True})):
    previos = {k: pf.property(k) for k in cambios}
    for k, v in cambios.items(): pf.setProperty(k, v)
    r["bloqueado_" + nombre] = (not pre.property("programaTocable")) and bool(zona.property("enabled")) and (not ayuda.property("visible"))
    r["motivo_" + nombre] = pre.property("motivoNoTocable")
    QMetaObject.invokeMethod(ventana, "abrir")
    r["aviso_" + nombre] = aviso.property("text") if aviso.property("visible") else ""
    QMetaObject.invokeMethod(ventana, "cerrar")
    for k, v in previos.items(): pf.setProperty(k, v)
# abrir carga la lista
QMetaObject.invokeMethod(ventana, "abrir")
r["ventana_abierta"] = bool(ventana.property("visible"))
lista = pre.findChild(QObject, "listaSelectorCiclo")
r["filas"] = lista.property("count")
# elegir una fila: mismo POST /cycle/select y se cierra
selector.elegir("i121")
r["post"] = getattr(backend, "ultimo", None)
r["ventana_cerrada_tras_elegir"] = not ventana.property("visible")
if captura:
    import tempfile, os
    from PySide6.QtQuick import QQuickView
    from PySide6.QtCore import QMetaObject
    from PySide6.QtTest import QTest
    ruta = os.path.join(tempfile.gettempdir(), "prueba_selector_captura.qml")
    open(ruta, "w", encoding="utf-8").write(QML_SRC.decode("utf-8").replace('import "Pantallas"', 'import "file:///' + qml_dir.replace(chr(92), "/") + '/Pantallas"'))
    v = QQuickView(e, None)
    v.setSource(QUrl.fromLocalFile(ruta))
    v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    v.resize(1196, 1917)
    v.show()
    r2 = v.rootObject()
    pre2 = r2.findChild(QObject, "pantallaPre")
    pre2.setProperty("selectorCiclo", selector)
    QMetaObject.invokeMethod(r2.findChild(QObject, "ventanaSelectorCiclo"), "abrir")
    QTest.qWait(500)
    v.grabWindow().save(captura)
print(json.dumps({"avisos": [a for a in avisos if "sesion" not in a.lower()], **r}))
"""


def _correr(captura="", sin_historial=False):
    argumentos = [sys.executable, "-c", _GUION, str(RAIZ / "src" / "autoclave" / "ui_qml" / "qml")]
    if captura:
        argumentos += [captura, "sin_historial" if sin_historial else "con_historial"]
    r = subprocess.run(argumentos, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=120, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_el_recuadro_programa_es_tocable_fuera_de_ciclo_y_elige_por_el_mismo_endpoint():
    d = _correr()
    # el bucle de binding de avisoSinConexion (altura) ya existía; no es del selector
    assert [a for a in d["avisos"] if "Binding loop" not in a] == []
    assert d["tocable_en_preparado"] and d["ventana_cerrada"] and d["numero_tocable"]
    assert d["permitido_sin_conexion"] and d["permitido_falla"]          # D8-5.1
    import json as _json
    es = _json.loads((RAIZ / "src" / "autoclave" / "i18n" / "es.json").read_text(encoding="utf-8"))
    claves = {"ciclo": "motivo_ciclo_en_curso", "estado_seguro": "motivo_estado_seguro",
              "confirmar_seguro": "motivo_estado_seguro", "paro": "motivo_paro",
              "prueba": "motivo_modo_prueba"}
    for caso, clave in claves.items():
        assert d["bloqueado_" + caso], caso
        assert d["motivo_" + caso] == "selector_ciclo." + clave, caso
        assert d["aviso_" + caso] == es["selector_ciclo"][clave], caso
    assert d["ventana_abierta"] and d["filas"] == 4
    assert d["post"] == {"cycle_id": "i121", "origen": "puerta_1"}
    assert d["ventana_cerrada_tras_elegir"]


def test_tras_elegir_se_refresca_el_cache_de_ciclo():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.bridge.selector_ciclo import SelectorCiclo
    refrescos = []
    ui = type("UI", (), {"refrescar_cache": lambda self: refrescos.append(1)})()
    s = SelectorCiclo(_Backend(_LISTA), door=1, ejecutar=lambda t: t(), ui_service=ui)
    s.elegir("instrumental_121")
    assert refrescos == [1]
    s2 = SelectorCiclo(_Backend(_LISTA, rechazo="no"), door=1, ejecutar=lambda t: t(), ui_service=ui)
    s2.elegir("instrumental_121")
    assert refrescos == [1]                       # un rechazo no refresca


def test_refrescar_cache_pide_el_sondeo_estatico():
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend(_Backend())
    assert not ui._force_static.is_set()
    ui.refrescar_cache()
    assert ui._force_static.is_set()
    ui.stop()
