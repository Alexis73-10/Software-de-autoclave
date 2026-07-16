from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(has_liquid_sensor: bool, t_inicial=20.0, t_inicial_2=20.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial, "temp_2_camara": t_inicial_2}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        return {
            "temperatura_calentamiento": 134.0,
            "tasa_calentamiento":        5.0,
            "timeout_calentamiento":     60,
            "rango_presion_calentamiento": 9.0,
            "margen_techo_calentamiento": 2.0,
            "tiempo_apertura_vapor_checkpoint": 3,
            "tiempo_cierre_vapor_checkpoint": 5,
        }.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = has_liquid_sensor

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do


def _liberar_checkpoints(fase, estado):
    """Avanza la temp por los checkpoints 80%/97% con presión saturada."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    for temp in (107.2, 129.98):  # 80% y 97% de t_obj=134.0
        estado.sensores_temp["temp_camara"] = temp
        estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp)
        fase.update()


def test_sin_sensor_liquido_completa_con_un_sensor():
    fase, estado, _ = _make_fase(has_liquid_sensor=False)
    fase.update()  # inicializar
    _liberar_checkpoints(fase, estado)
    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_con_sensor_liquido_no_completa_si_solo_camara_llega():
    fase, estado, _ = _make_fase(has_liquid_sensor=True)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"]   = 135.0
    estado.sensores_temp["temp_2_camara"] = 80.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_con_sensor_liquido_completa_cuando_ambos_llegan():
    fase, estado, _ = _make_fase(has_liquid_sensor=True)
    fase.update()  # inicializar
    _liberar_checkpoints(fase, estado)
    estado.sensores_temp["temp_camara"]   = 135.0
    estado.sensores_temp["temp_2_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_con_sensor_liquido_espera_si_temp2_es_none():
    fase, estado, _ = _make_fase(has_liquid_sensor=True)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 135.0
    estado.sensores_temp.pop("temp_2_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
