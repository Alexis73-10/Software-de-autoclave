# tests/test_preparacion_chaqueta_independiente.py
#
# 2026-11-04 (decisión del usuario): revierte A-2.2/P4 para la chaqueta en
# PREPARACION y PREPARADO. vapor_chaqueta solo lo cortan sus causas propias:
# pres_chaqueta sin lectura o en 0, corte D-CHQ, suministro de vapor (SUM-06)
# o eléctrico, paro, estado seguro y vaciado de chaqueta. Un sensor ajeno
# caído (drenaje, empaque, cámara, Referencia) o un suministro ajeno (agua,
# aire) ya no la corta; vapor_camara sigue OFF con el supervisor en falla y
# el gate de listo/inicio sigue exigiendo el supervisor.

from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state

_ESTADOS = [preparacion_state, preparado_state]


def _make(clase, *, flags=None, cycle_params=None, config_extra=None, **overrides):
    pres = {"pres_camara": 101.0, "pres_chaqueta": 200.0,
            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    temp = {"temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
            "temp_drenaje": 25.0}
    di = {"paro_emergencia": 1, "agua_bomba": 1, "agua_generador": 1,
          "aire_comprimido": 1, "vapor_suministro": 1, "suministro_electrico": 1,
          "agua_camara": 0, "puerta_1_cerrada": 1, "puerta_2_cerrada": 1}
    for k, v in overrides.items():
        if k in pres:
            pres[k] = v
        elif k in temp:
            temp[k] = v
        else:
            di[k] = v
    estado = MagicMock()
    estado.sensores_pres = pres
    estado.sensores_temp = temp
    estado.sensores_di = di
    flags = flags or {}
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    cfg_vals = {"presion_admosferica": 101.3, "rango_presion_atm": 20.0,
                "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
                "tiempo_estable_alarma": 0, "temp_max_apertura": 80.0,
                **(config_extra or {})}
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, *a: cfg_vals.get(k)
    params = {"presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
              "tipo_carga": "solido", **(cycle_params or {})}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, *a, **k: params.get(n)
    alarm_mgr = MagicMock()
    alarm_mgr.has_blocking_alarm.return_value = False
    set_do = MagicMock()
    obj = clase(alarm_mgr, estado, set_do, cycle, cfg)
    return obj, set_do


# ── Sensores ajenos caídos: la chaqueta sigue, el gate no queda listo ──────

@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", ["pres_empaque_1", "temp_drenaje", "pres_camara"])
def test_sensor_ajeno_caido_chaqueta_sigue_y_no_queda_listo(clase, sensor):
    obj, set_do = _make(clase, **{sensor: None})
    assert obj.run() is False                                  # gate: supervisor en falla
    set_do.vapor_chaqueta_on.assert_called()                    # 200 < 300: su lazo la enciende
    set_do.vapor_chaqueta_off.assert_not_called()
    set_do.vapor_camara_off.assert_called()                     # cámara sigue en OFF


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sensor_ajeno_en_cero_chaqueta_sigue(clase):
    obj, set_do = _make(clase, pres_empaque_2=0.0)
    assert obj.run() is False
    set_do.vapor_chaqueta_on.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_referencia_caida_no_corta_la_chaqueta(clase):
    # temp_ref es sensor del ciclo (alerta SEN-03 no bloqueante, no SEN-01)
    obj, set_do = _make(clase, temp_ref=None)
    obj.run()
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("suministro", ["agua_bomba", "agua_generador", "aire_comprimido"])
def test_suministro_ajeno_caido_chaqueta_sigue(clase, suministro):
    obj, set_do = _make(clase, **{suministro: 0})
    assert obj.run() is False
    set_do.vapor_chaqueta_on.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_supervisor_en_falla_no_reinicia_el_confirmador_de_la_chaqueta(clase):
    # Chaqueta en objetivo con el supervisor en falla: el apagado se confirma
    # a los 3 ticks, como con el supervisor bien (ConfirmadorApagado)
    obj, set_do = _make(clase, pres_chaqueta=305.0, temp_drenaje=None)
    obj.run()
    obj.run()
    set_do.vapor_chaqueta_off.assert_not_called()
    obj.run()
    set_do.vapor_chaqueta_off.assert_called_once()


# ── Causas propias de la chaqueta ──────────────────────────────────────────

@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("valor", [None, float("nan"), 0.0])
def test_pres_chaqueta_sin_lectura_o_cero_apaga(clase, valor):
    obj, set_do = _make(clase, pres_chaqueta=valor)
    assert obj.run() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_suministro_electrico_caido_apaga_la_chaqueta(clase):
    obj, set_do = _make(clase, suministro_electrico=0)
    assert obj.run() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_fallo_suministro_electrico_por_flag_apaga_la_chaqueta(clase):
    obj, set_do = _make(clase, flags={"FALLO_SUMINISTRO_ELECTRICO": True})
    assert obj.run() is False
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sin_di_de_suministro_electrico_falla_cerrado(clase):
    # 2026-11-04 (revisor): sin la entrada = sin suministro, como A-9
    obj, set_do = _make(clase)
    del obj.estado.sensores_di["suministro_electrico"]
    assert obj._sin_suministro_electrico() is True
    assert obj.run() is False
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sin_suministro_de_vapor_apaga_la_chaqueta(clase):
    obj, set_do = _make(clase, vapor_suministro=0)
    obj.run()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor_ajeno", [None, "temp_drenaje"])
def test_corte_dchq_apaga_aunque_este_bajo_objetivo(clase, sensor_ajeno):
    # objetivo 390 (> corte 375 de fábrica): sin D-CHQ el lazo la abriría
    extra = {sensor_ajeno: None} if sensor_ajeno else {}
    obj, set_do = _make(clase, pres_chaqueta=376.0,
                        cycle_params={"presion_chaqueta": 390.0}, **extra)
    obj.run()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_corte_dchq_usa_el_parametro_del_equipo(clase):
    obj, set_do = _make(clase, pres_chaqueta=320.0,
                        cycle_params={"presion_chaqueta": 360.0},
                        config_extra={"presion_max_chaqueta_control": 310.0})
    obj.run()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_bajo_el_corte_la_chaqueta_enciende(clase):
    obj, set_do = _make(clase, pres_chaqueta=370.0, cycle_params={"presion_chaqueta": 390.0})
    obj.run()
    set_do.vapor_chaqueta_on.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor_ajeno", [None, "temp_drenaje"])
def test_paro_siempre_gana(clase, sensor_ajeno):
    extra = {sensor_ajeno: None} if sensor_ajeno else {}
    obj, set_do = _make(clase, flags={"PARO_EMERGENCIA": True, "PARO_REAL": True}, **extra)
    assert obj.run() is False
    set_do.apagar_por_paro.assert_called_once()
    set_do.vapor_chaqueta_on.assert_not_called()


# ── Estado seguro activo: retirado con el protocolo (hotfix ES, 6-nov) ────



# ── Vaciado de chaqueta (PREPARADO) ────────────────────────────────────────

def _con_vaciado_en_curso(**overrides):
    import time

    from autoclave.state_machine.states import vaciado_chaqueta as vc
    obj, set_do = _make(preparado_state, puerta_1_cerrada=0, puerta_2_cerrada=0, **overrides)
    obj.estado.vaciado_chaqueta = vc.VaciadoChaqueta()
    obj.estado.vaciado_chaqueta.iniciar(time.monotonic())
    return obj, set_do, vc


def test_vaciado_en_curso_con_flag_electrico_no_enciende_la_chaqueta():
    obj, set_do, vc = _con_vaciado_en_curso()
    obj.estado.get_flag.side_effect = (
        lambda f: f == "FALLO_SUMINISTRO_ELECTRICO")
    obj.supervisor = MagicMock(return_value=True)   # aísla el vaciado
    assert obj._vapor_vaciado_permitido() is False
    assert obj.run() is False
    assert obj.estado.vaciado_chaqueta.estado == vc.EN_CURSO
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_vaciado_en_curso_con_di_electrica_en_cero_no_enciende_la_chaqueta():
    obj, set_do, _ = _con_vaciado_en_curso(suministro_electrico=0)
    obj.supervisor = MagicMock(return_value=True)
    obj.run()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_vaciado_en_curso_con_suministro_enciende_la_chaqueta():
    obj, set_do, _ = _con_vaciado_en_curso()
    obj.supervisor = MagicMock(return_value=True)
    obj.run()
    set_do.vapor_chaqueta_on.assert_called()


def test_vaciado_activo_con_supervisor_en_falla_off_y_luego_lazo_propio():
    obj, set_do, vc = _con_vaciado_en_curso(temp_drenaje=None)
    assert obj.run() is False                   # termina el vaciado: vapor OFF ese tick
    assert obj.estado.vaciado_chaqueta.estado == vc.HECHO
    set_do.vapor_chaqueta_off.assert_called()
    set_do.descompresion_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.reset_mock()
    assert obj.run() is False                   # siguiente: su lazo (200 < 300) la enciende
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


# ── Gate ───────────────────────────────────────────────────────────────────

def test_preparado_con_todo_bien_queda_listo():
    obj, _ = _make(preparado_state, pres_chaqueta=300.0)
    assert obj.run() is True


def test_preparacion_con_todo_bien_termina():
    obj, _ = _make(preparacion_state, pres_chaqueta=300.0)
    assert obj.run() is True


@pytest.mark.parametrize("clase", _ESTADOS)
def test_supervisor_en_falla_con_chaqueta_en_banda_no_queda_listo(clase):
    obj, _ = _make(clase, pres_chaqueta=300.0, temp_drenaje=None)
    assert obj.run() is False
