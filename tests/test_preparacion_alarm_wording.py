from unittest.mock import MagicMock

from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.alarms.alarm_types import AlarmType


def _make_state():
    return preparacion_state(
        alarm_manager=MagicMock(),
        estado=MagicMock(),
        set_do=MagicMock(),
        cycle=MagicMock(),
        config=MagicMock(),
    )


def test_alarma_alerta_no_dice_fallo():
    """CHAQUETA_FRIA se reporta como ALERTA — el texto no debe decir 'Fallo',
    porque el nivel impreso en el ticket ('Nivel: ALERTA') lo contradiría."""
    state = _make_state()
    state.alarm("CHAQUETA_FRIA", AlarmType.ALERTA)

    reported = state.alarm_manager.report.call_args.args[0]
    assert reported.type == AlarmType.ALERTA
    assert "Fallo" not in reported.description
    assert "Alerta" in reported.description


def test_alarma_falla_dice_fallo():
    state = _make_state()
    state.alarm("SUMINISTRO_VAPOR", AlarmType.FALLA)

    reported = state.alarm_manager.report.call_args.args[0]
    assert "Fallo" in reported.description


def test_alarma_emergencia_dice_emergencia():
    state = _make_state()
    state.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)

    reported = state.alarm_manager.report.call_args.args[0]
    assert "Emergencia" in reported.description
