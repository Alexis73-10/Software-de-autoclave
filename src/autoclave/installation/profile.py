# src/autoclave/installation/profile.py
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


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
    machine_id:     str
    model_id:       str
    serial_number:  str
    door_count:     int
    door_type:      str       # "simple" | "advanced"
    equipment_type: str       # "horizontal" | "vertical"
    drying_type:    str       # "vacuum" | "gravity"
    door_id:        int       # which door this PC controls (1 or 2)
    role:           Role
    created_at:     datetime
    locked:         bool = True


_REQUIRED_TYPES: dict[str, type] = {
    "machine_id":     str,
    "model_id":       str,
    "serial_number":  str,
    "door_count":     int,
    "door_type":      str,
    "equipment_type": str,
    "drying_type":    str,
    "door_id":        int,
    "role":           str,
    "created_at":     str,
    "locked":         bool,
}

_VALID_VALUES: dict[str, set] = {
    "door_count":     {1, 2},
    "door_type":      {"simple", "advanced"},
    "equipment_type": {"horizontal", "vertical"},
    "drying_type":    {"vacuum", "gravity"},
}


def validate_profile_data(data: dict) -> list[str]:
    """
    Validate raw profile dict. Returns a list of error strings.
    Empty list means the data is valid.
    """
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

    for field, valid in _VALID_VALUES.items():
        if field in data and isinstance(data[field], (str, int)) and data[field] not in valid:
            errors.append(f"valor inválido en '{field}': '{data[field]}' no está en {valid}")

    return errors
