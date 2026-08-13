# tests/test_control_loop_audio_step.py
from unittest.mock import MagicMock, patch

from autoclave.state_machine.machine.enum_global import GlobalState


class _FakeEstado:
    def __init__(self):
        self._state = GlobalState.PREPARADO
        self.fase_ciclo = ""
        self.Alarmas_activas = []
        self.estado_puertas = {}
        self.camara_segura_confirmada = False
        self.sensores_di = {}
        self.sensores_temp = {}
        self.sensores_pres = {}
        self.salidas_do = {}
        self.flags = {}

    def get_machine_state(self):
        return self._state

    def get_flag(self, flag):
        return False

    def set_flag(self, flag, value):
        pass

    def update(self, datos):
        pass


def _make_loop(announcer_observer):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    estado = _FakeEstado()
    cycle = MagicMock()
    cycle.get_param.return_value = False
    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = cycle

    link = MagicMock()
    link.is_connected.return_value = True

    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(
            units=MagicMock(get_all=MagicMock(return_value={})),
            door_service=MagicMock(),
            doors=[],
            estado=estado,
            link=link,
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
            announcer_observer=announcer_observer,
        )
    return loop


def test_tick_llama_al_observador_de_audio_cuando_no_esta_en_modo_prueba():
    observer = MagicMock()
    loop = _make_loop(observer)
    loop._tick()
    observer.update.assert_called_once_with(loop.estado)


def test_tick_no_llama_al_observador_en_modo_prueba():
    observer = MagicMock()
    loop = _make_loop(observer)
    loop._test_mode.set()
    loop._tick()
    observer.update.assert_not_called()


def test_tick_no_falla_si_no_hay_observador_de_audio():
    loop = _make_loop(None)
    loop._tick()  # no debe lanzar
