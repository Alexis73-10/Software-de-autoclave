# tests/test_control_loop_f0.py
from unittest.mock import MagicMock, patch

from autoclave.state_machine.machine.enum_global import GlobalState


class _FakeEstado:
    def __init__(self):
        self._state = GlobalState.CICLO
        self.fase_ciclo = "CALENTAMIENTO"
        self.sensores_temp = {"temp_camara": 134.0, "temp_2_camara": None}
        self.f0_acumulado = 0.0

    def get_machine_state(self):
        return self._state


def _make_loop(estado=None, cap=None, f0_activo=True):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    estado = estado or _FakeEstado()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, nombre, default=None: {
        ("globals", "F0"): f0_activo,
    }.get((seccion, nombre), default)
    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = cycle

    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(
            units=MagicMock(),
            door_service=MagicMock(),
            doors=[],
            estado=estado,
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
            cap=cap,
        )
    return loop, estado, cycle


def test_primer_tick_tras_entrar_no_acumula_solo_inicializa_timestamp():
    loop, estado, _ = _make_loop()
    loop._acumular_f0(now=1000.0)
    assert estado.f0_acumulado == 0.0
    assert loop._f0_ultimo_tick == 1000.0


def test_segundo_tick_acumula_con_dt_real_transcurrido():
    loop, estado, _ = _make_loop()
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)  # 60s = 1 min después
    # temp_camara = 134.0 -> incremento por minuto bastante mayor que 0
    assert estado.f0_acumulado > 0.0


def test_no_acumula_fuera_de_ciclo():
    estado = _FakeEstado()
    estado._state = GlobalState.PREPARADO
    loop, estado, _ = _make_loop(estado=estado)
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado == 0.0


def test_no_acumula_si_fase_no_esta_en_conjunto_que_acumula():
    estado = _FakeEstado()
    estado.fase_ciclo = "PRE_VACIO"
    loop, estado, _ = _make_loop(estado=estado)
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado == 0.0


def test_no_acumula_si_f0_esta_desactivado_en_el_ciclo():
    loop, estado, _ = _make_loop(f0_activo=False)
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado == 0.0


def test_no_acumula_ni_lanza_excepcion_si_temp_camara_es_none():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = None
    loop, estado, _ = _make_loop(estado=estado)
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado == 0.0


def test_usa_el_minimo_entre_ambos_sensores_cuando_hay_sensor_de_liquido():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_2_camara"] = 100.0  # el líquido va más atrás -> debe dominar
    cap = MagicMock(has_liquid_sensor=True)
    loop, estado, _ = _make_loop(estado=estado, cap=cap)
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    f0_con_liquido = estado.f0_acumulado

    estado2 = _FakeEstado()
    estado2.sensores_temp["temp_camara"] = 134.0
    loop2, estado2, _ = _make_loop(estado=estado2, cap=None)
    loop2._acumular_f0(now=1000.0)
    loop2._acumular_f0(now=1060.0)
    f0_solo_camara = estado2.f0_acumulado

    assert f0_con_liquido < f0_solo_camara


def test_degrada_a_temp_camara_si_hay_liquido_sensor_pero_sin_lectura():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_2_camara"] = None
    cap = MagicMock(has_liquid_sensor=True)
    loop, estado, _ = _make_loop(estado=estado, cap=cap)
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado > 0.0


def test_transicion_calentamiento_a_esterilizacion_no_reinicia_dt():
    """Ambas fases están en el conjunto que acumula: el timestamp no debe
    reiniciarse en la transición (acumulación continua)."""
    loop, estado, _ = _make_loop()
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    acumulado_antes = estado.f0_acumulado
    estado.fase_ciclo = "ESTERILIZACION"
    loop._acumular_f0(now=1120.0)
    assert estado.f0_acumulado > acumulado_antes
