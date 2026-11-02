"""Componentes graficos del dashboard de reportes (TarjetaIndicador, GraficaArea,
GraficaDona, AnilloProgreso): carga offscreen con y sin datos, sin avisos de QML.

Patron de test_llf_barra_fases_qml.py (subproceso con su propio QGuiApplication).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
import autoclave.ui_qml.bridge.i18n_qml  # registra I18n
from autoclave import i18n

cfg = json.loads(sys.argv[3])
i18n.cargar()
i18n.fijar_idioma("es")
qml_dir, qml = sys.argv[1], sys.argv[2]
app = QGuiApplication([])
from autoclave.ui_qml.app import _cargar_fuentes
_cargar_fuentes()
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_rep_graficos.qml"))
ventana = comp.create()
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(100)

def buscar(nombre, it=None):
    it = it or ventana.contentItem()
    for h in it.childItems():
        if h.objectName() == nombre:
            return h
        e = buscar(nombre, h)
        if e is not None:
            return e
    return None

def p(it, nombre):
    return it.property(nombre)

r = {}
exec(cfg["pasos"])
r["avisos"] = avisos
print("RES=" + json.dumps(r, ensure_ascii=False, default=str))
"""

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 1200; height: 900; visible: true
    Binding { target: Escala; property: "factor"; value: 1 }
    TarjetaIndicador { objectName: "tarjeta"; x: 10; y: 10; width: 300; height: 190 }
    GraficaArea { objectName: "area"; x: 330; y: 10; width: 640; height: 320
                  rotuloTotal: "Total"; rotuloFallos: "Fallos"; textoVacio: "Sin ciclos"
                  duracionBurbujaMs: 200 }
    GraficaDona { objectName: "dona"; x: 10; y: 350; width: 520; height: 240 }
    AnilloProgreso { objectName: "anillo"; x: 600; y: 350; width: 160; height: 220 }
}
"""

_MINI = [{"x": i / 4, "y": v} for i, v in enumerate([0.2, 0.9, 0.5, 1.0, 0.0])]
_TARJETA = {"clave": "exito", "titulo": "Exito", "valor": "88%", "pie": "7 de 8",
            "comparacion": {"disponible": True, "texto": "+3 pp", "flecha": "arriba",
                            "color": "menuVerdeTexto", "sin_datos": False, "texto_sin_datos": ""},
            "mini": _MINI}
_TARJETA_SIN = {"clave": "ciclos", "titulo": "Ciclos", "valor": "0", "pie": "",
                "comparacion": {"disponible": False, "texto": "", "flecha": "ninguna",
                                "color": "textoSecundario", "sin_datos": True,
                                "texto_sin_datos": "Sin datos del periodo anterior"},
                "mini": []}
_PUNTOS = [{"x": i / 5, "y_total": t / 5, "y_completados": c / 5, "con_fallo": t > c,
            "total": t, "completados": c, "fallos": t - c, "etiqueta": str(i + 1),
            "rotulo": f"Dia {i + 1}"} for i, (t, c) in enumerate([(1, 1), (3, 2), (5, 5), (2, 1), (4, 4), (0, 0)])]
_SERIE = {"vacia": False, "puntos": _PUNTOS,
          "eje_y": {"max": 5, "paso": 1, "marcas": [{"valor": v, "y": v / 5} for v in range(6)]},
          "eje_x": [{"x": 0.0, "texto": "1"}, {"x": 1.0, "texto": "6"}],
          "color_total": "accionPrimario", "color_completados": "menuVerde", "color_fallo": "peligroTexto"}
_DONA = {"vacia": False, "total": 10, "centro": "70%", "texto_vacio": "", "color_vacio": "bordeCampo",
         "porciones": [
             {"clave": "completados", "rotulo": "Completados", "cantidad": 7, "porcentaje": "70%",
              "fraccion": 0.7, "inicio": 0.0, "color": "menuVerde"},
             {"clave": "fallos", "rotulo": "Fallos", "cantidad": 2, "porcentaje": "20%",
              "fraccion": 0.2, "inicio": 0.7, "color": "peligroTexto"},
             {"clave": "cancelados", "rotulo": "Cancelados", "cantidad": 1, "porcentaje": "10%",
              "fraccion": 0.1, "inicio": 0.9, "color": "clave_inexistente"}]}
_DONA_VACIA = {"vacia": True, "total": 0, "centro": "", "texto_vacio": "Sin ciclos en el periodo",
               "color_vacio": "bordeCampo", "porciones": []}


def _correr(pasos):
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML, json.dumps({"pasos": pasos})],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
             "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)},
    )
    assert r.returncode == 0, r.stderr
    linea = [x for x in r.stdout.splitlines() if x.startswith("RES=")][-1]
    return json.loads(linea[4:])


def _datos(**kw):
    return "D = json.loads(%r)\n" % json.dumps(kw)


def test_defectos_sin_datos_no_dan_avisos():
    r = _correr("QTest.qWait(50)\nr['ok'] = all(buscar(n) is not None for n in "
                "['tarjeta','area','dona','anillo','graficaAreaVacia','donaCentro','anilloTexto'])")
    assert r["ok"] is True
    assert r["avisos"] == []


def test_tarjeta_con_y_sin_comparacion():
    r = _correr(_datos(a=_TARJETA, b=_TARJETA_SIN) + """
t = buscar('tarjeta')
t.setProperty('dato', D['a']); QTest.qWait(50)
r['valor'] = p(buscar('indicadorValor'), 'text')
r['flecha'] = p(t, 'flecha')
r['mini'] = p(buscar('indicadorMini'), 'visible')
r['texto'] = p(buscar('indicadorTextoComparacion'), 'text')
t.setProperty('dato', D['b']); QTest.qWait(50)
r['flecha2'] = p(t, 'flecha')
r['mini2'] = p(buscar('indicadorMini'), 'visible')
r['texto2'] = p(buscar('indicadorTextoComparacion'), 'text')
t.setProperty('dato', None); QTest.qWait(50)
r['nulo'] = p(buscar('indicadorValor'), 'text')
""")
    assert r["avisos"] == []
    assert r["valor"] == "88%" and r["flecha"] == "arriba" and r["mini"] is True and r["texto"] == "+3 pp"
    assert r["flecha2"] == "ninguna" and r["mini2"] is False
    assert r["texto2"] == "Sin datos del periodo anterior"
    assert r["nulo"] == ""


def test_grafica_area_con_datos_burbuja_y_cierre_solo():
    r = _correr(_datos(s=_SERIE) + """
a = buscar('area')
a.setProperty('serie', D['s']); QTest.qWait(50)
r['vacia'] = p(a, 'vacia')
r['puntos_fallo'] = [p(buscar('graficaAreaPuntoFallo_%d' % i), 'visible') for i in range(6)]
r['trazo'] = p(a, 'trazoTotal')
x = p(a, 'izq') + 0.4 * p(a, 'ancho')
from PySide6.QtCore import Qt, QPoint
QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(a.x() + x), int(a.y() + 100)))
QTest.qWait(50)
r['seleccion'] = p(a, 'seleccion')
r['burbuja'] = p(buscar('graficaAreaBurbuja'), 'visible')
r['rotulo'] = p(buscar('graficaAreaBurbujaRotulo'), 'text')
QTest.qWait(350)
r['tras_cierre'] = p(a, 'seleccion')
a.setProperty('serie', {'vacia': True, 'puntos': [], 'eje_y': {'max': 4, 'marcas': []}, 'eje_x': []})
QTest.qWait(50)
r['vacia2'] = p(buscar('graficaAreaVacia'), 'visible')
r['texto_vacio'] = p(buscar('graficaAreaVacia'), 'text')
""")
    assert r["avisos"] == []
    assert r["vacia"] is False
    assert r["puntos_fallo"] == [False, True, False, True, False, False]
    assert r["trazo"].startswith("M ") and " C " in r["trazo"]
    assert r["seleccion"] == 2 and r["burbuja"] is True and r["rotulo"] == "Dia 3"
    assert r["tras_cierre"] == -1
    assert r["vacia2"] is True and r["texto_vacio"] == "Sin ciclos"


def test_dona_con_datos_vacia_y_clave_desconocida():
    r = _correr(_datos(d=_DONA, v=_DONA_VACIA) + """
d = buscar('dona')
d.setProperty('dona', D['d']); QTest.qWait(50)
r['vacia'] = p(d, 'vacia')
r['centro'] = p(buscar('donaCentro'), 'text')
r['porcion2'] = buscar('donaPorcion_2') is not None
r['leyenda'] = [buscar('donaLeyendaFila_%d' % i) is not None for i in range(3)]
d.setProperty('dona', D['v']); QTest.qWait(50)
r['vacia2'] = p(d, 'vacia')
r['centro2'] = p(buscar('donaCentro'), 'text')
r['porcion0'] = buscar('donaPorcion_0') is not None
""")
    assert r["avisos"] == []
    assert r["vacia"] is False and r["centro"] == "70%" and r["porcion2"] and all(r["leyenda"])
    assert r["vacia2"] is True and r["centro2"] == "Sin ciclos en el periodo" and not r["porcion0"]


def test_anillo_acota_fraccion_y_color_desconocido():
    r = _correr("""
a = buscar('anillo')
a.setProperty('fraccion', 0.42); a.setProperty('colorClave', 'menuNaranja')
a.setProperty('texto', '42 / 100'); a.setProperty('titulo', 'Mantenimiento')
QTest.qWait(50)
r['f'] = p(a, 'fraccionAcotada'); r['t'] = p(buscar('anilloTexto'), 'text')
r['titulo'] = p(buscar('anilloTitulo'), 'visible')
a.setProperty('fraccion', 3.0); QTest.qWait(20); r['alto'] = p(a, 'fraccionAcotada')
a.setProperty('fraccion', -1.0); QTest.qWait(20); r['bajo'] = p(a, 'fraccionAcotada')
a.setProperty('colorClave', 'no_existe'); QTest.qWait(20)
""")
    assert r["avisos"] == []
    assert r["f"] == pytest.approx(0.42) and r["t"] == "42 / 100" and r["titulo"] is True
    assert r["alto"] == 1 and r["bajo"] == 0


def test_dominio_vacio_carga_en_los_componentes():
    from autoclave.ui_qml.domain.reporte_dashboard import presentable
    pr = presentable(None, None, "es")
    r = _correr(_datos(pr=pr) + """
pr = D['pr']
buscar('tarjeta').setProperty('dato', pr['indicadores'][0] if pr['indicadores'] else None)
buscar('area').setProperty('serie', pr['serie'])
buscar('dona').setProperty('dona', pr['dona'])
QTest.qWait(80)
""")
    assert r["avisos"] == []
