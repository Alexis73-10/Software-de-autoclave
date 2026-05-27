from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.alarms.alarm_types import AlarmType


def _make_preparado(suministro_electrico=1, fallo_suministro=False):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {
        "pres_camara": 101.0, "pres_chaqueta": 300.0,
        "pres_empaque_1": 101.0, "pres_empaque_2": 101.0,
    }
    estado.sensores_temp = {
        "temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
        "temp_chaqueta": 25.0, "temp_drenaje_cam": 25.0, "temp_drenaje": 25.0,
    }
    estado.sensores_di = {
        "vapor_suministro": 1, "agua_bomba": 1,
        "agua_generador": 1, "aire_comprimido": 1,
        "suministro_electrico": suministro_electrico,
        "puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
    }
    estado.get_flag.side_effect = (
        lambda f: fallo_suministro if f == "FALLO_SUMINISTRO_ELECTRICO" else False
    )
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = 300
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "tiempo_estable_alarma": 5,
    }.get(k, 0)
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager


def test_suministro_off_genera_alarma():
    p, alarm_mgr = _make_preparado(suministro_electrico=0, fallo_suministro=True)
    p.verificar_suministros()
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "SUMINISTRO_ELECTRICO" in ids


def test_suministro_ok_limpia_alarma():
    p, alarm_mgr = _make_preparado(suministro_electrico=1, fallo_suministro=False)
    p.verificar_suministros()
    alarm_mgr.clear.assert_any_call("SUMINISTRO_ELECTRICO")


def test_esta_preparado_false_con_fallo_suministro():
    p, _ = _make_preparado(suministro_electrico=0, fallo_suministro=True)
    p.mantener_chaqueta = lambda: True
    p.mantener_presion_camara = lambda: True
    p.mantener_drenaje = lambda: True
    p.puertas_cerradas = lambda: True
    assert p.esta_preparado() is False
