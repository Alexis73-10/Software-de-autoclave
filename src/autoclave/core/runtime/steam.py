#
# Saturación del agua según IAPWS-IF97, región 4 (tanda 13, VAP-01):
# ecuación 30 para ps(T) y ecuación 31 para Ts(p), forma cerrada, con los
# coeficientes n1..n10 de la tabla 34. La norma trabaja en K y MPa; aquí la
# entrada y la salida son °C y kPa absolutos (se convierte dentro).
# Antes se usaba una ecuación de Antoine que daba ≈2 kPa menos a 134 °C.
#
# Validez: 0.01–373.946 °C (273.16–647.096 K), es decir del punto triple al
# punto crítico; fuera de ese rango, o con entrada no finita → ValueError.
# No se recorta al rango de trabajo (99–145 °C).

import math

_N = (
    0.11670521452767e4,
    -0.72421316703206e6,
    -0.17073846940092e2,
    0.12020824702470e5,
    -0.32325550322333e7,
    0.14915108613530e2,
    -0.48232657361591e4,
    0.40511340542057e6,
    -0.23855557567849,
    0.65017534844798e3,
)

_KELVIN = 273.15
_T_MIN_C = 0.01         # punto triple, 273.16 K
_T_MAX_C = 373.946      # punto crítico, 647.096 K


def _ps_mpa(t_k: float) -> float:
    """Ecuación 30: presión de saturación (MPa) para T en K."""
    n = _N
    v = t_k + n[8] / (t_k - n[9])
    a = v * v + n[0] * v + n[1]
    b = n[2] * v * v + n[3] * v + n[4]
    c = n[5] * v * v + n[6] * v + n[7]
    return (2.0 * c / (-b + math.sqrt(b * b - 4.0 * a * c))) ** 4


def _ts_k(p_mpa: float) -> float:
    """Ecuación 31: temperatura de saturación (K) para p en MPa."""
    n = _N
    beta = p_mpa ** 0.25
    e = beta * beta + n[2] * beta + n[5]
    f = n[0] * beta * beta + n[3] * beta + n[6]
    g = n[1] * beta * beta + n[4] * beta + n[7]
    d = 2.0 * g / (-f - math.sqrt(f * f - 4.0 * e * g))
    return (n[9] + d - math.sqrt((n[9] + d) ** 2 - 4.0 * (n[8] + n[9] * d))) / 2.0


_P_MIN_KPA = _ps_mpa(_T_MIN_C + _KELVIN) * 1000.0   # ≈ 0.611657 kPa
_P_MAX_KPA = _ps_mpa(_T_MAX_C + _KELVIN) * 1000.0   # ≈ 22064 kPa, presión crítica


def p_saturacion_kpa(t_celsius: float) -> float:
    """Presión de saturación del vapor de agua en kPa absolutos (IAPWS-IF97,
    región 4). Rango válido: 0.01–373.946 °C; fuera de él o con entrada no
    finita → `ValueError`."""
    if not math.isfinite(t_celsius) or not _T_MIN_C <= t_celsius <= _T_MAX_C:
        raise ValueError(f"temperatura no válida para p_saturacion_kpa: {t_celsius!r}")
    return _ps_mpa(t_celsius + _KELVIN) * 1000.0


def t_saturacion_c(p_kpa: float) -> float:
    """Temperatura de saturación (°C) para una presión en kPa absolutos.

    Inversa de `p_saturacion_kpa` (IAPWS-IF97, región 4, ecuación 31). Rango
    válido equivalente: Psat(0.01 °C) ≈ 0.6117 kPa a 22064 kPa; `p_kpa <= 0`,
    fuera de rango o no finito → `ValueError`.
    """
    if not math.isfinite(p_kpa) or p_kpa <= 0 or not _P_MIN_KPA <= p_kpa <= _P_MAX_KPA:
        raise ValueError(f"presión no válida para t_saturacion_c: {p_kpa!r}")
    return _ts_k(p_kpa / 1000.0) - _KELVIN
