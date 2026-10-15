# tests/test_e1_supply_inputs.py
#
# E1-1 (CR-FC-02, PF-16 / V-08): entradas de suministro declaradas por perfil.
# Una entrada declarada en False es "no aplica": no alarma, no apaga la
# chaqueta y no bloquea. Campo ausente = todas requeridas (falla cerrada).

import itertools
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.installation import storage
from autoclave.installation.profile import (
    SUPPLY_INPUT_KEYS,
    InstallationProfile,
    Role,
    entrada_requerida,
    entradas_no_monitoreadas,
    validate_profile_data,
)
from autoclave.installation.equipment import EquipmentClass
from autoclave.devices.puertas.door_type import DoorType
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.states.ciclo import CicloState
from tests.alarmas_helpers import ids_viejos_activados, ids_viejos_activos, ids_viejos_resueltos

_VALIDO = {
    "machine_id": "ACV-2026-SN001", "model_id": "MX-500", "serial_number": "SN001",
    "equipment_class": "piso_lab", "door_count": 2, "door_type": "simple",
    "cooling_level": 2, "door_id": 1, "role": "operator_front",
    "created_at": "2026-01-01T00:00:00", "locked": True,
}

_SOLO_AIRE = {"agua_bomba": False, "agua_generador": False, "aire_comprimido": True,
              "vapor_suministro": False, "suministro_electrico": False}


def _perfil(supply_inputs=None, door_count=2, door_type=DoorType.SIMPLE):
    return SimpleNamespace(supply_inputs=supply_inputs, door_count=door_count,
                           door_type=door_type)


# ---------------------------------------------------------------------------
# Perfil: validación, valores por defecto y almacenamiento
# ---------------------------------------------------------------------------

def test_claves_de_suministro():
    assert set(SUPPLY_INPUT_KEYS) == {"agua_bomba", "agua_generador", "aire_comprimido",
                                      "vapor_suministro", "suministro_electrico"}


def test_campo_ausente_es_valido_y_todas_requeridas():
    assert validate_profile_data(_VALIDO) == []
    p = _perfil(supply_inputs=None)
    assert all(entrada_requerida(p, k) for k in SUPPLY_INPUT_KEYS)
    assert entradas_no_monitoreadas(p) == []


def test_sin_perfil_todas_requeridas():
    assert all(entrada_requerida(None, k) for k in SUPPLY_INPUT_KEYS)


def test_clave_faltante_en_el_diccionario_queda_requerida():
    p = _perfil(supply_inputs={"agua_bomba": False})
    assert entrada_requerida(p, "agua_bomba") is False
    assert entrada_requerida(p, "vapor_suministro") is True


def test_validacion_rechaza_valor_no_booleano():
    errores = validate_profile_data({**_VALIDO, "supply_inputs": {"agua_bomba": "no"}})
    assert any("supply_inputs" in e for e in errores)


def test_validacion_rechaza_clave_desconocida():
    errores = validate_profile_data({**_VALIDO, "supply_inputs": {"vapor": False}})
    assert any("supply_inputs" in e for e in errores)


def test_validacion_rechaza_no_diccionario():
    errores = validate_profile_data({**_VALIDO, "supply_inputs": ["agua_bomba"]})
    assert any("supply_inputs" in e for e in errores)


def test_validacion_acepta_solo_aire():
    assert validate_profile_data({**_VALIDO, "supply_inputs": _SOLO_AIRE}) == []


def test_entradas_no_monitoreadas_en_orden():
    p = _perfil(supply_inputs=_SOLO_AIRE)
    assert entradas_no_monitoreadas(p) == ["agua_bomba", "agua_generador",
                                           "vapor_suministro", "suministro_electrico"]


def test_storage_load_sin_campo_todas_requeridas(tmp_path, monkeypatch):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_VALIDO), encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    perfil = storage.load()
    assert perfil.supply_inputs == {k: True for k in SUPPLY_INPUT_KEYS}


def test_storage_load_y_save_conservan_supply_inputs(tmp_path, monkeypatch):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps({**_VALIDO, "supply_inputs": _SOLO_AIRE}), encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    perfil = storage.load()
    assert perfil.supply_inputs == _SOLO_AIRE

    f2 = tmp_path / "otro.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f2)
    storage.save(perfil)
    assert json.loads(f2.read_text(encoding="utf-8"))["supply_inputs"] == _SOLO_AIRE


def test_dataclass_por_defecto_todas_requeridas():
    p = InstallationProfile(
        machine_id="m", model_id="x", serial_number="s",
        equipment_class=EquipmentClass.PISO_LAB, door_count=2,
        door_type=DoorType.SIMPLE, cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT, created_at=datetime(2026, 1, 1),
    )
    assert p.supply_inputs == {k: True for k in SUPPLY_INPUT_KEYS}


# ---------------------------------------------------------------------------
# Estados: fábricas con todas las entradas de suministro en 0 (sin cablear)
# ---------------------------------------------------------------------------

def _estado(di_suministro=0, pres_chaqueta=250.0):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": pres_chaqueta,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_temp = {"temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
                            "temp_drenaje": 25.0}
    estado.sensores_di = {k: di_suministro for k in SUPPLY_INPUT_KEYS}
    estado.sensores_di.update({"paro_emergencia": 1, "agua_camara": 0,
                               "puerta_1_cerrada": 1, "puerta_2_cerrada": 1})
    estado.get_flag.return_value = False
    return estado


def _cycle():
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }.get(n, k.get("default"))
    return cycle


def _config():
    cfg = MagicMock()
    cfg.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0,
        "tiempo_estable_alarma": 0, "temp_max_apertura": 80.0,
    }.get(k)
    return cfg


def _reportadas(alarm_mgr):
    return ids_viejos_activados(alarm_mgr)


_COMBINACIONES = [dict(zip(SUPPLY_INPUT_KEYS, vals))
                  for vals in itertools.product([True, False], repeat=len(SUPPLY_INPUT_KEYS))]


@pytest.mark.parametrize("supply", _COMBINACIONES + [None],
                         ids=lambda s: "ausente" if s is None else
                         "-".join(k[:6] for k, v in s.items() if v) or "ninguna")
def test_preparacion_verificar_suministros_por_combinacion(supply):
    alarm_mgr = MagicMock()
    estado = _estado(di_suministro=0)
    p = preparacion_state(alarm_mgr, estado, MagicMock(), _cycle(), _config(),
                          profile=_perfil(supply_inputs=supply))
    revisadas = ["agua_bomba", "agua_generador", "aire_comprimido"]
    requeridas = [k for k in revisadas if supply is None or supply[k]]
    assert p.verificar_suministros() is (not requeridas)
    ids = _reportadas(alarm_mgr)
    for k in revisadas:
        assert (f"SUMINISTRO_{k.upper()}" in ids) is (k in requeridas)


@pytest.mark.parametrize("supply", _COMBINACIONES + [None],
                         ids=lambda s: "ausente" if s is None else
                         "-".join(k[:6] for k, v in s.items() if v) or "ninguna")
def test_preparado_verificar_suministros_por_combinacion(supply):
    alarm_mgr = MagicMock()
    estado = _estado(di_suministro=0)
    p = preparado_state(alarm_mgr, estado, MagicMock(), _cycle(), _config(),
                        profile=_perfil(supply_inputs=supply))
    revisadas = ["agua_bomba", "agua_generador", "aire_comprimido", "suministro_electrico"]
    requeridas = [k for k in revisadas if supply is None or supply[k]]
    assert p.verificar_suministros() is (not requeridas)
    ids = _reportadas(alarm_mgr)
    for k in revisadas:
        alarma = "SUMINISTRO_ELECTRICO" if k == "suministro_electrico" else f"SUMINISTRO_{k.upper()}"
        assert (alarma in ids) is (k in requeridas)


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_vapor_no_aplica_chaqueta_se_controla_por_presion(clase):
    alarm_mgr = MagicMock()
    set_do = MagicMock()
    estado = _estado(di_suministro=0, pres_chaqueta=250.0)
    p = clase(alarm_mgr, estado, set_do, _cycle(), _config(),
              profile=_perfil(supply_inputs=_SOLO_AIRE))
    fn = p.suministrar_vapor_chaqueta if clase is preparacion_state else p.mantener_chaqueta
    fn()
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()
    assert "SUMINISTRO_VAPOR" not in _reportadas(alarm_mgr)


@pytest.mark.parametrize("clase", [preparacion_state, preparado_state])
def test_vapor_requerido_y_ausente_mantiene_comportamiento(clase):
    alarm_mgr = MagicMock()
    set_do = MagicMock()
    estado = _estado(di_suministro=0, pres_chaqueta=250.0)
    p = clase(alarm_mgr, estado, set_do, _cycle(), _config(), profile=_perfil(supply_inputs=None))
    fn = p.suministrar_vapor_chaqueta if clase is preparacion_state else p.mantener_chaqueta
    fn()
    set_do.vapor_chaqueta_off.assert_called()
    assert "SUMINISTRO_VAPOR" in _reportadas(alarm_mgr)


def test_suministro_electrico_no_aplica_permite_listo():
    alarm_mgr = MagicMock()
    estado = _estado(di_suministro=0, pres_chaqueta=300.0)
    estado.sensores_di["aire_comprimido"] = 1
    p = preparado_state(alarm_mgr, estado, MagicMock(), _cycle(), _config(),
                        profile=_perfil(supply_inputs=_SOLO_AIRE))
    assert p.run() is True
    assert "SUMINISTRO_ELECTRICO" not in _reportadas(alarm_mgr)


def test_suministro_electrico_requerido_sin_entrada_no_queda_listo():
    alarm_mgr = MagicMock()
    estado = _estado(di_suministro=1, pres_chaqueta=300.0)
    estado.sensores_di["suministro_electrico"] = 0
    p = preparado_state(alarm_mgr, estado, MagicMock(), _cycle(), _config(),
                        profile=_perfil(supply_inputs=None))
    assert p.run() is False
    assert "SUMINISTRO_ELECTRICO" in _reportadas(alarm_mgr)


def test_esta_preparado_ignora_flag_electrico_si_no_aplica():
    estado = _estado(di_suministro=0, pres_chaqueta=300.0)
    estado.get_flag.side_effect = lambda f: f == "FALLO_SUMINISTRO_ELECTRICO"
    p = preparado_state(MagicMock(), estado, MagicMock(), _cycle(), _config(),
                        profile=_perfil(supply_inputs=_SOLO_AIRE))
    assert p.esta_preparado() is True


# ---------------------------------------------------------------------------
# CICLO
# ---------------------------------------------------------------------------

def _ciclo(supply):
    estado = _estado(di_suministro=0, pres_chaqueta=250.0)
    set_do = MagicMock()
    ciclo = CicloState(estado, set_do, _cycle(), _config(), MagicMock(),
                       profile=_perfil(supply_inputs=supply))
    ciclo.reset()
    return ciclo, set_do


def test_ciclo_vapor_no_aplica_no_apaga_chaqueta():
    ciclo, set_do = _ciclo(_SOLO_AIRE)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    set_do.vapor_chaqueta_on.assert_called()
    assert "SUMINISTRO_VAPOR" not in _reportadas(ciclo.alarm_manager)


def test_ciclo_vapor_requerido_y_ausente_apaga_chaqueta():
    ciclo, set_do = _ciclo(None)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called()
    assert "SUMINISTRO_VAPOR" in _reportadas(ciclo.alarm_manager)


def test_precalentamiento_sin_conflicto_on_off_con_vapor_no_aplica():
    # Antes: _mantener_chaqueta() mandaba OFF y la fase ON en el mismo tick.
    ciclo, set_do = _ciclo(_SOLO_AIRE)
    ciclo._fases[0].cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
        "presion_precalentamiento": 280.0, "tiempo_precalentamiento": 5,
        "timeout_precalentamiento": 10,
    }.get(n, k.get("default"))
    ciclo.run()
    assert ciclo.estado.fase_ciclo == "PRECALENTAMIENTO"
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_precalentamiento_con_vapor_requerido_conserva_conflicto_documentado():
    # Regresión: con la entrada requerida y en 0 sigue el comportamiento previo.
    ciclo, set_do = _ciclo(None)
    ciclo._fases[0].cycle.get_param.side_effect = lambda s, n, *a, **k: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
        "presion_precalentamiento": 280.0, "tiempo_precalentamiento": 5,
        "timeout_precalentamiento": 10,
    }.get(n, k.get("default"))
    ciclo.run()
    set_do.vapor_chaqueta_off.assert_called()
