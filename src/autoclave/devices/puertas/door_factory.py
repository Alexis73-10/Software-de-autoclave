from .simple_door import SimpleDoor
from .advanced_door import AdvancedDoor

def create_door(config, io):
    cfg           = io["cfg"]
    estado        = io["estado"]
    setdo         = io["setdo"]
    alarm_manager = io.get("alarm_manager")

    door_type = cfg["type"]

    if door_type == 1:
        return SimpleDoor(
            name=cfg["name"],
            di=cfg["di"],
            estado=estado
        )

    elif door_type == 2:
        return AdvancedDoor(
            name=cfg["name"],
            di=cfg["di"],
            do=cfg["do"],
            ai=cfg["ai"],
            estado=estado,
            setdo=setdo,
            config=config,
            alarm_manager=alarm_manager,
        )

    else:
        raise ValueError("Tipo de puerta no soportado")