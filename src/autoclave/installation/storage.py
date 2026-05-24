# src/autoclave/installation/storage.py
import json
import logging
from pathlib import Path
from datetime import datetime
from .profile import InstallationProfile, Role, ProfileValidationError, validate_profile_data

logger = logging.getLogger(__name__)

INSTALLATION_FILE = Path(__file__).resolve().parents[3] / "installation_profile.json"


def exists() -> bool:
    return INSTALLATION_FILE.exists()


def load() -> InstallationProfile:
    """
    Load and validate the installation profile.
    Raises ProfileValidationError if fields are missing or have bad values.
    Raises json.JSONDecodeError if the file is not valid JSON.
    """
    data = json.loads(INSTALLATION_FILE.read_text(encoding="utf-8"))

    errors = validate_profile_data(data)
    if errors:
        raise ProfileValidationError(errors)

    return InstallationProfile(
        machine_id=data["machine_id"],
        model_id=data["model_id"],
        serial_number=data["serial_number"],
        door_count=data["door_count"],
        door_type=data["door_type"],
        equipment_type=data["equipment_type"],
        drying_type=data["drying_type"],
        door_id=data["door_id"],
        role=Role(data["role"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        locked=data["locked"],
    )


def save(profile: InstallationProfile):
    if profile.locked and exists():
        raise RuntimeError("El perfil de instalación está bloqueado y no puede modificarse")

    INSTALLATION_FILE.write_text(json.dumps({
        "machine_id":     profile.machine_id,
        "model_id":       profile.model_id,
        "serial_number":  profile.serial_number,
        "door_count":     profile.door_count,
        "door_type":      profile.door_type,
        "equipment_type": profile.equipment_type,
        "drying_type":    profile.drying_type,
        "door_id":        profile.door_id,
        "role":           profile.role.value,
        "created_at":     profile.created_at.isoformat(),
        "locked":         profile.locked,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
