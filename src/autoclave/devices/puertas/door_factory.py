from .simple_door import SimpleDoor
from .advanced_door import AdvancedDoor

def create_door(config, io):
    door_type = config.get("tipo_puerta")

    cfg = io["cfg"]
    estado = io["estado"]
    setdo = io["setdo"]

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
            config=config
        )

    else:
        raise ValueError("Tipo de puerta no soportado")