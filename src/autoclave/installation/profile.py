from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from autoclave.installation.equipment import EquipmentClass
from autoclave.devices.puertas.door_type import DoorType


class Role(Enum):
    OPERATOR_FRONT = "operator_front"
    OPERATOR_BACK  = "operator_back"
    SERVICE        = "service"


class ProfileValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Perfil de instalación inválido: {'; '.join(errors)}")


@dataclass
class InstallationProfile:
    machine_id:      str
    model_id:        str
    serial_number:   str
    equipment_class: EquipmentClass
    door_count:      int
    door_type:       DoorType
    cooling_level:   int
    door_id:         int
    role:            Role
    created_at:      datetime
    locked:          bool = True


_REQUIRED_TYPES: dict[str, type] = {
    "machine_id":      str,
    "model_id":        str,
    "serial_number":   str,
    "equipment_class": str,
    "door_count":      int,
    "door_type":       str,
    "cooling_level":   int,
    "door_id":         int,
    "role":            str,
    "created_at":      str,
    "locked":          bool,
}

_VALID_EQUIPMENT_CLASSES = {e.value for e in EquipmentClass}
_VALID_DOOR_TYPES        = {e.value for e in DoorType}


def validate_profile_data(data: dict) -> list[str]:
    from autoclave.installation.equipment import get_capabilities
    errors: list[str] = []

    for field, expected_type in _REQUIRED_TYPES.items():
        if field not in data:
            errors.append(f"campo faltante: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"tipo incorrecto en '{field}': "
                f"esperado {expected_type.__name__}, "
                f"recibido {type(data[field]).__name__}"
            )

    if "door_count" in data and isinstance(data["door_count"], int):
        if data["door_count"] not in {1, 2}:
            errors.append(
                f"valor inválido en 'door_count': '{data['door_count']}' no está en {{1, 2}}"
            )

    if "equipment_class" in data and isinstance(data["equipment_class"], str):
        if data["equipment_class"] not in _VALID_EQUIPMENT_CLASSES:
            errors.append(
                f"valor inválido en 'equipment_class': '{data['equipment_class']}' "
                f"no está en {_VALID_EQUIPMENT_CLASSES}"
            )

    if "door_type" in data and isinstance(data["door_type"], str):
        if data["door_type"] not in _VALID_DOOR_TYPES:
            errors.append(
                f"valor inválido en 'door_type': '{data['door_type']}' "
                f"no está en {_VALID_DOOR_TYPES}"
            )

    # Validaciones cruzadas (solo si equipment_class es válido)
    ec_value = data.get("equipment_class")
    if (ec_value in _VALID_EQUIPMENT_CLASSES
            and isinstance(data.get("door_count"), int)
            and isinstance(data.get("cooling_level"), int)):
        cap = get_capabilities(EquipmentClass(ec_value))
        if data["door_count"] > cap.door_count_max:
            errors.append(
                f"door_count {data['door_count']} excede el máximo "
                f"({cap.door_count_max}) para '{ec_value}'"
            )
        if data["cooling_level"] > cap.cooling_level_max:
            errors.append(
                f"cooling_level {data['cooling_level']} excede el máximo "
                f"({cap.cooling_level_max}) para '{ec_value}'"
            )

    return errors
