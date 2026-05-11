# installation/storage.py

import json
from pathlib import Path
from datetime import datetime
from .profile import InstallationProfile, Role


INSTALLATION_FILE = Path("installation_profile.json")


def exists() -> bool:
    return INSTALLATION_FILE.exists()


def load() -> InstallationProfile:
    data = json.loads(INSTALLATION_FILE.read_text())

    return InstallationProfile(
        machine_id=data["machine_id"],
        model_id=data["model_id"],
        serial_number=data["serial_number"],
        door_count=data["door_count"],
        drying_type=data["drying_type"],
        door_id=data["door_id"],
        role=Role(data["role"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        locked=data["locked"],
    )


def save(profile: InstallationProfile):
    if profile.locked and exists():
        raise RuntimeError("Installation profile is locked")

    INSTALLATION_FILE.write_text(json.dumps({
        "machine_id": profile.machine_id,
        "model_id": profile.model_id,
        "serial_number": profile.serial_number,
        "door_count": profile.door_count,
        "drying_type": profile.drying_type,
        "door_id": profile.door_id,
        "role": profile.role.value,
        "created_at": profile.created_at.isoformat(),
        "locked": profile.locked,
    }, indent=2))
