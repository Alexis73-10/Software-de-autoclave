# core/runtime/lectura.py
#
# Validación de lecturas analógicas (E0, CR-FC-01). Los conversores entregan
# None cuando el ADC lee fuera de rango; un valor no finito tampoco es un dato.

import math


def lectura_valida(valor) -> bool:
    """True solo si `valor` es un número finito. None, NaN, ±inf o un valor
    no numérico cuentan como lectura inválida (error de sensor)."""
    if valor is None or isinstance(valor, bool):
        return False
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError):
        return False
