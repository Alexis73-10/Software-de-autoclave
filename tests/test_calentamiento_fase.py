# tests/test_calentamiento_fase.py
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(t_obj=134.0, tasa=5.0, timeout_min=60, tolerancia=9.0, t_inicial=20.0,
               margen_techo=2.0, tiempo_apertura=3, tiempo_cierre=5,
               margen_entrada_esterilizacion=0.5):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento": t_obj,
            "tasa_calentamiento":        tasa,
            "timeout_calentamiento":     timeout_min,
            "rango_presion_calentamiento": tolerancia,
            "margen_techo_calentamiento": margen_techo,
            "tiempo_apertura_vapor_checkpoint": tiempo_apertura,
            "tiempo_cierre_vapor_checkpoint": tiempo_cierre,
            "margen_entrada_esterilizacion": margen_entrada_esterilizacion,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = False

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
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
    """Con el checkpoint liberado, alcanzar t_obj completa la fase."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98  # 97% — libera el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_no_completa_justo_en_t_obj_espera_margen_entrada_esterilizacion():
    """Con el checkpoint ya liberado, llegar exactamente a t_obj no alcanza
    para completar — hace falta t_obj + margen_entrada_esterilizacion, para
    dar colchón contra la fluctuación real de la lectura al llegar al
    objetivo (evita un FALLO espurio al entrar a ESTERILIZACION, que no
    tiene tolerancia en su primer chequeo de temperatura)."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, margen_entrada_esterilizacion=0.5)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98  # 97% — libera el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 134.0  # == t_obj, sin margen todavía
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.descompresion_lenta_off.assert_not_called()

    estado.sensores_temp["temp_camara"] = 134.5  # == t_obj + margen
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_off.assert_called()


def test_checkpoint_pendiente_bloquea_completacion():
    """Si temp >= t_obj pero el checkpoint sigue sin liberarse, no completa."""
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar

    # Salta directo a t_obj sin pasar por el checkpoint con presión correcta
    # (aire residual / vapor no saturado: presión fija en 100.0 kPa). La temperatura
    # también supera el techo del checkpoint (129.98 + 2.0 = 131.98), así que el
    # mecanismo de pulsos fuerza la válvula a OFF en vez de pulsar — eso es correcto,
    # lo que este test verifica es que la fase NO completa mientras tanto.
    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_checkpoint is True
    set_do.descompresion_lenta_off.assert_not_called()


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
    """Al alcanzar el 97% del objetivo, la fase entra en verificación."""
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 129.98  # 97% de 134
    # P_sat(129.98°C) es alto — poner presión muy alta (aire)
    estado.sensores_pres["pres_camara"] = 200.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert estado.fase_en_sostenimiento is True


def test_checkpoint_se_libera_con_presion_correcta():
    """Cuando presión ≈ P_sat(T), el checkpoint se libera."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=15.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 129.98  # 97% de 134
    # Presión correcta para el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()  # entrar en checkpoint
    result = fase.update()  # liberar checkpoint
    assert fase._en_checkpoint is False
    assert estado.fase_en_sostenimiento is False


def test_salidas_apagadas_al_completar():
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()

    estado.sensores_temp["temp_camara"] = 129.98  # 97% — libera el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 135.0  # >= t_obj + margen_entrada_esterilizacion (134.5)
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_checkpoint_pulso_on_luego_off_por_tiempo():
    """Presión baja y temp por debajo del techo → pulsos ON/OFF por tiempo."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98  # 97% de 134 → checkpoint
    estado.sensores_pres["pres_camara"] = 50.0    # muy por debajo de P_sat(129.98)-9
    result = fase.update()  # entra a checkpoint + primer pulso
    assert result == FaseResult.EN_CURSO
    assert fase._vapor_chk_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_vapor_chk -= 4  # simular que ya pasó tiempo_apertura_vapor_checkpoint (3s)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._vapor_chk_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_checkpoint_techo_alcanzado_fuerza_off_sin_pulsar():
    """Si temp alcanza el techo (checkpoint + margen), deja de pulsar aunque la presión siga baja."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0, margen_techo=2.0)
    fase.update()  # inicializar

    set_do.reset_mock()  # el tick de inicialización enciende vapor por rampa; aislar el tick bajo prueba
    # checkpoint = 129.98, techo = 129.98 + 2.0 = 131.98
    estado.sensores_temp["temp_camara"] = 131.98
    estado.sensores_pres["pres_camara"] = 50.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._t_pulso_vapor_chk is None
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_checkpoint_retoma_pulso_al_bajar_del_techo():
    """Tras frenar por techo, si temp vuelve a bajar del techo, retoma pulsos ON."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0, margen_techo=2.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 131.98  # en el techo → frena
    estado.sensores_pres["pres_camara"] = 50.0
    fase.update()
    assert fase._t_pulso_vapor_chk is None

    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = 130.78  # baja del techo de nuevo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._vapor_chk_abierto is True
    set_do.vapor_camara_on.assert_called()


def test_checkpoint_liberado_resetea_estado_de_pulso():
    """Al liberar el checkpoint, el estado de temporización del pulso queda limpio."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98
    estado.sensores_pres["pres_camara"] = 50.0
    fase.update()  # entra a checkpoint, arranca pulso ON
    assert fase._t_pulso_vapor_chk is not None

    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)  # presión correcta → libera
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_checkpoint is False
    assert fase._t_pulso_vapor_chk is None
    assert fase._vapor_chk_abierto is False
