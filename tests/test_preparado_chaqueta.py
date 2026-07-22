from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(vapor=1, pres_chaqueta=300.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"vapor_suministro": vapor}
    estado.sensores_pres = {"pres_chaqueta": pres_chaqueta}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }[key]
    config = MagicMock()
    config.get.return_value = 5
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_vapor_mantener_chaqueta_retorna_true():
    p, alarm_mgr, set_do = _make_preparado(vapor=0)
    assert p.mantener_chaqueta() is True
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_vapor_alarma_no_bloqueante():
    p, alarm_mgr, _ = _make_preparado(vapor=0)
    p.mantener_chaqueta()
    alarma = alarm_mgr.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_fuera_de_banda_sigue_bloqueando():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=100.0)
    assert p.mantener_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_called()


def test_esta_preparado_true_sin_vapor_con_resto_ok():
    p, alarm_mgr, set_do = _make_preparado(vapor=0)
    p.mantener_presion_camara = lambda: True
    p.mantener_drenaje = lambda: True
    p.puertas_cerradas = lambda: True
    p.estado.get_flag.side_effect = lambda f: False
    assert p.esta_preparado() is True
