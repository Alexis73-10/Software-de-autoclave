# tests/test_esterilizacion_fase.py
from unittest.mock import MagicMock
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(t_est=134.0, tiempo_min=3.5, temp_add=2.0, temp_err=5.0,
               pres_rango=20.0, pres_err=40.0):
    # Temperatura dentro de banda: [T_est, T_est + add]
    temp_inicial = t_est + 1.0
    p_sat_inicial = p_saturacion_kpa(temp_inicial)

    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp_inicial}
    estado.sensores_pres = {"pres_camara": p_sat_inicial + 5.0}   # dentro de la banda
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_esterilizacion":       t_est,
            "tiempo_esterilizacion":             tiempo_min,
            "temperatura_add_esterilizacion":    temp_add,
            "temperatura_error_esterilizacion":  temp_err,
            "rango_presion_esterilizacion":      pres_rango,
            "presion_error_esterilizacion":      pres_err,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = EsterilizacionFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_primer_tick_activa_descompresion_lenta():
    fase, estado, set_do = _make_fase()
    fase.update()
    set_do.descompresion_lenta_on.assert_called_once()


def test_en_curso_con_condiciones_normales():
    fase, estado, set_do = _make_fase()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    # temperatura y presión dentro de banda


def test_completado_cuando_expira_timer():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()
    fase._timer_fin -= 200
    # Mantener condiciones válidas
    t_est = 134.0
    temp = t_est + 1.0
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp) + 5.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_fallo_temp_baja():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 133.9
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.descompresion_lenta_off.assert_called()
    fase.alarm_manager.report.assert_called()
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "TEMP_BAJA" in alarm.id


def test_fallo_temp_alta():
    fase, estado, set_do = _make_fase(t_est=134.0, temp_add=2.0, temp_err=5.0)
    fase.update()
    # T_lim_alta = 134 + 2 + 5 = 141
    estado.sensores_temp["temp_camara"] = 141.1
    result = fase.update()
    assert result == FaseResult.FALLO
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "TEMP_ALTA" in alarm.id


def test_fallo_presion_baja():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    p_sat = p_saturacion_kpa(134.0)
    estado.sensores_pres["pres_camara"] = p_sat - 0.1  # justo debajo de P_sat
    result = fase.update()
    assert result == FaseResult.FALLO
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "PRES_BAJA" in alarm.id


def test_fallo_presion_alta():
    fase, estado, set_do = _make_fase(t_est=134.0, pres_rango=20.0, pres_err=40.0)
    fase.update()
    # Usar la temperatura actual para calcular P_sat
    temp = estado.sensores_temp["temp_camara"]
    p_sat = p_saturacion_kpa(temp)
    # P_lim_alta = P_sat + 20 + 40 = P_sat + 60
    estado.sensores_pres["pres_camara"] = p_sat + 61.0
    result = fase.update()
    assert result == FaseResult.FALLO
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "PRES_ALTA" in alarm.id


def test_valvula_on_en_limite_inferior():
    """Cuando temp == T_est (límite), la válvula pulsa para evitar caída."""
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()


def test_valvula_off_cuando_temp_en_banda():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 135.0  # sobre T_est
    # Actualizar presión para mantener validez
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0) + 5.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_salidas_apagadas_en_fallo():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 120.0  # temp baja → fallo
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
