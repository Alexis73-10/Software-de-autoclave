from enum import Enum, auto

class DoorState (Enum):
    DESCONOCIDO = auto()
    CERRADO = auto()
    ABIERTO = auto()
    CERRANDO = auto()
    ABRIENDO = auto()
    ATRAPADA = auto()
    ERROR = auto()
