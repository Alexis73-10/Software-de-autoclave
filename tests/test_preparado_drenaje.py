from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(temp_drenaje, temp_segura=70.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "temp_segura_drenaje": temp_segura,
        "rango_temp_drenaje": rango,
        "tiempo_estable_alarma": 5,
    }[key]
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=70.0)
    p.mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()


def test_valvula_enciende_sobre_objetivo_sin_disparar_alarma():
    # objetivo=70, rango=5 -> limite_sup=75. 71 esta sobre el objetivo pero
    # dentro de la banda: la valvula debe reaccionar, la alarma no.
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=71.0)
    resultado = p.mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    alarm_mgr.clear.assert_any_call("TEMP_DRENAJE_ALTA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMP_DRENAJE_ALTA" not in ids_reportados
    assert resultado is True


def test_alarma_dispara_sobre_limite_superior():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=76.0)
    p.tiempo_estable = 0
    p.mantener_drenaje()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMP_DRENAJE_ALTA" in ids_reportados


def test_gate_false_bajo_limite_inferior_de_banda_sin_alarma():
    # objetivo=70, rango=5 -> limite_inf=65. Sin accion fisica de "muy frio",
    # pero el gate de listo/inicio si exige estar dentro de la banda completa.
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=60.0)
    resultado = p.mantener_drenaje()
    assert resultado is False
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMP_DRENAJE_ALTA" not in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=70.0)
    p.mantener_drenaje()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()


def test_apagado_se_resetea_si_sube_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=70.0)
    p.mantener_drenaje()
    p.mantener_drenaje()
    p.estado.sensores_temp["temp_drenaje"] = 71.0
    p.mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    p.estado.sensores_temp["temp_drenaje"] = 70.0
    p.mantener_drenaje()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()
