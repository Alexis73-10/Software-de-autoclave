from dataclasses import dataclass
from enum import Enum


class EquipmentClass(Enum):
    MESA_N     = "mesa_n"
    MESA_B     = "mesa_b"
    MESA_B_LAB = "mesa_b_lab"
    PISO       = "piso"
    PISO_LAB   = "piso_lab"


@dataclass(frozen=True)
class EquipmentCapabilities:
    has_vacuum:        bool
    has_full_jacket:   bool
    door_count_max:    int
    cooling_level_max: int
    has_liquids:       bool
    has_liquid_sensor: bool
    bleve_protection:  bool
    cooling_mode_max:  int


_CAPABILITIES: dict[EquipmentClass, EquipmentCapabilities] = {
    EquipmentClass.MESA_N: EquipmentCapabilities(
        has_vacuum=False, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False, cooling_mode_max=1,
    ),
    EquipmentClass.MESA_B: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False, cooling_mode_max=3,
    ),
    EquipmentClass.MESA_B_LAB: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=True, has_liquid_sensor=True,
        bleve_protection=True, cooling_mode_max=5,
    ),
    EquipmentClass.PISO: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=True, door_count_max=2,
        cooling_level_max=4, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False, cooling_mode_max=3,
    ),
    EquipmentClass.PISO_LAB: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=True, door_count_max=2,
        cooling_level_max=4, has_liquids=True, has_liquid_sensor=True,
        bleve_protection=True, cooling_mode_max=5,
    ),
}


def get_capabilities(equipment_class: EquipmentClass) -> EquipmentCapabilities:
    return _CAPABILITIES[equipment_class]
