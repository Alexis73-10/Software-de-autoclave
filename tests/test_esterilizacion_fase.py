# tests/test_esterilizacion_fase.py
import time
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.core.runtime.steam import p_saturacion_kpa


def _make_fase(t_est=134.0, tiempo_min=3.5, factor=70.0, presion_add=11.0,
               intervalo=3, rango_temp=3.0, rango_pres=30.0,
               brecha_seg=0.3, brecha_seg_p=6.0, brecha_err_t=0.1, brecha_err_p=2.0,
               escape_lento_on=1, escape_lento_off=0,
               escape_rapido_on=0, escape_rapido_off=400,
               t_inicial=None, p_inicial=None):
    """Por defecto arranca en RECUPERACION: T_inicial = t_est (viene de
    ESTABILIZACION ya en condición de vapor saturado), presión en
    P_sat(t_est) — dentro de todos los márgenes de falla por defecto."""
    if t_inicial is None:
        t_inicial = t_est
    if p_inicial is None:
        p_inicial = p_saturacion_kpa(t_inicial)

    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": p_inicial}
    estado.fase_en_sostenimiento = False
    estado.motivo_fallo = ""
    set_do = MagicMock()
    cycle = MagicMock()

    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_esterilizacion": t_est,
            "tiempo_esterilizacion": tiempo_min,
            "factor_esterilizacion": factor,
            "presion_add_esterilizacion": presion_add,
            "intervalo_segmentos_ester": intervalo,
            "rango_temperatura_ester": rango_temp,
            "rango_presion_ester": rango_pres,
            "brecha_segura_temperatura": brecha_seg,
            "brecha_segura_presion": brecha_seg_p,
            "brecha_error_temperatura": brecha_err_t,
            "brecha_error_presion": brecha_err_p,
            "escape_lento_on_ester": escape_lento_on,
            "escape_lento_off_ester": escape_lento_off,
            "escape_rapido_on_ester": escape_rapido_on,
            "escape_rapido_off_ester": escape_rapido_off,
        }
        return valores.get(param, default)

    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap = MagicMock()

    fase = EsterilizacionFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do


# ── RECUPERACION ────────────────────────────────────────────────────────────

def test_primer_tick_en_recuperacion_vapor_on_continuo():
    fase, estado, set_do = _make_fase()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is True
    set_do.vapor_camara_on.assert_called()


def test_fase_en_sostenimiento_desde_el_primer_tick():
    fase, estado, set_do = _make_fase()
    fase.update()
    assert estado.fase_en_sostenimiento is True


# ── Transición bidireccional RECUPERACION <-> PWM_ACTIVO ────────────────────

def test_transicion_a_pwm_activo_cuando_supera_brecha_segura():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3)
    fase.update()  # inicializa en RECUPERACION
    temp = 135.0
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp)  # dentro de banda
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is False


def test_transicion_bidireccional_vuelve_a_recuperacion_sin_chattering_guard():
    """A diferencia de CALENTAMIENTO, la transición es bidireccional y se
    evalúa en cada tick sin guardia anti-chattering (plan sección 4.1)."""
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3)
    fase.update()
    temp = 135.0
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp)
    fase.update()
    assert fase._en_recuperacion is False

    estado.sensores_temp["temp_camara"] = 134.0  # vuelve a estar por debajo de la brecha
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is True
    set_do.vapor_camara_on.assert_called()


def test_presion_baja_dispara_recuperacion_aunque_temperatura_este_alta():
    """Regresión directa del patrón observado en producción: la fuga
    continua de descompresion_lenta hace caer la presión mientras la
    temperatura se mantiene igual o por encima del setpoint. Sin este
    disparador, RECUPERACION solo miraba temperatura y nunca se activaba
    en ese caso — la presión seguía cayendo bajo el techo de PWM_ACTIVO
    hasta FALLO sin que el control pasara a modo agresivo."""
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3, brecha_seg_p=6.0)
    fase.update()  # inicializa en RECUPERACION
    p_sat_est = p_saturacion_kpa(134.0)
    temp = 135.0  # por encima del setpoint, NO dispararía por temperatura
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_sat_est - 6.1  # < P_sat(t_est) - 6.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is True
    set_do.vapor_camara_on.assert_called()


def test_presion_dentro_del_margen_no_dispara_recuperacion_por_presion():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3, brecha_seg_p=6.0)
    fase.update()
    p_sat_est = p_saturacion_kpa(134.0)
    temp = 135.0
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_sat_est - 5.9  # dentro del margen
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is False


# ── PWM_ACTIVO: banda fija [-2,+1] kPa sobre P_sat(T_actual) ────────────────

def test_pwm_forzado_on_por_debajo_de_la_banda():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3)
    fase.update()
    temp = 135.0
    p_sat_t = p_saturacion_kpa(temp)
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_sat_t - 3.0  # < p_sat_t - 2
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is False
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_pwm_forzado_off_por_encima_de_la_banda():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3)
    fase.update()
    temp = 135.0
    p_sat_t = p_saturacion_kpa(temp)
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_sat_t + 2.0  # > p_sat_t + 1
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_recuperacion is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_pwm_duty_cycle_dentro_de_la_banda():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3, factor=50.0, intervalo=2)
    fase.update()
    temp = 135.0
    p_sat_t = p_saturacion_kpa(temp)
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_sat_t - 0.5  # dentro de [-2,+1]
    set_do.reset_mock()
    result = fase.update()  # entra a PWM, primer pulso ON
    assert result == FaseResult.EN_CURSO
    assert fase._pwm_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_pwm -= 2  # pasó t_on (50% de 2s = 1s)
    fase.update()
    assert fase._pwm_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_pwm_techo_control_max_fuerza_off_sin_importar_la_banda():
    """El techo P_control_max corta el vapor aunque la banda local diga ON
    (plan sección 4.1: evita que la banda dinámica arrastre la presión hasta
    el umbral real de falla)."""
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_seg=0.3, presion_add=11.0)
    fase.update()
    temp = 135.0
    p_sat_est = p_saturacion_kpa(134.0)
    p_control_max = p_sat_est + 11.0
    estado.sensores_temp["temp_camara"] = temp
    # Muy por debajo de P_sat(T_actual) -> la banda local pediría ON,
    # pero por encima de P_control_max -> el techo debe forzar OFF.
    estado.sensores_pres["pres_camara"] = p_control_max + 1.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


# ── Escape lento / escape rápido (paralelos, independientes) ────────────────

def test_escape_lento_off_cero_permanece_abierto():
    fase, estado, set_do = _make_fase(escape_lento_on=1, escape_lento_off=0)
    fase.update()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_lenta_off.assert_not_called()


def test_escape_rapido_on_cero_permanece_cerrado():
    fase, estado, set_do = _make_fase(escape_rapido_on=0, escape_rapido_off=400)
    fase.update()
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_escape_lento_alterna_por_tiempo():
    fase, estado, set_do = _make_fase(escape_lento_on=2, escape_lento_off=3)
    fase.update()  # abre
    assert fase._lento_abierto is True

    set_do.reset_mock()
    fase._t_pulso_lento -= 3  # pasó t_on (2s)
    fase.update()
    assert fase._lento_abierto is False
    set_do.descompresion_lenta_off.assert_called()

    set_do.reset_mock()
    fase._t_pulso_lento -= 4  # pasó t_off (3s)
    fase.update()
    assert fase._lento_abierto is True
    set_do.descompresion_lenta_on.assert_called()


def test_escape_rapido_alterna_por_tiempo():
    fase, estado, set_do = _make_fase(escape_rapido_on=2, escape_rapido_off=3)
    fase.update()  # primer pulso: abre
    assert fase._rapido_abierto is True

    set_do.reset_mock()
    fase._t_pulso_rapido -= 3  # pasó t_on (2s)
    fase.update()
    assert fase._rapido_abierto is False
    set_do.descompresion_rapida_off.assert_called()


def test_escapes_no_bloquean_a_vapor_camara():
    """Los tres lazos son independientes (plan sección 4.4)."""
    fase, estado, set_do = _make_fase(escape_lento_on=0, escape_rapido_off=0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()


# ── Condición de finalización (única variable: el tiempo) ───────────────────

def test_completa_al_expirar_el_timer_en_recuperacion():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()  # inicializa en RECUPERACION
    assert fase._en_recuperacion is True
    fase._timer_fin -= 100
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()


def test_completa_al_expirar_el_timer_en_pwm_activo():
    fase, estado, set_do = _make_fase(tiempo_min=1, t_est=134.0, brecha_seg=0.3)
    fase.update()
    temp = 135.0
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp)
    fase.update()
    assert fase._en_recuperacion is False

    fase._timer_fin -= 100
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_no_completa_antes_de_tiempo():
    fase, estado, set_do = _make_fase(tiempo_min=10)
    result = fase.update()
    assert result == FaseResult.EN_CURSO


# ── FALLO: temperatura alta (debounce 3, referencia fija) ───────────────────

def test_temp_alta_no_falla_con_1_o_2_lecturas_excesivas():
    fase, estado, set_do = _make_fase(t_est=134.0, rango_temp=3.0)
    fase.update()
    for _ in range(2):
        estado.sensores_temp["temp_camara"] = 137.5  # > 134+3
        result = fase.update()
        assert result == FaseResult.EN_CURSO


def test_temp_alta_falla_al_tercer_exceso_consecutivo():
    fase, estado, set_do = _make_fase(t_est=134.0, rango_temp=3.0)
    fase.update()
    result = FaseResult.EN_CURSO
    for _ in range(3):
        estado.sensores_temp["temp_camara"] = 137.5
        result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()
    assert estado.motivo_fallo != ""


# ── FALLO: temperatura baja (debounce 3, referencia fija) ───────────────────

def test_temp_baja_falla_al_tercer_exceso_consecutivo():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_err_t=0.1)
    fase.update()
    result = FaseResult.EN_CURSO
    for _ in range(3):
        estado.sensores_temp["temp_camara"] = 133.8  # < 134 - 0.1
        result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()


def test_temp_baja_no_falla_con_2_lecturas():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_err_t=0.1)
    fase.update()
    for _ in range(2):
        estado.sensores_temp["temp_camara"] = 133.8
        result = fase.update()
        assert result == FaseResult.EN_CURSO


# ── FALLO: presión alta (debounce 3, referencia P_sat(t_est) fija) ──────────

def test_pres_alta_falla_al_tercer_exceso_consecutivo():
    fase, estado, set_do = _make_fase(t_est=134.0, rango_pres=30.0)
    fase.update()
    p_sat_est = p_saturacion_kpa(134.0)
    result = FaseResult.EN_CURSO
    for _ in range(3):
        estado.sensores_pres["pres_camara"] = p_sat_est + 31.0
        result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()


# ── FALLO: presión baja (debounce 3, referencia P_sat(t_est) fija) ──────────
# Corrige el bug ESTERILIZACION_PRES_BAJA: la referencia es P_sat(t_est) fija,
# nunca P_sat(T_actual).

def test_pres_baja_falla_al_tercer_exceso_consecutivo():
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_err_p=2.0)
    fase.update()
    p_sat_est = p_saturacion_kpa(134.0)
    result = FaseResult.EN_CURSO
    for _ in range(3):
        estado.sensores_pres["pres_camara"] = p_sat_est - 2.1
        result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()


def test_pres_baja_usa_referencia_fija_no_temperatura_actual():
    """Regresión directa del bug documentado: si la referencia fuera
    P_sat(T_actual) en vez de P_sat(temperatura_esterilizacion), una subida
    de temperatura real podría enmascarar una presión realmente baja frente
    al setpoint. Aquí T_actual sube pero la presión sigue evaluada contra
    P_sat(t_est) fija."""
    fase, estado, set_do = _make_fase(t_est=134.0, brecha_err_p=2.0, rango_temp=10.0)
    fase.update()
    p_sat_est = p_saturacion_kpa(134.0)
    result = FaseResult.EN_CURSO
    for _ in range(3):
        estado.sensores_temp["temp_camara"] = 138.0  # sube T_actual (P_sat(138) > P_sat(134))
        estado.sensores_pres["pres_camara"] = p_sat_est - 2.1  # baja frente a la referencia fija
        result = fase.update()
    assert result == FaseResult.FALLO


# ── Sensores no disponibles ──────────────────────────────────────────────────

def test_temp_none_no_avanza_ni_lanza_excepcion():
    fase, estado, set_do = _make_fase()
    fase.update()  # inicializa
    estado.sensores_temp.pop("temp_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_pres_none_no_avanza_ni_lanza_excepcion():
    fase, estado, set_do = _make_fase()
    fase.update()
    estado.sensores_pres.pop("pres_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_sensor_none_no_completa_aunque_el_timer_ya_haya_expirado():
    """Riesgo aceptado documentado en el plan (sección 8): sin timeout de
    fase, un sensor en None puede bloquear la fase indefinidamente incluso
    si el conteo de tiempo ya se cumplió."""
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()  # inicializa y fija _timer_fin
    fase._timer_fin -= 100  # el timer ya venció
    estado.sensores_pres.pop("pres_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
