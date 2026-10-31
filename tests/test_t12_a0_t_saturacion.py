"""Tanda 12 (A0): t_saturacion_c, inversa exacta de p_saturacion_kpa."""
import math

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa, t_saturacion_c


@pytest.mark.parametrize("t", [100.0 + 0.5 * i for i in range(91)])
def test_ida_y_vuelta_100_a_145(t):
    assert abs(t_saturacion_c(p_saturacion_kpa(t)) - t) < 1e-6


def test_valores_conocidos():
    assert abs(t_saturacion_c(101.325) - 100.0) < 0.2
    assert abs(t_saturacion_c(p_saturacion_kpa(134.0)) - 134.0) < 1e-9


def test_fuera_de_rango_no_recorta():
    # Igual que p_saturacion_kpa: devuelve el valor calculado sin recortar.
    assert t_saturacion_c(p_saturacion_kpa(90.0)) == pytest.approx(90.0, abs=1e-6)
    assert t_saturacion_c(p_saturacion_kpa(150.0)) == pytest.approx(150.0, abs=1e-6)


@pytest.mark.parametrize("p", [0.0, -1.0, -300.0, math.nan, math.inf, -math.inf])
def test_presion_invalida_lanza_valueerror(p):
    with pytest.raises(ValueError):
        t_saturacion_c(p)
