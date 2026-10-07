from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from autoclave.state_machine.alarms.catalogo import DefinicionAlarma, Nivel


class EstadoInstancia(Enum):
    ACTIVA = "ACTIVA"
    RESUELTA_SIN_RECONOCER = "RESUELTA_SIN_RECONOCER"


class EventoAlarma(Enum):
    APARECIDA = "APARECIDA"
    RESUELTA = "RESUELTA"
    RECONOCIDA = "RECONOCIDA"
    REACTIVADA = "REACTIVADA"


def clave_de(codigo: str, origen: str | None) -> str:
    return f"{codigo}|{origen}" if origen else codigo


@dataclass
class InstanciaAlarma:
    clave: str
    definicion: DefinicionAlarma
    origen: str | None
    valores: dict
    descripcion: str
    aparecida: datetime
    estado: EstadoInstancia = EstadoInstancia.ACTIVA
    resuelta: datetime | None = None
    reconocida_por: str | None = None
    reconocida_en: datetime | None = None
    ciclo_id: int | None = None
    id_historial: int | None = None

    @property
    def codigo(self) -> str:
        return self.definicion.codigo

    @property
    def titulo(self) -> str:
        return self.definicion.titulo

    @property
    def nivel(self) -> Nivel:
        return self.definicion.nivel
