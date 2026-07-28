from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(agua_camara):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"agua_camara": agua_camara}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_agua_residual_ok_sin_pedir_rapida():
    p, alarm_mgr, set_do = _make_preparacion(agua_camara=0)
    ok, quiere_rapida = p.drenar_camara()
    assert ok is True
    assert quiere_rapida is False
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


def test_con_agua_residual_pide_rapida():
    p, alarm_mgr, set_do = _make_preparacion(agua_camara=1)
    ok, quiere_rapida = p.drenar_camara()
    assert ok is False
    assert quiere_rapida is True
    set_do.descompresion_rapida_on.assert_not_called()
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "AGUA_RESIDUAL_CAMARA" in ids
