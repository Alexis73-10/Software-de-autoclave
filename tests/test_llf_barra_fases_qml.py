"""Llenado de fases (contrato A-3): BarraFases + CirculoFaseLiquido + ConectorFase.

Componentes sueltos en un subproceso con su propio QGuiApplication (offscreen,
patron de test_t21_panel_fin_ciclo_qml.py). Cubre la regla de no inducir a
error (HAZ-LLF-01, REQ-36): un circulo nunca se ve lleno si su estado no es
"completada".
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.req("REQ-36")

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl
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
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_llf_barra.qml"))
ventana = comp.create()
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(150)

def _visual(it, nombre):
    for h in it.childItems():
        if h.objectName() == nombre:
            return h
        e = _visual(h, nombre)
        if e is not None:
            return e
    return None

def buscar(nombre):
    return _visual(ventana.contentItem(), nombre)

barra = buscar("barraFases")
CL = ["precalentamiento", "vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]

def armar(spec):
    out = []
    for i, t in enumerate(spec):
        e = t[0]
        est = {"c": "completada", "p": "pendiente", "f": "fallida", "i": "interrumpida"}.get(e, "activa")
        if e == "a":
            fr = float(t[2:]) if len(t) > 2 else None
        else:
            fr = 1.0 if e == "c" else 0.0 if e == "p" else None
        out.append({"fase": CL[i], "estado": est, "fraccion": fr})
    return out

def poner(spec, vigentes=None):
    if vigentes is not None:
        barra.setProperty("datosVigentes", vigentes)
    barra.setProperty("fases", armar(spec))

def circ(i):
    return buscar("circuloFase_" + CL[i])

def con(i):
    return buscar("conectorFase_" + CL[i])

def liq(i):
    return buscar("liquidoFase_" + CL[i])

def chorro(i):
    return buscar("chorroFase_" + CL[i])

def p(it, nombre):
    return it.property(nombre)

def esperar(ms):
    QTest.qWait(ms)

r = {}
exec(cfg["pasos"])
r["avisos"] = avisos
print("RES=" + json.dumps(r, ensure_ascii=False))
"""

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 1200; height: 700; visible: true
    Binding { target: Escala; property: "factor"; value: 1 }
    BarraFases {
        objectName: "barraFases"
        width: 1200; height: 700
        escala: 1.0
    }
}
"""


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


def test_defectos_iguales_a_python():
    r = _correr('r["tope"] = p(barra, "topeFraccion"); r["indet"] = p(barra, "nivelIndeterminado")\n'
                'r["inst"] = p(barra, "instantaneo"); r["cd"] = p(barra, "cicloDbId")')
    assert r["avisos"] == []
    from autoclave.core.runtime import progreso_ciclo as pc
    tope = getattr(pc, "TOPE_FRACCION_ACTIVA", 0.90)
    assert r["tope"] == pytest.approx(tope)
    try:
        from autoclave.ui_qml.domain.ciclo_en_curso import NIVEL_INDETERMINADO as indet
    except ImportError:
        indet = 0.25
    assert r["indet"] == pytest.approx(indet)
    assert r["inst"] is True and r["cd"] == -1


def test_nivel_visual_y_tope():
    r = _correr("""
poner(["c", "a:0.45", "p", "p", "p", "p"])
esperar(50)
r["medio"] = p(circ(1), "nivelVisual")
r["pend"] = p(circ(2), "nivelVisual")
r["completada"] = p(circ(0), "nivelVisual")
poner(["c", "a:1.0", "p", "p", "p", "p"])
esperar(50)
r["uno"] = p(circ(1), "nivelVisual")
r["uno_nivel"] = p(circ(1), "nivel")
# forzar un nivel interno de 1.0 en un circulo no completado: la tercera capa lo acota
circ(1).setProperty("nivel", 1.0)
r["forzado"] = p(circ(1), "nivelVisual")
poner(["c", "a", "p", "p", "p", "p"])
esperar(50)
r["indeterminado"] = p(circ(1), "nivelVisual")
poner(["c", "a:2.5", "p", "p", "p", "p"])
esperar(50)
r["fuera_de_rango"] = p(circ(1), "nivelVisual")
""")
    assert r["avisos"] == []
    assert r["medio"] == pytest.approx(0.45)
    assert r["pend"] == 0 and r["completada"] == 1.0
    assert r["uno"] == pytest.approx(0.90)
    assert r["forzado"] == pytest.approx(0.90)
    assert r["indeterminado"] == pytest.approx(0.25)
    assert r["fuera_de_rango"] == pytest.approx(0.90)


def test_completada_sin_onda_y_con_degradado_activa_con_onda():
    r = _correr("""
barra.setProperty("instantaneo", False)
poner(["c", "a:0.5", "p", "p", "p", "p"])
esperar(100)
r["act_ampl"] = p(circ(1), "amplitudOnda")
r["act_liquido"] = p(liq(1), "visible")
r["comp_ampl"] = p(circ(0), "amplitudOnda")
r["comp_lleno"] = p(circ(0), "_lleno")
r["comp_liquido"] = p(liq(0), "visible")
r["pend_liquido"] = p(liq(2), "visible")
r["pend_lleno"] = p(circ(2), "_lleno")
""")
    assert r["avisos"] == []
    assert r["act_ampl"] > 0 and r["act_liquido"] is True
    assert r["comp_ampl"] == 0 and r["comp_lleno"] is True and r["comp_liquido"] is False
    assert r["pend_liquido"] is False and r["pend_lleno"] is False


def test_sin_datos_vigentes_sin_onda_ni_chorro():
    r = _correr("""
poner(["c", "c", "a:0.2", "p", "p", "p"])
esperar(50)
r["chorro_con"] = p(circ(2), "chorroVisible")
r["ampl_con"] = p(circ(2), "amplitudOnda")
poner(["c", "c", "a:0.2", "p", "p", "p"], False)
esperar(50)
r["chorro_sin"] = p(circ(2), "chorroVisible")
r["ampl_sin"] = p(circ(2), "amplitudOnda")
r["nivel_sin"] = p(circ(2), "nivelVisual")
""")
    assert r["chorro_con"] is True and r["ampl_con"] > 0
    assert r["chorro_sin"] is False and r["ampl_sin"] == 0
    assert r["nivel_sin"] == pytest.approx(0.2)


def test_conectores():
    r = _correr("""
poner(["c", "c", "a:0.5", "p", "p", "p"])
esperar(50)
r["completada"] = [p(con(1), "progreso"), p(con(2), "progreso")]
r["de_la_activa"] = p(con(3), "progreso")
r["pendiente"] = p(con(4), "progreso")
""")
    assert r["completada"] == [1.0, 1.0]
    assert r["de_la_activa"] == 0.0 and r["pendiente"] == 0.0


def test_chorro_solo_con_nivel_bajo_y_nunca_en_la_primera():
    r = _correr("""
poner(["c", "c", "a:0.2", "p", "p", "p"]); esperar(50)
r["bajo"] = p(circ(2), "chorroVisible")
poner(["c", "c", "a:0.49", "p", "p", "p"]); esperar(50)
r["casi_mitad"] = p(circ(2), "chorroVisible")
poner(["c", "c", "a:0.5", "p", "p", "p"]); esperar(50)
r["mitad"] = p(circ(2), "chorroVisible")
poner(["c", "c", "a:0.8", "p", "p", "p"]); esperar(50)
r["alto"] = p(circ(2), "chorroVisible")
r["forma_alto"] = p(chorro(2), "visible")
poner(["a:0.1", "p", "p", "p", "p", "p"]); esperar(50)
r["primera"] = p(circ(0), "chorroVisible")
r["primera_forma"] = p(chorro(0), "visible")
poner(["c", "a:0.1", "p", "p", "p", "p"]); esperar(50)
r["conector_activa_no_lleno"] = p(circ(1), "chorroVisible")
poner(["c", "c", "a:0.1", "p", "p", "p"]); esperar(50)
r["forma_bajo"] = p(chorro(2), "visible")
""")
    assert r["bajo"] is True and r["forma_bajo"] is True
    assert r["casi_mitad"] is True
    assert r["mitad"] is False and r["alto"] is False and r["forma_alto"] is False
    assert r["primera"] is False and r["primera_forma"] is False


def test_primera_carga_y_ciclo_nuevo_sin_animacion_y_luego_animan():
    r = _correr("""
barra.setProperty("instantaneo", False)
poner(["c", "a:0.3", "p", "p", "p", "p"])
r["primera"] = p(circ(1), "nivel")                 # sin animacion: ya en 0.3
poner(["c", "a:0.8", "p", "p", "p", "p"])          # ya no es primera carga: anima
r["justo_despues"] = p(circ(1), "nivel")
esperar(1300)
r["tras_animar"] = p(circ(1), "nivel")
barra.setProperty("cicloDbId", 7)                  # ciclo nuevo: de nuevo sin animacion
poner(["c", "a:0.1", "p", "p", "p", "p"])
r["ciclo_nuevo"] = p(circ(1), "nivel")
barra.setProperty("enVista", False); barra.setProperty("enVista", True)
poner(["c", "a:0.6", "p", "p", "p", "p"])
r["al_volver"] = p(circ(1), "nivel")
""")
    assert r["avisos"] == []
    assert r["primera"] == pytest.approx(0.3)
    assert r["justo_despues"] < 0.8 - 0.2
    assert r["tras_animar"] == pytest.approx(0.8, abs=0.01)
    assert r["ciclo_nuevo"] == pytest.approx(0.1)
    assert r["al_volver"] == pytest.approx(0.6)


def test_cambio_de_fase_cierra_llena_conector_y_sube_siguiente():
    r = _correr("""
barra.setProperty("instantaneo", False)
poner(["c", "a:0.85", "p", "p", "p", "p"])
poner(["c", "a:0.85", "p", "p", "p", "p"])
poner(["c", "c", "a:0.1", "p", "p", "p"])
r["inicio_nivel_siguiente"] = p(circ(2), "nivel")
r["inicio_conector"] = p(con(2), "progreso")
esperar(450)
r["conector_medio"] = p(con(2), "progreso")
r["cierre"] = p(circ(1), "nivel")
esperar(1800)
r["fin_conector"] = p(con(2), "progreso")
r["fin_nivel"] = p(circ(2), "nivel")
r["fin_cierre"] = p(circ(1), "nivel")
r["fin_ampl_cierre"] = p(circ(1), "amplitudOnda")
""")
    assert r["avisos"] == []
    assert r["inicio_nivel_siguiente"] == 0
    assert r["inicio_conector"] == 0
    assert 0 < r["conector_medio"] < 1
    assert r["cierre"] == pytest.approx(1.0, abs=0.02)
    assert r["fin_conector"] == 1.0
    assert r["fin_nivel"] == pytest.approx(0.1)
    assert r["fin_cierre"] == 1.0 and r["fin_ampl_cierre"] == 0


def test_salto_de_varias_fases():
    r = _correr("""
barra.setProperty("instantaneo", False)
poner(["c", "a:0.5", "p", "p", "p", "p"])
poner(["c", "a:0.5", "p", "p", "p", "p"])
poner(["c", "c", "c", "a:0.2", "p", "p"])
esperar(700)
r["niveles"] = [p(circ(i), "nivel") for i in range(4)]
r["conectores"] = [p(con(i), "progreso") for i in range(1, 6)]
r["amplitudes"] = [p(circ(i), "amplitudOnda") for i in range(3)]
""")
    assert r["avisos"] == []
    assert r["niveles"][:3] == [1.0, 1.0, 1.0]
    assert r["niveles"][3] == pytest.approx(0.2)
    assert r["conectores"] == [1.0, 1.0, 1.0, 0.0, 0.0]
    assert r["amplitudes"] == [0, 0, 0]


def test_fallo_a_mitad_de_la_secuencia():
    r = _correr("""
barra.setProperty("instantaneo", False)
poner(["c", "a:0.85", "p", "p", "p", "p"])
poner(["c", "a:0.85", "p", "p", "p", "p"])
poner(["c", "c", "a:0.1", "p", "p", "p"])
esperar(250)                                       # el cierre y el conector siguen en curso
poner(["c", "c", "f", "p", "p", "p"])
esperar(500)
r["color"] = circ(2).property("color").name().upper()
r["estado"] = p(circ(2), "estado")
r["nivel_visual"] = p(circ(2), "nivelVisual")
r["lleno"] = p(circ(2), "_lleno")
r["ampl"] = p(circ(2), "amplitudOnda")
r["chorro"] = p(circ(2), "chorroVisible")
r["cierre"] = p(circ(1), "nivel")
r["conector"] = p(con(2), "progreso")
poner(["c", "c", "i", "p", "p", "p"])
esperar(400)
r["color_interrumpida"] = circ(2).property("color").name().upper()
""")
    assert r["avisos"] == []
    assert r["color"] == "#EE0000" and r["estado"] == "fallida"
    assert r["lleno"] is False and r["ampl"] == 0 and r["chorro"] is False
    assert r["cierre"] == 1.0 and r["conector"] == 1.0
    assert r["color_interrumpida"] == "#FF9933"


def test_recalculo_baja_con_transicion_y_reinicio_a_cero():
    r = _correr("""
barra.setProperty("instantaneo", False)
poner(["c", "c", "c", "a:0.9", "p", "p"])
poner(["c", "c", "c", "a:0.9", "p", "p"])
poner(["c", "c", "c", "a:0.75", "p", "p"])
esperar(200)
r["bajando"] = p(circ(3), "nivel")
esperar(1300)
r["abajo"] = p(circ(3), "nivel")
poner(["c", "c", "c", "a:0.0", "p", "p"])
esperar(1400)
r["cero"] = p(circ(3), "nivel")
""")
    assert r["avisos"] == []
    assert 0.75 < r["bajando"] < 0.9
    assert r["abajo"] == pytest.approx(0.75, abs=0.01)
    assert r["cero"] == pytest.approx(0.0, abs=0.01)
