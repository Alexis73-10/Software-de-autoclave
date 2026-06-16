from enum import Enum


class DoorType(Enum):
    SIMPLE            = "simple"
    MOTORIZED         = "motorized"
    LOCKING           = "locking"
    MOTORIZED_LOCKING = "motorized_locking"
    ADVANCED          = "advanced"
