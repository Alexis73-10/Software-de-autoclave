# tests/test_calentamiento_fase.py
import time
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.core.runtime.steam import p_saturacion_kpa


def _make_fase(t_obj=134.0, presion_add=11.0, timeout_min=60,
               factor=50.0, rango=2.0, tasa_calentamiento=0.0, tasa_presion=0.0,
               tiempo_estable=0, intervalo=2, t_inicial=20.0,
               escape_lento_on=1, escape_lento_off=0,
               escape_rapido_on=0, escape_rapido_off=10):
    """tasa_calentamiento/tasa_presion quedan en 0 (deshabilitadas, ver guard
    '> 0' en calentamiento.py) por defecto: los tests que no ejercitan el
    debounce de pendiente cambian temperatura/presión entre ticks sin
    control de tiempo real, lo que produciría una tasa artificialmente alta
    y un FALLO espurio si el chequeo estuviera activo."""
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    estado.motivo_fallo = ""
    set_do = MagicMock()
    cycle = MagicMock()

    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento": t_obj,
            "presion_add_calentamiento": presion_add,
            "timeout_calentamiento": timeout_min,
            "factor_calentamiento": factor,
            "rango_calentamiento": rango,
            "tasa_calentamiento": tasa_calentamiento,
            "tasa_presion": tasa_presion,
            "tiempo_estable_preesterilizacion": tiempo_estable,
            "intervalo_segmentos_calor": intervalo,
            "escape_lento_on": escape_lento_on,
            "escape_lento_off": escape_lento_off,
            "escape_rapido_on": escape_rapido_on,
            "escape_rapido_off": escape_rapido_off,
        }
        return valores.get(param, default)

    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap = MagicMock()

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do


# ── APROXIMACION ──────────────────────────────────────────────────────────

def test_aproximacion_vapor_on_continuo_lejos_de_la_banda():
    fase, estado, set_do = _make_fase(t_obj=134.0, t_inicial=20.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is False
    set_do.vapor_camara_on.assert_called()


def test_primer_tick_espera_si_temp_none():
    fase, estado, set_do = _make_fase()
    estado.sensores_temp.pop("temp_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._inicializado is False


# ── Entrada a PWM_ACTIVO ─────────────────────────────────────────────────

def test_entra_a_pwm_dentro_de_la_banda():
    fase, estado, set_do = _make_fase(t_obj=134.0, rango=2.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(130.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is True


def test_pwm_no_retorna_a_aproximacion_si_sale_de_la_banda():
    """Una vez en PWM_ACTIVO, no hay retroceso aunque la lectura salga
    momentáneamente de la banda (evita chattering, ver plan sección 4.1)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, rango=2.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(130.0)
    fase.update()
    assert fase._en_pwm is True

    estado.sensores_pres["pres_camara"] = 50.0  # muy fuera de la banda ahora
    fase.update()
    assert fase._en_pwm is True


# ── PWM duty cycle ────────────────────────────────────────────────────────

def test_pwm_pulso_on_luego_off_por_tiempo():
    fase, estado, set_do = _make_fase(t_obj=134.0, rango=2.0, factor=50.0, intervalo=2)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(130.0)
    set_do.reset_mock()
    result = fase.update()  # entra a PWM, primer pulso ON
    assert result == FaseResult.EN_CURSO
    assert fase._pwm_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_pwm -= 2  # simular que pasó t_on (50% de 2s = 1s)
    fase.update()
    assert fase._pwm_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_pwm_factor_cero_permanece_encendido():
    fase, estado, set_do = _make_fase(t_obj=134.0, rango=2.0, factor=0.0, intervalo=2)
    fase.update()
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(130.0)
    fase.update()  # entra a PWM
    set_do.reset_mock()
    fase.update()
    set_do.vapor_camara_off.assert_not_called()
    set_do.vapor_camara_on.assert_called()


# ── Escape lento / escape rápido (paralelos, independientes) ─────────────

def test_escape_lento_off_cero_permanece_abierto():
    fase, estado, set_do = _make_fase(escape_lento_on=1, escape_lento_off=0)
    fase.update()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_lenta_off.assert_not_called()


def test_escape_rapido_on_cero_permanece_cerrado():
    fase, estado, set_do = _make_fase(escape_rapido_on=0, escape_rapido_off=10)
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
    fase._t_pulso_rapido -= 3  # pasó t_on
    fase.update()
    assert fase._rapido_abierto is False
    set_do.descompresion_rapida_off.assert_called()


def test_escapes_no_bloquean_a_vapor_camara():
    """Los tres lazos son independientes: el estado de los escapes no
    condiciona el control de vapor_camara ni viceversa (plan sección 4.4)."""
    fase, estado, set_do = _make_fase(escape_lento_on=0, escape_rapido_off=0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()


# ── Condición de finalización ─────────────────────────────────────────────

def test_completa_sin_sostenimiento_cuando_tiempo_estable_es_cero():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()


def test_no_completa_si_falta_presion_aunque_temp_llegue():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0)  # sin el add
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_sostenimiento_arma_timer_y_no_completa_de_inmediato():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._timer_estable_inicio is not None
    assert estado.fase_en_sostenimiento is True


def test_sostenimiento_completa_tras_transcurrir_el_tiempo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer

    fase._timer_estable_inicio -= 6  # simula que ya pasaron 6s (>= 5)
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_sostenimiento_timer_no_se_reinicia_si_condicion_sale_de_rango():
    """A diferencia de EstabilizacionFase, el timer de sostenimiento de
    CALENTAMIENTO no se reinicia ante una lectura momentáneamente fuera de
    rango — es una decisión de diseño explícita (plan sección 5, FMEA)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer
    timer_inicial = fase._timer_estable_inicio

    estado.sensores_temp["temp_camara"] = 130.0  # sale de rango momentáneamente
    fase.update()
    assert fase._timer_estable_inicio == timer_inicial  # no se reinició

    fase._timer_estable_inicio -= 6
    result = fase.update()
    assert result == FaseResult.COMPLETADO


# ── FALLO: timeout global ──────────────────────────────────────────────────

def test_fallo_por_timeout_apaga_las_tres_salidas():
    fase, estado, set_do = _make_fase(timeout_min=1)
    fase.update()  # inicializar
    fase._timer_timeout_fin -= 100
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()
    assert estado.motivo_fallo != ""


# ── FALLO: debounce de pendiente (3 lecturas consecutivas) ────────────────

def test_tasa_calentamiento_no_falla_con_1_o_2_lecturas_excesivas():
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0)
    fase.update()  # inicializar

    for _ in range(2):
        fase._temp_anterior = 20.0
        fase._t_tick_anterior = time.time() - 60  # dt = 1 min
        estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min > 10°C/min
        result = fase.update()
        assert result == FaseResult.EN_CURSO


def test_tasa_calentamiento_falla_al_tercer_exceso_consecutivo():
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0)
    fase.update()  # inicializar

    result = FaseResult.EN_CURSO
    for _ in range(3):
        fase._temp_anterior = 20.0
        fase._t_tick_anterior = time.time() - 60
        estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min > 10°C/min
        result = fase.update()

    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()


def test_tasa_calentamiento_bidireccional_detecta_caida_abrupta():
    """El FMEA (plan sección 8) marca tanto subida como caída abrupta de
    temperatura como anómalas, no solo la subida."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, t_inicial=134.0)
    fase.update()  # inicializar

    result = FaseResult.EN_CURSO
    for _ in range(3):
        fase._temp_anterior = 134.0
        fase._t_tick_anterior = time.time() - 60
        estado.sensores_temp["temp_camara"] = 100.0  # caída de 34°C/min > 10
        result = fase.update()

    assert result == FaseResult.FALLO


def test_tasa_presion_falla_al_tercer_exceso_consecutivo():
    fase, estado, set_do = _make_fase(tasa_presion=50.0)
    fase.update()  # inicializar

    result = FaseResult.EN_CURSO
    for _ in range(3):
        fase._pres_anterior = 100.0
        fase._t_tick_anterior = time.time() - 60
        estado.sensores_pres["pres_camara"] = 200.0  # 100 kPa/min > 50
        result = fase.update()

    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()


def test_tasa_deshabilitada_con_cero_no_falla_por_salto_grande():
    fase, estado, set_do = _make_fase(tasa_calentamiento=0.0, tasa_presion=0.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 135.0
    estado.sensores_pres["pres_camara"] = 300.0
    result = fase.update()
    assert result != FaseResult.FALLO


# ── Sensores no disponibles ────────────────────────────────────────────────

def test_pres_none_no_avanza_ni_lanza_excepcion():
    fase, estado, set_do = _make_fase()
    fase.update()  # inicializar
    estado.sensores_pres.pop("pres_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
