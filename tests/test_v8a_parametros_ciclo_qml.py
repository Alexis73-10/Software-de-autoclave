"""V8a (tanda 8): pantalla Parámetros del ciclo (QML, offscreen).

D8-5.7: el tipo de carga es un selector Sólido/Líquido sin mínimo ni máximo;
al elegir Líquido la ventana anticipa la regla; tras guardar, la pantalla
avisa del cambio automático del modo de descompresión con texto del
catálogo; con carga líquida el selector de modo solo ofrece 4, 5 y 0 y "Por
defecto" no propone un modo no permitido.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]

_GUION = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
import autoclave.ui_qml.bridge.i18n_qml
import autoclave.ui_qml.controllers  # registra Autoclave.Controllers
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.sesion_backend import Resultado

cfg = json.loads(sys.argv[2])
enviados = []

class Sesion:
    def enviar(self, metodo, ruta, cuerpo=None):
        enviados.append([metodo, ruta, cuerpo])
        ruta = ruta.split("?")[0]
        estado, datos = cfg["rutas"].get(metodo + " " + ruta, [200, {}])
        if 200 <= estado < 300:
            return Resultado("ok", datos, estado)
        return Resultado((datos or {}).get("codigo") or "error_generico", datos, estado)

sesion_backend.instalar(Sesion())
qml_dir = sys.argv[1]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(b'''import QtQuick
import "Pantallas"
Item { width: 1088; height: 1400
  OpcionesParametrosCiclo { objectName: "vista"; anchors.fill: parent; edicionPermitida: true } }''',
             QUrl.fromLocalFile(qml_dir + "/prueba_v8a.qml"))
raiz = comp.create()
assert raiz is not None, comp.errorString()
vista = raiz.findChild(QQuickItem, "vista")
control = vista.findChild(QObject, "parametrosCicloController")

def hijo(n, nodo=None):
    nodo = nodo or vista
    for item in nodo.childItems():
        if item.objectName() == n:
            return item
        e = hijo(n, item)
        if e is not None:
            return e
    return None

def visible(n):
    h = hijo(n)
    return h is not None and h.isVisible()

def abrir(seccion, clave):
    control.abrirSeccion(seccion)
    vista.setProperty("vista", "seccion")
    app.processEvents()
    QMetaObject.invokeMethod(hijo("param_" + clave), "pulsada")
    app.processEvents()

r = {}
exec(cfg["pasos"])
r["avisos"] = avisos
r["enviados"] = enviados
print("RES=" + json.dumps(r, ensure_ascii=False, default=str))
"""

_PROGRAMAS = {"programas": [{"numero": 4, "cycle_id": "liquidos", "nombre": "Líquidos",
                             "editable": True, "danado": False, "habilitado": True,
                             "secciones": [{"clave": "globals", "no_se_ejecuta": False},
                                           {"clave": "descompresion", "no_se_ejecuta": False}]}]}


def _p(clave, tipo, valor, defecto, opciones=(), modos=(), mn=None, mx=None):
    return {"clave": clave, "path": [clave], "tipo": tipo, "valor": valor, "defecto": defecto,
            "min": mn, "max": mx, "unidad": "", "opciones": list(opciones), "modos": list(modos),
            "modificado": valor != defecto, "ultima_modificacion": None}


def _correr(pasos, rutas):
    base = {"GET /programas": [200, _PROGRAMAS]}
    base.update(rutas)
    cfg = {"rutas": base, "pasos": pasos}
    qml = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _GUION, str(qml), json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=120, env=env)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RES=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    res = json.loads(linea[4:])
    assert [a for a in res["avisos"] if "sesion" not in a.lower()] == []
    return res


_TIPO_SOLIDO = {"editable": True, "parametros": [
    _p("tipo_carga", "enum", "solido", "solido", opciones=["solido", "liquido"])]}


def test_tipo_carga_sin_minimo_ni_maximo_y_aviso_previo_al_elegir_liquido():
    res = _correr("""
abrir("globals", "tipo_carga")
r["ajuste"] = visible("ventanaAjuste")
r["selector"] = visible("selectorNuevoValor")
r["minimo"] = visible("valorAjuste_opciones.minimo")
r["maximo"] = visible("valorAjuste_opciones.maximo")
r["actual"] = visible("valorAjuste_opciones.actual")
r["previo_solido"] = visible("avisoLiquidoPrevio")
hijo("ventanaAjuste").setProperty("nuevo", "liquido")
app.processEvents()
r["previo_liquido"] = visible("avisoLiquidoPrevio")
r["texto_previo"] = hijo("avisoLiquidoPrevio").property("text")
""", {"GET /programas/4/seccion/globals": [200, _TIPO_SOLIDO]})
    assert res["ajuste"] and res["selector"] and res["actual"]
    assert not res["minimo"] and not res["maximo"]
    assert not res["previo_solido"] and res["previo_liquido"]
    assert "4, 5" in res["texto_previo"] and "0" in res["texto_previo"]


def test_tras_guardar_avisa_del_cambio_automatico_del_modo():
    arrastre = [{"fase": "descompresion", "path": ["modo"], "clave": "modo", "anterior": 1, "nuevo": 4}]
    res = _correr("""
r["aviso_antes"] = visible("avisoParametros")
abrir("globals", "tipo_carga")
hijo("ventanaAjuste").setProperty("nuevo", "liquido")
app.processEvents()
QMetaObject.invokeMethod(hijo("guardarAjuste"), "pulsado")
app.processEvents()
r["ajuste_cerrado"] = not visible("ventanaAjuste")
r["aviso"] = visible("avisoParametros")
r["texto"] = hijo("textoAvisoParametros").property("text")
QMetaObject.invokeMethod(hijo("cerrarAvisoParametros"), "pulsado")
app.processEvents()
r["aviso_cerrado"] = not visible("avisoParametros")
""", {"GET /programas/4/seccion/globals": [200, _TIPO_SOLIDO],
      "PATCH /cycle/parameter": [200, {"ok": True, "value": "liquido", "arrastres": arrastre}]})
    assert not res["aviso_antes"]
    assert res["ajuste_cerrado"] and res["aviso"] and res["aviso_cerrado"]
    assert "4" in res["texto"] and "Con enfriamiento" in res["texto"]
    patch = [e for e in res["enviados"] if e[0] == "PATCH"]
    assert patch and patch[0][2]["value"] == "liquido"


def test_rechazo_por_modo_no_permitido_muestra_el_motivo():
    res = _correr("""
abrir("descompresion", "modo")
hijo("ventanaAjuste").setProperty("nuevo", 1)
app.processEvents()
QMetaObject.invokeMethod(hijo("guardarAjuste"), "pulsado")
app.processEvents()
r["error"] = visible("errorParametros")
r["texto"] = control.property("mensaje")
""", {"GET /programas/4/seccion/descompresion": [200, {"editable": True, "parametros": [
          _p("modo", "int", 4, 4, modos=[0, 1, 2, 3, 4, 5], mn=0, mx=5)]}],
      "PATCH /cycle/parameter": [422, {"codigo": "MODO_NO_PERMITIDO_LIQUIDO"}]})
    assert res["error"] and res["texto"] == "opciones.err_modo_liquido"


def test_con_liquido_el_selector_de_modo_solo_ofrece_4_5_y_0():
    res = _correr("""
abrir("descompresion", "modo")
sel = hijo("selectorModo")
r["visible"] = sel.isVisible()
ops = sel.property("opciones")
ops = ops.toVariant() if hasattr(ops, "toVariant") else ops
r["opciones"] = [o["etiqueta"] for o in ops]
r["valor"] = sel.property("valor")
r["defecto_habilitado"] = hijo("defectoAjuste").property("habilitado")
r["minimo"] = visible("valorAjuste_opciones.minimo")
""", {"GET /programas/4/seccion/descompresion": [200, {"editable": True, "parametros": [
          _p("modo", "int", 4, 1, modos=[4, 5, 0], mn=0, mx=5)]}]})
    assert res["visible"]
    assert res["opciones"] == ["4", "5", "0"]
    assert res["valor"] == 4
    # el defecto (1) no es un modo permitido con líquido: no se propone
    assert res["defecto_habilitado"] is False
    assert res["minimo"] is False


# ── D8-5.8: todo parámetro "modo" se elige de una lista ─────────────────────

_PROGRAMAS_SECADO = {"programas": [{"numero": 2, "cycle_id": "134_instrumental", "nombre": "Instrumental",
                                    "editable": True, "danado": False, "habilitado": True,
                                    "secciones": [{"clave": "secado", "no_se_ejecuta": False}]}]}


def test_modo_de_secado_se_elige_de_la_lista_de_modos_validos():
    res = _correr("""
abrir("secado", "modo")
sel = hijo("selectorModo")
ops = sel.property("opciones")
ops = ops.toVariant() if hasattr(ops, "toVariant") else ops
r["visible"] = sel.isVisible()
r["opciones"] = [o["etiqueta"] for o in ops]
r["teclado"] = visible("campoNuevoValor")
r["minimo"] = visible("valorAjuste_opciones.minimo")
r["nombre"] = hijo("descripcionModo").property("text")
QMetaObject.invokeMethod(hijo("cancelarAjuste"), "pulsado")
app.processEvents()
r["fila"] = hijo("param_modo").property("valor")
""", {"GET /programas": [200, _PROGRAMAS_SECADO],
      "GET /programas/2/seccion/secado": [200, {"editable": True, "parametros": [
          _p("modo", "int", 3, 3, modos=[1, 2, 3], mn=1, mx=3)]}]})
    assert res["visible"] and not res["teclado"] and not res["minimo"]
    assert res["opciones"] == ["1", "2", "3"]
    assert "Pulsos de vacío y aire" in res["nombre"]
    assert res["fila"].startswith("3") and "Pulsos de vacío y aire" in res["fila"]
