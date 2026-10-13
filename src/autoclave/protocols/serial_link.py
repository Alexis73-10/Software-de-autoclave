
# autoclave.protocols.serial_link
# --------------------------------
# Módulo responsable de la comunicación con la tarjeta ESP32 vía puerto serial
# (protocolo v2 con CRC, ver docs/mis_plans/planeacion_protocolo_serial_esp32.md).

# Funciones principales:
# - Escanea automáticamente los puertos disponibles y detecta el ESP32.
# - Reconecta de forma automática si se pierde la conexión.
# - Lee continuamente los datos enviados (AI, DI, DO), validando el CRC de
#   cada línea; las líneas inválidas se descartan y se cuentan.
# - Mantiene en memoria el último estado recibido.
# - Permite enviar comandos SET DOx ON/OFF (con CRC).
# - Puede invocar un callback externo (`on_update`) al recibir nuevos datos
#   o al cambiar el estado del enlace.

# No implementa lógica de control ni conversión de unidades.

# Tiempos: toda medición de duración (vida de la comunicación, latido,
# reintentos) usa time.monotonic(). data["last_update"] conserva
# datetime.now() solo como sello informativo de visualización.


from __future__ import annotations

import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from autoclave.utils.logging import logger
from autoclave.protocols import device_reset
from autoclave.protocols.crc16 import agregar_crc, validar_linea
from autoclave.protocols.serial_link_config import SerialLinkConfig, cargar_config


class LineaMalformada(ValueError):
    """Línea con CRC válido pero contenido que no respeta el protocolo."""


class SerialLink:
    DATA_TIMEOUT       = 3.0  # segundos sin líneas válidas => comunicación caída
    HEARTBEAT_INTERVAL = 2.0  # segundos entre HB enviados al ESP32
    GEN_FAILURE_RESET_THRESHOLD = 5  # ~15s de reintentos (scan_interval=3.0) antes de resetear el dispositivo
    _WATCHDOG_PERIOD   = 0.1  # periodo del hilo de supervisión (latido, timeout, reconexión)

    def __init__(
        self,
        baudrate: int = 115200,
        scan_interval: Optional[float] = None,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[SerialLinkConfig] = None,
    ):
        self.config = config if config is not None else cargar_config()
        self.baudrate = baudrate
        self.scan_interval = (scan_interval if scan_interval is not None
                              else self.config.reintento_handshake_s)
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

        # Vida de la comunicación: instante (monotonic) de la última línea
        # con CRC válido, o de la apertura del puerto si aún no llega ninguna.
        self._ultima_valida_mono: Optional[float] = None

        # Instante (monotonic) de la última trama DI válida, o None si en esta
        # conexión no ha llegado ninguna. Sin DI vigente, el ControlLoop
        # publica paro de emergencia (adenda E0/E1, A-3; E6 lo reutiliza).
        self._ultima_di_mono: Optional[float] = None

        # Diagnóstico de líneas inválidas (CRC, contenido o longitud).
        self._invalidas_total = 0
        self._invalidas_consecutivas = 0

        # Buffer de recepción (solo lo toca el hilo lector).
        self._rx_buf = bytearray()
        self._descartando_linea_larga = False

        self._ack_event = threading.Event()
        self._expected_ack: Optional[str] = None

        self._ever_connected = False
        self._device_reset_attempted = False
        self._consecutive_gen_failures = 0

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
            ser = serial.Serial(port, self.baudrate, timeout=0.2)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            logger.info(f"Conectado a ESP32 en {port}")

            self._rx_buf = bytearray()
            self._descartando_linea_larga = False
            with self.data_lock:
                self.data["port_open"] = True
                self.data["data_alive"] = False
                self.data["last_update"] = None
                # DI de la conexión anterior no vale: 0 = paro (contacto NC)
                # hasta la primera trama DI de esta conexión (A-3)
                self.data["di"] = [0] * 56
                self._ultima_di_mono = None
                self._ultima_valida_mono = time.monotonic()
                self._invalidas_consecutivas = 0
            self.serial = ser

            self._ever_connected = True
            self._consecutive_gen_failures = 0
            return True

        except Exception as e:
            logger.warning(f"Error abriendo puerto {port}: {e}")
            self.serial = None

            if not self._device_reset_attempted:
                if device_reset.is_device_not_functioning_error(e):
                    self._consecutive_gen_failures += 1
                    if self._consecutive_gen_failures >= self.GEN_FAILURE_RESET_THRESHOLD:
                        self._device_reset_attempted = True
                        logger.warning(
                            "SerialLink: %d intentos con dispositivo no funcional — "
                            "intentando reset PnP de %s",
                            self._consecutive_gen_failures, port,
                        )
                        device_reset.reset_usb_serial_device(port)
                        self._consecutive_gen_failures = 0
                else:
                    self._consecutive_gen_failures = 0

            return False

    def _disconnect(self, solo_si: Optional[serial.Serial] = None):
        """Cierra el puerto. Con `solo_si`, solo actúa si ese objeto sigue
        siendo el puerto vigente: evita que un error tardío del puerto viejo
        (p.ej. el hilo lector saliendo de read()) cierre una conexión nueva."""
        with self.serial_lock:
            if solo_si is not None and self.serial is not solo_si:
                return
            if self.serial and self.serial.is_open:
                try:
                    self.serial.close()
                except Exception:
                    pass
            self.serial = None

        with self.data_lock:
            self.data["port_open"] = False
            self.data["data_alive"] = False
            self._ultima_di_mono = None

        # Nueva caída = nuevo episodio: habilita un nuevo intento de reset
        # PnP si este episodio también termina atascado (no solo el primero
        # de toda la vida del proceso).
        self._device_reset_attempted = False
        self._consecutive_gen_failures = 0

        # Sin esta notificación, quien deriva su estado de on_update (Units)
        # se quedaría con el último "conectado" recibido.
        self._notificar()

    def edad_ultima_di(self, now: Optional[float] = None) -> Optional[float]:
        """Segundos (time.monotonic) desde la última trama DI válida, o None
        si en esta conexión no ha llegado ninguna."""
        with self.data_lock:
            ultima = self._ultima_di_mono
        if ultima is None:
            return None
        return (time.monotonic() if now is None else now) - ultima

    def is_connected(self) -> bool:
        with self.data_lock:
            return self.data["port_open"] and self.data["data_alive"]

    # ---------------------------------------------------------------------
    # Loops
    # ---------------------------------------------------------------------

    def _read_loop(self):
        while self.running:
            ser = self.serial
            if not ser or not ser.is_open:
                time.sleep(0.1)
                continue

            try:
                chunk = ser.read(max(1, ser.in_waiting))
            except Exception as e:
                # SerialException o el error que lance pyserial si el puerto
                # se cerró desde otro hilo durante read().
                logger.warning("Conexión serial perdida: %s", e)
                self._disconnect(solo_si=ser)
                continue

            if chunk:
                self._alimentar(chunk)

    def _watchdog_loop(self):
        last_hb: Optional[float] = None
        last_scan: Optional[float] = None
        while self.running:
            try:
                last_hb, last_scan = self._watchdog_tick(time.monotonic(), last_hb, last_scan)
            except Exception as e:
                logger.warning("SerialLink: error en supervisión: %s", e)
            time.sleep(self._WATCHDOG_PERIOD)

    def _watchdog_tick(self, now: float, last_hb: Optional[float],
                       last_scan: Optional[float]) -> tuple[Optional[float], Optional[float]]:
        """Una pasada de supervisión con `now` = time.monotonic(). Separado
        del loop para poder probarlo sin hilos."""
        if not self.data["port_open"]:
            if last_scan is None or now - last_scan >= self.scan_interval:
                self._connect()
                last_scan = now
            return None, last_scan

        if last_hb is None or now - last_hb >= self.HEARTBEAT_INTERVAL:
            self._send_cmd("HB")
            last_hb = now
        self._check_timeout(now)
        return last_hb, last_scan

    def _check_timeout(self, now: Optional[float] = None):
        """Declara caída la comunicación si pasan DATA_TIMEOUT segundos
        (time.monotonic) sin una línea de CRC válido. Corre en el hilo de
        supervisión, independiente de readline()/read()."""
        if now is None:
            now = time.monotonic()
        with self.data_lock:
            if not self.data["port_open"]:
                return
            ultima = self._ultima_valida_mono

        if ultima is not None and now - ultima > self.DATA_TIMEOUT:
            logger.warning("Timeout de datos serial (%.1f s sin líneas válidas)", now - ultima)
            self._disconnect()

    # ---------------------------------------------------------------------
    # Recepción
    # ---------------------------------------------------------------------

    def _alimentar(self, chunk: bytes):
        """Acumula bytes y procesa cada línea completa terminada en \\n. Una
        línea que supera longitud_max_linea sin \\n se descarta entera (hasta
        el siguiente \\n) y cuenta como una sola línea inválida."""
        self._rx_buf += chunk
        maximo = self.config.longitud_max_linea
        while True:
            idx = self._rx_buf.find(b"\n")
            if idx < 0:
                if len(self._rx_buf) > maximo:
                    if not self._descartando_linea_larga:
                        self._registrar_invalida("línea demasiado larga sin \\n", None)
                        self._descartando_linea_larga = True
                    self._rx_buf.clear()
                return

            raw = bytes(self._rx_buf[:idx])
            del self._rx_buf[:idx + 1]

            if self._descartando_linea_larga:
                self._descartando_linea_larga = False
                continue
            if len(raw) > maximo:
                self._registrar_invalida("línea demasiado larga", None)
                continue
            self._procesar_linea_cruda(raw)

    def _procesar_linea_cruda(self, raw: bytes):
        """Procesa una línea (sin \\n). Nunca propaga excepciones: cualquier
        error de la línea la descarta y la cuenta como inválida, para que el
        hilo lector no muera."""
        try:
            try:
                texto = raw.rstrip(b"\r").decode("ascii")
            except UnicodeDecodeError:
                self._registrar_invalida("bytes no ASCII", raw)
                return

            payload = validar_linea(texto)
            if payload is None:
                self._registrar_invalida("CRC inválido o ausente", raw)
                return

            try:
                self._procesar_payload(payload)
            except LineaMalformada as e:
                self._registrar_invalida(f"contenido inválido ({e})", raw)
                return

            self._registrar_valida()
        except Exception as e:  # salvaguarda: el hilo lector nunca muere
            logger.exception("SerialLink: error inesperado procesando línea: %s", e)
            try:
                self._registrar_invalida(f"error inesperado ({e})", raw)
            except Exception:
                pass

    def _registrar_valida(self):
        with self.data_lock:
            self.data["last_update"] = datetime.now()  # sello informativo, no mide tiempos
            self.data["data_alive"] = True
            self._ultima_valida_mono = time.monotonic()
            self._invalidas_consecutivas = 0
        self._notificar()

    def _registrar_invalida(self, motivo: str, raw: Optional[bytes]):
        with self.data_lock:
            self._invalidas_total += 1
            self._invalidas_consecutivas += 1
            consecutivas = self._invalidas_consecutivas

        muestra = raw[:80] if raw is not None else b""
        logger.info("SerialLink: línea descartada (%s) %r [consecutivas=%d]",
                    motivo, muestra, consecutivas)

        if consecutivas >= self.config.lineas_invalidas_max:
            logger.warning("SerialLink: %d líneas inválidas consecutivas — pérdida de comunicación",
                           consecutivas)
            with self.data_lock:
                self._invalidas_consecutivas = 0
            self._disconnect()

    def _procesar_payload(self, payload: str):
        """Interpreta un payload con CRC ya validado. Lanza LineaMalformada si
        el contenido no respeta el protocolo; en ese caso no se modifica
        ningún dato (se valida completo antes de publicar)."""
        if payload.startswith("AI:"):
            vals = payload[3:].split(",")
            if len(vals) != 16:
                raise LineaMalformada(f"AI con {len(vals)} valores")
            ai = [_entero_decimal(v, 0, 4095) for v in vals]
            with self.data_lock:
                self.data["ai"] = ai

        elif payload.startswith("DI:"):
            self._bits("di", payload[3:], 56)

        elif payload.startswith("DO:"):
            self._bits("do", payload[3:], 32)

        elif payload == "ACK":
            pass

        elif payload.startswith("OK "):
            if self._expected_ack and payload == self._expected_ack:
                self._ack_event.set()

        else:
            raise LineaMalformada("tipo de línea desconocido")

    def _bits(self, clave: str, bits: str, n: int):
        if len(bits) != n or any(b not in "01" for b in bits):
            raise LineaMalformada(f"{clave.upper()} con formato inválido")
        with self.data_lock:
            self.data[clave] = [1 if b == "1" else 0 for b in bits]
            if clave == "di":
                self._ultima_di_mono = time.monotonic()

    def _notificar(self):
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

    def get_diagnostico(self) -> Dict[str, Any]:
        """Contadores de diagnóstico de la comunicación (expuestos en /status)."""
        with self.data_lock:
            return {
                "lineas_invalidas_total": self._invalidas_total,
                "lineas_invalidas_consecutivas": self._invalidas_consecutivas,
            }

    def _send_raw(self, cmd: str):
        ser = self.serial
        if not ser or not ser.is_open:
            return
        try:
            with self.serial_lock:
                ser.write(cmd.encode("ascii"))
        except Exception as e:
            logger.warning("SerialLink: error escribiendo en el puerto: %s", e)
            self._disconnect(solo_si=ser)

    def _send_cmd(self, payload: str):
        """Envía un comando del protocolo v2: `payload*HHHH\\n`."""
        self._send_raw(agregar_crc(payload) + "\n")

    def set_output(self, channel: int, state: bool) -> bool:
        if channel < 1 or channel > 32:
            return False

        if not self.serial or not self.serial.is_open:
            return False

        self._send_cmd(f"SET DO{channel} {'ON' if state else 'OFF'}")
        return True

    def all_off(self, timeout=1.0) -> bool:
        self._ack_event.clear()
        self._expected_ack = "OK ALL_OFF"

        self._send_cmd("ALL_OFF")

        ok = self._ack_event.wait(timeout)
        self._expected_ack = None

        if not ok:
            logger.warning("Timeout esperando OK ALL_OFF")

        return ok


def _entero_decimal(texto: str, minimo: int, maximo: int) -> int:
    if not texto.isdigit() or not texto.isascii():
        raise LineaMalformada(f"valor no numérico {texto!r}")
    valor = int(texto)
    if not (minimo <= valor <= maximo):
        raise LineaMalformada(f"valor fuera de rango {valor}")
    return valor
