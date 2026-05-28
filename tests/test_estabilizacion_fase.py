# tests/test_estabilizacion_fase.py
from unittest.mock import MagicMock
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.estabilizacion import EstabilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(tiempo_min=5, t_obj=134.0, rango_temp=1.0, rango_pres=9.0, timeout_rec_min=2):
    estado = MagicMock()
    p_sat = p_saturacion_kpa(t_obj)
    estado.sensores_temp = {"temp_camara": t_obj}
    estado.sensores_pres = {"pres_camara": p_sat}
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "tiempo_estable_preesterilizacion": tiempo_min,
            "temperatura_calentamiento": t_obj,
            "rango_temp_estabilizacion": rango_temp,
            "presion_add_calentamiento": rango_pres,
            "timeout_recuperacion_estabilizacion": timeout_rec_min,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = EstabilizacionFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_skip_cuando_tiempo_es_cero():
    fase, estado, set_do = _make_fase(tiempo_min=0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_on.assert_not_called()


def test_primer_tick_activa_descompresion_lenta():
    fase, estado, set_do = _make_fase()
    fase.update()
    set_do.descompresion_lenta_on.assert_called_once()


def test_completado_cuando_expira_timer():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()  # inicializar
    fase._timer_principal_fin -= 100  # simular tiempo transcurrido
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_fallo_si_no_recupera_temperatura():
    fase, estado, set_do = _make_fase(tiempo_min=5, timeout_rec_min=1)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 120.0  # fuera de rango
    fase.update()  # arrancar timer recuperación
    fase._timer_recuperacion -= 200  # simular timeout
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.descompresion_lenta_off.assert_called()


def test_timer_recuperacion_se_resetea_al_recuperar():
    from autoclave.core.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(tiempo_min=5, timeout_rec_min=2)
    fase.update()  # inicializar
    # Simular que la condición sale del rango
    estado.sensores_temp["temp_camara"] = 120.0
    fase.update()
    assert fase._timer_recuperacion is not None
    # Restaurar condición
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0)
    fase.update()
    assert fase._timer_recuperacion is None


def test_bang_bang_valvula_on_cuando_temp_baja():
    fase, estado, set_do = _make_fase()
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 133.0  # bajo T_obj
    set_do.reset_mock()
    fase.update()
    set_do.vapor_camara_on.assert_called()


def test_salidas_apagadas_al_completar():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()
    fase._timer_principal_fin -= 100
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
