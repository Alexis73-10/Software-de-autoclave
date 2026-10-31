# ui_qml/domain/alarmas.py
#
# Clasificación pura de alarmas por severidad (tokens.json → alarmSeverity;
# hallazgo UI-05 del plan de interfaz dual-pantalla). Cuatro niveles:
#   1 Informativo    -> toast, no persistente, sin ack
#   2 Aviso          -> banner, persistente, sin ack
#   3 Alarma         -> banner parpadeante, persistente, requiere ack
#   4 Fallo crítico  -> pantalla completa, persistente, requiere ack, bloqueante

from dataclasses import dataclass

_PRESENTACION = {1: "toast", 2: "banner", 3: "banner-blink", 4: "fullscreen"}
_PERSISTENTE = {1: False, 2: True, 3: True, 4: True}
_ACK_REQUERIDO = {1: False, 2: False, 3: True, 4: True}
_BLOQUEANTE = {1: False, 2: False, 3: False, 4: True}


@dataclass(frozen=True)
class Alarma:
    id: str
    severidad: int
    ts: str
    acked: bool = False


def _validar_severidad(severidad: int) -> None:
    if severidad not in _PRESENTACION:
        raise ValueError(f"Severidad de alarma desconocida: {severidad!r}")


def presentacion_de(severidad: int) -> str:
    _validar_severidad(severidad)
    return _PRESENTACION[severidad]


def es_persistente(severidad: int) -> bool:
    _validar_severidad(severidad)
    return _PERSISTENTE[severidad]


def requiere_ack(severidad: int) -> bool:
    _validar_severidad(severidad)
    return _ACK_REQUERIDO[severidad]


def es_bloqueante(severidad: int) -> bool:
    _validar_severidad(severidad)
    return _BLOQUEANTE[severidad]


def alarma_bloqueante(alarmas: list[Alarma]) -> Alarma | None:
    """La alarma bloqueante (severidad 4, sin reconocer) más antigua entre
    las activas, o None si no hay ninguna. Solo una puede ocupar la
    pantalla completa a la vez; se prioriza la más antigua (la causa raíz)."""
    candidatas = [a for a in alarmas if es_bloqueante(a.severidad) and not a.acked]
    if not candidatas:
        return None
    return min(candidatas, key=lambda a: a.ts)
