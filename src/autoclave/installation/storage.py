import json
import logging
from datetime import datetime
from autoclave.installation.equipment import EquipmentClass
from autoclave.devices.puertas.door_type import DoorType
from autoclave.utils.paths import app_root
from .profile import (InstallationProfile, Role, ProfileValidationError, validate_profile_data,
                      normalizar_supply_inputs, normalizar_temperature_probes)

logger = logging.getLogger(__name__)

INSTALLATION_FILE = app_root() / "installation_profile.json"


def exists() -> bool:
    return INSTALLATION_FILE.exists()


def load() -> InstallationProfile:
    data = json.loads(INSTALLATION_FILE.read_text(encoding="utf-8"))
    errors = validate_profile_data(data)
    if errors:
        raise ProfileValidationError(errors)

    return InstallationProfile(
        machine_id=data["machine_id"],
        model_id=data["model_id"],
        serial_number=data["serial_number"],
        equipment_class=EquipmentClass(data["equipment_class"]),
        door_count=data["door_count"],
        door_type=DoorType(data["door_type"]),
        cooling_level=data["cooling_level"],
        door_id=data["door_id"],
        role=Role(data["role"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        locked=data["locked"],
        supply_inputs=normalizar_supply_inputs(data.get("supply_inputs")),
        temperature_probes=normalizar_temperature_probes(data.get("temperature_probes")),
    )


def save(profile: InstallationProfile):
    if profile.locked and exists():
        raise RuntimeError("El perfil de instalación está bloqueado y no puede modificarse")

    INSTALLATION_FILE.write_text(json.dumps({
        "machine_id":      profile.machine_id,
        "model_id":        profile.model_id,
        "serial_number":   profile.serial_number,
        "equipment_class": profile.equipment_class.value,
        "door_count":      profile.door_count,
        "door_type":       profile.door_type.value,
        "cooling_level":   profile.cooling_level,
        "door_id":         profile.door_id,
        "role":            profile.role.value,
        "created_at":      profile.created_at.isoformat(),
        "locked":          profile.locked,
        "supply_inputs":   normalizar_supply_inputs(profile.supply_inputs),
        "temperature_probes": normalizar_temperature_probes(profile.temperature_probes),
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def delete():
    INSTALLATION_FILE.unlink(missing_ok=True)
