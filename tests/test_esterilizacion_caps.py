from unittest.mock import MagicMock
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(has_liquid_sensor: bool, t_camara=135.0, t_2_camara=135.0):
    t_est = 134.0
    p_sat = p_saturacion_kpa(t_camara)
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_camara, "temp_2_camara": t_2_camara}
    estado.sensores_pres = {"pres_camara": p_sat + 5.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        return {
            "temperatura_esterilizacion":       t_est,
            "tiempo_esterilizacion":            3.5,
            "temperatura_add_esterilizacion":   2.0,
            "temperatura_error_esterilizacion": 5.0,
            "rango_presion_esterilizacion":     20.0,
            "presion_error_esterilizacion":     40.0,
        }.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = has_liquid_sensor

    fase = EsterilizacionFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, alarms


def test_sin_sensor_liquido_no_verifica_temp2():
    fase, estado, _ = _make_fase(has_liquid_sensor=False, t_camara=135.0, t_2_camara=20.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO  # no falla aunque temp2 sea baja


def test_con_sensor_liquido_falla_si_temp2_bajo_setpoint():
    fase, estado, alarms = _make_fase(has_liquid_sensor=True, t_camara=135.0, t_2_camara=100.0)
    result = fase.update()
    assert result == FaseResult.FALLO
    alarms.report.assert_called()
    alarm_id = alarms.report.call_args[0][0].id
    assert "TEMP2" in alarm_id


def test_con_sensor_liquido_en_curso_ambos_sobre_setpoint():
    fase, estado, _ = _make_fase(has_liquid_sensor=True, t_camara=135.0, t_2_camara=135.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
