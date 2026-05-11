# autoclave/installation/wizard.py

from datetime import datetime
from .profile import InstallationProfile, Role
from .storage import save


def launch_installation_wizard():
    print("=== MODO INSTALACIÓN ===")

    profile = InstallationProfile(
        machine_id="AUTOCLAVE-001",
        model_id="MX-500",
        serial_number="SN123456",
        door_count=2,
        drying_type="vacuum",
        door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.utcnow(),
        locked=True,
    )

    save(profile)

    print("Instalación completada. Reinicie el sistema.")
