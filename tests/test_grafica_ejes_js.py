# tests/test_grafica_ejes_js.py
#
# Lógica pura de la gráfica de la pantalla de ciclo en curso
# (qml/Componentes/grafica_ejes.mjs, planeacion_pantalla_ciclo_en_curso.md §8):
# ejes autoajustables con pasos "limpios" y decimación mín/máx por columna.

import json
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

MODULO = (Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml"
          / "qml" / "Componentes" / "grafica_ejes.mjs")


@pytest.fixture(scope="module")
def js():
    QCoreApplication.instance() or QCoreApplication(sys.argv)   # QJSEngine la necesita
    motor = QJSEngine()
    modulo = motor.importModule(str(MODULO))
    assert not modulo.isError(), modulo.toString()

    def llamar(nombre, *args):
        f = modulo.property(nombre)
        assert f.isCallable(), nombre
        r = f.call([motor.toScriptValue(a) for a in args])
        assert not r.isError(), r.toString()
        return json.loads(motor.globalObject().property("JSON").property("stringify").call([r]).toString())

    yield llamar
    del motor


# ── eje X (minutos) ─────────────────────────────────────────────────────

@pytest.mark.parametrize("t_min, maximo, paso", [
    (0.0, 1, 1),        # sin datos aún: una marca
    (0.4, 1, 1),
    (3.2, 4, 1),
    (8.0, 8, 1),
    (8.1, 10, 2),
    (38.6, 40, 5),      # caso del mockup: 0..40 cada 5
    (40.0, 40, 5),
    (75.0, 80, 10),
    (100.0, 105, 15),
    (200.0, 210, 30),
    (300.0, 300, 60),
])
def test_eje_x_paso_limpio_sin_pasar_de_8_intervalos(js, t_min, maximo, paso):
    assert js("ejeX", t_min) == {"maximo": maximo, "paso": paso}


def test_eje_x_muy_largo_sigue_con_pasos_de_60(js):
    r = js("ejeX", 700.0)
    assert r["paso"] == 60 and r["maximo"] == 720


# ── ejes Y (5 divisiones, mínimo 0) ─────────────────────────────────────

@pytest.mark.parametrize("dato_max, maximo, paso", [
    (131.0, 150, 30),   # temperatura del mockup
    (100.0, 125, 25),   # margen 5 %: 105 / 5 = 21 -> paso 25
    (304.0, 400, 80),   # presión absoluta a 134 °C
    (101.3, 125, 25),
    (9.0, 10, 2),
])
def test_eje_y_cinco_divisiones_paso_limpio(js, dato_max, maximo, paso):
    assert js("ejeY", dato_max) == {"maximo": maximo, "paso": paso, "divisiones": 5}


@pytest.mark.parametrize("dato_max", [None, 0, -5])
def test_eje_y_sin_datos_positivos_usa_escala_minima(js, dato_max):
    r = js("ejeY", dato_max)
    assert r["maximo"] > 0 and r["maximo"] == r["paso"] * 5


# ── decimación ──────────────────────────────────────────────────────────

def test_decimar_no_toca_series_cortas(js):
    xs = [0, 1, 2, 3]
    ys = [5, 6, 7, 8]
    assert js("decimar", xs, ys, 0, 3, 100) == {"x": xs, "y": ys}


def test_decimar_conserva_picos_por_columna(js):
    n = 10000
    xs = [i / 10 for i in range(n)]               # 0 .. 999.9
    ys = [0.0] * n
    ys[4321] = 500.0                              # pico aislado
    ys[7777] = -40.0                              # valle aislado
    r = js("decimar", xs, ys, 0, xs[-1], 200)
    assert len(r["x"]) <= 200 * 4
    assert 500.0 in r["y"] and -40.0 in r["y"]
    assert r["x"] == sorted(r["x"])               # sigue ordenada en el tiempo
    assert r["x"][0] == 0 and r["x"][-1] == xs[-1]


def test_decimar_salta_huecos_sin_lectura(js):
    xs = [0, 1, 2, 3]
    ys = [5, None, 7, 8]
    assert js("decimar", xs, ys, 0, 3, 100) == {"x": [0, 2, 3], "y": [5, 7, 8]}
