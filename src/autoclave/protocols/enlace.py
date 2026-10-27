# autoclave.protocols.enlace
# --------------------------
# Interfaz común de los enlaces de E/S (tanda 19, MOD-02): SerialLink (tarjeta
# ESP32, protocolo serial v2) y ModbusLink (módulos Ebyte M31-U, Modbus TCP).
#
# EnlaceES es la interfaz pública que usa el resto del programa (V-01 de la
# tanda 19: ControlLoop, SetOutput, BackendContext, rutas del sistema y
# factory). EventoTarjeta vive aquí y serial_link lo reexporta, para no romper
# los imports existentes.
#
# Diccionario de on_update / get_state(): "ai" (16; 0-7 temperatura, 8-15
# presión; con Modbus un canal sin lectura es None), "ai_seq", "di" (56),
# "do" (32), "port_open", "data_alive", "last_update".

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class EventoTarjeta:
    """Suceso de la tarjeta para el ControlLoop.
    origen: "handshake" (falló el handshake), "operacion" (WD, reinicio,
    expansor o discrepancia con el handshake ya hecho) o "conectada"
    (handshake completo; alarm_id None)."""
    origen: str
    alarm_id: Optional[str]
    motivo: str


# Alarmas propias del enlace Modbus (MOD-12); las demás se reutilizan de
# serial_link (ALARMAS_HANDSHAKE / ALARMAS_OPERACION). TARJETA_SIN_ACK no
# aplica a Modbus.
ALARMAS_MODBUS = (
    "TARJETA_CONFIG_SEGURIDAD",
    "TARJETA_MODULOS_ORDEN",
)


# Miembros públicos que ambas clases deben tener (prueba de conformidad).
MIEMBROS_ENLACE = (
    "on_update", "al_conectar",
    "start", "stop", "solicitar_handshake",
    "is_connected", "puerto_presente", "handshake_completo",
    "tarjeta",
    "edad_ultima_di", "secuencia_ultima_di",
    "secuencia_ultima_ai", "estado_ultima_ai", "edad_ultima_ai",
    "marcar_tick_control", "expansor_fuera_de_linea",
    "tomar_eventos",
    "get_state", "get_diagnostico", "set_output", "all_off",
)


@runtime_checkable
class EnlaceES(Protocol):
    on_update: Optional[Callable[[Dict[str, Any]], None]]
    al_conectar: Optional[Callable[[Dict[str, Any]], None]]

    # Ciclo de vida
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def solicitar_handshake(self) -> None: ...

    # Estado de la conexión
    def is_connected(self) -> bool: ...
    def puerto_presente(self) -> bool: ...

    @property
    def handshake_completo(self) -> bool: ...

    def tarjeta(self) -> Dict[str, Any]: ...

    # Vida de las lecturas (time.monotonic)
    def edad_ultima_di(self, now: Optional[float] = None) -> Optional[float]: ...
    def secuencia_ultima_di(self) -> Optional[int]: ...
    def secuencia_ultima_ai(self) -> Optional[int]: ...
    def estado_ultima_ai(self) -> tuple[Optional[float], Optional[int]]: ...
    def edad_ultima_ai(self, now: Optional[float] = None) -> Optional[float]: ...

    # Vigilancia del lazo y diagnóstico
    def marcar_tick_control(self) -> None: ...
    def expansor_fuera_de_linea(self) -> bool: ...
    def tomar_eventos(self) -> list[EventoTarjeta]: ...
    def get_state(self) -> Dict[str, Any]: ...
    def get_diagnostico(self) -> Dict[str, Any]: ...

    # Salidas
    def set_output(self, channel: int, state: bool) -> bool: ...
    def all_off(self, timeout: float = 1.0) -> bool: ...
