# tests/test_calentamiento_fase.py
import time
import logging
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


def _sembrar_historial(fase, temp, pres, hace_seg):
    """Reemplaza el historial de pendiente por una única muestra de
    referencia con `hace_seg` segundos de antigüedad (>= _VENTANA_PENDIENTE_SEG
    para que el próximo update() la use al calcular tasa_t/tasa_p)."""
    fase._historial_pendiente.clear()
    fase._historial_pendiente.append((time.time() - hace_seg, temp, pres))


# ── APROXIMACION ──────────────────────────────────────────────────────────

def test_primer_tick_espera_si_temp_none():
    fase, estado, set_do = _make_fase()
    estado.sensores_temp.pop("temp_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._inicializado is False


# ── Controlador continuo (RAMPA) ──────────────────────────────────────────

def test_lejos_del_objetivo_duty_es_uno_y_vapor_on_continuo():
    fase, estado, set_do = _make_fase(t_obj=134.0, t_inicial=20.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 1.0
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_duty_baja_por_presion_cercana_al_objetivo_aunque_lejos_de_p_sat_temp():
    """Regresion del bug real (ciclo 72, 2026-08-05): la presion corre
    persistentemente por encima de P_sat(temp_actual) durante toda la
    subida (chaqueta/aire residual/calibracion). duty_proximidad se mide
    contra p_obj fijo, nunca contra P_sat(temp_actual) -- por eso ya cae
    antes de cruzar el objetivo. temp=110 se mantiene bien debajo del tope
    del 97% (129.98 con t_obj=134) para que duty_calidad_vapor no
    interfiera en este caso."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 110.0  # P_sat(110) ~ 146 kPa, muy lejos de p_obj
    estado.sensores_pres["pres_camara"] = p_obj - 1.0  # a 1 kPa del objetivo, dentro de rango=2.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual < 1.0


def test_calidad_vapor_fuerza_cero_si_temp_supera_el_tope_y_presion_no_corresponde():
    """Si la temperatura ya cruzo t_obj (por lo tanto tambien el tope del
    97%) pero la presion esta muy por debajo de lo que esa temperatura
    implicaria (vapor no saturado), duty_calidad_vapor gana sobre
    duty_proximidad y fuerza duty a 0 -- mas estricto que el duty_estable
    que aplicaria por proximidad sola. Reemplaza el viejo seguro
    unidireccional del gate anterior (temp >= t_obj) con uno mas estricto."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = 50.0  # muy por debajo de lo que P_sat(134)+11 exige
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0


def test_calidad_vapor_no_restringe_por_debajo_del_tope_de_97_por_ciento():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 129.0  # < 0.97*134 = 129.98
    estado.sensores_pres["pres_camara"] = 50.0  # lejos de P_sat(129)+11, pero el tope no se activo aun
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 1.0  # ni proximidad ni calidad_vapor restringen todavia


def test_duty_estable_igual_al_factor_configurado_en_el_objetivo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=70.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
    assert abs(fase._duty_actual - 0.3) < 1e-9  # 1 - 70/100


def test_duty_estable_cero_si_factor_es_cien():
    # tiempo_estable=999: evita que ESTABLE_PREESTERILIZACION (paso 7, fuera
    # de alcance de esta tarea) complete la fase en el mismo tick en que
    # temp/pres tocan el objetivo -- este test aisla solo el duty cycle.
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=100.0,
                                       tiempo_estable=999)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_duty_interpola_linealmente_dentro_de_la_banda_de_proximidad():
    """Ejercita la interpolacion via la distancia de PRESION (no de
    temperatura): con temp=100 bien debajo del tope del 97%,
    duty_calidad_vapor no interfiere y se puede aislar la formula de
    duty_proximidad."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 100.0  # dist_t grande -> prox_t=1.0 (clamped)
    estado.sensores_pres["pres_camara"] = p_obj - 1.0  # dist_p=1.0, margen=2.0 -> prox_p=0.5
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    # cercania=min(1.0, 0.5)=0.5 -> duty_proximidad=0.5+0.5*0.5=0.75
    assert abs(fase._duty_actual - 0.75) < 1e-9


def test_techo_independiente_fuerza_duty_cero_sin_importar_el_resto():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj + 20.0  # supera el techo (p_obj + presion_add)
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_duty_tasa_restringe_incluso_cerca_del_objetivo():
    """Cambio de comportamiento intencional respecto al diseno anterior: la
    tasa ya no es exclusiva de un tramo de aproximacion -- restringe en
    todo momento. Se ejercita via tasa_presion, con temp=100 (debajo del
    tope del 97%) para que duty_calidad_vapor no enmascare el efecto, y un
    salto de presion pequeno (+3 kPa) para quedar bajo el techo
    independiente (p_obj + 11) y no enmascararlo tampoco."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0,
                                       tasa_calentamiento=200.0, tasa_presion=10.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 100.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # duty_proximidad ya en duty_estable=1.0 (factor=0), sin tasa aun

    _sembrar_historial(fase, 100.0, p_obj, 10)
    estado.sensores_pres["pres_camara"] = p_obj + 3.0  # 18 kPa/min > tasa_presion=10, bajo el techo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    # tasa medida = (3.0 kPa) / (10s -> 1/6 min) = 18 kPa/min; duty_tasa = 10/18.
    # Tolerancia relajada a 1e-3 (en vez de 1e-9): _sembrar_historial siembra
    # el timestamp de referencia con time.time() real, y el tiempo de
    # ejecucion entre esa llamada y este update() (microsegundos, variable
    # segun la maquina/carga) se suma a la ventana de 10s medida -- con
    # 1e-9 esta asercion falla de forma reproducible por jitter de reloj de
    # pared, no por un error de formula. 1e-3 sigue siendo lo bastante
    # estricta para detectar una formula incorrecta (que produciria una
    # diferencia de ordenes de magnitud mayor).
    assert abs(fase._duty_actual - (10.0 / 18.0)) < 1e-3


# ── Correcciones de revisión final (sostenimiento / intervalo=0 / log) ────

def test_duty_calidad_vapor_no_restringe_dentro_de_sostenimiento():
    """Reproduce el patron del ciclo 72 dentro de ESTABLE_PREESTERILIZACION:
    temp ya paso el tope del 97% y la presion real todavia no "alcanza" a
    esa temperatura -- fuera de sostenimiento esto forzaria duty=0, pero
    dentro de la banda de sostenimiento el chequeo no debe aplicarse (paso
    7 ya maneja la seguridad de esa banda con su propio timeout de
    recuperacion)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0,
                                       tiempo_estable=999)
    fase.update()  # inicializar
    fase._en_sostenimiento = True

    p_obj = p_saturacion_kpa(134.0) + 11.0
    p_min_para_temp = p_saturacion_kpa(134.5) + 11.0
    assert p_obj < p_min_para_temp  # confirma que el escenario ejercita el caso: sin la
    # correccion, duty_calidad_vapor evaluaria 0.0 aqui

    estado.sensores_temp["temp_camara"] = 134.5  # dentro de t_obj + rango_temp_estabilizacion (1.0)
    estado.sensores_pres["pres_camara"] = p_obj + 1.7  # >= p_obj, pero < p_min_para_temp(134.5)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual > 0.0  # NO forzado a 0.0 por duty_calidad_vapor


def test_intervalo_cero_con_duty_cero_apaga_vapor_directo():
    """intervalo_segmentos_calor<=0 debe aplicar duty directo a
    vapor_camara_on/off sin pasar por _tick_dos_estados -- de lo contrario
    (t_on=t_off=0) _tick_dos_estados cae en su rama 'enclavada abierta' sin
    importar duty."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0,
                                       intervalo=0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj + 20.0  # supera el techo -> duty=0.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_intervalo_cero_con_duty_uno_enciende_vapor_directo():
    fase, estado, set_do = _make_fase(t_obj=134.0, t_inicial=20.0, intervalo=0)
    result = fase.update()  # lejos del objetivo -> duty=1.0
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 1.0
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_log_observabilidad_edge_triggered_en_transicion_a_duty_cero(caplog):
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0)
    fase.update()  # inicializar, duty=1.0 (lejos del objetivo)
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj + 20.0  # supera el techo -> duty=0.0

    caplog.set_level(logging.WARNING)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0
    assert caplog.text.count("vapor_camara a 0") == 1

    caplog.clear()
    fase.update()  # duty se mantiene en 0.0 -- edge-triggered, no debe repetirse
    assert fase._duty_actual == 0.0
    assert "vapor_camara a 0" not in caplog.text


def test_tasa_excedida_muchos_ticks_consecutivos_nunca_produce_fallo():
    """Restituido (eliminado sin reemplazo en un cambio anterior, señalado en
    la revision final): la unica garantia de integracion de que
    tasa_calentamiento/tasa_presion excedidas nunca producen FaseResult.FALLO
    -- los tests puros de _duty_por_tasa no ven FaseResult. A diferencia del
    test viejo (bang-bang), ahora el duty es proporcional, asi que no se
    aserta vapor_camara_off en cada tick -- solo que la fase nunca falla."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0,
                                       tasa_calentamiento=1.0, tasa_presion=1.0)
    fase.update()  # inicializar

    temp = 20.0
    pres = 100.0
    for i in range(30):
        temp_anterior, pres_anterior = temp, pres
        temp += 5.0  # salto grande cada tick -> tasa medida muy por encima del limite
        pres += 1.0  # se mantiene lejos de p_obj (~313 kPa) durante todo el bucle
        estado.sensores_temp["temp_camara"] = temp
        estado.sensores_pres["pres_camara"] = pres
        _sembrar_historial(fase, temp_anterior, pres_anterior, 10)
        result = fase.update()
        assert result == FaseResult.EN_CURSO


def test_pwm_pulso_on_luego_off_por_tiempo():
    # tiempo_estable=999: idem nota en test_duty_estable_cero_si_factor_es_cien.
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0, intervalo=2,
                                       tiempo_estable=999)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    set_do.reset_mock()
    result = fase.update()  # duty=0.5 -> primer pulso ON
    assert result == FaseResult.EN_CURSO
    assert fase._pwm_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_pwm -= 2  # simular que paso t_on (50% de 2s = 1s)
    fase.update()
    assert fase._pwm_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_pwm_factor_cero_permanece_encendido():
    # tiempo_estable=999: idem nota en test_duty_estable_cero_si_factor_es_cien.
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0, intervalo=2,
                                       tiempo_estable=999)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
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


# ── Funciones puras de duty cycle (control continuo) ─────────────────────
from autoclave.state_machine.cycle_phases.calentamiento import (
    _duty_por_tasa,
    _duty_por_proximidad,
    _duty_por_calidad_vapor,
)


def test_duty_por_tasa_sin_restriccion_si_tasa_max_es_cero():
    assert _duty_por_tasa(tasa_actual=1000.0, tasa_max=0.0) == 1.0


def test_duty_por_tasa_sin_restriccion_si_tasa_actual_es_none():
    assert _duty_por_tasa(tasa_actual=None, tasa_max=10.0) == 1.0


def test_duty_por_tasa_sin_restriccion_si_tasa_actual_es_negativa_o_cero():
    assert _duty_por_tasa(tasa_actual=0.0, tasa_max=10.0) == 1.0
    assert _duty_por_tasa(tasa_actual=-5.0, tasa_max=10.0) == 1.0


def test_duty_por_tasa_uno_si_pendiente_dentro_del_limite():
    assert _duty_por_tasa(tasa_actual=5.0, tasa_max=10.0) == 1.0


def test_duty_por_tasa_proporcional_si_pendiente_excede_el_limite():
    assert _duty_por_tasa(tasa_actual=20.0, tasa_max=10.0) == 0.5


def test_duty_por_proximidad_uno_lejos_del_objetivo():
    assert _duty_por_proximidad(dist=10.0, margen=2.0) == 1.0


def test_duty_por_proximidad_cero_en_o_despues_del_objetivo():
    assert _duty_por_proximidad(dist=0.0, margen=2.0) == 0.0
    assert _duty_por_proximidad(dist=-5.0, margen=2.0) == 0.0


def test_duty_por_proximidad_interpola_dentro_de_la_banda():
    assert _duty_por_proximidad(dist=1.0, margen=2.0) == 0.5


def test_duty_por_proximidad_margen_cero_es_un_escalon():
    assert _duty_por_proximidad(dist=5.0, margen=0.0) == 1.0
    assert _duty_por_proximidad(dist=0.0, margen=0.0) == 0.0
    assert _duty_por_proximidad(dist=-1.0, margen=0.0) == 0.0


def test_duty_por_calidad_vapor_sin_restriccion_bajo_el_tope_del_97_por_ciento():
    # t_obj=134 -> tope = 129.98; temp=129.0 esta debajo, sin importar la presion
    assert _duty_por_calidad_vapor(temp=129.0, pres=0.0, t_obj=134.0, p_add=11.0) == 1.0


def test_duty_por_calidad_vapor_cero_si_supera_el_tope_y_presion_no_corresponde():
    # temp=130 >= tope (129.98); presion muy por debajo de P_sat(130)+11
    assert _duty_por_calidad_vapor(temp=130.0, pres=1.0, t_obj=134.0, p_add=11.0) == 0.0


def test_duty_por_calidad_vapor_uno_si_presion_ya_corresponde_a_la_temperatura():
    temp = 130.0
    p_min = p_saturacion_kpa(temp) + 11.0
    assert _duty_por_calidad_vapor(temp=temp, pres=p_min, t_obj=134.0, p_add=11.0) == 1.0
