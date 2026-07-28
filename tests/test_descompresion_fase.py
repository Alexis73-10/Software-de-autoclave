import time as _time
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult

_CONFIG = {
    "presion_admosferica": 101.3,
    "rango_presion_atm":   20.0,
}

_BASE_PARAMS = {
    ("descompresion", "tiempo_pre_despresurizacion"): 0,
    ("descompresion", "modo_1", "timeout"): 10,
    ("descompresion", "modo_2", "timeout"): 30,
    ("descompresion", "modo_3", "presion_cambio"): 150,
    ("descompresion", "modo_3", "timeout"): 30,
    ("descompresion", "modo_4", "presion_camara_enfriamiento"): 200,
    ("descompresion", "modo_4", "temperatura_enfriamiento"): 80.0,
    ("descompresion", "modo_4", "tiempo_apertura_chaqueta"): 5,
    ("descompresion", "modo_4", "tiempo_cierre_chaqueta"): 10,
    ("descompresion", "modo_4", "timeout"): 120,
    ("descompresion", "modo_5", "presion_camara_enfriamiento"): 200,
    ("descompresion", "modo_5", "temperatura_enfriamiento"): 80.0,
    ("descompresion", "modo_5", "tiempo_apertura_chaqueta"): 5,
    ("descompresion", "modo_5", "tiempo_cierre_chaqueta"): 10,
    ("descompresion", "modo_5", "timeout"): 120,
}


def _make_fase(modo=1, pres=300.0, temp=120.0, tiempo_pre=0, extra_params=None):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres}
    estado.sensores_temp = {"temp_camara": temp}

    set_do = MagicMock()

    config = MagicMock()
    config.get.side_effect = lambda k, *a: _CONFIG.get(k)

    params = dict(_BASE_PARAMS)
    params[("descompresion", "modo")] = modo
    params[("descompresion", "tiempo_pre_despresurizacion")] = tiempo_pre
    if extra_params:
        params.update(extra_params)

    cycle = MagicMock()
    cycle.get_param.side_effect = lambda *keys, default=None: params.get(keys, default)

    fase = DescompresionFase(estado, set_do, cycle, config, alarm_manager=None, cap=MagicMock())
    fase.reset()
    return fase, estado, set_do


# ── Pre-espera ────────────────────────────────────────────────────────────────

def test_pre_espera_mantiene_salidas_apagadas():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0, tiempo_pre=5)
    fase.update()        # primera llamada: etapa = "pre_espera"
    set_do.reset_mock()
    fase.update()        # sigue en espera (< 5 s)
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.agua_chaqueta_on.assert_not_called()


def test_pre_espera_0_entra_directo_al_modo():
    fase, estado, set_do = _make_fase(modo=0, pres=300.0, tiempo_pre=0)
    fase.update()        # primera llamada: sin pre-espera → etapa = "modo"
    assert fase._etapa == "modo"


# ── Modo 0 ────────────────────────────────────────────────────────────────────

def test_modo_0_en_curso_con_pres_alta():
    # presion_admosferica=101.3 + rango=20 → umbral=121.3
    fase, estado, set_do = _make_fase(modo=0, pres=300.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_modo_0_completa_al_alcanzar_presion_atm():
    fase, estado, set_do = _make_fase(modo=0, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_modo_0_completa_fuerza_lenta_abierta():
    fase, estado, set_do = _make_fase(modo=0, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_on.assert_called()


def test_modo_0_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=0, pres=50.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_called()


# ── Modo 1 ────────────────────────────────────────────────────────────────────

def test_modo_1_activa_rapida():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0)
    fase.update()
    fase.update()
    set_do.descompresion_rapida_on.assert_called()


def test_modo_1_completa_y_deja_rapida_abierta():
    fase, estado, set_do = _make_fase(modo=1, pres=121.0)
    fase.update()
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_1_completa_en_vacio_cierra_rapida_y_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=1, pres=50.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()


# ── Modo 2 ────────────────────────────────────────────────────────────────────

def test_modo_2_activa_lenta():
    fase, estado, set_do = _make_fase(modo=2, pres=300.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_on.assert_called()


def test_modo_2_completa_y_deja_lenta_abierta():
    fase, estado, set_do = _make_fase(modo=2, pres=121.0)
    fase.update()
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_2_completa_en_vacio_cierra_lenta_y_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=2, pres=50.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()


# ── Timeouts ──────────────────────────────────────────────────────────────────

def test_modo_1_timeout_retorna_fallo():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0)
    fase.update()
    fase._t_timeout = _time.time() - 1  # expirado
    result = fase.update()
    assert result == FaseResult.FALLO


def test_apagar_todo_al_fallo_timeout():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0)
    fase.update()
    fase._t_timeout = _time.time() - 1
    fase.update()
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.agua_chaqueta_off.assert_called()


# ── Modo 3 ────────────────────────────────────────────────────────────────────

def test_modo_3_lenta_hasta_presion_cambio():
    # presion_cambio=150, pres=300 → sub-etapa lenta, rapida no activa
    fase, estado, set_do = _make_fase(modo=3, pres=300.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_3_transicion_a_rapida():
    # pres=140 <= presion_cambio=150 → cierra lenta, sub-etapa = "rapida"
    fase, estado, set_do = _make_fase(modo=3, pres=140.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_off.assert_called()
    assert fase._sub_etapa == "rapida"


def test_modo_3_completa_en_subetapa_rapida():
    fase, estado, set_do = _make_fase(modo=3, pres=121.0)
    fase.update()
    fase._sub_etapa = "rapida"
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_3_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=3, pres=50.0)
    fase.update()
    fase._sub_etapa = "rapida"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()


def test_modo_3_timeout_retorna_fallo():
    fase, estado, set_do = _make_fase(modo=3, pres=300.0)
    fase.update()
    fase._t_timeout = _time.time() - 1
    result = fase.update()
    assert result == FaseResult.FALLO


# ── Modo 4 ────────────────────────────────────────────────────────────────────

def test_modo_4_activa_agua_chaqueta():
    fase, estado, set_do = _make_fase(modo=4, pres=300.0, temp=120.0)
    fase.update()
    fase.update()
    set_do.agua_chaqueta_on.assert_called()


def test_modo_4_pulso_aire_cuando_pres_baja():
    # pres=100 < presion_camara_enfriamiento=200 → aire_on
    fase, estado, set_do = _make_fase(modo=4, pres=100.0, temp=120.0)
    fase.update()
    fase.update()
    set_do.aire_comprimido_camara_on.assert_called()


def test_modo_4_aire_espera_3s_entre_pulsos():
    # Segundo tick dentro de 3 s: no vuelve a pulsar
    fase, estado, set_do = _make_fase(modo=4, pres=100.0, temp=120.0)
    fase.update()
    fase.update()   # pulso → _t_aire = now + 3 s
    set_do.aire_comprimido_camara_on.reset_mock()
    fase.update()   # dentro de 3 s → sin nuevo pulso
    set_do.aire_comprimido_camara_on.assert_not_called()


def test_modo_4_chaqueta_siempre_abierta_si_cierre_0():
    fase, estado, set_do = _make_fase(
        modo=4, pres=300.0, temp=120.0,
        extra_params={("descompresion", "modo_4", "tiempo_cierre_chaqueta"): 0},
    )
    fase.update()
    set_do.reset_mock()
    fase.update()
    set_do.descompresion_chaqueta_on.assert_called()
    set_do.descompresion_chaqueta_off.assert_not_called()


def test_modo_4_chaqueta_pulso_on_off():
    fase, estado, set_do = _make_fase(
        modo=4, pres=300.0, temp=120.0,
        extra_params={
            ("descompresion", "modo_4", "tiempo_apertura_chaqueta"): 5,
            ("descompresion", "modo_4", "tiempo_cierre_chaqueta"): 10,
        },
    )
    fase.update()
    fase.update()   # primer tick: _t_pulso inicializado, chaqueta ON
    # Simular > 5 s transcurridos
    fase._t_pulso_chaqueta = _time.time() - 6
    fase._chaqueta_abierta = True
    set_do.reset_mock()
    fase.update()
    set_do.descompresion_chaqueta_off.assert_called()


def test_modo_4_transicion_a_descompresion_al_alcanzar_temp():
    fase, estado, set_do = _make_fase(modo=4, pres=300.0, temp=120.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 79.0   # <= temperatura_enfriamiento=80
    fase.update()
    set_do.agua_chaqueta_off.assert_called()
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.descompresion_rapida_on.assert_called()
    set_do.descompresion_chaqueta_on.assert_called()
    assert fase._sub_etapa == "descompresion"


def test_modo_4_completa_y_deja_chaqueta_rapida_abiertas():
    fase, estado, set_do = _make_fase(modo=4, pres=121.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.descompresion_chaqueta_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_4_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=4, pres=50.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_chaqueta_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()


# ── Modo 5 ────────────────────────────────────────────────────────────────────

def test_modo_5_lenta_activa_durante_enfriamiento():
    fase, estado, set_do = _make_fase(modo=5, pres=300.0, temp=120.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_on.assert_called()


def test_modo_5_lenta_apagada_al_transicionar():
    fase, estado, set_do = _make_fase(modo=5, pres=300.0, temp=120.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 79.0
    fase.update()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_on.assert_called()


def test_modo_5_completa_y_deja_chaqueta_rapida_abiertas():
    fase, estado, set_do = _make_fase(modo=5, pres=121.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_5_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=5, pres=50.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()
