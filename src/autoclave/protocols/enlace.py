# autoclave.protocols.enlace
# --------------------------
# Interfaz del enlace de E/S (tanda 19, MOD-02). Desde la tanda 20 (T20-03,
# retiro del enlace serial con la ESP32) tiene una sola implementación,
# ModbusLink (módulos Ebyte M31-U, Modbus TCP); se conserva como interfaz
# para las pruebas y sus dobles (tests/helpers/enlace_doble.py).
#
# EnlaceES es la interfaz pública que usa el resto del programa (V-01 de la
# tanda 19: ControlLoop, SetOutput, BackendContext, rutas del sistema y
# factory). EventoTarjeta vive aquí.
#
# Diccionario de on_update / get_state(): "ai" (24 desde la tanda 23, AIN-03:
# 0-5 RTD 1-6 de temperatura, 6-7 sin uso (None), 8-23 AI 1-16 de presión;
# con Modbus un canal sin lectura es None), "ai_seq", "di" (56),
# "do" (32), "port_open", "data_alive", "last_update".

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class EventoTarjeta:
    """Suceso de la tarjeta para el ControlLoop.
    origen: "handshake" (falló la conexión verificada), "operacion" (WD,
    expansor, discrepancia u orden de módulos con la conexión ya verificada)
    o "conectada" (conexión verificada; alarm_id None)."""
    origen: str
    alarm_id: Optional[str]
    motivo: str


# Alarmas de la tarjeta de E/S del plan de protocolo (§11.6), heredadas del
# enlace serial (trasladadas aquí desde serial_link.py en la tanda 20, T20-03,
# con el mismo contenido). ModbusLink reutiliza las que aplican; las que solo
# emitía el serial (ALARMAS_SOLO_SERIAL) ya no se emiten, pero su entrada de
# catálogo y sus textos se conservan para el historial y la bitácora antiguos
# (DECISIÓN SIN CONFIRMAR de T20-03).
ALARMAS_HANDSHAKE = (
    "TARJETA_SIN_TRAMA_VALIDA",
    "TARJETA_VERSION_INCOMPATIBLE",
    "TARJETA_SIN_ACK",
    "TARJETA_ALL_OFF_SIN_CONFIRMAR",
    "TARJETA_SALIDAS_NO_APAGADAS",
    "TARJETA_EXPANSOR_FUERA_DE_LINEA",
)
ALARMAS_OPERACION = (
    "TARJETA_WATCHDOG",
    "TARJETA_REINICIO",
    "DISCREPANCIA_SALIDAS",
    "TARJETA_EXPANSOR_FUERA_DE_LINEA",
)
# Solo las emitía el enlace serial (retirado en la tanda 20): solo historial.
ALARMAS_SOLO_SERIAL = (
    "TARJETA_SIN_ACK",
    "TARJETA_ALL_OFF_SIN_CONFIRMAR",
    "TARJETA_REINICIO",
)

# Alarmas propias del enlace Modbus (MOD-12). TARJETA_SIN_ACK no aplica a
# Modbus.
ALARMAS_MODBUS = (
    "TARJETA_CONFIG_SEGURIDAD",
    "TARJETA_MODULOS_ORDEN",
)


# Miembros públicos que toda implementación debe tener (prueba de conformidad).
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
