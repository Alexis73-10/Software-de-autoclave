# tests/test_q1rev_f0_pausa_di.py
"""Re-revisión Q1 (RR-01): F0 no suma durante la pausa por DI vencida. La
fase está detenida (CicloState, T2-a) pero fase_ciclo sigue en ESTERILIZACION
y los ticks llegan cada 0,5 s, así que el tope de 2 intervalos no actúa."""
from unittest.mock import patch

from tests.test_control_loop_f0 import _make_loop
from tests.test_control_loop_test_mode import _make_control_loop


def _loop_05():
    loop, estado, _ = _make_loop()
    loop.interval = 0.5
    loop.state_machine.ciclo.tolerancia_di_activa = False
    return loop, estado


def test_sin_datos_vigentes_no_suma_y_reinicia_el_sello():
    loop, estado = _loop_05()
    loop._acumular_f0(now=1000.0, vigentes=True)
    loop._acumular_f0(now=1000.5, vigentes=False)
    assert estado.f0_acumulado == 0.0
    assert loop._f0_ultimo_tick is None
    loop._acumular_f0(now=1001.0, vigentes=True)     # vuelve: solo inicializa
    assert estado.f0_acumulado == 0.0
    loop._acumular_f0(now=1001.5, vigentes=True)
    assert estado.f0_acumulado > 0.0


def test_con_la_tolerancia_di_activa_no_suma():
    loop, estado = _loop_05()
    loop._acumular_f0(now=1000.0, vigentes=True)
    loop.state_machine.ciclo.tolerancia_di_activa = True
    loop._acumular_f0(now=1000.5, vigentes=True)
    loop._acumular_f0(now=1001.0, vigentes=True)
    assert estado.f0_acumulado == 0.0
    assert loop._f0_ultimo_tick is None


def test_con_datos_vigentes_y_sin_tolerancia_sigue_sumando():
    loop, estado = _loop_05()
    loop._acumular_f0(now=1000.0, vigentes=True)
    loop._acumular_f0(now=1000.5, vigentes=True)
    assert estado.f0_acumulado > 0.0


def test_el_tick_pasa_los_datos_vigentes_al_acumulador():
    loop, _, _ = _make_control_loop()
    loop.link.is_connected.return_value = True
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.link.edad_ultima_di.return_value = 99.0          # DI vencida
    loop._conectado_desde = 0.0
    loop.link_was_connected = True
    llamadas = []
    loop._acumular_f0 = lambda now, vigentes=True: llamadas.append(vigentes)
    with patch("autoclave.services.domain.loop.control_loop.time.monotonic",
               return_value=500.0):
        loop._tick()
    assert llamadas == [False]
