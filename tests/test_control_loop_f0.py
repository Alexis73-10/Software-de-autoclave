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

    def set_flag(self, name, value):
        # EmergencyStop publica el paro al construirse (D-16)
        pass


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
    # el ciclo corre con la copia del programa (T-17); aquí, el mismo doble
    loop.state_machine.ciclo.programa_en_curso = cycle
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


def test_usa_solo_el_sensor_principal():
    # Tanda 2026-10-14 §1.1: F0 usa solo el Principal (ya no el mínimo
    # temp_camara/temp_2_camara). Principal por omisión = temp_camara.
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_2_camara"] = 100.0  # no en uso: no cuenta
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

    assert f0_con_liquido == estado2.f0_acumulado > 0


def test_principal_temp_2_camara_acumula_con_ese_sensor():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_2_camara"] = 121.1
    loop, estado, _ = _make_loop(estado=estado, cap=MagicMock(has_liquid_sensor=True))
    programa = MagicMock()
    programa.sensores = {"temp_camara": "no_en_uso", "temp_2_camara": "principal",
                         "temp_ref": "no_en_uso"}
    programa.get_param.return_value = True
    loop.programa_en_ejecucion = lambda: programa
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert abs(estado.f0_acumulado - 1.0) < 1e-6     # 1 min a 121.1 °C = F0 1


def test_equipo_no_lab_no_acumula_f0():
    estado = _FakeEstado()
    estado.sensores_temp["temp_camara"] = 134.0
    loop, estado, _ = _make_loop(estado=estado, cap=MagicMock(has_liquid_sensor=False))
    loop._acumular_f0(now=1000.0)
    loop._acumular_f0(now=1060.0)
    assert estado.f0_acumulado == 0.0


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
