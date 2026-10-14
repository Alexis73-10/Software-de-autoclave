
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
#
# E6 (planeacion_firmware_1_5.md §5): handshake de conexión (§4.6 del plan de
# protocolo), parseo de BOOT/VER/ST/WD, comparación comandado vs DO reportado
# y latido atado al tick del ControlLoop (FW-D6). Mientras el handshake no se
# completa, is_connected() es False y no salen órdenes de salida. Los fallos
# y sucesos de la tarjeta se encolan como EventoTarjeta; quien decide la
# reacción (alarma, FALLO del ciclo, nuevo handshake) es el ControlLoop, que
# los toma en cada tick con tomar_eventos().


from __future__ import annotations

import re
import serial
import serial.tools.list_ports
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Dict, Any

from autoclave.utils.logging import logger
from autoclave.protocols import device_reset
from autoclave.protocols.crc16 import agregar_crc, validar_linea
from autoclave.protocols.serial_link_config import SerialLinkConfig, cargar_config


PROTOCOLO_ESPERADO = 2
PCF_OK_SANO = "3F"          # los 6 expansores sin error (plan de protocolo §4.5)

# Alarmas del plan de protocolo §11.6.
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

_RE_VERSION = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")
_RE_ID = re.compile(r"^[0-9A-F]{12}$")
_RE_HEX = {n: re.compile(rf"^[0-9A-F]{{{n}}}$") for n in (2, 4, 8)}
_MAX_U32 = 2 ** 32 - 1
_MAX_U64 = 2 ** 64 - 1


class LineaMalformada(ValueError):
    """Línea con CRC válido pero contenido que no respeta el protocolo."""


@dataclass(frozen=True)
class EventoTarjeta:
    """Suceso de la tarjeta para el ControlLoop.
    origen: "handshake" (falló el handshake), "operacion" (WD, reinicio,
    expansor o discrepancia con el handshake ya hecho) o "conectada"
    (handshake completo; alarm_id None)."""
    origen: str
    alarm_id: Optional[str]
    motivo: str


class SerialLink:
    DATA_TIMEOUT       = 3.0  # segundos sin líneas válidas => comunicación caída
    HEARTBEAT_INTERVAL = 2.0  # segundos entre HB enviados al ESP32
    GEN_FAILURE_RESET_THRESHOLD = 5  # ~15s de reintentos (scan_interval=3.0) antes de resetear el dispositivo
    _WATCHDOG_PERIOD   = 0.1  # periodo del hilo de supervisión (latido, timeout, reconexión)
    # FW-D6: el HB solo sale si el ControlLoop completó un tick en este margen.
    # Si el lazo se congela, el latido se detiene y el watchdog de 5 s del
    # firmware apaga todas las salidas.
    MARGEN_TICK_CONTROL = 1.5
    # Plan de protocolo §6.5: no se comparan los canales comandados hace menos.
    _TOLERANCIA_COMANDO_S = 1.0
    # TMG-05: tope de una escritura al puerto; al vencer = desconexión.
    _WRITE_TIMEOUT_S = 0.5

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
        # TMG-03: registrar una orden de salida y escribirla al puerto es
        # atómico respecto a otros escritores (lazo, reenvío del lector,
        # /io/test). Sin esto un reenvío rezagado podía salir después de una
        # orden nueva e invertir la salida.
        self._cmd_lock = threading.RLock()

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

        # --- Handshake (E6) -------------------------------------------------
        # _handshake_ok: conexión válida; solo entonces is_connected() y las
        # órdenes de salida. _handshake_pendiente: ejecutarlo en el próximo
        # tick de supervisión (tras conectar, WD o reinicio de la tarjeta).
        # _proximo_handshake: reintento tras un handshake fallido.
        self._handshake_ok = False
        self._handshake_pendiente = False
        self._proximo_handshake: Optional[float] = None
        self._en_handshake = False
        # Progreso del handshake, escrito por el hilo lector (bajo _hs_cond).
        self._hs_cond = threading.Condition()
        self._hs_reset()

        self._tarjeta: Dict[str, Any] = {"version": None, "protocolo": None, "id": None}
        self._st: Optional[Dict[str, Any]] = None
        self._ultimo_uptime: Optional[int] = None
        self._pcf_malas = 0
        self._pcf_reportado = False

        # Comparación comandado vs DO reportado: canal -> (estado, instante
        # monotonic de la orden). Solo canales comandados desde el handshake.
        self._comandado: Dict[int, tuple[bool, float]] = {}
        self._discrepancia_tramas = 0
        self._reenvio_hecho = False
        self._discrepancia_reportada = False

        self._eventos_lock = threading.Lock()
        self._eventos: list[EventoTarjeta] = []

        # FW-D6: último tick completado del ControlLoop (monotonic) o None.
        self._ultimo_tick_control: Optional[float] = None

        # Callback(tarjeta: dict) al completar cada handshake (audit_log,
        # emparejamiento). Corre en el hilo de supervisión.
        self.al_conectar: Optional[Callable[[Dict[str, Any]], None]] = None

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
            # TMG-05: write_timeout para que un driver USB atascado no
            # bloquee para siempre al escritor con serial_lock tomado.
            ser = serial.Serial(port, self.baudrate, timeout=0.2,
                                write_timeout=self._WRITE_TIMEOUT_S)
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
                # Conexión nueva = handshake nuevo antes de aceptar órdenes
                self._handshake_ok = False
                self._handshake_pendiente = True
                self._proximo_handshake = None
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
            self._handshake_ok = False
            self._handshake_pendiente = False
            self._proximo_handshake = None
        with self._hs_cond:
            self._hs_cond.notify_all()      # un handshake en curso deja de esperar

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
        """Puerto abierto, datos vivos y handshake completo (D-02: sin
        handshake válido el equipo queda sin conexión para todo el sistema)."""
        with self.data_lock:
            return (self.data["port_open"] and self.data["data_alive"]
                    and self._handshake_ok)

    @property
    def handshake_completo(self) -> bool:
        return self._handshake_ok

    def tarjeta(self) -> Dict[str, Any]:
        """Versión, protocolo e ID informados por la tarjeta en el último
        handshake (None si aún no hay)."""
        with self.data_lock:
            return dict(self._tarjeta)

    def marcar_tick_control(self) -> None:
        """Lo llama ControlLoop.run() al completarse cada tick sin excepción (FW-D6, TMG-01)."""
        self._ultimo_tick_control = time.monotonic()

    def expansor_fuera_de_linea(self) -> bool:
        """SAF-01: con la conexión válida, un expansor ya reportado fuera de
        línea (pcf_ok distinto de 3F sostenido) que no se ha recuperado. Sus
        entradas quedan congeladas en el firmware (FW-01)."""
        return self._handshake_ok and self._pcf_reportado

    def solicitar_handshake(self) -> None:
        """Invalida la conexión y repite el handshake en el próximo tick de
        supervisión (alarma fuera de ciclo, plan de protocolo §7)."""
        with self.data_lock:
            if not self.data["port_open"]:
                return
            self._handshake_ok = False
            self._handshake_pendiente = True
        self._notificar()

    def tomar_eventos(self) -> list[EventoTarjeta]:
        """Devuelve y vacía la cola de eventos de la tarjeta."""
        with self._eventos_lock:
            eventos, self._eventos = self._eventos, []
        return eventos

    def _evento(self, origen: str, alarm_id: Optional[str], motivo: str) -> None:
        if alarm_id is not None:
            logger.warning("SerialLink: %s (%s): %s", alarm_id, origen, motivo)
        with self._eventos_lock:
            self._eventos.append(EventoTarjeta(origen, alarm_id, motivo))

    def _invalidar_por_tarjeta(self, alarm_id: str, motivo: str) -> None:
        """WD o reinicio de la tarjeta con el handshake hecho: el firmware
        quedó NO_SINCRONIZADO (rechaza SET), así que se repite el handshake
        antes de aceptar órdenes (plan de protocolo §6.7)."""
        with self.data_lock:
            if not self._handshake_ok:
                return
            self._handshake_ok = False
            self._handshake_pendiente = True
        self._evento("operacion", alarm_id, motivo)

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

        if not self._handshake_ok:
            vencido = (self._proximo_handshake is not None
                       and now >= self._proximo_handshake)
            if self._handshake_pendiente or vencido:
                if not self._ejecutar_handshake():
                    # D-02: reintento automático cada reintento_handshake_s
                    self._proximo_handshake = now + self.config.reintento_handshake_s
                    self._handshake_pendiente = False
        elif self._tick_control_reciente(now):
            # FW-D6: sin tick reciente del lazo no hay HB; el watchdog del
            # firmware apaga todo a los 5 s.
            if last_hb is None or now - last_hb >= self.HEARTBEAT_INTERVAL:
                self._send_cmd("HB")
                last_hb = now
        self._check_timeout(now)
        return last_hb, last_scan

    def _tick_control_reciente(self, now: float) -> bool:
        ultimo = self._ultimo_tick_control
        return ultimo is not None and now - ultimo <= self.MARGEN_TICK_CONTROL

    # ---------------------------------------------------------------------
    # Handshake de conexión (plan de protocolo §4.6)
    # ---------------------------------------------------------------------

    def _hs_reset(self) -> None:
        with self._hs_cond:
            self._hs_valida = False          # llegó una línea de CRC válido
            self._hs_sin_crc = 0             # líneas AI/DI/DO sin CRC (firmware V2)
            self._hs_ver: Optional[tuple] = None
            self._hs_acks = 0
            self._hs_ok_all_off = 0
            self._hs_esperando_estado = False
            self._hs_do: Optional[list] = None   # último DO tras OK ALL_OFF
            self._hs_st: list[dict] = []         # ST recibidas tras OK ALL_OFF

    def _hs_esperar(self, condicion, fin: float, timeout: Optional[float] = None) -> bool:
        """Espera `condicion()` hasta `fin` (o `timeout`). Deja de esperar si
        el puerto se cierra (p.ej. 10 líneas inválidas seguidas)."""
        restante = fin - time.monotonic()
        if timeout is not None:
            restante = min(restante, timeout)
        with self._hs_cond:
            if restante > 0:
                self._hs_cond.wait_for(
                    lambda: condicion() or not self.data["port_open"], restante)
            return bool(condicion())

    def _hs_comando(self, payload: str, contador: Callable[[], Any], fin: float) -> bool:
        """Envía `payload` hasta all_off_intentos veces, esperando
        all_off_timeout_s cada vez a que `contador()` cambie."""
        for _ in range(self.config.all_off_intentos):
            if time.monotonic() >= fin:
                return False
            with self._hs_cond:
                antes = contador()
            self._send_cmd(payload)
            if self._hs_esperar(lambda: contador() != antes, fin,
                                self.config.all_off_timeout_s):
                return True
        return False

    def _ejecutar_handshake(self) -> bool:
        """Handshake completo. Bloquea el hilo de supervisión hasta
        handshake_presupuesto_s. True si la conexión quedó válida; si falla,
        encola un EventoTarjeta con la alarma específica."""
        fin = time.monotonic() + self.config.handshake_presupuesto_s
        with self.data_lock:
            self._handshake_ok = False
            self._handshake_pendiente = False
            self._tarjeta = {"version": None, "protocolo": None, "id": None}
        # TMG-02: ALL_OFF de mejor esfuerzo antes de empezar. Si la tarjeta
        # seguía SINCRONIZADA con salidas en ON (handshake invalidado fuera
        # de ciclo), las líneas VER/HB de un handshake que falla alimentan su
        # watchdog y las salidas quedarían en su último estado sin límite.
        # No se espera OK: la confirmación es el paso 5.
        self._send_cmd("ALL_OFF")
        self._hs_reset()
        self._en_handshake = True
        try:
            alarma, motivo = self._handshake_pasos(fin)
        finally:
            self._en_handshake = False
            # SAF-02: fuera del handshake no se acumulan ST ni DO (antes
            # _hs_st crecía sin límite con cada ST en operación).
            with self._hs_cond:
                self._hs_esperando_estado = False
                self._hs_st = []
                self._hs_do = None

        if alarma is not None:
            self._evento("handshake", alarma, motivo)
            return False

        with self.data_lock:
            self._comandado = {}
            self._discrepancia_tramas = 0
            self._reenvio_hecho = False
            self._discrepancia_reportada = False
            self._pcf_malas = 0
            self._pcf_reportado = False
            self._ultimo_uptime = (self._st or {}).get("uptime_s")
            self._handshake_ok = True
            self._proximo_handshake = None
            tarjeta = dict(self._tarjeta)
        logger.info("SerialLink: handshake completo con la tarjeta %s (firmware %s)",
                    tarjeta["id"], tarjeta["version"])
        self._evento("conectada", None, "Handshake completo")
        if self.al_conectar is not None:
            try:
                self.al_conectar(tarjeta)
            except Exception as e:
                logger.warning("SerialLink: error en al_conectar: %s", e)
        self._notificar()
        return True

    def _handshake_pasos(self, fin: float) -> tuple[Optional[str], str]:
        """Pasos 2 a 6 del §4.6. Devuelve (alarma, motivo); alarma None = OK."""
        # 2. Primera trama con CRC válido
        if not self._hs_esperar(lambda: self._hs_valida, fin):
            if self._hs_sin_crc:
                # HAZ-FC-11: firmware V2 (sin CRC) cargado en la tarjeta
                return ("TARJETA_VERSION_INCOMPATIBLE",
                        "La tarjeta envía tramas sin CRC: firmware anterior a 1.0.0 "
                        "(protocolo 1). Cargar el firmware 1.0.0.")
            return "TARJETA_SIN_TRAMA_VALIDA", "No llegó ninguna trama válida de la tarjeta."

        # 3. VER y protocolo 2
        if not self._hs_comando("VER", lambda: self._hs_ver, fin):
            return ("TARJETA_VERSION_INCOMPATIBLE",
                    "La tarjeta no respondió a VER: firmware sin soporte del protocolo 2.")
        version, protocolo, ident = self._hs_ver
        with self.data_lock:
            self._tarjeta = {"version": version, "protocolo": protocolo, "id": ident}
        if protocolo != PROTOCOLO_ESPERADO:
            return ("TARJETA_VERSION_INCOMPATIBLE",
                    f"La tarjeta informa protocolo {protocolo} (firmware {version}); "
                    f"se requiere el protocolo {PROTOCOLO_ESPERADO}.")

        # 4. HB y ACK
        if not self._hs_comando("HB", lambda: self._hs_acks, fin):
            return "TARJETA_SIN_ACK", "La tarjeta no confirmó el latido (HB sin ACK)."

        # 5. ALL_OFF y OK ALL_OFF (all_off_intentos de all_off_timeout_s)
        if not self._hs_comando("ALL_OFF", lambda: self._hs_ok_all_off, fin):
            return ("TARJETA_ALL_OFF_SIN_CONFIRMAR",
                    "La tarjeta no confirmó el apagado de salidas (ALL_OFF).")

        # 6. Dos ST consecutivas sanas (pcf_ok=3F, sync=1) con DO todo en 0
        return self._hs_verificar_estado(fin)

    def _hs_verificar_estado(self, fin: float) -> tuple[Optional[str], str]:
        n = self.config.tramas_discrepancia
        vistas = 0
        buenas = 0
        malas: dict[str, int] = {}
        ultima_causa: Optional[tuple[str, str]] = None
        while True:
            if not self._hs_esperar(lambda: len(self._hs_st) > vistas, fin):
                if ultima_causa is not None:
                    return ultima_causa
                return ("TARJETA_SIN_TRAMA_VALIDA",
                        "La tarjeta no envió tramas de estado (ST) tras el ALL_OFF.")
            with self._hs_cond:
                nuevas = self._hs_st[vistas:]
                vistas = len(self._hs_st)
            for ev in nuevas:
                if ev["do"] is None:
                    continue    # ST anterior al primer DO tras el ALL_OFF: no cuenta
                causa = self._hs_causa(ev)
                if causa is None:
                    buenas += 1
                    malas = {}
                    if buenas >= n:
                        return None, ""
                    continue
                buenas = 0
                ultima_causa = causa
                malas = {causa[0]: malas.get(causa[0], 0) + 1}
                if malas[causa[0]] >= n:
                    return causa

    @staticmethod
    def _hs_causa(ev: dict) -> Optional[tuple[str, str]]:
        """None si la trama ST (con el DO previo) es sana; si no, la causa."""
        if ev["pcf_ok"] != PCF_OK_SANO:
            return ("TARJETA_EXPANSOR_FUERA_DE_LINEA",
                    f"Expansor de E/S sin respuesta (pcf_ok={ev['pcf_ok']}, se espera "
                    f"{PCF_OK_SANO}).")
        if any(ev["do"]):
            encendidas = [str(i + 1) for i, b in enumerate(ev["do"]) if b]
            return ("TARJETA_SALIDAS_NO_APAGADAS",
                    f"Salidas encendidas tras el ALL_OFF: DO{', DO'.join(encendidas)}.")
        if ev["sync"] != 1:
            return ("TARJETA_ALL_OFF_SIN_CONFIRMAR",
                    "La tarjeta sigue NO_SINCRONIZADA tras el ALL_OFF (sync=0).")
        return None

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
                if "*" not in texto and texto[:3] in ("AI:", "DI:", "DO:"):
                    # Trama del firmware V2 (sin CRC): el handshake lo informa
                    with self._hs_cond:
                        self._hs_sin_crc += 1
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
        with self._hs_cond:
            if not self._hs_valida:
                self._hs_valida = True
                self._hs_cond.notify_all()
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
            do = self.get_state()["do"]
            with self._hs_cond:
                if self._hs_esperando_estado:
                    self._hs_do = do
            self._comparar_salidas(do)

        elif payload.startswith("ST:"):
            self._procesar_st(_parsear_st(payload[3:]))

        elif payload == "ACK":
            with self._hs_cond:
                self._hs_acks += 1
                self._hs_cond.notify_all()

        elif payload.startswith("OK "):
            if self._expected_ack and payload == self._expected_ack:
                self._ack_event.set()
            if payload == "OK ALL_OFF":
                with self._hs_cond:
                    self._hs_ok_all_off += 1
                    if self._en_handshake:
                        # Solo cuentan el DO y las ST posteriores a la confirmación
                        self._hs_esperando_estado = True
                        self._hs_do = None
                        self._hs_st = []
                    self._hs_cond.notify_all()

        elif payload.startswith("VER "):
            datos = _parsear_version(payload[4:])
            with self._hs_cond:
                self._hs_ver = datos
                self._hs_cond.notify_all()

        elif payload.startswith("BOOT "):
            version, _, ident = _parsear_version(payload[5:])
            logger.info("SerialLink: BOOT de la tarjeta %s (firmware %s)", ident, version)
            self._invalidar_por_tarjeta(
                "TARJETA_REINICIO",
                f"La tarjeta se reinició (BOOT, firmware {version}); salidas apagadas.")

        elif payload == "WD: ALL_OFF":
            self._invalidar_por_tarjeta(
                "TARJETA_WATCHDOG",
                "El watchdog de la tarjeta apagó todas las salidas (sin órdenes válidas del PC).")

        else:
            raise LineaMalformada("tipo de línea desconocido")

    def _procesar_st(self, st: Dict[str, Any]):
        with self.data_lock:
            self._st = st
            anterior = self._ultimo_uptime
            if self._handshake_ok:
                self._ultimo_uptime = st["uptime_s"]
        with self._hs_cond:
            if self._hs_esperando_estado:
                self._hs_st.append({"pcf_ok": st["pcf_ok"], "sync": st["sync"],
                                    "do": self._hs_do})
                self._hs_cond.notify_all()

        if not self._handshake_ok:
            return
        # Reinicio que no llegó como BOOT: uptime que retrocede, o la tarjeta
        # informa watchdog disparado / NO_SINCRONIZADO con la conexión válida.
        if anterior is not None and st["uptime_s"] < anterior:
            self._invalidar_por_tarjeta(
                "TARJETA_REINICIO",
                f"El tiempo de funcionamiento de la tarjeta retrocedió "
                f"({anterior} s -> {st['uptime_s']} s): reinicio.")
            return
        if st["wd"] == 1 or st["sync"] == 0:
            self._invalidar_por_tarjeta(
                "TARJETA_WATCHDOG",
                f"La tarjeta informa watchdog={st['wd']} sync={st['sync']}: salidas apagadas.")
            return

        # pcf_ok distinto de 3F sostenido N tramas (filtra un NACK aislado)
        if st["pcf_ok"] != PCF_OK_SANO:
            self._pcf_malas += 1
            if self._pcf_malas >= self.config.tramas_discrepancia and not self._pcf_reportado:
                self._pcf_reportado = True
                self._evento("operacion", "TARJETA_EXPANSOR_FUERA_DE_LINEA",
                             f"Expansor de E/S sin respuesta (pcf_ok={st['pcf_ok']}).")
        else:
            self._pcf_malas = 0
            self._pcf_reportado = False

    def _comparar_salidas(self, do: list):
        """Plan de protocolo §6.5: discrepancia entre lo comandado y el DO
        reportado, sostenida tramas_discrepancia tramas, genera un único
        reenvío; si persiste, un evento DISCREPANCIA_SALIDAS. Solo canales
        comandados desde el handshake y hace al menos 1 s."""
        if not self._handshake_ok:
            return
        ahora = time.monotonic()
        with self.data_lock:
            difieren = sorted(
                ch for ch, (est, t) in self._comandado.items()
                if ahora - t >= self._TOLERANCIA_COMANDO_S and bool(do[ch - 1]) != est
            )
            if not difieren:
                self._discrepancia_tramas = 0
                self._reenvio_hecho = False
                self._discrepancia_reportada = False
                return
            self._discrepancia_tramas += 1
            if self._discrepancia_tramas < self.config.tramas_discrepancia:
                return
            self._discrepancia_tramas = 0
            reenviar = not self._reenvio_hecho
            reportar = self._reenvio_hecho and not self._discrepancia_reportada
            if reenviar:
                self._reenvio_hecho = True
                for ch in difieren:
                    self._comandado[ch] = (self._comandado[ch][0], ahora)
            if reportar:
                self._discrepancia_reportada = True
            estados = {ch: self._comandado[ch][0] for ch in difieren}

        canales = ", ".join(f"DO{ch}" for ch in difieren)
        if reenviar:
            logger.warning("SerialLink: salidas %s distintas de lo comandado; reenvío único",
                           canales)
            # TMG-03: el estado a reenviar se relee bajo _cmd_lock justo antes
            # de escribir; si el lazo comandó otro valor entretanto, sale ese.
            with self._cmd_lock:
                for ch in estados:
                    with self.data_lock:
                        est = self._comandado[ch][0] if ch in self._comandado else None
                    if est is not None and self._handshake_ok:
                        self._send_cmd(f"SET DO{ch} {'ON' if est else 'OFF'}")
        elif reportar:
            self._evento("operacion", "DISCREPANCIA_SALIDAS",
                         f"Las salidas {canales} no siguen lo comandado tras el reenvío.")

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
                "handshake_completo": self._handshake_ok,
                # Última trama ST de la tarjeta (contadores del firmware,
                # disc_do y ai_inv solo diagnóstico, D-05), o None.
                "tarjeta_st": dict(self._st) if self._st is not None else None,
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

        # Sin handshake completo no salen órdenes de salida (§5 punto 1)
        if not self._handshake_ok:
            return False

        with self._cmd_lock:
            with self.data_lock:
                self._registrar_comando(channel, bool(state), time.monotonic())
            self._send_cmd(f"SET DO{channel} {'ON' if state else 'OFF'}")
        return True

    def _registrar_comando(self, channel: int, estado: bool, ahora: float) -> None:
        """Bajo data_lock. La exclusión de 1 s de la comparación cuenta desde
        el último CAMBIO de estado comandado: las puertas y otras salidas se
        reafirman en cada tick con el mismo valor, y renovar el instante en
        cada reenvío las dejaría sin comparar nunca."""
        previo = self._comandado.get(channel)
        if previo is None or previo[0] != estado:
            self._comandado[channel] = (estado, ahora)

    def all_off(self, timeout=1.0) -> bool:
        # El ALL_OFF del handshake va por _hs_comando; este es el del lazo.
        if not self._handshake_ok:
            return False
        with self._cmd_lock:
            ahora = time.monotonic()
            with self.data_lock:
                for ch in range(1, 33):
                    self._registrar_comando(ch, False, ahora)
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


def _hex(texto: str, ancho: int) -> str:
    if not _RE_HEX[ancho].match(texto):
        raise LineaMalformada(f"hexadecimal de {ancho} dígitos inválido {texto!r}")
    return texto


def _bit(texto: str) -> int:
    if texto not in ("0", "1"):
        raise LineaMalformada(f"se esperaba 0 o 1, llegó {texto!r}")
    return int(texto)


def _parsear_st(campos_texto: str) -> Dict[str, Any]:
    """`<ver>,<pcf_ok>,<disc_do>,<ai_inv>,<crc_rx_err>,<i2c_err>,<wd>,<uptime_s>,<sync>`
    (planeacion_firmware_1_5.md §4.5)."""
    c = campos_texto.split(",")
    if len(c) != 9:
        raise LineaMalformada(f"ST con {len(c)} campos")
    if _entero_decimal(c[0], 0, _MAX_U32) != PROTOCOLO_ESPERADO:
        raise LineaMalformada(f"ST de protocolo {c[0]}")
    return {
        "pcf_ok": _hex(c[1], 2),
        "disc_do": _hex(c[2], 8),
        "ai_inv": _hex(c[3], 4),
        "crc_rx_err": _entero_decimal(c[4], 0, _MAX_U32),
        "i2c_err": _entero_decimal(c[5], 0, _MAX_U32),
        "wd": _bit(c[6]),
        "uptime_s": _entero_decimal(c[7], 0, _MAX_U64),
        "sync": _bit(c[8]),
    }


def _parsear_version(texto: str) -> tuple[str, int, str]:
    """`<version> <protocolo> <ID12>` de BOOT y VER (FW-D1, FW-D2)."""
    partes = texto.split(" ")
    if len(partes) != 3:
        raise LineaMalformada("BOOT/VER con formato inválido")
    version, protocolo, ident = partes
    if not _RE_VERSION.match(version):
        raise LineaMalformada(f"versión inválida {version!r}")
    if not _RE_ID.match(ident):
        raise LineaMalformada(f"ID de tarjeta inválido {ident!r}")
    return version, _entero_decimal(protocolo, 0, 999), ident
