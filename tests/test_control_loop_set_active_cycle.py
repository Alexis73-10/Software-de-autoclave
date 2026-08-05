from unittest.mock import MagicMock, patch

from autoclave.state_machine.machine.enum_global import GlobalState


class _FakeEstado:
    """Estado mínimo que soporta la interfaz usada por ControlLoop/StateMachine."""

    def __init__(self):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self._state = GlobalState.PREPARACION
        self.sensores_di = {"paro_emergencia": 0, "suministro_electrico": 1}
        self.Alarmas_activas = []  # Required by AlarmManager

    def get_machine_state(self):
        return self._state

    def set_machine_state(self, state):
        self._state = state

    def get_flag(self, name):
        return self._flags.get(name, False)

    def set_flag(self, name, value):
        self._flags[name] = value

    def update(self, data):
        pass


def _make_control_loop(estado=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    estado = estado or _FakeEstado()
    cycle_manager = MagicMock()
    initial_cycle = MagicMock(name="initial_cycle")
    cycle_manager.get_selected_cycle.return_value = initial_cycle

    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as mock_sm_cls:
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
            cap="fake_cap",
        )
    return loop, mock_sm_cls, initial_cycle, estado


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_set_active_cycle_permitido_fuera_de_ciclo_reconstruye_state_machine(mock_sm_class):
    loop, mock_sm_cls, _, _ = _make_control_loop()
    mock_sm_class.reset_mock()
    new_cycle = MagicMock(name="new_cycle")

    ok, reason = loop.set_active_cycle(new_cycle)

    assert (ok, reason) == (True, "")
    assert loop.cycle is new_cycle
    mock_sm_class.assert_called_once_with(
        io=loop.link, estado=loop.estado, set_do=loop.set_do,
        cycle=new_cycle, config=loop.config_manager, cap="fake_cap",
    )
    assert loop.state_machine is mock_sm_class.return_value


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_set_active_cycle_bloqueado_en_ciclo(mock_sm_class):
    estado = _FakeEstado()
    estado.set_machine_state(GlobalState.CICLO)
    loop, mock_sm_cls, initial_cycle, _ = _make_control_loop(estado)
    mock_sm_class.reset_mock()
    new_cycle = MagicMock(name="new_cycle")

    ok, reason = loop.set_active_cycle(new_cycle)

    assert ok is False
    assert "ciclo" in reason.lower()
    assert loop.cycle is initial_cycle
    mock_sm_class.assert_not_called()


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_set_active_cycle_permitido_en_estados_no_ciclo(mock_sm_class):
    for state in (GlobalState.PREPARACION, GlobalState.PREPARADO,
                  GlobalState.FALLA, GlobalState.HIBERNACION):
        estado = _FakeEstado()
        estado.set_machine_state(state)
        loop, mock_sm_cls, _, _ = _make_control_loop(estado)
        mock_sm_class.reset_mock()

        ok, _ = loop.set_active_cycle(MagicMock())

        assert ok is True, f"debería permitir cambio de ciclo en estado {state}"
