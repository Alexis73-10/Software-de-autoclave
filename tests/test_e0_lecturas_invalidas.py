# tests/test_e0_lecturas_invalidas.py
#
# E0 (CR-FC-01, PF-15 / V-07): ninguna lectura None provoca excepción ni pasa
# como válida en PREPARACION y PREPARADO.

import math
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.lectura import lectura_valida
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from tests.helpers.alarmas_helpers import ids_viejos_activados, ids_viejos_activos, ids_viejos_resueltos

_TEMPS = ["temp_camara", "temp_2_camara", "temp_ref", "temp_drenaje"]
# Tanda 2026-10-14 §1.1: los sensores del ciclo (Cámara 1, Cámara 2,
# Referencia) sin lectura dan una alerta NO bloqueante (SEN-03, ver
# test_t3_sensores_ciclo.py); solo el drenaje sigue bloqueando.
_TEMPS_BLOQUEAN = ["temp_drenaje"]

# Órdenes de válvula que PREPARACION/PREPARADO pueden emitir
_ORDENES_VALVULA = [
    "vapor_chaqueta_on", "vapor_chaqueta_off",
    "aire_admosferico_camara_on", "aire_admosferico_camara_off",
    "descompresion_rapida_on", "descompresion_rapida_off",
    "descompresion_lenta_off",
    "agua_intercambiador_on", "agua_intercambiador_off",
]


# ---------------------------------------------------------------------------
# E0-1: función pura
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [None, math.nan, math.inf, -math.inf, "abc"])
def test_lectura_valida_rechaza_none_y_no_finitos(valor):
    assert lectura_valida(valor) is False


@pytest.mark.parametrize("valor", [0, 0.0, 25.5, -3, 134])
def test_lectura_valida_acepta_numeros_finitos(valor):
    assert lectura_valida(valor) is True


# ---------------------------------------------------------------------------
# Fábricas
# ---------------------------------------------------------------------------

def _sensores_ok():
    pres = {"pres_camara": 101.0, "pres_chaqueta": 300.0,
            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    temp = {k: 25.0 for k in _TEMPS}
    di = {"paro_emergencia": 0, "agua_bomba": 1, "agua_generador": 1,
          "aire_comprimido": 1, "vapor_suministro": 1, "suministro_electrico": 1,
          "agua_camara": 0, "puerta_1_cerrada": 1, "puerta_2_cerrada": 1}
    return pres, temp, di


def _config():
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
        "tiempo_estable_alarma": 0,
    }.get(k)
    return cfg


def _cycle():
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }.get(n)
    return cycle


def _estado(pres, temp, di):
    estado = MagicMock()
    estado.sensores_pres = pres
    estado.sensores_temp = temp
    estado.sensores_di = di
    estado.get_flag.return_value = False
    return estado


def _make(clase, **overrides):
    pres, temp, di = _sensores_ok()
    for k, v in overrides.items():
        if k in pres:
            pres[k] = v
        elif k in temp:
            temp[k] = v
    alarm_mgr = MagicMock()
    set_do = MagicMock()
    estado = _estado(pres, temp, di)
    if clase is preparacion_state:
        obj = preparacion_state(alarm_mgr, estado, set_do, _cycle(), _config())
    else:
        obj = preparado_state(alarm_mgr, estado, set_do, _cycle(), _config())
    return obj, alarm_mgr, set_do


def _reportadas(alarm_mgr):
    return ids_viejos_activados(alarm_mgr)


def _ordenes(set_do):
    return [n for n in _ORDENES_VALVULA if getattr(set_do, n).called]


# ---------------------------------------------------------------------------
# E0-1: temperatura None = error de sensor (misma alarma que un 0)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
@pytest.mark.parametrize("sensor", _TEMPS_BLOQUEAN)
def test_temperatura_none_es_error_de_sensor(clase, sensor):
    obj, alarm_mgr, _ = _make(clase, **{sensor: None})
    assert obj.verificar_sensores() is False
    assert f"ERROR_AI_{sensor.upper()}" in _reportadas(alarm_mgr)
    # y no se limpia la alarma de ese sensor en el mismo tick
    assert f"ERROR_AI_{sensor.upper()}" not in ids_viejos_resueltos(alarm_mgr)


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
@pytest.mark.parametrize("sensor", _TEMPS_BLOQUEAN)
def test_temperatura_nan_es_error_de_sensor(clase, sensor):
    obj, alarm_mgr, _ = _make(clase, **{sensor: math.nan})
    assert obj.verificar_sensores() is False
    assert f"ERROR_AI_{sensor.upper()}" in _reportadas(alarm_mgr)


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
@pytest.mark.parametrize("sensor", _TEMPS_BLOQUEAN)
def test_temperatura_none_run_no_lanza_y_no_queda_listo(clase, sensor):
    obj, alarm_mgr, set_do = _make(clase, **{sensor: None})
    assert obj.run() is False
    assert f"ERROR_AI_{sensor.upper()}" in _reportadas(alarm_mgr)
    # Adenda A-2.2: con un sensor caído el vapor de chaqueta va a OFF (antes
    # las salidas quedaban congeladas) y nunca se enciende por ese None.
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    # A-4: si el caído es el drenaje, se enfría; nunca se apaga el intercambiador
    set_do.agua_intercambiador_off.assert_not_called()
    if sensor == "temp_drenaje":
        set_do.agua_intercambiador_on.assert_called()


# ---------------------------------------------------------------------------
# E0-2: temp_drenaje None — comportamiento reemplazado por la adenda A-4
# (SAF-02): sin lectura válida se fuerza agua_intercambiador ON en vez de
# "saltar el tick". Sigue sin excepción, sin TEMP_DRENAJE_ALTA y sin quedar listo.
# ---------------------------------------------------------------------------

def test_preparacion_temp_drenaje_none_sin_excepcion_enfria():
    obj, alarm_mgr, set_do = _make(preparacion_state, temp_drenaje=None)
    assert obj.verificar_temperatura_drenaje() is False
    set_do.agua_intercambiador_on.assert_called_once()
    set_do.agua_intercambiador_off.assert_not_called()
    assert "TEMP_DRENAJE_ALTA" not in _reportadas(alarm_mgr)


def test_preparacion_ejecutor_temp_drenaje_none_no_queda_listo():
    obj, _, set_do = _make(preparacion_state, temp_drenaje=None)
    assert obj.ejecutor() is False
    set_do.agua_intercambiador_on.assert_called()
    set_do.agua_intercambiador_off.assert_not_called()


def test_preparado_temp_drenaje_none_sin_excepcion_enfria():
    obj, alarm_mgr, set_do = _make(preparado_state, temp_drenaje=None)
    assert obj.mantener_drenaje() is False
    set_do.agua_intercambiador_on.assert_called_once()
    set_do.agua_intercambiador_off.assert_not_called()
    assert "TEMP_DRENAJE_ALTA" not in _reportadas(alarm_mgr)


def test_preparado_esta_preparado_temp_drenaje_none_no_falla():
    obj, _, set_do = _make(preparado_state, temp_drenaje=None)
    obj.ejecutor()
    assert obj.esta_preparado() is False
    set_do.agua_intercambiador_on.assert_called()
    set_do.agua_intercambiador_off.assert_not_called()


def test_preparado_temp_drenaje_none_reinicia_confirmador_en_curso():
    # A-4: el tick sin dato enciende el intercambiador y reinicia el conteo de
    # apagado; tras recuperar la lectura hacen falta otra vez 3 ticks.
    obj, _, set_do = _make(preparado_state, temp_drenaje=50.0)
    obj.mantener_drenaje()
    obj.mantener_drenaje()
    obj.estado.sensores_temp["temp_drenaje"] = None
    obj.mantener_drenaje()
    obj.estado.sensores_temp["temp_drenaje"] = 50.0
    obj.mantener_drenaje()
    obj.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    obj.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()


# ---------------------------------------------------------------------------
# E0-3: pres_chaqueta / pres_camara None (antes del primer dato)
# ---------------------------------------------------------------------------

def test_preparacion_pres_chaqueta_none():
    # Adenda A-5 (SAF-03): sin dato, vapor de chaqueta a OFF (antes: sin orden)
    obj, _, set_do = _make(preparacion_state, pres_chaqueta=None)
    assert obj.suministrar_vapor_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_preparacion_pres_camara_none():
    obj, _, set_do = _make(preparacion_state, pres_camara=None)
    ok, quiere_rapida = obj.igualar_presion_camara()
    assert ok is False
    assert not quiere_rapida
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_not_called()
    set_do.descompresion_lenta_off.assert_not_called()


def test_preparacion_ejecutor_pres_camara_none_sin_orden_de_rapida():
    obj, _, set_do = _make(preparacion_state, pres_camara=None)
    assert obj.ejecutor() is False
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


@pytest.mark.parametrize("sensor", ["pres_chaqueta", "pres_camara"])
def test_preparacion_run_pres_none_no_lanza_ni_queda_listo(sensor):
    obj, _, set_do = _make(preparacion_state, **{sensor: None})
    assert obj.run() is False


def test_preparado_pres_chaqueta_none():
    # Adenda A-5 (SAF-03): sin dato, vapor de chaqueta a OFF (antes: sin orden)
    obj, _, set_do = _make(preparado_state, pres_chaqueta=None)
    assert obj.mantener_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_preparado_pres_camara_none():
    obj, _, set_do = _make(preparado_state, pres_camara=None)
    assert obj.mantener_presion_camara() is False
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


@pytest.mark.parametrize("sensor", ["pres_chaqueta", "pres_camara"])
def test_preparado_run_pres_none_no_lanza_ni_queda_listo(sensor):
    obj, _, set_do = _make(preparado_state, **{sensor: None})
    assert obj.run() is False
