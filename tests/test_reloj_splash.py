# tests/test_reloj_splash.py
from datetime import datetime

from autoclave.ui_qml.domain.reloj_splash import formatear_fecha, formatear_hora


# ── formatear_hora ───────────────────────────────────────────────────────

def test_formatea_hora_hh_mm_24h():
    assert formatear_hora(datetime(2026, 8, 12, 16, 0)) == "16:00"


def test_formatea_hora_con_ceros_a_la_izquierda():
    assert formatear_hora(datetime(2026, 8, 12, 9, 5)) == "09:05"


def test_formatea_hora_ignora_segundos():
    assert formatear_hora(datetime(2026, 8, 12, 23, 59, 47)) == "23:59"


# ── formatear_fecha ──────────────────────────────────────────────────────

def test_formatea_fecha_con_mes_abreviado_espanol_minuscula():
    assert formatear_fecha(datetime(2026, 10, 12)) == "12 oct - 2026"


def test_formatea_fecha_dia_con_cero_a_la_izquierda():
    assert formatear_fecha(datetime(2026, 1, 5)) == "05 ene - 2026"


def test_formatea_fecha_todos_los_meses_sin_tilde():
    abreviaturas_esperadas = [
        "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic",
    ]
    for mes, esperado in enumerate(abreviaturas_esperadas, start=1):
        fecha = formatear_fecha(datetime(2026, mes, 1))
        assert fecha.split(" ")[1] == esperado
        assert all(c.islower() or not c.isalpha() for c in fecha)
