# Letalidad acumulada (F0, ISO 17665): tiempo equivalente de esterilización
# a temperatura de referencia, z fijo. Ver docs/mis_plans/planeacion_f0.md.

_Z = 10.0
_T_REF_ISO = 121.1


def calcular_incremento_f0(t_ref_celsius: float, dt_min: float) -> float:
    """Incremento de letalidad acumulada (min equivalentes a 121.1°C) para
    un tick de duración dt_min a la temperatura de referencia t_ref_celsius."""
    return 10 ** ((t_ref_celsius - _T_REF_ISO) / _Z) * dt_min
