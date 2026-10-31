# tests/test_automatizacion_perfil.py
#
# Instalación por automatización: campos del perfil, validación pura, sello en
# storage.load y rechazo de los campos de identidad en cambio_perfil.

import hashlib
import hmac
import json
import sys
import types
from datetime import datetime

import pytest

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation import cambio_perfil, storage
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.modelo import calcular_modelo
from autoclave.installation.profile import (
    InstallationProfile, ProfileValidationError, Role, validate_profile_data)

SELLO = "a" * 64


def _base(**extra):
    d = {
        "machine_id": "ACV-2026-SN000123", "model_id": "X", "serial_number": "SN000123",
        "equipment_class": "piso_lab", "door_count": 2, "door_type": "simple",
        "cooling_level": 3, "door_id": 1, "role": "operator_front",
        "created_at": "2026-05-25T05:49:47", "locked": True,
    }
    d.update(extra)
    return d


def _auto(**extra):
    return _base(tipo_instalacion="automatizacion", serial_original="ABC123",
                 modelo_original="MODELO X 20L", sello_identidad=SELLO, **extra)


def test_perfil_viejo_carga_como_fabricacion(tmp_path, monkeypatch):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_base()), encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    p = storage.load()
    assert p.tipo_instalacion == "fabricacion"
    assert p.serial_original is None and p.sello_identidad is None


def test_automatizacion_valida():
    assert validate_profile_data(_auto()) == []


@pytest.mark.parametrize("quitar", ["serial_original", "modelo_original", "sello_identidad"])
def test_automatizacion_sin_campo_es_invalida(quitar):
    d = _auto()
    del d[quitar]
    assert validate_profile_data(d)


@pytest.mark.parametrize("campo", ["serial_original", "modelo_original", "sello_identidad"])
def test_fabricacion_con_campos_es_invalida(campo):
    valor = SELLO if campo == "sello_identidad" else "ABC"
    assert validate_profile_data(_base(**{campo: valor}))
    assert validate_profile_data(_base(tipo_instalacion="fabricacion", **{campo: valor}))


def test_fabricacion_explicita_sin_campos_es_valida():
    assert validate_profile_data(_base(tipo_instalacion="fabricacion")) == []


def test_tipo_desconocido_es_invalido():
    assert validate_profile_data(_base(tipo_instalacion="otro"))


@pytest.mark.parametrize("campo,valor", [
    ("serial_original", "abc123"), ("serial_original", "AB C"), ("serial_original", " ABC"),
    ("serial_original", "A|B"), ("serial_original", "ÁBC"), ("serial_original", ""),
    ("serial_original", "A" * 41),
    ("modelo_original", "modelo x"), ("modelo_original", "MODELO  X"),
    ("modelo_original", " MODELO X"), ("modelo_original", "M|X"), ("modelo_original", ""),
    ("modelo_original", "M" * 81), ("sello_identidad", "A" * 64), ("sello_identidad", "a" * 63),
])
def test_originales_no_canonicos_o_sello_malo(campo, valor):
    d = _auto()
    d[campo] = valor
    assert validate_profile_data(d)


@pytest.mark.parametrize("sn", ["SN1", "SN12345", "SN1234567", "XX123456", "sn123456"])
def test_serial_automatizacion_exige_sn_mas_6(sn):
    d = _auto()
    d["serial_number"] = sn
    assert validate_profile_data(d)


def test_model_id_ajeno_sigue_rechazado():
    d = _auto(capacidad_litros=100, tipo_carga="V")
    d["model_id"] = "AJENO"
    assert any("model_id" in e for e in validate_profile_data(d))
    d["model_id"] = calcular_modelo("piso_lab", 100, "V", 2)
    assert validate_profile_data(d) == []


# --- storage ---

def _perfil(**kw):
    base = dict(machine_id="ACV-2026-SN000123", model_id="X", serial_number="SN000123",
                equipment_class=EquipmentClass.PISO_LAB, door_count=2, door_type=DoorType.SIMPLE,
                cooling_level=3, door_id=1, role=Role.OPERATOR_FRONT,
                created_at=datetime(2026, 5, 25, 5, 49, 47), locked=False)
    base.update(kw)
    return InstallationProfile(**base)


def test_save_fabricacion_identico_byte_a_byte(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    storage.save(_perfil())
    esperado = json.dumps({
        "machine_id": "ACV-2026-SN000123", "model_id": "X", "serial_number": "SN000123",
        "equipment_class": "piso_lab", "door_count": 2, "door_type": "simple",
        "cooling_level": 3, "door_id": 1, "role": "operator_front",
        "created_at": "2026-05-25T05:49:47", "locked": False,
        "supply_inputs": storage.normalizar_supply_inputs(None),
        "temperature_probes": storage.normalizar_temperature_probes(None),
    }, indent=2, ensure_ascii=False)
    assert f.read_text(encoding="utf-8") == esperado


def _falso_activacion(monkeypatch, verifica):
    """Sustituye solo activacion_v2.verificar_sello_identidad en el módulo real."""
    from autoclave.installation import activacion_v2
    monkeypatch.setattr(activacion_v2, "verificar_sello_identidad", verifica)


def _sello(data):
    clave = b"clave-de-prueba"
    msg = "|".join(["1", data["tipo_instalacion"], data["serial_number"],
                    data["serial_original"], data["modelo_original"]]).encode()
    return hmac.new(clave, msg, hashlib.sha256).hexdigest()


def _verifica(data, k_t=None):
    return hmac.compare_digest(data.get("sello_identidad", ""), _sello(data))


def _perfil_auto():
    p = _perfil(tipo_instalacion="automatizacion", serial_original="ABC123",
                modelo_original="MODELO X 20L")
    p.sello_identidad = _sello({"tipo_instalacion": "automatizacion",
                                "serial_number": p.serial_number,
                                "serial_original": p.serial_original,
                                "modelo_original": p.modelo_original})
    return p


def test_round_trip_automatizacion_y_sello_alterado(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    _falso_activacion(monkeypatch, _verifica)
    original = _perfil_auto()
    storage.save(original)
    cargado = storage.load()
    assert (cargado.tipo_instalacion, cargado.serial_original, cargado.modelo_original,
            cargado.sello_identidad) == ("automatizacion", "ABC123", "MODELO X 20L",
                                         original.sello_identidad)
    data = json.loads(f.read_text(encoding="utf-8"))
    data["modelo_original"] = "OTRO MODELO"
    f.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileValidationError):
        storage.load()


def test_load_automatizacion_sin_sello_valido_falla(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    _falso_activacion(monkeypatch, lambda data, k_t=None: False)
    f.write_text(json.dumps(_auto()), encoding="utf-8")
    with pytest.raises(ProfileValidationError):
        storage.load()


def test_round_trip_con_sello_real(tmp_path, monkeypatch):
    """Integración B+A: sello real de activacion_v2 con un K_t de prueba inyectado."""
    from autoclave.installation import activacion_v2 as v2
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "p.json")
    v2.configurar_transporte(bytes.fromhex("ab" * 32))
    try:
        p = _perfil(tipo_instalacion="automatizacion", serial_original="ABC123",
                    modelo_original="MODELO X 20L")
        p.sello_identidad = v2.sellar_identidad("automatizacion", p.serial_number,
                                                p.serial_original, p.modelo_original)
        storage.save(p)
        assert storage.load().sello_identidad == p.sello_identidad
        v2.configurar_transporte(bytes.fromhex("cd" * 32))      # otro K_t: el sello ya no vale
        with pytest.raises(ProfileValidationError):
            storage.load()
        v2.configurar_transporte(b"")                           # sin K_t: falla cerrado
        with pytest.raises(ProfileValidationError):
            storage.load()
    finally:
        v2.configurar_transporte(None)


def test_load_fabricacion_no_consulta_el_sello(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)

    def _no(data, k_t=None):
        raise AssertionError("fabricacion no debe verificar sello")
    _falso_activacion(monkeypatch, _no)
    f.write_text(json.dumps(_base()), encoding="utf-8")
    assert storage.load().tipo_instalacion == "fabricacion"


# --- cambio_perfil ---

@pytest.mark.parametrize("campo", cambio_perfil.CAMPOS_DE_IDENTIDAD)
def test_cambio_perfil_rechaza_campos_de_identidad(tmp_path, campo):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_base()), encoding="utf-8")
    antes = f.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        cambio_perfil.escribir_campo(f, campo, "x", "prueba", confirmado=True)
    assert f.read_text(encoding="utf-8") == antes


def test_campos_de_identidad_exactos():
    assert cambio_perfil.CAMPOS_DE_IDENTIDAD == (
        "serial_number", "machine_id", "tipo_instalacion",
        "serial_original", "modelo_original", "sello_identidad")
