from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(vapor=1, agua_bomba=1, agua_generador=1, aire_comprimido=1):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {
        "vapor_suministro": vapor,
        "agua_bomba": agua_bomba,
        "agua_generador": agua_generador,
        "aire_comprimido": aire_comprimido,
    }
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager


def test_falta_vapor_no_bloquea_verificar_suministros():
    p, alarm_mgr = _make_preparacion(vapor=0)
    assert p.verificar_suministros() is True
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert not any("VAPOR" in i for i in ids)


def test_falta_agua_bomba_sigue_bloqueando():
    p, alarm_mgr = _make_preparacion(agua_bomba=0)
    assert p.verificar_suministros() is False
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "SUMINISTRO_AGUA_BOMBA" in ids
