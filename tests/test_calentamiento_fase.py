# tests/test_calentamiento_fase.py
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(t_obj=134.0, tasa=5.0, timeout_min=60, tolerancia=9.0, t_inicial=20.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento": t_obj,
            "tasa_calentamiento": tasa,
            "timeout_calentamiento": timeout_min,
            "presion_add_calentamiento": tolerancia,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_primer_tick_activa_descompresion_lenta():
    fase, estado, set_do = _make_fase()
    fase.update()
    set_do.descompresion_lenta_on.assert_called_once()


def test_calentamiento_normal_valvula_on():
    """Temperatura lejos del objetivo → válvula abierta."""
    fase, estado, set_do = _make_fase(t_obj=134.0, t_inicial=20.0)
    estado.sensores_temp["temp_camara"] = 20.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()


def test_completado_cuando_alcanza_temperatura():
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_fallo_por_timeout():
    fase, estado, set_do = _make_fase(t_obj=134.0, timeout_min=1)
    fase.update()  # inicializar
    fase._timer_timeout_fin -= 200  # simular tiempo transcurrido
    estado.sensores_temp["temp_camara"] = 50.0
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_rampa_frena_valvula_cuando_supera_limite():
    """Si temperatura real supera T_permitida, válvula se cierra."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tasa=1.0, t_inicial=20.0)
    fase.update()  # inicializar con t_inicio=20
    # Con tasa=1°C/min y t_inicio=20, a t=0s T_permitida≈20°C
    # Forzamos temp = 50°C (muy por encima de la rampa) y elapsed≈0
    fase._t_inicio_fase += 0  # no avanzar tiempo
    estado.sensores_temp["temp_camara"] = 50.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_checkpoint_entra_en_sostenimiento():
    """Al alcanzar el 50% del objetivo, la fase entra en verificación."""
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 67.0  # 50% de 134
    # P_sat(67°C) ≈ 27.6 kPa — poner presión muy alta (aire)
    estado.sensores_pres["pres_camara"] = 200.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert estado.fase_en_sostenimiento is True


def test_checkpoint_se_libera_con_presion_correcta():
    """Cuando presión ≈ P_sat(T), el checkpoint se libera."""
    from autoclave.core.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=15.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 67.0
    # Presión correcta para el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(67.0)
    fase.update()  # entrar en checkpoint
    result = fase.update()  # liberar checkpoint
    assert fase._en_checkpoint is False
    assert estado.fase_en_sostenimiento is False


def test_salidas_apagadas_al_completar():
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
