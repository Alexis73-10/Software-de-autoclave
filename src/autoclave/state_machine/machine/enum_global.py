from enum import Enum, auto

class GlobalState(Enum):
    PREPARACION = auto()
    PREPARADO = auto()
    CICLO = auto()
    FALLA = auto()
    # P-8 (tanda 6): EMERGENCIA e HIBERNACION se retiraron por inalcanzables
    # (PF-07). El paro es la bandera PARO_EMERGENCIA en cualquier estado; la
    # suspensión (standby) es de la UI y no usa un estado de la máquina.
