from unittest.mock import MagicMock

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_set_active_cycle import _FakeEstado


def _loop():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = _FakeEstado()
    cm = MagicMock()
    am = MagicMock(name="alarm_manager")
    loop = ControlLoop(
        units=MagicMock(), door_service=MagicMock(), doors=[], estado=estado,
        link=MagicMock(), set_do=MagicMock(), alarm_manager=am,
        cycle_manager=cm, config_manager=MagicMock(), cap=None,
    )
    return loop, am, estado


def test_state_machine_usa_el_alarm_manager_del_loop():
    loop, am, _ = _loop()
    sm = loop.state_machine
    assert sm.alarm_manager is am
    assert sm.preparacion.alarm_manager is am and sm.ciclo.alarm_manager is am


def test_cambiar_de_ciclo_conserva_el_mismo_alarm_manager():
    loop, am, _ = _loop()
    ok, _ = loop.set_active_cycle(MagicMock())
    assert ok and loop.state_machine.alarm_manager is am


def test_salida_de_falla_usa_resolver_todas_por_reinicio():
    loop, am, estado = _loop()
    sm = loop.state_machine
    estado.estado_maquina = {}          # StateMachine.update() lo lee para el log
    estado.set_machine_state(GlobalState.FALLA)
    sm.prev_state = GlobalState.FALLA
    sm.falla = MagicMock()
    sm.falla.run.return_value = True
    estado.fase_ciclo = "FALLO_SECADO"
    sm.update()
    am.resolver_todas_por_reinicio.assert_called_once()
