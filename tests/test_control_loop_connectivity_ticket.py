from unittest.mock import MagicMock, patch


class _FakeEstado:
    def __init__(self):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self.sensores_di = {"paro_emergencia": 0, "suministro_electrico": 1}

    def get_machine_state(self):
        from autoclave.state_machine.machine.enum_global import GlobalState
        return GlobalState.PREPARACION

    def get_flag(self, name):
        return self._flags.get(name, False)

    def set_flag(self, name, value):
        self._flags[name] = value

    def update(self, data):
        pass


def _make_loop(realtime_printer=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = MagicMock()

    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(
            units=MagicMock(),
            door_service=MagicMock(),
            doors=[],
            estado=_FakeEstado(),
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
            realtime_printer=realtime_printer,
        )
    return loop


def _run_one_tick(loop, connected):
    loop.link.is_connected.return_value = connected
    loop._running.set()

    def _stop(*_a, **_k):
        loop._running.clear()

    with patch("time.sleep", side_effect=_stop):
        loop.run()


def test_desconexion_imprime_ticket():
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    assert loop.link_was_connected is True  # estado primado

    _run_one_tick(loop, connected=False)

    printer.enqueue.assert_called_once()
    texto = printer.enqueue.call_args.args[0]
    assert "TARJETA: DESCONECTADA" in texto


def test_reconexion_imprime_ticket():
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    loop.link_was_connected = False  # simula que ya estaba desconectada

    _run_one_tick(loop, connected=True)

    printer.enqueue.assert_called_once()
    texto = printer.enqueue.call_args.args[0]
    assert "TARJETA: RECONECTADA" in texto


def test_conexion_estable_no_imprime():
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    assert loop.link_was_connected is True

    _run_one_tick(loop, connected=True)

    printer.enqueue.assert_not_called()


def test_sin_realtime_printer_no_rompe():
    loop = _make_loop(realtime_printer=None)

    _run_one_tick(loop, connected=False)  # no debe lanzar excepción
