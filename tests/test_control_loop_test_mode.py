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


# ── Revisión de seguridad de la etapa 1 de autenticación (SAF-03, TMG-01/04) ──

def test_lock_de_la_maquina_es_reentrante():
    """El backend toma bloqueo_maquina() en su guard y dentro llama a
    enter/exit_test_mode, que también lo toman: no debe bloquearse."""
    loop, _, _ = _make_control_loop()
    with loop.bloqueo_maquina():
        assert loop.enter_test_mode() == (True, "")
        loop.exit_test_mode()
    assert loop.test_mode_active is False


def test_enter_y_exit_corren_con_el_lock_tomado():
    loop, _, _ = _make_control_loop()
    tomado = []
    loop.set_do.reset_all_outputs.side_effect = lambda: tomado.append(loop._sm_lock._is_owned())
    loop.enter_test_mode()
    loop.exit_test_mode()
    assert tomado == [True, True]


def test_exit_apaga_antes_de_reanudar():
    """Si reanudara primero, un tick podría correr la máquina de estados con
    las salidas de prueba todavía encendidas."""
    loop, _, _ = _make_control_loop()
    loop.enter_test_mode()
    en_prueba_al_apagar = []
    loop.set_do.reset_all_outputs.side_effect = lambda: en_prueba_al_apagar.append(loop.test_mode_active)
    loop.exit_test_mode()
    assert en_prueba_al_apagar == [True]
    assert loop.test_mode_active is False


def test_tick_decide_puertas_y_maquina_con_el_lock_tomado():
    """TMG-04: la comprobación de modo prueba y lo que depende de ella van
    dentro del mismo lock que usan enter/exit."""
    puerta = MagicMock()
    loop, mock_sm, _ = _make_control_loop(doors=[puerta])
    vistos = []
    puerta.update.side_effect = lambda: vistos.append(("puerta", loop._sm_lock._is_owned()))
    mock_sm.update.side_effect = lambda: vistos.append(("maquina", loop._sm_lock._is_owned()))
    _run_one_tick(loop)
    assert vistos == [("puerta", True), ("maquina", True)]


def test_cancelacion_por_paro_avisa_una_vez_y_fuera_del_lock():
    loop, _, estado = _make_control_loop()
    avisos = []
    loop.al_cancelar_modo_prueba(lambda: avisos.append(loop._sm_lock._is_owned()))
    loop.enter_test_mode()
    estado.sensores_di["paro_emergencia"] = 1

    _run_one_tick(loop)
    _run_one_tick(loop)   # ya fuera de modo prueba: no vuelve a avisar

    assert avisos == [False]


def test_cancelacion_por_paro_apaga_con_el_lock_tomado():
    loop, _, estado = _make_control_loop()
    loop.enter_test_mode()
    tomado = []
    loop.set_do.reset_all_outputs.side_effect = lambda: tomado.append(loop._sm_lock._is_owned())
    estado.sensores_di["paro_emergencia"] = 1
    _run_one_tick(loop)
    assert tomado and all(tomado)


def test_error_en_un_aviso_no_rompe_el_tick():
    loop, mock_sm, estado = _make_control_loop()
    loop.al_cancelar_modo_prueba(lambda: 1 / 0)
    loop.enter_test_mode()
    estado.sensores_di["paro_emergencia"] = 1
    _run_one_tick(loop)
    assert loop.test_mode_active is False
    mock_sm.update.assert_called_once()
