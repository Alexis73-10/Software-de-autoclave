from enum import Enum, auto

class GlobalState(Enum):
    PREPARACION = auto()
    PREPARADO = auto()
    CICLO = auto()
    FALLA = auto()
    EMERGENCIA = auto()
    HIBERNACION = auto()
