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
