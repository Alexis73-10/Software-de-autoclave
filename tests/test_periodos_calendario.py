# tests/test_periodos_calendario.py
#
# Periodos de calendario del Historial (utils/periodos.py): rango del día, de la
# semana (lunes a domingo) y del mes, y navegación con las flechas.

from datetime import date

import pytest

from autoclave.utils import periodos

_HOY = date(2026, 10, 6)   # martes


@pytest.mark.parametrize("periodo, fecha, inicio, fin", [
    ("dia",    date(2026, 10, 2),  date(2026, 10, 2),  date(2026, 10, 3)),
    ("semana", date(2026, 10, 2),  date(2026, 9, 28),  date(2026, 10, 5)),
    ("semana", date(2026, 10, 4),  date(2026, 9, 28),  date(2026, 10, 5)),
    ("mes",    date(2026, 2, 14),  date(2026, 2, 1),   date(2026, 3, 1)),
    ("mes",    date(2026, 12, 31), date(2026, 12, 1),  date(2027, 1, 1)),
])
def test_rango(periodo, fecha, inicio, fin):
    assert periodos.rango(periodo, fecha) == (inicio, fin)


def test_periodo_desconocido():
    with pytest.raises(ValueError):
        periodos.rango("anio", _HOY)


@pytest.mark.parametrize("periodo, fecha, pasos, esperado", [
    ("dia",    date(2026, 10, 6), -1, date(2026, 10, 5)),
    ("semana", date(2026, 10, 6), -1, date(2026, 9, 28)),    # lunes de la semana anterior
    ("mes",    date(2026, 10, 6), -1, date(2026, 9, 1)),
    ("mes",    date(2026, 1, 31), -1, date(2025, 12, 1)),     # cambio de año
    ("mes",    date(2025, 12, 1),  1, date(2026, 1, 1)),
    ("mes",    date(2026, 10, 6), -12, date(2025, 10, 1)),
])
def test_desplazar(periodo, fecha, pasos, esperado):
    assert periodos.desplazar(periodo, fecha, pasos, _HOY) == esperado


@pytest.mark.parametrize("periodo", ["dia", "semana", "mes"])
def test_desplazar_no_pasa_del_periodo_actual(periodo):
    assert periodos.desplazar(periodo, _HOY, 1, _HOY) == _HOY
    assert periodos.desplazar(periodo, _HOY, 5, _HOY) == _HOY


def test_es_actual():
    assert periodos.es_actual("mes", date(2026, 10, 1), _HOY)
    assert not periodos.es_actual("mes", date(2026, 9, 30), _HOY)
    assert periodos.es_actual("semana", date(2026, 10, 5), _HOY)
    assert not periodos.es_actual("dia", date(2026, 10, 5), _HOY)
