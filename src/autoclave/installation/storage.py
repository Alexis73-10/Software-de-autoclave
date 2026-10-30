import json
import logging
import os
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
        board_id=data.get("board_id"),
        vapor_source=data.get("vapor_source"),
        capacidad_litros=data.get("capacidad_litros"),
        tipo_carga=data.get("tipo_carga"),
    )


def save(profile: InstallationProfile):
    if profile.locked and exists():
        raise RuntimeError("El perfil de instalación está bloqueado y no puede modificarse")

    texto = json.dumps({
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
        # FW-D7: solo si está emparejada (el campo ausente = sin emparejar)
        **({"board_id": profile.board_id} if profile.board_id else {}),
        # E1b: solo si se eligió (ausente = perfil anterior, ambas salidas)
        **({"vapor_source": profile.vapor_source} if profile.vapor_source else {}),
        # M1: solo en perfiles nuevos (ausentes = perfil anterior, no se migra)
        **({"capacidad_litros": profile.capacidad_litros, "tipo_carga": profile.tipo_carga}
           if profile.capacidad_litros is not None or profile.tipo_carga is not None else {}),
    }, indent=2, ensure_ascii=False)
    # TMG-03 de T9: escritura atómica (temporal + fsync + replace); un corte no
    # deja el perfil truncado
    tmp = INSTALLATION_FILE.with_name(INSTALLATION_FILE.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, INSTALLATION_FILE)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def delete():
    INSTALLATION_FILE.unlink(missing_ok=True)
