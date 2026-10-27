# tests/helpers/enlace_doble.py
# -----------------------------
# Doble en memoria de EnlaceES (protocols/enlace.py) para las pruebas que no
# necesitan el protocolo Modbus en sí (tanda 20, F1): ControlLoop, SetOutput,
# BackendContext, rutas del sistema. Sustituye a los dobles del enlace serial.
#
# Sin hilos ni red: el estado se fija a mano y `publicar()` llama a on_update
# como lo hace ModbusLink tras un sondeo. Las salidas se aplican de inmediato
# (la bobina leída sigue a la orden) salvo que se atasquen con `atascar()`.
# Para probar el protocolo Modbus se usa el simulador (m31_simulado.py).

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from autoclave.protocols.enlace import EventoTarjeta

MAC_DOBLE = "005404849DB1"


class EnlaceDoble:
    """Implementa todos los miembros de MIEMBROS_ENLACE."""

    def __init__(self, conectado: bool = True, mac: str = MAC_DOBLE):
        self.on_update: Optional[Callable[[Dict[str, Any]], None]] = None
        self.al_conectar: Optional[Callable[[Dict[str, Any]], None]] = None
        self.conectado = conectado
        self.presente = conectado
        self.expansor_caido = False
        self.iniciado = False
        self.detenido = False
        self.handshakes_pedidos = 0
        self.ticks = 0
        self.all_off_ok = True
        self.all_off_llamadas = 0
        self.ordenes: list[tuple[int, bool]] = []
        self._atascadas: dict[int, bool] = {}
        self._eventos: list[EventoTarjeta] = []
        self._tarjeta = {"version": "13 / 10,12,12,12,10", "protocolo": "modbus-tcp", "id": mac}
        self._seq_di = 0
        self._seq_ai = 0
        self._t_di: Optional[float] = None
        self._t_ai: Optional[float] = None
        self.data: Dict[str, Any] = {
            "ai": [None] * 16,
            "ai_seq": 0,
            "di": [0] * 56,
            "do": [0] * 32,
            "port_open": conectado,
            "data_alive": conectado,
            "last_update": None,
        }

    # --- Ciclo de vida --------------------------------------------------
    def start(self) -> None:
        self.iniciado = True
        if self.conectado:
            self._emitir_conectada()

    def stop(self) -> None:
        self.detenido = True

    def solicitar_handshake(self) -> None:
        self.handshakes_pedidos += 1

    # --- Estado de la conexión ------------------------------------------
    def is_connected(self) -> bool:
        return self.conectado

    def puerto_presente(self) -> bool:
        return self.presente

    @property
    def handshake_completo(self) -> bool:
        return self.conectado

    def tarjeta(self) -> Dict[str, Any]:
        return dict(self._tarjeta) if self.conectado else {}

    # --- Vida de las lecturas -------------------------------------------
    def edad_ultima_di(self, now: Optional[float] = None) -> Optional[float]:
        if self._t_di is None:
            return None
        return (time.monotonic() if now is None else now) - self._t_di

    def secuencia_ultima_di(self) -> Optional[int]:
        return self._seq_di if self._t_di is not None else None

    def secuencia_ultima_ai(self) -> Optional[int]:
        return self._seq_ai if self._t_ai is not None else None

    def estado_ultima_ai(self) -> tuple[Optional[float], Optional[int]]:
        if self._t_ai is None:
            return None, None
        return self._t_ai, self._seq_ai

    def edad_ultima_ai(self, now: Optional[float] = None) -> Optional[float]:
        if self._t_ai is None:
            return None
        return (time.monotonic() if now is None else now) - self._t_ai

    # --- Vigilancia y diagnóstico ---------------------------------------
    def marcar_tick_control(self) -> None:
        self.ticks += 1

    def expansor_fuera_de_linea(self) -> bool:
        return self.expansor_caido

    def tomar_eventos(self) -> list[EventoTarjeta]:
        eventos, self._eventos = self._eventos, []
        return eventos

    def get_state(self) -> Dict[str, Any]:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in self.data.items()}

    def get_diagnostico(self) -> Dict[str, Any]:
        return {
            "lineas_invalidas_total": 0,
            "lineas_invalidas_consecutivas": 0,
            "handshake_completo": self.conectado,
            "tarjeta_st": None,
            "modulos": {"enlace": "modbus", "mac": self._tarjeta["id"]},
        }

    # --- Salidas --------------------------------------------------------
    def set_output(self, channel: int, state: bool) -> bool:
        if not self.conectado or not 1 <= int(channel) <= 32:
            return False
        self.ordenes.append((int(channel), bool(state)))
        i = int(channel) - 1
        self.data["do"][i] = int(self._atascadas.get(i, bool(state)))
        return True

    def all_off(self, timeout: float = 1.0) -> bool:
        self.all_off_llamadas += 1
        if not self.conectado:
            return False
        for i in range(32):
            self.data["do"][i] = int(self._atascadas.get(i, False))
        return self.all_off_ok and not any(self.data["do"])

    # --- Control desde la prueba ----------------------------------------
    def publicar(self, ai: Optional[list] = None, di: Optional[list] = None,
                 now: Optional[float] = None) -> None:
        """Simula un sondeo correcto: actualiza AI/DI, secuencias y edades y
        llama a on_update."""
        t = time.monotonic() if now is None else now
        if ai is not None:
            self.data["ai"] = list(ai) + [None] * (16 - len(ai))
        if di is not None:
            self.data["di"] = [int(bool(b)) for b in di] + [0] * (56 - len(di))
        self._seq_di += 1
        self._seq_ai += 1
        self._t_di = self._t_ai = t
        self.data["ai_seq"] = self._seq_ai
        self.data["port_open"] = self.data["data_alive"] = True
        self.data["last_update"] = t
        if self.on_update is not None:
            self.on_update(self.get_state())

    def desconectar(self) -> None:
        self.conectado = False
        self.data["port_open"] = self.data["data_alive"] = False
        if self.on_update is not None:
            self.on_update(self.get_state())

    def reconectar(self) -> None:
        self.conectado = self.presente = True
        self.data["port_open"] = self.data["data_alive"] = True
        self._emitir_conectada()

    def emitir(self, origen: str, alarm_id: Optional[str], motivo: str = "") -> None:
        self._eventos.append(EventoTarjeta(origen, alarm_id, motivo))

    def atascar(self, canal: int, valor: bool) -> None:
        """La bobina `canal` (1-32) se lee siempre con `valor`."""
        self._atascadas[int(canal) - 1] = bool(valor)
        self.data["do"][int(canal) - 1] = int(valor)

    def _emitir_conectada(self) -> None:
        self.emitir("conectada", None, "doble")
        if self.al_conectar is not None:
            self.al_conectar(self.tarjeta())


class EnlaceRegistrador(EnlaceDoble):
    """EnlaceDoble que registra cada orden de salida con el texto del protocolo
    anterior (`"ALL_OFF"`, `"SET DOn ON"` / `"SET DOn OFF"`) y los canales
    (1-32) que quedan encendidos en los pines del módulo tras la orden: lista
    de (t, orden, encendidos) en `registro`, con t = `reloj[0]` (tanda 20,
    T20-03: sustituye al SerialLink con el doble del firmware V3 en B9).

    Los pines siguen a la orden de inmediato; el DO que publica el enlace
    (`get_state()["do"]`) solo se actualiza con `publicar_do()`, como la
    publicación periódica de estados."""

    def __init__(self, reloj, registro: list, **kw):
        super().__init__(**kw)
        self.reloj = reloj
        self.registro = registro
        self.pines = [False] * 32

    def _registrar(self, orden: str) -> None:
        encendidos = [c + 1 for c, v in enumerate(self.pines) if v]
        self.registro.append((self.reloj[0], orden, encendidos))

    def set_output(self, channel: int, state: bool) -> bool:
        if not self.conectado or not 1 <= int(channel) <= 32:
            return False
        self.ordenes.append((int(channel), bool(state)))
        self.pines[int(channel) - 1] = bool(state)
        self._registrar(f"SET DO{int(channel)} {'ON' if state else 'OFF'}")
        return True

    def all_off(self, timeout: float = 1.0) -> bool:
        self.all_off_llamadas += 1
        if not self.conectado:
            return False
        self.pines = [False] * 32
        self._registrar("ALL_OFF")
        return self.all_off_ok

    def publicar_do(self) -> None:
        self.data["do"] = [int(v) for v in self.pines]
