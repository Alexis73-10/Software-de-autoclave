# tests/test_q1rev_f0_corte_enlace.py
"""Revisión Q1 (TMG-01 / SEN-03 parte F0): un corte del enlace o de la
primera DI no debe acreditar F0 por el tramo sin datos."""
from unittest.mock import patch

from tests.test_control_loop_f0 import _make_loop
from tests.test_control_loop_test_mode import _make_control_loop


def test_gap_mayor_a_dos_intervalos_no_acredita_y_reinicia_el_sello():
    loop, estado, _ = _make_loop()
    loop.interval = 0.5
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1030.0)        # 30 s sin ticks: no cuenta
    assert estado.f0_acumulado == 0.0
    assert loop._f0_ultimo_tick == 1030.0
    loop._acumular_f0(now=1030.5)        # tick normal tras el corte: acumula
    assert estado.f0_acumulado > 0.0


def test_tick_normal_sigue_acumulando_igual():
    loop, estado, _ = _make_loop()
    loop.interval = 0.5
    t = 1000.0
    loop._acumular_f0(now=t)
    for _ in range(120):                 # 60 s en ticks de 0,5 s
        t += 0.5
        loop._acumular_f0(now=t)
    loop2, estado2, _ = _make_loop()
    loop2.interval = 60.0
    loop2._acumular_f0(now=1000.0)
    loop2._acumular_f0(now=1060.0)
    assert abs(estado.f0_acumulado - estado2.f0_acumulado) < 1e-9
    assert estado.f0_acumulado > 0.0


def test_gap_justo_en_dos_intervalos_aun_acumula():
    loop, estado, _ = _make_loop()
    loop.interval = 0.5
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1001.0)
    assert estado.f0_acumulado > 0.0


def test_tick_sin_conexion_reinicia_el_sello_de_f0():
    loop, _, _ = _make_control_loop()
    loop._f0_ultimo_tick = 123.0
    loop.link.is_connected.return_value = False
    loop.link.expansor_fuera_de_linea.return_value = False
    loop._tick()
    assert loop._f0_ultimo_tick is None


def test_tick_esperando_primera_di_reinicia_el_sello_de_f0():
    loop, _, _ = _make_control_loop()
    loop.link.is_connected.return_value = True
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.link.edad_ultima_di.return_value = None     # recién conectado, sin DI
    loop._f0_ultimo_tick = 123.0
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic",
               return_value=500.0):
        loop._tick()
    assert loop._f0_ultimo_tick is None
