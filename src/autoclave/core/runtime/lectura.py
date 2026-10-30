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


def carga_enfriada(temp, temp_enfriamiento) -> bool:
    """True si la lectura del Principal está en o bajo la temperatura de
    enfriamiento (líquidos, modos 4/5). Falla cerrada (SAF-01 de T11): sin
    lectura válida o con 0 (sensor sin señal, SEN-03) NO está enfriada."""
    if not lectura_valida(temp) or float(temp) == 0 or not lectura_valida(temp_enfriamiento):
        return False
    return float(temp) <= float(temp_enfriamiento)
