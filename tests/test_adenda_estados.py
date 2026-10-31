# tests/test_adenda_estados.py
#
# Adenda E0/E1 (docs/mis_plans/instruccion_claude_code_e0_e1_adenda.md),
# correcciones a nivel de estados y dispositivos:
#   A-1 (SAF-01)  VacuumPump respeta supply_inputs.agua_bomba
#   A-2 (TMG-02)  sondas de temperatura por perfil + salidas seguras si el
#                 supervisor falla por un sensor
#   A-4 (SAF-02)  temp_drenaje sin lectura válida -> agua_intercambiador ON
#   A-5 (SAF-03)  pres_chaqueta sin dato -> vapor_chaqueta OFF + ERROR_AI
#   A-9 (TMG-11)  CICLO usa lectura_valida

import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.devices.pump.pump import VacuumPump
from autoclave.installation.profile import (
    TEMPERATURE_PROBE_KEYS,
    normalizar_temperature_probes,
    sonda_instalada,
    sondas_no_vigiladas,
    validate_profile_data,
)
from autoclave.state_machine.states.ciclo import CicloState
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from tests.helpers.alarmas_helpers import ids_viejos_activados, ids_viejos_activos, ids_viejos_resueltos

_TEMPS = ["temp_camara", "temp_2_camara", "temp_ref", "temp_drenaje"]
# Tanda 2026-10-14 §1.1: los sensores del ciclo (Cámara 1, Cámara 2,
# Referencia) sin lectura dan una alerta NO bloqueante (SEN-03, ver
# test_t3_sensores_ciclo.py); solo el drenaje sigue bloqueando.
_TEMPS_BLOQUEAN = ["temp_drenaje"]


# ---------------------------------------------------------------------------
# A-1: VacuumPump.puede_activar() respeta supply_inputs
# ---------------------------------------------------------------------------

def _bomba(agua_bomba_di, agua_bomba_requerida, bomba_encendida=0):
    estado = MagicMock()
    estado.get_flag.return_value = False
    estado.sensores_di = {"agua_bomba": agua_bomba_di}
    estado.salidas_do = {"bomba_vacio": bomba_encendida}
    perfil = SimpleNamespace(supply_inputs={"agua_bomba": agua_bomba_requerida})
    return VacuumPump(estado, profile=perfil)


def test_bomba_arranca_con_agua_bomba_no_aplica_y_di_en_0():
    assert _bomba(agua_bomba_di=0, agua_bomba_requerida=False).puede_activar() is True


def test_bomba_no_arranca_con_agua_bomba_requerida_y_di_en_0():
    assert _bomba(agua_bomba_di=0, agua_bomba_requerida=True).puede_activar() is False


def test_bomba_sin_perfil_exige_el_di_como_antes():
    estado = MagicMock()
    estado.get_flag.return_value = False
    estado.sensores_di = {"agua_bomba": 0}
    estado.salidas_do = {"bomba_vacio": 0}
    assert VacuumPump(estado).puede_activar() is False


def test_bomba_ya_encendida_no_se_reactiva_aunque_no_aplique_el_agua():
    assert _bomba(0, False, bomba_encendida=1).puede_activar() is False


def test_bomba_bloqueada_por_fallo_electrico_aunque_no_aplique_el_agua():
    b = _bomba(0, False)
    b.estado.get_flag.side_effect = lambda f: f == "FALLO_SUMINISTRO_ELECTRICO"
    assert b.puede_activar() is False


def test_setoutput_pasa_el_perfil_a_la_bomba():
    from autoclave.devices.io.set_io import SetOutput
    estado = MagicMock()
    estado.get_flag.return_value = False
    estado.sensores_di = {"agua_bomba": 0}
    estado.salidas_do = {"bomba_vacio": 0}
    io = MagicMock()
    perfil = SimpleNamespace(supply_inputs={"agua_bomba": False})
    SetOutput(io, estado, profile=perfil).bomba_vacio_on()
    io.set_output.assert_any_call(19, True)


# ---------------------------------------------------------------------------
# A-2.1: temperature_probes en el perfil
# ---------------------------------------------------------------------------

def test_claves_de_sondas_son_los_canales_reales():
    from autoclave.core.runtime.status import EstadoAutoclave
    assert set(TEMPERATURE_PROBE_KEYS) == set(EstadoAutoclave.map_temp)


def test_sin_campo_todas_las_sondas_instaladas():
    perfil = SimpleNamespace()
    assert all(sonda_instalada(perfil, k) for k in TEMPERATURE_PROBE_KEYS)
    assert sondas_no_vigiladas(perfil) == []
    assert all(sonda_instalada(None, k) for k in TEMPERATURE_PROBE_KEYS)


def test_normalizar_completa_con_true():
    assert normalizar_temperature_probes({"temp_ref": False}) == {
        k: (k != "temp_ref") for k in TEMPERATURE_PROBE_KEYS}
    assert normalizar_temperature_probes(None) == {k: True for k in TEMPERATURE_PROBE_KEYS}


def test_sondas_no_vigiladas_en_orden_fijo():
    perfil = SimpleNamespace(temperature_probes={"temp_drenaje": False, "temp_ref": False})
    assert sondas_no_vigiladas(perfil) == ["temp_ref", "temp_drenaje"]


_PERFIL_BASE = {
    "machine_id": "ACV-2026-SN1", "model_id": "SPK", "serial_number": "SN1",
    "equipment_class": "piso_lab", "door_count": 2, "door_type": "simple",
    "cooling_level": 0, "door_id": 1, "role": "operator_front",
    "created_at": "2026-05-25T05:49:47", "locked": True,
}


def test_validacion_acepta_sondas_validas():
    data = dict(_PERFIL_BASE, temperature_probes={"temp_ref": False})
    assert validate_profile_data(data) == []


@pytest.mark.parametrize("valor", [
    {"temp_chaqueta": True},              # clave desconocida
    {"temp_ref": 1},                      # no booleano
    {"temp_camara": False},               # la sonda de control no es opcional
    ["temp_camara"],                      # no es diccionario
])
def test_validacion_rechaza_sondas_invalidas(valor):
    data = dict(_PERFIL_BASE, temperature_probes=valor)
    assert validate_profile_data(data) != []


def test_storage_ida_y_vuelta(tmp_path, monkeypatch):
    import json
    from autoclave.installation import storage
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(dict(_PERFIL_BASE, temperature_probes={"temp_ref": False})),
                 encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    perfil = storage.load()
    assert perfil.temperature_probes["temp_ref"] is False
    assert perfil.temperature_probes["temp_camara"] is True
    f.unlink()
    storage.save(perfil)
    assert json.loads(f.read_text(encoding="utf-8"))["temperature_probes"]["temp_ref"] is False


def test_storage_sin_campo_todas_instaladas(tmp_path, monkeypatch):
    import json
    from autoclave.installation import storage
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_PERFIL_BASE), encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    assert storage.load().temperature_probes == {k: True for k in TEMPERATURE_PROBE_KEYS}


# ---------------------------------------------------------------------------
# Fábricas de PREPARACION / PREPARADO
# ---------------------------------------------------------------------------

def _config():
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
        "tiempo_estable_alarma": 0, "temp_max_apertura": 80.0,
    }.get(k)
    return cfg


def _cycle():
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }.get(n)
    return cycle


def _make(clase, perfil=None, **overrides):
    pres = {"pres_camara": 101.0, "pres_chaqueta": 300.0,
            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    temp = {k: 25.0 for k in _TEMPS}
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
    estado.get_flag.return_value = False
    alarm_mgr = MagicMock()
    set_do = MagicMock()
    obj = clase(alarm_mgr, estado, set_do, _cycle(), _config(), profile=perfil)
    return obj, alarm_mgr, set_do


def _reportadas(alarm_mgr):
    return ids_viejos_activados(alarm_mgr)


_ESTADOS = [preparacion_state, preparado_state]


# ---------------------------------------------------------------------------
# A-2.1: las sondas no instaladas no se vigilan ni bloquean
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", ["temp_2_camara", "temp_ref"])
def test_sonda_no_instalada_sin_lectura_no_alarma_ni_bloquea(clase, sensor):
    perfil = SimpleNamespace(temperature_probes={sensor: False})
    obj, am, _ = _make(clase, perfil, **{sensor: None})
    assert obj.verificar_sensores() is True
    assert f"ERROR_AI_{sensor.upper()}" not in _reportadas(am)


@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", _TEMPS_BLOQUEAN)
def test_sonda_instalada_sin_lectura_sigue_alarmando(clase, sensor):
    perfil = SimpleNamespace(temperature_probes={k: True for k in _TEMPS})
    obj, am, _ = _make(clase, perfil, **{sensor: None})
    assert obj.verificar_sensores() is False
    assert f"ERROR_AI_{sensor.upper()}" in _reportadas(am)


def test_preparacion_drenaje_sin_sonda_enfria_y_no_bloquea():
    perfil = SimpleNamespace(temperature_probes={"temp_drenaje": False})
    obj, am, set_do = _make(preparacion_state, perfil, temp_drenaje=None)
    assert obj.verificar_temperatura_drenaje() is True
    set_do.agua_intercambiador_on.assert_called()
    set_do.agua_intercambiador_off.assert_not_called()


def test_preparado_drenaje_sin_sonda_enfria_y_no_bloquea():
    perfil = SimpleNamespace(temperature_probes={"temp_drenaje": False})
    obj, am, set_do = _make(preparado_state, perfil, temp_drenaje=None)
    assert obj.mantener_drenaje() is True
    set_do.agua_intercambiador_on.assert_called()
    set_do.agua_intercambiador_off.assert_not_called()


def test_preparado_sin_sondas_opcionales_queda_listo():
    perfil = SimpleNamespace(temperature_probes={"temp_2_camara": False, "temp_ref": False})
    obj, _, _ = _make(preparado_state, perfil, temp_2_camara=None, temp_ref=None)
    assert obj.run() is True


# ---------------------------------------------------------------------------
# A-2.2: supervisor falla por sensor -> energía OFF, lazos independientes siguen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", _TEMPS_BLOQUEAN)
def test_sonda_caida_apaga_vapor_de_chaqueta_y_camara(clase, sensor):
    # chaqueta fría: sin la corrección, el lazo la habría dejado en ON
    obj, _, set_do = _make(clase, None, pres_chaqueta=200.0, **{sensor: None})
    assert obj.run() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sonda_caida_sigue_igualando_presion_de_camara(clase):
    obj, _, set_do = _make(clase, None, temp_camara=None, pres_camara=60.0)
    obj.run()
    set_do.aire_admosferico_camara_on.assert_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sonda_caida_sigue_enfriando_drenaje_caliente(clase):
    obj, _, set_do = _make(clase, None, temp_camara=None, temp_drenaje=90.0)
    obj.run()
    set_do.agua_intercambiador_on.assert_called()


def test_preparacion_sonda_caida_sigue_drenando_camara():
    obj, _, set_do = _make(preparacion_state, None, temp_camara=None, agua_camara=1)
    obj.run()
    # P-12 (tanda 6): sin tipo_carga cuenta como líquido y sin Principal no
    # se sabe si está caliente: sigue drenando, por la lenta
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


# La falla de suministro también lleva a salidas seguras (decisión P4):
# ver test_adenda_decisiones.py.


# ---------------------------------------------------------------------------
# A-4: temp_drenaje sin lectura válida -> agua_intercambiador ON
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [None, math.nan])
def test_preparacion_drenaje_invalido_fuerza_intercambiador(valor):
    obj, _, set_do = _make(preparacion_state, None, temp_drenaje=valor)
    assert obj.verificar_temperatura_drenaje() is False      # no queda listo
    set_do.agua_intercambiador_on.assert_called_once()
    set_do.agua_intercambiador_off.assert_not_called()


@pytest.mark.parametrize("valor", [None, math.nan])
def test_preparado_drenaje_invalido_fuerza_intercambiador(valor):
    obj, _, set_do = _make(preparado_state, None, temp_drenaje=valor)
    assert obj.mantener_drenaje() is False
    set_do.agua_intercambiador_on.assert_called_once()
    set_do.agua_intercambiador_off.assert_not_called()


def test_preparado_drenaje_invalido_reinicia_el_confirmador_de_apagado():
    # tras recuperar la lectura, apagar exige otra vez 3 ticks confirmados
    obj, _, set_do = _make(preparado_state, None, temp_drenaje=50.0)
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


def _ciclo(temp_drenaje=25.0, pres_chaqueta=300.0, temp_camara=120.0, pres_camara=200.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp_camara, "temp_drenaje": temp_drenaje}
    estado.sensores_pres = {"pres_camara": pres_camara, "pres_chaqueta": pres_chaqueta,
                            # S1: empaque sin lectura falla el ciclo (SEN-08)
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"vapor_suministro": 1, "puerta_1_cerrada": 1, "puerta_2_cerrada": 1}
    estado.get_flag.return_value = False
    config = MagicMock()
    config.get.side_effect = lambda k: {"temp_segura_drenaje": 60.0, "presion_empaque": 300,
                                        "presion_admosferica": 101.3,
                                        "rango_presion_atm": 20.0}.get(k)
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0}.get(n, k.get("default"))
    set_do = MagicMock()
    am = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, am)
    ciclo.reset()
    return ciclo, set_do, am


@pytest.mark.parametrize("valor", [None, math.nan, math.inf])
def test_ciclo_drenaje_invalido_fuerza_intercambiador(valor):
    ciclo, set_do, _ = _ciclo(temp_drenaje=valor)
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called_once()
    set_do.agua_intercambiador_off.assert_not_called()


def test_ciclo_drenaje_invalido_reinicia_el_conteo_de_apagado():
    ciclo, set_do, _ = _ciclo(temp_drenaje=25.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    ciclo.estado.sensores_temp["temp_drenaje"] = None
    ciclo._mantener_drenaje()
    ciclo.estado.sensores_temp["temp_drenaje"] = 25.0
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()


def test_ciclo_drenaje_invalido_en_espera_de_confirmacion():
    ciclo, set_do, _ = _ciclo(temp_drenaje=None)
    ciclo._resultado_pendiente = "COMPLETADO"
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called()


# ---------------------------------------------------------------------------
# A-5: pres_chaqueta sin dato -> vapor_chaqueta OFF + ERROR_AI_PRES_*
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [None, math.nan])
def test_preparacion_pres_chaqueta_sin_dato_apaga_vapor(valor):
    obj, _, set_do = _make(preparacion_state, None, pres_chaqueta=valor)
    assert obj.suministrar_vapor_chaqueta() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("valor", [None, math.nan])
def test_preparado_pres_chaqueta_sin_dato_apaga_vapor(valor):
    obj, _, set_do = _make(preparado_state, None, pres_chaqueta=valor)
    assert obj.mantener_chaqueta() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", ["pres_chaqueta", "pres_camara"])
def test_presion_none_genera_error_ai(clase, sensor):
    obj, am, _ = _make(clase, None, **{sensor: None})
    assert obj.verificar_sensores() is False
    # S1 (tanda 8, D8-1.3): sin lectura de presión tiene alarma propia
    # (SEN-06 cámara, SEN-07 chaqueta; "llame a servicio"), no SEN-01
    esperado = "SEN-06" if sensor == "pres_camara" else "SEN-07"
    assert esperado in _reportadas(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_presion_chaqueta_none_run_apaga_vapor(clase):
    obj, _, set_do = _make(clase, None, pres_chaqueta=None)
    assert obj.run() is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("clase", _ESTADOS)
def test_presion_valida_sigue_sin_alarma(clase):
    obj, am, _ = _make(clase, None)
    assert obj.verificar_sensores() is True
    assert not [a for a in _reportadas(am) if a.startswith("ERROR_AI_PRES")]


def test_ciclo_pres_chaqueta_sin_dato_apaga_vapor():
    ciclo, set_do, _ = _ciclo(pres_chaqueta=None)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    set_do.vapor_chaqueta_on.assert_not_called()


# ---------------------------------------------------------------------------
# A-9: CICLO usa lectura_valida
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sensor,grupo", [("temp_camara", "temp"), ("pres_camara", "pres")])
def test_ciclo_sensor_critico_nan_es_sensor_ausente(sensor, grupo):
    ciclo, _, am = _ciclo()
    getattr(ciclo.estado, f"sensores_{grupo}")[sensor] = math.nan
    ciclo.run()
    assert ciclo.estado.fase_ciclo == "SENSOR_AUSENTE"
    # S1 (tanda 8): la presión de cámara sin lectura tiene código propio (SEN-04)
    esperado = "SEN-04" if sensor == "pres_camara" else "SENSOR_AUSENTE"
    assert esperado in ids_viejos_activados(am)


def test_ciclo_valvula_reposo_pres_nan_sin_orden():
    ciclo, set_do, _ = _ciclo(pres_camara=math.nan)
    ciclo._mantener_valvula_reposo()
    set_do.aire_admosferico_camara_on.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_not_called()


def test_preparado_suministro_electrico_ausente_es_fallo():
    obj, am, _ = _make(preparado_state, None)
    del obj.estado.sensores_di["suministro_electrico"]
    assert obj.verificar_suministros() is False
    assert "SUMINISTRO_ELECTRICO" in _reportadas(am)
