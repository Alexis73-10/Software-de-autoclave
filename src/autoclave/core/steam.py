#
# Constantes NIST WebBook para agua líquida, rango válido 99–145 °C.
# log₁₀(P_kPa) = A - B / (C + T_celsius)

_A = 7.26509
_B = 1810.94
_C = 244.485


def p_saturacion_kpa(t_celsius: float) -> float:
    """Presión de saturación del vapor de agua en kPa absolutos. Rango válido: 99–145°C."""
    return 10 ** (_A - _B / (_C + t_celsius))
