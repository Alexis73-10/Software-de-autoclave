#
# Constantes NIST WebBook para agua líquida, rango válido 99–145 °C.
# log₁₀(P_kPa) = A - B / (C + T_celsius)

import math

_A = 7.26509
_B = 1810.94
_C = 244.485


def p_saturacion_kpa(t_celsius: float) -> float:
    """Presión de saturación del vapor de agua en kPa absolutos. Rango válido: 99–145°C."""
    return 10 ** (_A - _B / (_C + t_celsius))


def t_saturacion_c(p_kpa: float) -> float:
    """Temperatura de saturación (°C) para una presión en kPa absolutos.

    Inversa exacta de `p_saturacion_kpa` (misma ecuación de Antoine):
    T = B / (A - log₁₀(P)) - C. Rango válido equivalente a 99–145 °C; fuera
    de él devuelve el valor calculado sin recortar, igual que
    `p_saturacion_kpa`. `p_kpa <= 0` o no finito → `ValueError`.
    """
    if not math.isfinite(p_kpa) or p_kpa <= 0:
        raise ValueError(f"presión no válida para t_saturacion_c: {p_kpa!r}")
    return _B / (_A - math.log10(p_kpa)) - _C
