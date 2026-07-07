from unittest.mock import MagicMock, patch

from autoclave.state_machine.machine.enum_global import GlobalState


class _FakeEstado:
    """Estado mínimo que soporta la interfaz usada por ControlLoop/StateMachine."""

    def __init__(self):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self._state = GlobalState.PREPARACION
        self.sensores_di = {"paro_emergencia": 0, "suministro_electrico": 1}

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


def _make_control_loop(estado=None, doors=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    estado = estado or _FakeEstado()
    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = MagicMock()

    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as mock_sm_cls:
        loop = ControlLoop(
            units=MagicMock(),
            door_service=MagicMock(),
            doors=doors if doors is not None else [],
            estado=estado,
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
        )
    return loop, mock_sm_cls.return_value, estado


def _run_one_tick(loop):
    loop.link.is_connected.return_value = True
    loop._running.set()

    def _stop(*_a, **_k):
        loop._running.clear()

    with patch("time.sleep", side_effect=_stop):
        loop.run()


def test_enter_test_mode_pausa_y_apaga_salidas():
    loop, _, _ = _make_control_loop()

    ok, reason = loop.enter_test_mode()

    assert (ok, reason) == (True, "")
    assert loop.test_mode_active is True
    loop.set_do.reset_all_outputs.assert_called_once()


def test_enter_test_mode_bloqueado_en_ciclo():
    estado = _FakeEstado()
    estado.set_machine_state(GlobalState.CICLO)
    loop, _, _ = _make_control_loop(estado)

    ok, reason = loop.enter_test_mode()

    assert ok is False
    assert "ciclo" in reason.lower()
    assert loop.test_mode_active is False


def test_enter_test_mode_bloqueado_con_paro_emergencia_activo():
    estado = _FakeEstado()
    estado.set_flag("PARO_EMERGENCIA", True)
    loop, _, _ = _make_control_loop(estado)

    ok, reason = loop.enter_test_mode()

    assert ok is False
    assert "emergencia" in reason.lower()


def test_enter_test_mode_permitido_en_preparacion_y_preparado():
    for state in (GlobalState.PREPARACION, GlobalState.PREPARADO):
        estado = _FakeEstado()
        estado.set_machine_state(state)
        loop, _, _ = _make_control_loop(estado)

        ok, _ = loop.enter_test_mode()

        assert ok is True, f"debería permitir modo prueba en fase {state}"


def test_exit_test_mode_apaga_salidas_y_reanuda():
    loop, _, _ = _make_control_loop()
    loop.enter_test_mode()
    loop.set_do.reset_all_outputs.reset_mock()

    loop.exit_test_mode()

    assert loop.test_mode_active is False
    loop.set_do.reset_all_outputs.assert_called_once()


def test_run_no_actualiza_state_machine_en_modo_prueba():
    loop, mock_sm, _ = _make_control_loop()
    loop.enter_test_mode()

    _run_one_tick(loop)

    mock_sm.update.assert_not_called()


def test_run_actualiza_state_machine_fuera_de_modo_prueba():
    loop, mock_sm, _ = _make_control_loop()

    _run_one_tick(loop)

    mock_sm.update.assert_called_once()


def test_run_no_actualiza_puertas_en_modo_prueba():
    door = MagicMock()
    loop, _, _ = _make_control_loop(doors=[door])
    loop.enter_test_mode()

    _run_one_tick(loop)

    door.update.assert_not_called()


def test_run_actualiza_puertas_fuera_de_modo_prueba():
    door = MagicMock()
    loop, _, _ = _make_control_loop(doors=[door])

    _run_one_tick(loop)

    door.update.assert_called_once()


def test_run_en_modo_prueba_procesos_activos_vs_pausados():
    """Inventario completo de un tick en modo prueba: qué sigue corriendo y
    qué queda pausado. Documenta el comportamiento real (no el deseado)."""
    door = MagicMock()
    loop, mock_sm, estado = _make_control_loop(doors=[door])
    loop.cycle_logger = MagicMock()
    loop.enter_test_mode()

    loop.set_do.reset_mock()  # limpiar la llamada de reset_all_outputs de enter_test_mode

    _run_one_tick(loop)

    # PAUSADO en modo prueba
    mock_sm.update.assert_not_called()
    door.update.assert_not_called()
    loop.set_do.buzer.update.assert_not_called()

    # SIGUE CORRIENDO en modo prueba (por diseño: sensores y seguridad)
    assert estado.sensores_di.get("paro_emergencia") == 0  # paro_emergencia.update() sí corrió (no lanzó)
    loop.door_service.update.assert_called_once()
    loop.cycle_logger.update.assert_called_once()


def test_enter_test_mode_detiene_secuencia_de_buzzer():
    loop, _, _ = _make_control_loop()

    loop.enter_test_mode()

    loop.set_do.buzer.stop.assert_called_once()


def test_run_no_actualiza_buzzer_en_modo_prueba():
    loop, _, _ = _make_control_loop()
    loop.enter_test_mode()
    loop.set_do.buzer.reset_mock()

    _run_one_tick(loop)

    loop.set_do.buzer.update.assert_not_called()


def test_run_actualiza_buzzer_fuera_de_modo_prueba():
    loop, _, _ = _make_control_loop()

    _run_one_tick(loop)

    loop.set_do.buzer.update.assert_called_once()


def test_paro_emergencia_cancela_modo_prueba_y_reanuda_en_el_mismo_tick():
    loop, mock_sm, estado = _make_control_loop()
    loop.enter_test_mode()
    loop.set_do.reset_all_outputs.reset_mock()

    estado.sensores_di["paro_emergencia"] = 1

    _run_one_tick(loop)

    assert loop.test_mode_active is False
    loop.set_do.reset_all_outputs.assert_called()
    mock_sm.update.assert_called_once()
