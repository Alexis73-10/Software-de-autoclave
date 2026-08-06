# tests/test_letalidad.py
from autoclave.core.runtime.letalidad import calcular_incremento_f0


def test_incremento_a_temperatura_referencia_121_1_con_1_min_es_1():
    result = calcular_incremento_f0(t_ref_celsius=121.1, dt_min=1.0)
    assert abs(result - 1.0) < 1e-9


def test_incremento_a_101_grados_es_aproximadamente_0_01():
    result = calcular_incremento_f0(t_ref_celsius=101.0, dt_min=1.0)
    assert abs(result - 0.01) < 0.001


def test_incremento_muy_por_debajo_de_121_1_es_practicamente_cero():
    result = calcular_incremento_f0(t_ref_celsius=60.0, dt_min=1.0)
    assert result < 1e-4


def test_incremento_monotonico_con_temperatura_creciente():
    temps = [100.0, 110.0, 121.1, 130.0, 134.0]
    incrementos = [calcular_incremento_f0(t, 1.0) for t in temps]
    for i in range(len(incrementos) - 1):
        assert incrementos[i] < incrementos[i + 1]


def test_incremento_escala_linealmente_con_dt_min():
    base = calcular_incremento_f0(134.0, 1.0)
    doble = calcular_incremento_f0(134.0, 2.0)
    assert abs(doble - 2 * base) < 1e-9
