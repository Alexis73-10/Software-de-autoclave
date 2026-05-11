
# autoclave.protocols.serial_link
# --------------------------------
# Módulo responsable de la comunicación con la tarjeta ESP32 vía puerto serial.

# Funciones principales:
# - Escanea automáticamente los puertos disponibles y detecta el ESP32.
# - Reconecta de forma automática si se pierde la conexión.
# - Lee continuamente los datos enviados (AI, DI, DO).
# - Mantiene en memoria el último estado recibido.
# - Permite enviar comandos SET DOx ON/OFF.
# - Puede invocar un callback externo (`on_update`) al recibir nuevos datos.

# No implementa lógica de control ni conversión de unidades.


from __future__ import annotations

import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from autoclave.utils.logging import logger


class SerialLink:
    DATA_TIMEOUT = 3.0  # segundos sin datos => comunicación caída

    def __init__(
        self,
        baudrate: int = 115200,
        scan_interval: float = 3.0,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.baudrate = baudrate
        self.scan_interval = scan_interval
        self.on_update = on_update

        self.serial: Optional[serial.Serial] = None
        self.running = False

        self.data_lock = threading.Lock()
        self.serial_lock = threading.Lock()

        self.data = {
            "ai": [0] * 16,
            "di": [0] * 56,
            "do": [0] * 32,
            "port_open": False,
            "data_alive": False,
            "last_update": None,
        }

        self._ack_event = threading.Event()
        self._expected_ack: Optional[str] = None

        self._read_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None

    # ---------------------------------------------------------------------
    # Ciclo de vida
    # ---------------------------------------------------------------------

    def start(self):
        if self.running:
            return

        logger.info("Iniciando SerialLink")
        self.running = True

        self._read_thread = threading.Thread(
            target=self._read_loop, daemon=True
        )
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True
        )

        self._read_thread.start()
        self._watchdog_thread.start()

    def stop(self):
        logger.info("Deteniendo SerialLink")
        self.running = False
        self._disconnect()

    # ---------------------------------------------------------------------
    # Conexión
    # ---------------------------------------------------------------------

    def _scan_ports(self) -> Optional[str]:
        for port in serial.tools.list_ports.comports():
            desc = (port.description or "").lower()
            if any(x in desc for x in ("esp32", "cp210", "ch340")):
                return port.device
        return None

    def _connect(self) -> bool:
        port = self._scan_ports()
        if not port:
            return False

        try:
            self.serial = serial.Serial(port, self.baudrate, timeout=0.2)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            logger.info(f"Conectado a ESP32 en {port}")

            with self.data_lock:
                self.data["port_open"] = True
                self.data["data_alive"] = False
                self.data["last_update"] = None

            return True

        except Exception as e:
            logger.warning(f"Error abriendo puerto {port}: {e}")
            self.serial = None
            return False

    def _disconnect(self):
        with self.serial_lock:
            if self.serial and self.serial.is_open:
                try:
                    self.serial.close()
                except Exception:
                    pass
            self.serial = None

        with self.data_lock:
            self.data["port_open"] = False
            self.data["data_alive"] = False

    def is_connected(self) -> bool:
        with self.data_lock:
            return self.data["port_open"] and self.data["data_alive"]

    # ---------------------------------------------------------------------
    # Loops
    # ---------------------------------------------------------------------

    def _read_loop(self):
        while self.running:
            if not self.serial or not self.serial.is_open:
                time.sleep(0.1)
                continue

            try:
                line = self.serial.readline().decode(errors="ignore").strip()
                if not line:
                    self._check_timeout()
                    continue

                self._process_line(line)

            except serial.SerialException:
                logger.warning("Conexión serial perdida")
                self._disconnect()

    def _watchdog_loop(self):
        while self.running:
            if not self.data["port_open"]:
                self._connect()
            time.sleep(self.scan_interval)

    def _check_timeout(self):
        with self.data_lock:
            last = self.data["last_update"]

        if last and (datetime.now() - last).total_seconds() > self.DATA_TIMEOUT:
            logger.warning("Timeout de datos serial")
            self._disconnect()

    # ---------------------------------------------------------------------
    # Procesamiento
    # ---------------------------------------------------------------------

    def _process_line(self, line: str):
        with self.data_lock:
            if line.startswith("AI:"):
                vals = line[3:].split(",")
                if len(vals) == 16:
                    self.data["ai"] = [int(v) for v in vals]

            elif line.startswith("DI:"):
                bits = line[3:]
                if len(bits) >= 56:
                    self.data["di"] = [int(b) for b in bits[:56]]

            elif line.startswith("DO:"):
                bits = line[3:]
                if len(bits) >= 32:
                    self.data["do"] = [int(b) for b in bits[:32]]

            elif line.startswith("OK"):
                if self._expected_ack and self._expected_ack in line:
                    self._ack_event.set()

            self.data["last_update"] = datetime.now()
            self.data["data_alive"] = True

        if self.on_update:
            try:
                self.on_update(self.get_state())
            except Exception as e:
                logger.warning(f"Error en on_update: {e}")

    # ---------------------------------------------------------------------
    # API pública
    # ---------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        with self.data_lock:
            return {
                k: (v.copy() if isinstance(v, list) else v)
                for k, v in self.data.items()
            }

    def _send_raw(self, cmd: str):
        if not self.serial or not self.serial.is_open:
            return
        with self.serial_lock:
            self.serial.write(cmd.encode("utf-8"))

    def set_output(self, channel: int, state: bool) -> bool:
        if channel < 1 or channel > 32:
            return False

        if not self.serial or not self.serial.is_open:
            return False

        cmd = f"SET DO{channel} {'ON' if state else 'OFF'}\n"
        self._send_raw(cmd)
        return True

    def all_off(self, timeout=1.0) -> bool:
        self._ack_event.clear()
        self._expected_ack = "OK ALL_OFF"

        self._send_raw("ALL_OFF\n")

        ok = self._ack_event.wait(timeout)
        self._expected_ack = None

        if not ok:
            logger.warning("Timeout esperando OK ALL_OFF")

        return ok
