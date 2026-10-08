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


def esperar(cond, timeout=2.0, paso=0.01) -> bool:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(paso)
    return cond()
