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


# ── zoom (tanda 34, ZOM-02..ZOM-06) ─────────────────────────────────────

_AREA = {"x0": 93, "x1": 1035, "y0": 279, "y1": 709}     # 942 x 430 px
_COMPLETA = {"t0": 0, "t1": 40, "yIzq0": 0, "yIzq1": 150, "yDer0": 0, "yDer1": 400}


def _cerca(a, b, tol=1e-6):
    return all(abs(a[k] - b[k]) <= tol for k in b)


def test_sin_zoom_la_vista_completa_es_la_de_hoy(js):
    # ZOM-02: ejes desde 0, ejeX(tiempo actual) y ejeY(máximo de cada eje)
    v = js("vistaCompleta", js("ejeX", 38.6), js("ejeY", 131.0), js("ejeY", 304.0))
    assert v == {"t0": 0, "t1": 40, "yIzq0": 0, "yIzq1": 150, "yDer0": 0, "yDer1": 400}
    assert js("esVistaCompleta", v, _COMPLETA) is True
    assert js("acotarVentana", v, _COMPLETA) == v


@pytest.mark.parametrize("vmin, vmax, objetivo, esperado", [
    (15, 25, 8, [16, 18, 20, 22, 24]),            # 10 / 8 = 1,25 -> paso 2
    (110, 135, 5, [110, 115, 120, 125, 130, 135]),   # 25 / 5 = 5 -> paso 5
    (0, 40, 8, [0, 5, 10, 15, 20, 25, 30, 35, 40]),  # 40 / 8 = 5 -> paso 5
    (146.6667, 180, 5, [150, 160, 170, 180]),        # 6,67 -> paso 10
    (0.3, 1.1, 5, [0.4, 0.6, 0.8, 1.0]),             # 0,16 -> paso 0,2
    (2.5, 3.0, 8, [2.5, 2.6, 2.7, 2.8, 2.9, 3.0]),   # 0,0625 -> paso 0,1
])
def test_marcas_ventana_paso_redondo_sin_marcas_fuera(js, vmin, vmax, objetivo, esperado):
    r = js("marcasVentana", vmin, vmax, objetivo)
    assert r == pytest.approx(esperado)
    assert all(vmin - 1e-9 <= v <= vmax + 1e-9 for v in r)
    paso = r[1] - r[0]
    mant = paso / 10 ** __import__("math").floor(__import__("math").log10(paso))
    assert round(mant, 6) in (1, 2, 5)
    assert len(r) - 1 <= objetivo


def test_marcas_ventana_degenerada_vacia(js):
    assert js("marcasVentana", 5, 5, 8) == []
    assert js("marcasVentana", 6, 5, 8) == []


def _gesto(xa, ya, xb, yb):
    return {"xa": xa, "ya": ya, "xb": xb, "yb": yb}


def test_gesto_horizontal_solo_amplia_el_tiempo(js):
    # dedos a 200 px en X y 0 en Y; se separan al doble en X, centrados en x = 564
    ini = _gesto(464, 494, 664, 494)
    act = _gesto(364, 494, 764, 494)
    v = js("ventanaPorGesto", _COMPLETA, ini, act, _AREA, 40)
    assert v["t1"] - v["t0"] == pytest.approx(20)                # factor 2
    tc = (564 - 93) / 942 * 40                                   # minuto bajo el centro
    assert v["t0"] + (564 - 93) / 942 * 20 == pytest.approx(tc)  # sigue bajo el centro
    assert (v["yIzq0"], v["yIzq1"], v["yDer0"], v["yDer1"]) == pytest.approx((0, 150, 0, 400))


def test_gesto_vertical_solo_amplia_los_valores(js):
    ini = _gesto(564, 444, 564, 544)     # 100 px en Y, 0 en X (bajo el umbral)
    act = _gesto(564, 394, 564, 594)     # 200 px: factor 2
    v = js("ventanaPorGesto", _COMPLETA, ini, act, _AREA, 40)
    assert (v["t0"], v["t1"]) == pytest.approx((0, 40))
    assert v["yIzq1"] - v["yIzq0"] == pytest.approx(75)
    assert v["yDer1"] - v["yDer0"] == pytest.approx(200)
    # misma fracción de su escala completa en los dos ejes Y
    assert v["yIzq0"] / 150 == pytest.approx(v["yDer0"] / 400)
    assert v["yIzq1"] / 150 == pytest.approx(v["yDer1"] / 400)


def test_gesto_diagonal_amplia_los_dos(js):
    ini = _gesto(464, 444, 664, 544)
    act = _gesto(364, 394, 764, 594)
    v = js("ventanaPorGesto", _COMPLETA, ini, act, _AREA, 40)
    assert v["t1"] - v["t0"] == pytest.approx(20)
    assert v["yIzq1"] - v["yIzq0"] == pytest.approx(75)


def test_gesto_separacion_inicial_bajo_el_umbral_no_escala_ese_eje(js):
    # 30 px en X (< 40) que pasan a 300: X no se escala; Y sí (100 -> 200)
    ini = _gesto(549, 444, 579, 544)
    act = _gesto(414, 394, 714, 594)
    v = js("ventanaPorGesto", _COMPLETA, ini, act, _AREA, 40)
    assert v["t1"] - v["t0"] == pytest.approx(40)
    assert v["yIzq1"] - v["yIzq0"] == pytest.approx(75)


def test_gesto_desplaza_con_el_punto_medio(js):
    ventana = {"t0": 10, "t1": 20, "yIzq0": 60, "yIzq1": 90, "yDer0": 160, "yDer1": 240}
    ini = _gesto(400, 400, 600, 500)
    act = _gesto(400 - 94.2, 400 + 43, 600 - 94.2, 500 + 43)   # sin cambio de separación
    v = js("ventanaPorGesto", ventana, ini, act, _AREA, 40)
    # 94,2 px a la izquierda = 1/10 del ancho -> la ventana avanza 1 min
    assert (v["t0"], v["t1"]) == pytest.approx((11, 21))
    # 43 px hacia abajo = 1/10 del alto -> los valores suben 1/10 de la ventana
    assert (v["yIzq0"], v["yIzq1"]) == pytest.approx((63, 93))
    assert (v["yDer0"], v["yDer1"]) == pytest.approx((168, 248))


def test_limites_no_se_aleja_mas_alla_de_la_vista_completa(js):
    lejos = {"t0": -30, "t1": 90, "yIzq0": -50, "yIzq1": 300, "yDer0": -100, "yDer1": 900}
    assert js("acotarVentana", lejos, _COMPLETA) == _COMPLETA


def test_limites_desplazar_queda_dentro(js):
    fuera = {"t0": 35, "t1": 45, "yIzq0": -10, "yIzq1": 20, "yDer0": 390, "yDer1": 470}
    v = js("acotarVentana", fuera, _COMPLETA)
    assert (v["t0"], v["t1"]) == pytest.approx((30, 40))
    assert (v["yIzq0"], v["yIzq1"]) == pytest.approx((0, 30))
    assert (v["yDer0"], v["yDer1"]) == pytest.approx((320, 400))


def test_limites_ventana_minima(js):
    chica = {"t0": 20, "t1": 20.5, "yIzq0": 100, "yIzq1": 101, "yDer0": 200, "yDer1": 201}
    v = js("acotarVentana", chica, _COMPLETA)
    assert v["t1"] - v["t0"] == pytest.approx(2)            # 2 min
    assert v["yIzq1"] - v["yIzq0"] == pytest.approx(15)     # 10 % de 150
    assert v["yDer1"] - v["yDer0"] == pytest.approx(40)     # 10 % de 400
    assert (v["t0"] + v["t1"]) / 2 == pytest.approx(20.25)  # centrada


def test_limites_vista_completa_menor_que_2_min_no_amplia_x(js):
    completa = dict(_COMPLETA, t1=1)
    v = js("acotarVentana", {**completa, "t0": 0.2, "t1": 0.4}, completa)
    assert (v["t0"], v["t1"]) == pytest.approx((0, 1))


def test_rueda_amplia_un_eje_centrado_en_el_puntero(js):
    v = js("ventanaPorRueda", _COMPLETA, "x", 2, 0.25)
    assert (v["t0"], v["t1"]) == pytest.approx((5, 25))
    assert v["yIzq1"] == 150
    v = js("ventanaPorRueda", _COMPLETA, "y", 2, 0.5)
    assert (v["yIzq0"], v["yIzq1"], v["yDer0"], v["yDer1"]) == pytest.approx((37.5, 112.5, 100, 300))
    assert (v["t0"], v["t1"]) == (0, 40)


def test_es_vista_completa_e_interpolar(js):
    zoom = {"t0": 15, "t1": 25, "yIzq0": 110, "yIzq1": 135, "yDer0": 293.3, "yDer1": 360}
    assert js("esVistaCompleta", zoom, _COMPLETA) is False
    medio = js("interpolarVentana", zoom, _COMPLETA, 0.5)
    assert medio["t0"] == pytest.approx(7.5) and medio["t1"] == pytest.approx(32.5)
    assert js("interpolarVentana", zoom, _COMPLETA, 1.0) == _COMPLETA


def test_tramo_ventana_con_un_vecino_a_cada_lado(js):
    xs = [0, 1, 2, 3, 4, 5, 6]
    assert js("tramoVentana", xs, 2.5, 4.5) == {"desde": 2, "hasta": 5}
    assert js("tramoVentana", xs, 0, 6) == {"desde": 0, "hasta": 6}
    assert js("tramoVentana", xs, 2, 4) == {"desde": 1, "hasta": 5}
    assert js("tramoVentana", [], 0, 1) == {"desde": 0, "hasta": -1}


def test_continua_datos_distingue_otro_ciclo(js):
    h = js("huellaDatos", [0, 0.5, 1.0])
    assert js("continuaDatos", h, [0, 0.5, 1.0, 1.5]) is True     # lecturas nuevas
    assert js("continuaDatos", h, [0, 0.5, 1.0]) is True
    assert js("continuaDatos", h, [0, 0.4, 0.9, 1.3]) is False    # otro ciclo
    assert js("continuaDatos", h, [0, 0.5]) is False              # más corto
    assert js("continuaDatos", h, []) is False                    # sin datos
    assert js("continuaDatos", None, [0, 1]) is True
