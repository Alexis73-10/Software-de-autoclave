from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(vapor=1, presion_chaqueta=300.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {
        "paro_emergencia": 0,
        "vapor_suministro": vapor,
        "agua_bomba": 1, "agua_generador": 1, "aire_comprimido": 1,
        "agua_camara": 1,
    }
    estado.sensores_pres = {"pres_chaqueta": presion_chaqueta}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }[key]
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_vapor_retorna_true_sin_bloquear():
    p, alarm_mgr, set_do = _make_preparacion(vapor=0)
    assert p.suministrar_vapor_chaqueta() is True
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_vapor_reporta_alarma_no_bloqueante():
    p, alarm_mgr, _ = _make_preparacion(vapor=0)
    p.suministrar_vapor_chaqueta()
    alarma = alarm_mgr.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_fuera_de_banda_retorna_false():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=100.0)
    assert p.suministrar_vapor_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_called()


def test_vapor_vuelve_se_retoma_en_el_siguiente_tick():
    # Ya no hay step que "saltar": suministrar_vapor_chaqueta() se evalua
    # cada tick del ejecutor sin depender de las demas condiciones.
    p, alarm_mgr, set_do = _make_preparacion(vapor=0, presion_chaqueta=100.0)
    p.igualar_presion_camara = lambda: (True, False)
    p.drenar_camara = lambda: (True, False)
    p.verificar_temperatura_drenaje = lambda: True

    p.ejecutor()
    p.estado.sensores_di["vapor_suministro"] = 1
    p.ejecutor()

    set_do.vapor_chaqueta_on.assert_called()


def test_valvula_enciende_bajo_objetivo_sin_disparar_alarma():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=299.0)
    resultado = p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    alarm_mgr.clear.assert_any_call("CHAQUETA_FRIA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" not in ids_reportados
    assert resultado is True


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=300.0)
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_alarma_chaqueta_fria_dispara_bajo_limite_inferior():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=270.0)
    p.suministrar_vapor_chaqueta()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=300.0)
    p.suministrar_vapor_chaqueta()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_apagado_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=300.0)
    p.suministrar_vapor_chaqueta()
    p.suministrar_vapor_chaqueta()
    p.estado.sensores_pres["pres_chaqueta"] = 299.0
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    p.estado.sensores_pres["pres_chaqueta"] = 300.0
    p.suministrar_vapor_chaqueta()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
