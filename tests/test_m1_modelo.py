"""M1 (tanda 7): cálculo del modelo comercial y campos nuevos del perfil
(planeacion_asistente_modelo.md §2, §3 y §6)."""

import json
from datetime import datetime

import pytest

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation import storage
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.modelo import (CAPACIDAD_MAX, CAPACIDAD_MIN, CLASES_INSTALABLES,
                                           TIPOS_CARGA, calcular_modelo, clase_instalable)
from autoclave.installation.profile import InstallationProfile, Role, validate_profile_data


# ── §2: regla de cálculo ─────────────────────────────────────────────────

@pytest.mark.parametrize("clase, litros, carga, puertas, esperado", [
    ("piso", 45, "V", 1, "SPK-SAT 45V"),
    ("piso", 45, "V", 2, "SPK-SAT 45V2"),
    ("piso_lab", 45, "V", 2, "SPK-SAT 45V2-LAB"),
    ("piso_lab", 180, "H", 1, "SPK-SAT 180H-LAB"),
    ("piso", 2000, "H", 2, "SPK-SAT 2000H2"),
    ("piso_lab", 2000, "H", 2, "SPK-SAT 2000H2-LAB"),
])
def test_tabla_de_la_spec(clase, litros, carga, puertas, esperado):
    assert calcular_modelo(clase, litros, carga, puertas) == esperado


def test_acepta_la_enumeracion_de_clase():
    assert calcular_modelo(EquipmentClass.PISO_LAB, 45, "V", 1) == "SPK-SAT 45V-LAB"


def test_largos_maximos():
    assert len(calcular_modelo("piso", 2000, "H", 2)) == 14
    assert len(calcular_modelo("piso_lab", 2000, "H", 2)) == 18


def test_limites_del_rango_aceptados():
    assert calcular_modelo("piso", CAPACIDAD_MIN, "V", 1) == "SPK-SAT 20V"
    assert calcular_modelo("piso", CAPACIDAD_MAX, "V", 1) == "SPK-SAT 2000V"


@pytest.mark.parametrize("clase", ["mesa_n", "mesa_b", "mesa_b_lab", EquipmentClass.MESA_B,
                                   "otra", "", None, "PISO"])
def test_rechaza_clase_fuera_de_alcance(clase):
    with pytest.raises(ValueError):
        calcular_modelo(clase, 45, "V", 1)


@pytest.mark.parametrize("litros", [19, 2001, 0, -45, 45.5, 45.0, "45", True, False, None])
def test_rechaza_capacidad_invalida(litros):
    with pytest.raises(ValueError):
        calcular_modelo("piso", litros, "V", 1)


@pytest.mark.parametrize("carga", ["v", "h", "X", "", None, "VH", 1])
def test_rechaza_tipo_de_carga_invalido(carga):
    with pytest.raises(ValueError):
        calcular_modelo("piso", 45, carga, 1)


@pytest.mark.parametrize("puertas", [0, 3, -1, True, 1.0, "1", None])
def test_rechaza_puertas_invalidas(puertas):
    with pytest.raises(ValueError):
        calcular_modelo("piso", 45, "V", puertas)


def test_constantes_publicas():
    assert CLASES_INSTALABLES == ("piso", "piso_lab")
    assert TIPOS_CARGA == ("V", "H")
    assert (CAPACIDAD_MIN, CAPACIDAD_MAX) == (20, 2000)
    assert clase_instalable("piso") and clase_instalable(EquipmentClass.PISO_LAB)
    assert not clase_instalable("mesa_b") and not clase_instalable(EquipmentClass.MESA_N)


def test_modulo_puro_sin_qt():
    import autoclave.installation.modelo as m
    fuente = open(m.__file__, encoding="utf-8").read()
    assert "PySide" not in fuente and "Qt" not in fuente


# ── §3: perfil de instalación ────────────────────────────────────────────

BASE = {
    "machine_id":      "ACV-2026-SN001",
    "model_id":        "SPK-SAT 45V2-LAB",
    "serial_number":   "SN001",
    "equipment_class": "piso_lab",
    "door_count":      2,
    "door_type":       "advanced",
    "cooling_level":   2,
    "door_id":         1,
    "role":            "operator_front",
    "created_at":      "2026-01-01T00:00:00",
    "locked":          True,
    "capacidad_litros": 45,
    "tipo_carga":      "V",
}


def test_perfil_nuevo_consistente_es_valido():
    assert validate_profile_data(BASE) == []


@pytest.mark.parametrize("cambios", [
    {"model_id": "SPK-SAT 45V2"},                 # falta -LAB
    {"model_id": "MX-500"},                       # texto libre
    {"capacidad_litros": 46},                     # editado a mano
    {"tipo_carga": "H"},
    {"door_count": 1},
    {"equipment_class": "piso"},
])
def test_perfil_con_model_id_inconsistente_es_invalido(cambios):
    errores = validate_profile_data({**BASE, **cambios})
    assert any("model_id" in e for e in errores), errores


@pytest.mark.parametrize("cambios, campo", [
    ({"capacidad_litros": 19}, "capacidad_litros"),
    ({"capacidad_litros": 2001}, "capacidad_litros"),
    ({"capacidad_litros": 45.5}, "capacidad_litros"),
    ({"capacidad_litros": "45"}, "capacidad_litros"),
    ({"capacidad_litros": True}, "capacidad_litros"),
    ({"tipo_carga": "v"}, "tipo_carga"),
    ({"tipo_carga": "X"}, "tipo_carga"),
])
def test_perfil_con_campo_nuevo_invalido(cambios, campo):
    errores = validate_profile_data({**BASE, **cambios})
    assert any(campo in e for e in errores), errores


@pytest.mark.parametrize("quitar", ["capacidad_litros", "tipo_carga"])
def test_los_dos_campos_van_juntos(quitar):
    datos = dict(BASE)
    del datos[quitar]
    errores = validate_profile_data(datos)
    assert any("capacidad_litros" in e and "tipo_carga" in e for e in errores), errores


def test_perfil_nuevo_de_mesa_es_invalido():
    datos = {**BASE, "equipment_class": "mesa_b", "door_count": 1, "cooling_level": 0,
             "model_id": "SPK-SAT 45V"}
    assert validate_profile_data(datos) != []


def test_perfil_anterior_sin_campos_nuevos_sigue_valido():
    viejo = {k: v for k, v in BASE.items() if k not in ("capacidad_litros", "tipo_carga")}
    viejo["model_id"] = "AC-500 especial"
    assert validate_profile_data(viejo) == []


def test_perfil_anterior_de_mesa_sigue_valido():
    """DECISIÓN SIN CONFIRMAR (spec §3): cargar un perfil existente de mesa no se rechaza."""
    viejo = {k: v for k, v in BASE.items() if k not in ("capacidad_litros", "tipo_carga")}
    viejo.update(equipment_class="mesa_b", door_count=1, cooling_level=0, model_id="MESA-1")
    assert validate_profile_data(viejo) == []


def _perfil(**cambios):
    d = dict(machine_id="ACV-2026-SN001", model_id="SPK-SAT 45V2-LAB", serial_number="SN001",
             equipment_class=EquipmentClass.PISO_LAB, door_count=2, door_type=DoorType.ADVANCED,
             cooling_level=2, door_id=1, role=Role.OPERATOR_FRONT,
             created_at=datetime(2026, 1, 1), locked=True, capacidad_litros=45, tipo_carga="V")
    d.update(cambios)
    return InstallationProfile(**d)


def test_storage_guarda_y_carga_los_campos_nuevos(tmp_path, monkeypatch):
    ruta = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", ruta)
    storage.save(_perfil())
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["capacidad_litros"] == 45 and datos["tipo_carga"] == "V"
    p = storage.load()
    assert p.capacidad_litros == 45 and p.tipo_carga == "V" and p.model_id == "SPK-SAT 45V2-LAB"


def test_storage_perfil_anterior_sin_campos(tmp_path, monkeypatch):
    ruta = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", ruta)
    storage.save(_perfil(model_id="AC-500", capacidad_litros=None, tipo_carga=None))
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert "capacidad_litros" not in datos and "tipo_carga" not in datos   # no se migra
    p = storage.load()
    assert p.capacidad_litros is None and p.tipo_carga is None and p.model_id == "AC-500"


def test_campos_por_defecto_none():
    p = InstallationProfile(
        machine_id="m", model_id="x", serial_number="s", equipment_class=EquipmentClass.PISO,
        door_count=1, door_type=DoorType.SIMPLE, cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT, created_at=datetime(2026, 1, 1))
    assert p.capacidad_litros is None and p.tipo_carga is None


# ── §3: herramientas tools/declarar_*.py ─────────────────────────────────

@pytest.mark.parametrize("campo, valor", [
    ("model_id", "SPK-SAT 90V2-LAB"), ("door_count", 1), ("equipment_class", "piso"),
    ("capacidad_litros", 90), ("tipo_carga", "H"),
])
def test_escribir_campo_rechaza_campos_del_modelo(tmp_path, campo, valor):
    from autoclave.installation.cambio_perfil import escribir_campo
    ruta = tmp_path / "installation_profile.json"
    ruta.write_text(json.dumps(BASE), encoding="utf-8")
    with pytest.raises(ValueError, match="reinstal"):
        escribir_campo(ruta, campo, valor, "prueba", confirmado=True)
    assert json.loads(ruta.read_text(encoding="utf-8")) == BASE


def test_escribir_campo_conserva_los_campos_del_modelo(tmp_path):
    from autoclave.installation.cambio_perfil import escribir_campo
    ruta = tmp_path / "installation_profile.json"
    ruta.write_text(json.dumps(BASE), encoding="utf-8")
    escribir_campo(ruta, "temperature_probes", {"temp_ref": False}, "prueba", confirmado=True)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["capacidad_litros"] == 45 and datos["tipo_carga"] == "V"
    assert datos["model_id"] == "SPK-SAT 45V2-LAB"
