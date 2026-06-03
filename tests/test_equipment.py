import pytest
from autoclave.installation.equipment import EquipmentClass, EquipmentCapabilities, get_capabilities


def test_mesa_n_capabilities():
    cap = get_capabilities(EquipmentClass.MESA_N)
    assert isinstance(cap, EquipmentCapabilities)
    assert cap.has_vacuum is False
    assert cap.has_full_jacket is False
    assert cap.door_count_max == 1
    assert cap.cooling_level_max == 0
    assert cap.has_liquids is False
    assert cap.has_liquid_sensor is False
    assert cap.bleve_protection is False


def test_mesa_b_capabilities():
    cap = get_capabilities(EquipmentClass.MESA_B)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is False
    assert cap.door_count_max == 1
    assert cap.cooling_level_max == 0
    assert cap.has_liquids is False
    assert cap.has_liquid_sensor is False
    assert cap.bleve_protection is False


def test_mesa_b_lab_capabilities():
    cap = get_capabilities(EquipmentClass.MESA_B_LAB)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is False
    assert cap.door_count_max == 1
    assert cap.cooling_level_max == 0
    assert cap.has_liquids is True
    assert cap.has_liquid_sensor is True
    assert cap.bleve_protection is True


def test_piso_capabilities():
    cap = get_capabilities(EquipmentClass.PISO)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is True
    assert cap.door_count_max == 2
    assert cap.cooling_level_max == 4
    assert cap.has_liquids is False
    assert cap.has_liquid_sensor is False
    assert cap.bleve_protection is False


def test_piso_lab_capabilities():
    cap = get_capabilities(EquipmentClass.PISO_LAB)
    assert cap.has_vacuum is True
    assert cap.has_full_jacket is True
    assert cap.door_count_max == 2
    assert cap.cooling_level_max == 4
    assert cap.has_liquids is True
    assert cap.has_liquid_sensor is True
    assert cap.bleve_protection is True


def test_capabilities_frozen():
    cap = get_capabilities(EquipmentClass.MESA_N)
    with pytest.raises(Exception):
        cap.has_vacuum = True  # type: ignore


def test_all_equipment_classes_have_capabilities():
    for ec in EquipmentClass:
        cap = get_capabilities(ec)
        assert isinstance(cap, EquipmentCapabilities)


def test_cooling_mode_max_por_clase():
    assert get_capabilities(EquipmentClass.MESA_N).cooling_mode_max == 1
    assert get_capabilities(EquipmentClass.MESA_B).cooling_mode_max == 3
    assert get_capabilities(EquipmentClass.MESA_B_LAB).cooling_mode_max == 5
    assert get_capabilities(EquipmentClass.PISO).cooling_mode_max == 3
    assert get_capabilities(EquipmentClass.PISO_LAB).cooling_mode_max == 5
