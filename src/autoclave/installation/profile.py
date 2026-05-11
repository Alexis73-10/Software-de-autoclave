# installation/profile.py

from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class Role(Enum):
    OPERATOR_FRONT = "operator_front"
    OPERATOR_BACK = "operator_back"
    SERVICE = "service"


@dataclass
class InstallationProfile:
    machine_id: str
    model_id: str
    serial_number: str
    door_count: int
    drying_type: str
    door_id: int
    role: Role
    created_at: datetime
    locked: bool = True
