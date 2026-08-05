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
               escape_rapido_on=0, escape_rapido_off=10,
               rango_temp_estabilizacion=1.0, timeout_recuperacion_estabilizacion=5):
    """tasa_calentamiento/tasa_presion quedan en 0 (deshabilitadas, ver guard
    '> 0' en calentamiento.py) por defecto: los tests que no ejercitan el
    control por tasa cambian temperatura/presión entre ticks sin control de
    tiempo real, lo que produciría una tasa artificialmente alta y forzaría
    vapor_camara a OFF de forma espuria si el control estuviera activo."""
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
            "rango_temp_estabilizacion": rango_temp_estabilizacion,
            "timeout_recuperacion_estabilizacion": timeout_recuperacion_estabilizacion,
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


def test_pwm_activo_ignora_tasa_calentamiento_excedida():
    """El control por tasa es exclusivo de APROXIMACION (plan, restricción
    global) — una vez en PWM_ACTIVO, una pendiente que excedería
    tasa_calentamiento no debe forzar OFF fuera del ciclo PWM programado."""
    fase, estado, set_do = _make_fase(t_obj=134.0, rango=2.0, factor=50.0, intervalo=2,
                                       tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(130.0)
    fase.update()  # entra a PWM_ACTIVO
    assert fase._en_pwm is True

    fase._temp_anterior = 130.0
    fase._t_tick_anterior = time.time() - 60
    # Fuerza el flanco ON del ciclo PWM en este tick (mismo patrón que
    # test_pwm_pulso_on_luego_off_por_tiempo): _t_pulso_pwm usa tiempo real
    # de reloj, y el test corre en microsegundos, así que sin rebobinarlo
    # _tick_dos_estados no vería elapsed >= t_off y no llamaría a ninguna
    # salida este tick, dejando la aserción sin poder distinguir un bug real.
    fase._pwm_abierto = False
    fase._t_pulso_pwm = time.time() - 100
    estado.sensores_temp["temp_camara"] = 200.0  # 70°C/min > 10, muy por encima del límite
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


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


# ── Condición de finalización / tramo ESTABLE_PREESTERILIZACION ──────────────

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
    assert fase._en_sostenimiento is True
    assert fase._timer_sostenido_desde is not None
    assert estado.fase_en_sostenimiento is True


def test_sostenimiento_completa_tras_transcurrir_el_tiempo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer

    fase._timer_sostenido_desde -= 6  # simula que ya pasaron 6s (>= 5) dentro de banda
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_sostenimiento_se_reinicia_si_presion_excede_la_banda_superior():
    """Caso central del rediseño: si la presión se pasa de banda por inercia
    térmica durante el sostenimiento, el conteo se reinicia — la fase espera
    a que la presión regrese cerca de p_obj antes de volver a contar, en vez
    de completar con la presión todavía inflada (motivo original del cambio:
    CALENTAMIENTO entregaba a ESTERILIZACION con presión alta)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer
    assert fase._timer_sostenido_desde is not None

    estado.sensores_pres["pres_camara"] = p_obj + 50.0  # overshoot, muy fuera de banda (+-11)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._timer_sostenido_desde is None  # se reinició
    assert estado.fase_en_sostenimiento is False

    # Vuelve a banda: arranca un timer nuevo, no retoma el anterior
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
    assert fase._timer_sostenido_desde is not None

    fase._timer_sostenido_desde -= 6
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_sostenimiento_no_completa_si_temp_cae_por_debajo_del_objetivo():
    """Regresión: la banda de sostenimiento debe ser de un solo lado — tolera
    overshoot por encima de t_obj/p_obj (el proposito de este tramo), pero
    nunca debe aceptar una lectura por debajo del objetivo, porque ESTERILIZACION
    falla con solo 0.1°C de margen inferior (brecha_error_temperatura) y 3
    ticks de debounce — una entrega por debajo del setpoint aborta el ciclo
    casi de inmediato."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer
    assert fase._timer_sostenido_desde is not None

    estado.sensores_temp["temp_camara"] = 133.5  # 0.5°C bajo el objetivo, dentro de rango_temp_estabilizacion=1.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._timer_sostenido_desde is None  # se reinició, NO se considera "dentro de rango"
    assert estado.fase_en_sostenimiento is False


def test_sostenimiento_no_completa_si_presion_cae_por_debajo_del_objetivo():
    """Mismo caso que el de temperatura, pero para presión: una lectura bajo
    p_obj no debe contar como "dentro de rango" aunque esté dentro de la
    banda en valor absoluto."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer
    assert fase._timer_sostenido_desde is not None

    estado.sensores_pres["pres_camara"] = p_obj - 5.0  # bajo el objetivo, dentro de presion_add=11 en valor absoluto
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._timer_sostenido_desde is None  # se reinició
    assert estado.fase_en_sostenimiento is False


def test_sostenimiento_timer_recuperacion_se_cancela_al_recuperar():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5,
                                       timeout_recuperacion_estabilizacion=2)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer de sostenimiento

    estado.sensores_pres["pres_camara"] = p_obj + 50.0  # sale de banda
    fase.update()
    assert fase._timer_recuperacion_fin is not None

    estado.sensores_pres["pres_camara"] = p_obj  # recupera
    fase.update()
    assert fase._timer_recuperacion_fin is None


def test_sostenimiento_fallo_si_nunca_converge_dentro_del_timeout_recuperacion():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5,
                                       timeout_recuperacion_estabilizacion=1)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # entra al tramo y arma timer de sostenimiento

    estado.sensores_pres["pres_camara"] = p_obj + 50.0  # sale de banda, arma recuperación
    fase.update()
    assert fase._timer_recuperacion_fin is not None

    fase._timer_recuperacion_fin -= 100  # simula que expiró el timeout de recuperación
    result = fase.update()
    assert result == FaseResult.FALLO
    assert estado.motivo_fallo != ""
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()


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


# ── Sensores no disponibles ────────────────────────────────────────────────

def test_pres_none_no_avanza_ni_lanza_excepcion():
    fase, estado, set_do = _make_fase()
    fase.update()  # inicializar
    estado.sensores_pres.pop("pres_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO


# ── Control por tasa en APROXIMACION (bang-bang) ──────────────────────────

def test_aproximacion_bangbang_on_primer_tick_sin_pendiente_disponible():
    """Aunque tasa_calentamiento/tasa_presion estén habilitadas, el primer
    tick no tiene pendiente calculable (_t_tick_anterior aún None) — la
    válvula permanece ON por defecto."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=50.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is False
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_on_si_tasas_dentro_del_limite():
    fase, estado, set_do = _make_fase(tasa_calentamiento=50.0, tasa_presion=200.0)
    fase.update()  # inicializar, primer tick sin pendiente

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60  # dt = 1 min
    estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min <= 50
    estado.sensores_pres["pres_camara"] = 150.0  # 50 kPa/min <= 200
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_off_si_tasa_temperatura_excede():
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min > 10
    estado.sensores_pres["pres_camara"] = 150.0  # 50 kPa/min <= 200, dentro
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO  # el control por tasa nunca produce FALLO, solo fuerza OFF
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_aproximacion_bangbang_off_si_tasa_presion_excede():
    fase, estado, set_do = _make_fase(tasa_calentamiento=100.0, tasa_presion=30.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 25.0  # 5°C/min <= 100, dentro
    estado.sensores_pres["pres_camara"] = 200.0  # 100 kPa/min > 30
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_aproximacion_bangbang_vuelve_a_on_sin_tiempo_minimo_de_apagado():
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 40.0  # excede -> OFF
    estado.sensores_pres["pres_camara"] = 150.0
    fase.update()
    assert fase._en_pwm is False

    fase._t_tick_anterior = time.time() - 60  # siguiente tick, dt = 1 min otra vez
    estado.sensores_temp["temp_camara"] = 41.0  # 1°C/min <= 10 ahora
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_tasa_temperatura_deshabilitada():
    fase, estado, set_do = _make_fase(tasa_calentamiento=0.0, tasa_presion=30.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 200.0  # 180°C/min, sería enorme pero deshabilitado (0)
    estado.sensores_pres["pres_camara"] = 110.0  # 10 kPa/min <= 30, dentro
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_tasa_presion_deshabilitada():
    fase, estado, set_do = _make_fase(tasa_calentamiento=100.0, tasa_presion=0.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 25.0  # 5°C/min <= 100, dentro
    estado.sensores_pres["pres_camara"] = 900.0  # 800 kPa/min, sería enorme pero deshabilitado (0)
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_no_apaga_por_caida_abrupta_de_temperatura():
    """El control solo limita la dirección de subida (sin abs()) porque la
    válvula no puede enfriar la cámara."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 100.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 50.0  # caída de 50°C/min
    estado.sensores_pres["pres_camara"] = 110.0  # dentro de rango
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_tasa_excedida_muchos_ticks_consecutivos_nunca_produce_fallo():
    """tasa_calentamiento/tasa_presion son ahora puramente de control — ya
    no existe ningún camino de FALLO por pendiente, sin importar cuántos
    ticks consecutivos excedan el límite (ver spec de remoción de FALLO,
    docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md)."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=50.0)
    fase.update()  # inicializar

    result = FaseResult.EN_CURSO
    for _ in range(10):
        fase._temp_anterior = 20.0
        fase._pres_anterior = 100.0
        fase._t_tick_anterior = time.time() - 60
        estado.sensores_temp["temp_camara"] = 100.0  # 80°C/min, muy por encima de 10
        estado.sensores_pres["pres_camara"] = 500.0  # 400 kPa/min, muy por encima de 50
        set_do.reset_mock()
        result = fase.update()
        assert result == FaseResult.EN_CURSO
        set_do.vapor_camara_off.assert_called()
        set_do.vapor_camara_on.assert_not_called()

    assert result != FaseResult.FALLO
