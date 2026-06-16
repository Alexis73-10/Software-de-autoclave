from .simple_door import SimpleDoor
from .advanced_door import AdvancedDoor
from .door_type import DoorType


def create_door(config, io):
    cfg           = io["cfg"]
    estado        = io["estado"]
    setdo         = io["setdo"]
    alarm_manager = io.get("alarm_manager")
    door_type     = cfg["type"]

    if door_type == DoorType.SIMPLE:
        return SimpleDoor(
            name=cfg["name"],
            di=cfg["di"],
            estado=estado,
        )

    return AdvancedDoor(
        name=cfg["name"],
        di=cfg["di"],
        do=cfg.get("do", {}),
        ai=cfg.get("ai", {}),
        estado=estado,
        setdo=setdo,
        config=config,
        alarm_manager=alarm_manager,
    )
