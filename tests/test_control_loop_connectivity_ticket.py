from unittest.mock import MagicMock, patch


class _FakeEstado:
    def __init__(self):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self.sensores_di = {"paro_emergencia": 0, "suministro_electrico": 1}
        self.sensores_temp = {"temp_camara": None}
        self.fase_ciclo = ""
        self.f0_acumulado = 0.0

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


def test_arranque_sin_tarjeta_no_imprime():
    """Al arrancar, la tarjeta aún no respondió (handshake serial en curso).
    Esto NO es una desconexión real — no debe imprimirse nada."""
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    assert loop.link_was_connected is True  # estado primado
    assert loop._link_ever_connected is False

    _run_one_tick(loop, connected=False)

    printer.enqueue.assert_not_called()


def test_arranque_conexion_inicial_no_imprime():
    """La tarjeta conecta por primera vez tras el arranque — es el final
    normal del handshake, no una 'reconexión'. No debe imprimirse nada."""
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    loop.link_was_connected = False       # arranque aún sin datos
    loop._link_ever_connected = False     # nunca estuvo realmente conectada

    _run_one_tick(loop, connected=True)

    printer.enqueue.assert_not_called()


def test_desconexion_real_imprime_ticket():
    """Una vez que la tarjeta ya estuvo conectada de verdad, una caída real
    durante la sesión sí debe imprimirse."""
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    loop.link_was_connected = True
    loop._link_ever_connected = True      # ya hubo conexión real antes

    _run_one_tick(loop, connected=False)

    printer.enqueue.assert_called_once()
    texto = printer.enqueue.call_args.args[0]
    assert "TARJETA: DESCONECTADA" in texto


def test_reconexion_real_imprime_ticket():
    """Reconexión tras una caída real (no el handshake inicial) sí se imprime."""
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    loop.link_was_connected = False       # simula que ya estaba desconectada
    loop._link_ever_connected = True      # ...tras haber estado conectada de verdad

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


def test_control_loop_pasa_door_service_a_state_machine():
    from unittest.mock import patch
    from autoclave.services.domain.loop.control_loop import ControlLoop

    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = MagicMock()
    door_service = MagicMock()

    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as MockSM:
        ControlLoop(
            units=MagicMock(),
            door_service=door_service,
            doors=[],
            estado=_FakeEstado(),
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
        )

    _, kwargs = MockSM.call_args
    assert kwargs["door_service"] is door_service
