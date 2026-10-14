"""Doble de prueba de un puerto serial (pyserial) para SerialLink.

El simulador de src/autoclave/simulador es un backend HTTP falso y no emula
el puerto serial, así que las pruebas del enlace usan este doble."""

import threading
import time

from autoclave.protocols.crc16 import agregar_crc


def linea(payload: str) -> bytes:
    """Línea del protocolo v2 con CRC y \\n."""
    return (agregar_crc(payload) + "\n").encode("ascii")


AI_OK = "AI:" + ",".join(str(100 + i) for i in range(16))
DI_OK = "DI:" + "0" * 56
DO_OK = "DO:" + "0" * 32


class PuertoDoble:
    def __init__(self):
        self.is_open = True
        self._rx = bytearray()
        self._cv = threading.Condition()
        self.escrito: list[str] = []
        self.timeout = 0.05
        self.al_escribir = None  # callback(payload_sin_crc) para respuestas automáticas

    # --- lado "ESP32" -------------------------------------------------------
    def inyectar(self, datos: bytes):
        with self._cv:
            self._rx += datos
            self._cv.notify_all()

    # --- API pyserial usada por SerialLink ----------------------------------
    @property
    def in_waiting(self):
        with self._cv:
            return len(self._rx)

    def read(self, n=1):
        if not self.is_open:
            raise OSError("puerto cerrado")
        with self._cv:
            if not self._rx:
                self._cv.wait(self.timeout)
            if not self.is_open:
                raise OSError("puerto cerrado")
            datos = bytes(self._rx[:n])
            del self._rx[:n]
            return datos

    def write(self, datos: bytes):
        if not self.is_open:
            raise OSError("puerto cerrado")
        texto = datos.decode("ascii")
        self.escrito.append(texto)
        if self.al_escribir is not None:
            payload = texto.rstrip("\n").rsplit("*", 1)[0]
            self.al_escribir(payload)
        return len(datos)

    def reset_input_buffer(self):
        with self._cv:
            self._rx.clear()

    def reset_output_buffer(self):
        pass

    def close(self):
        with self._cv:
            self.is_open = False
            self._cv.notify_all()

    # --- utilidades ---------------------------------------------------------
    def comandos(self) -> list[str]:
        """Payloads enviados por el PC, sin CRC ni \\n."""
        return [t.rstrip("\n").rsplit("*", 1)[0] for t in self.escrito]


def st(pcf_ok="3F", disc_do="00000000", ai_inv="0000", crc_rx_err=0, i2c_err=0,
       wd=0, uptime_s=10, sync=1, ver=2) -> str:
    """Payload ST: del firmware 1.0.0 (orden de planeacion_firmware_1_5.md §4.5)."""
    return f"ST:{ver},{pcf_ok},{disc_do},{ai_inv},{crc_rx_err},{i2c_err},{wd},{uptime_s},{sync}"


ID_TARJETA = "A1B2C3D4E5F6"


class TarjetaSimulada:
    """Firmware 1.0.0 simulado sobre un PuertoDoble: responde a VER, HB,
    ALL_OFF y SET DOn, y publica AI/DI/DO/ST con `publicar()` (a mano o con
    `arrancar()`, en un hilo cada `periodo` s). Los atributos permiten
    simular cada fallo del handshake."""

    def __init__(self, puerto: PuertoDoble, periodo=0.02):
        self.puerto = puerto
        self.periodo = periodo
        self.version = "1.0.0"
        self.protocolo = 2
        self.id = ID_TARJETA
        self.responde_ver = True
        self.responde_ack = True
        self.responde_all_off = True
        self.pcf_ok = "3F"
        self.sync = 0               # FW-D4: arranca NO_SINCRONIZADO
        self.sync_forzado = None    # None = según ALL_OFF; 0/1 = fijo
        self.do = [0] * 32
        self.do_forzado = None      # lista de 32 bits que reemplaza al DO real
        self.uptime_s = 10
        self.wd = 0
        self.sin_crc = False        # firmware V2: tramas sin CRC
        self.mudo = False           # no publica nada
        self._hilo = None
        self._activo = False
        puerto.al_escribir = self._al_escribir

    # --- respuestas ---------------------------------------------------------
    def _enviar(self, payload: str):
        if self.sin_crc:
            self.puerto.inyectar((payload + "\n").encode("ascii"))
        else:
            self.puerto.inyectar(linea(payload))

    def _al_escribir(self, payload: str):
        if self.sin_crc or self.mudo:
            return
        if self.responde_ack:
            self._enviar("ACK")
        if payload == "VER":
            if self.responde_ver:
                self._enviar(f"VER {self.version} {self.protocolo} {self.id}")
        elif payload == "ALL_OFF":
            self.do = [0] * 32
            self.sync = 1
            self.wd = 0
            if self.responde_all_off:
                self._enviar("OK ALL_OFF")
        elif payload.startswith("SET DO") and self.sync:
            num, estado = payload[6:].split(" ")
            self.do[int(num) - 1] = 1 if estado == "ON" else 0
            self._enviar(f"OK DO{num} {estado}")

    # --- publicación periódica ----------------------------------------------
    def publicar(self):
        if self.mudo:
            return
        do = self.do_forzado if self.do_forzado is not None else self.do
        sync = self.sync if self.sync_forzado is None else self.sync_forzado
        self._enviar(AI_OK)
        self._enviar(DI_OK)
        self._enviar("DO:" + "".join(str(b) for b in do))
        self._enviar(st(pcf_ok=self.pcf_ok, uptime_s=self.uptime_s, wd=self.wd, sync=sync))

    def boot(self):
        """Reinicio del firmware: salidas apagadas, NO_SINCRONIZADO, BOOT."""
        self._enviar(f"BOOT {self.version} {self.protocolo} {self.id}")
        self.do = [0] * 32
        self.sync = 0
        self.uptime_s = 0

    def disparar_watchdog(self):
        self._enviar("WD: ALL_OFF")
        self.do = [0] * 32
        self.sync = 0
        self.wd = 1

    def arrancar(self):
        self._activo = True

        def bucle():
            while self._activo:
                self.publicar()
                time.sleep(self.periodo)

        self._hilo = threading.Thread(target=bucle, daemon=True)
        self._hilo.start()

    def detener(self):
        self._activo = False
        if self._hilo:
            self._hilo.join(1)


def esperar(cond, timeout=2.0, paso=0.01) -> bool:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(paso)
    return cond()
