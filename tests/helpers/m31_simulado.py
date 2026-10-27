# tests/helpers/m31_simulado.py
# -----------------------------
# Simulador de los módulos Ebyte M31-U (principal + expansiones) para las
# pruebas automáticas del enlace Modbus TCP (tanda 19, MOD-14).
#
# Servidor Modbus TCP de pymodbus en el mismo proceso, en un hilo propio con
# su bucle asyncio, escuchando SOLO en 127.0.0.1 y en un puerto libre que
# asigna el sistema (puerto 0). Nunca usa red real, puertos COM ni hardware.
#
# Mapa (manual M31-U V1.4; ver planeacion_enlace_modbus.md MOD-03/06/07/10):
#   bobinas 0x0000..0x001F (DO 1-32), entradas discretas 0x0000..0x000F (DI),
#   registros de entrada 0x0000..0x000F (AI en µA; <3850 con rango 4-20 mA
#   se entrega 0) y 0x0DAC..0x0DB1 (PT100 en décimas de °C, con signo),
#   registros holding de parámetros básicos, configuración de DO/AI/PT100 y
#   diagnóstico (0x7534 MAC, 0x7587 error, 0x7588 máscara, 0x758A negociación).
#
# Emula:
#   - temporizador de desconexión (0x0C35, décimas de s) reiniciado por
#     CUALQUIER petición; al vencer con 0x0C36=1 aplica el estado de falla
#     de cada bobina (0x1B58..: 0 mantiene, 1 apaga, 2 enciende) y cuenta el
#     corte en `cortes`;
#   - 0x0C37 como contador (+1 por segundo desde 100; ADB-05, banco 27-oct),
#     sin relación con el corte;
#   - reinicio por 0x0C1D = 0x5BB5 (fc06/fc16; ADB-04): responde, y luego
#     bobinas = estado de encendido (0x2904), conexiones cerradas, silencio
#     durante `tiempo_reinicio_s`, `reinicios += 1`. La configuración persiste
#     (salvo `config_no_persiste`); con `config_activa_tras_reinicio`, el
#     corte usa la configuración vigente en el último reinicio;
#   - composición real del banco (tanda 20, ADB-01/02): principal
#     M31-XAXX0A00G-U, firmware 0x000D y texto 0x0C2C «9232-0-13»; esclavos
#     ID 0..4 GXAXX0A00, GAXXXA000, GXXAX00A0, GXXAX00A0, GXDXX0600 con
#     versiones 10, 12, 12, 12, 10;
#   - usuario y contraseña de la web (0x758B, 5 registros; 0x7590, 3
#     registros; 2 ASCII por registro, byte alto primero, relleno NUL;
#     DECISIÓN SIN CONFIRMAR hasta leerlos en el banco);
#   - descarte silencioso de escrituras fuera de rango (sin excepción Modbus);
#   - fallas inyectables (ver métodos públicos).
#
# Uso:
#     sim = M31Simulado(); sim.iniciar()
#     ... ModbusLink(config=ModbusLinkConfig(ip="127.0.0.1", puerto=sim.puerto))
#     sim.detener()

from __future__ import annotations

import asyncio
import threading
import time
from typing import Optional

from pymodbus.constants import ExcCodes
from pymodbus.datastore import ModbusServerContext
from pymodbus.exceptions import NoSuchIdException
from pymodbus.server import ModbusTcpServer

from autoclave.protocols.modbus_link import texto_a_registros

# --- Direcciones -----------------------------------------------------------
REINICIO = 0x0C1D                  # escribir CLAVE_REINICIO reinicia el módulo
CLAVE_REINICIO = 0x5BB5
FW_PRINCIPAL = 0x0C1F
FW_TEXTO = 0x0C2C                  # 8 registros, texto del firmware del principal
WEB_USUARIO = 0x758B               # 5 registros
WEB_CLAVE = 0x7590                 # 3 registros
MODELO_PRINCIPAL = 0x0C20          # 12 registros
TIEMPO_DESCONEXION = 0x0C35
MODO_FALLA = 0x0C36
BANDERA_FALLA = 0x0C37
MODELO_ESCLAVOS = 0x0C80           # 8 registros por esclavo, 32 esclavos
FW_ESCLAVOS = 0x0D80               # 1 registro por esclavo, 32 esclavos
FILTRO_AI = 0x0DA2
RANGO_AI = 0x0DAC                  # holding, 16
DO_FALLA = 0x1B58                  # 32
DO_ENCENDIDO = 0x2904              # 32
DO_MODO = 0x32C8                   # 32
PT_COMPENSACION = 0x38A4           # 6
PT_UNIDAD = 0x39A4                 # 6
PT_FILTRO = 0x3AA4                 # 6
PT_DESHABILITADA = 0x3BA4          # 6
MAC = 0x7534                       # 3
CODIGO_ERROR = 0x7587
MASCARA = 0x7588                   # 2
NEGOCIACION = 0x758A

TEMP_INPUT = 0x0DAC                # registros de entrada, 6

MODELO_PRINCIPAL_DEFECTO = "M31-XAXX0A00G-U"
# ADB-01: el esclavo ID 0 son las E/S del principal (16 AI).
MODELOS_ESCLAVOS_DEFECTO = ("M31-GXAXX0A00-U", "M31-GAXXXA000-U", "M31-GXXAX00A0-U",
                            "M31-GXXAX00A0-U", "M31-GXDXX0600-U")
# ADB-02: versión en el byte bajo; texto completo del principal en 0x0C2C.
FW_DEFECTO = 0x000D                # principal 9232-0-13
FW_TEXTO_DEFECTO = "9232-0-13"
FW_ESCLAVOS_DEFECTO = (10, 12, 12, 12, 10)
USUARIO_WEB_DEFECTO = "admin"
CLAVE_WEB_DEFECTO = "Ficti1"       # contraseña ficticia de prueba
VALOR_0C37_INICIAL = 100

# Códigos de diagnóstico de las PT100 (MOD-03).
PT100_DESCONECTADA = 32766
PT100_CORTO = -32766
PT100_FALLA_CHIP = 32765
PT100_FUERA_ALTO = 32767
PT100_FUERA_BAJO = -32768
PT100_DESHABILITADA = -32767

# Fábrica de la configuración que el software reescribe (manual).
_FABRICA = {TIEMPO_DESCONEXION: 100, MODO_FALLA: 0, FILTRO_AI: 0}
for _i in range(32):
    _FABRICA[DO_FALLA + _i] = 0
    _FABRICA[DO_ENCENDIDO + _i] = 0
    _FABRICA[DO_MODO + _i] = 0
for _i in range(16):
    _FABRICA[RANGO_AI + _i] = 0
for _i in range(6):
    _FABRICA[PT_COMPENSACION + _i] = 0
    _FABRICA[PT_UNIDAD + _i] = 0
    _FABRICA[PT_FILTRO + _i] = 6
    _FABRICA[PT_DESHABILITADA + _i] = 0

# Rango de escritura válido (con signo para la compensación).
_RANGO_ESCRITURA: dict[int, tuple[int, int]] = {
    # 0x0C37 sigue siendo escribible para poder afirmar (vía `escrituras`)
    # que el enlace no lo escribe (ADB-05).
    TIEMPO_DESCONEXION: (1, 65535), MODO_FALLA: (0, 1), BANDERA_FALLA: (0, 65535),
    FILTRO_AI: (0, 4),
}
for _i in range(5):
    _RANGO_ESCRITURA[WEB_USUARIO + _i] = (0, 65535)
for _i in range(3):
    _RANGO_ESCRITURA[WEB_CLAVE + _i] = (0, 65535)
for _i in range(32):
    _RANGO_ESCRITURA[DO_FALLA + _i] = (0, 2)
    _RANGO_ESCRITURA[DO_ENCENDIDO + _i] = (0, 1)
    _RANGO_ESCRITURA[DO_MODO + _i] = (0, 1)
for _i in range(16):
    _RANGO_ESCRITURA[RANGO_AI + _i] = (0, 6)
for _i in range(6):
    _RANGO_ESCRITURA[PT_COMPENSACION + _i] = (-200, 200)
    _RANGO_ESCRITURA[PT_UNIDAD + _i] = (0, 2)
    _RANGO_ESCRITURA[PT_FILTRO + _i] = (1, 16)
    _RANGO_ESCRITURA[PT_DESHABILITADA + _i] = (0, 1)


def registros_a_texto_crudo(regs: list[int]) -> str:
    """Inverso de texto_a_registros (sin validar), para las pruebas."""
    b = bytearray()
    for r in regs:
        b += bytes([(r >> 8) & 0xFF, r & 0xFF])
    return bytes(b).rstrip(b"\0").decode("latin-1")


def _u16(v: int) -> int:
    return v & 0xFFFF


def _s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class _Contexto(ModbusServerContext):
    """Contexto propio: todo el comportamiento lo decide el simulador."""

    def __init__(self, sim: "M31Simulado"):   # sin super(): no usa los bloques de pymodbus
        self._sim = sim
        self.simdevices = []
        self.old_simulator = True

    async def async_getValues(self, device_id, func_code, address, count=1):
        return self._sim._leer(device_id, func_code, address, count)

    async def async_setValues(self, device_id, func_code, address, values):
        return self._sim._escribir(device_id, func_code, address, list(values))

    def device_ids(self):
        return [self._sim.unit_id]


class M31Simulado:
    def __init__(self, unit_id: int = 1):
        self.unit_id = unit_id
        self.host = "127.0.0.1"
        self.puerto: Optional[int] = None
        self._lock = threading.RLock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[ModbusTcpServer] = None
        self._hilo: Optional[threading.Thread] = None
        self._hilo_timer: Optional[threading.Thread] = None
        self._corriendo = False
        self._listo = threading.Event()

        # Estado del proceso
        self.bobinas = [False] * 32
        self.di = [False] * 16
        self.temperaturas = [250] * 6              # décimas de °C
        self.corrientes = [12000] * 16             # µA

        # Holding
        self.holding: dict[int, int] = dict(_FABRICA)
        self.holding[BANDERA_FALLA] = VALOR_0C37_INICIAL
        self.holding[FW_PRINCIPAL] = FW_DEFECTO
        self.holding[CODIGO_ERROR] = 0
        self.holding[MASCARA] = 0
        self.holding[MASCARA + 1] = 0
        self.holding[NEGOCIACION] = 0
        self.fijar_mac("A1B2C3D4E5F6")
        self.fijar_modelos(MODELO_PRINCIPAL_DEFECTO, list(MODELOS_ESCLAVOS_DEFECTO))
        self.fijar_firmware(FW_DEFECTO, list(FW_ESCLAVOS_DEFECTO))
        self.fijar_firmware_texto(FW_TEXTO_DEFECTO)
        self.fijar_credenciales_web(USUARIO_WEB_DEFECTO, CLAVE_WEB_DEFECTO)

        # Diagnóstico y fallas
        self.peticiones = 0
        self.escrituras: list[tuple[int, int, list]] = []   # (fc, dirección, valores)
        self.silencio = False
        self.registros_ignorados: set[int] = set()
        self.bobinas_atascadas: dict[int, bool] = {}        # índice 0..31 -> valor
        self.bobinas_no_apagan = False                      # 0F ignora los 0
        self._ultima_peticion = time.monotonic()
        self._disparado = False
        self.cortes = 0                     # cortes por desconexión aplicados

        # Reinicio del módulo (ADB-04)
        self.reinicios = 0
        self.tiempo_reinicio_s = 0.2
        self.config_no_persiste = False
        self.config_activa_tras_reinicio = False
        self._reiniciando_hasta: Optional[float] = None
        self._config_activa = self._instantanea_config()
        self._ultimo_inc_0c37 = time.monotonic()

    # ------------------------------------------------------------------
    # Arranque y parada
    # ------------------------------------------------------------------

    def iniciar(self, puerto: int = 0) -> int:
        self._listo.clear()
        self._corriendo = True
        self._puerto_pedido = puerto
        self._error_arranque: Optional[BaseException] = None
        self._hilo = threading.Thread(target=self._correr, name="m31-sim", daemon=True)
        self._hilo.start()
        if not self._listo.wait(5.0) or self._error_arranque is not None:
            self.detener()
            raise RuntimeError(f"no arrancó el simulador M31: {self._error_arranque}")
        with self._lock:
            self._ultima_peticion = time.monotonic()
        self._hilo_timer = threading.Thread(target=self._temporizador, name="m31-sim-wd",
                                            daemon=True)
        self._hilo_timer.start()
        return self.puerto

    def _correr(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._arrancar())
        except BaseException as e:      # noqa: BLE001
            self._error_arranque = e
            self._listo.set()
            loop.close()
            return
        self._listo.set()
        try:
            loop.run_forever()
        finally:
            try:
                pendientes = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for t in pendientes:
                    t.cancel()
                if pendientes:
                    loop.run_until_complete(asyncio.gather(*pendientes, return_exceptions=True))
            finally:
                loop.close()

    async def _arrancar(self):
        self._server = ModbusTcpServer(
            _Contexto(self), address=(self.host, self._puerto_pedido),
            ignore_missing_devices=True)
        await self._server.serve_forever(background=True)
        self.puerto = self._server.transport.sockets[0].getsockname()[1]

    def detener(self):
        self._corriendo = False
        loop, server = self._loop, self._server
        if loop is not None and server is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(server.shutdown(), loop).result(3.0)
            except Exception:
                pass
            loop.call_soon_threadsafe(loop.stop)
        for h in (self._hilo, self._hilo_timer):
            if h is not None and h is not threading.current_thread():
                h.join(5.0)
        self._server = None
        self._loop = None

    def cerrar_conexiones(self):
        """Corta las conexiones TCP abiertas (como un reinicio del módulo)."""
        loop, server = self._loop, self._server
        if loop is None or server is None:
            return

        def _cerrar():
            for prot in list(server.active_connections.values()):
                try:
                    prot.close()
                except Exception:
                    pass
        loop.call_soon_threadsafe(_cerrar)

    # ------------------------------------------------------------------
    # Inyección de estado y fallas
    # ------------------------------------------------------------------

    def fijar_mac(self, mac_hex: str):
        v = int(mac_hex, 16)
        with self._lock:
            self.holding[MAC] = (v >> 32) & 0xFFFF
            self.holding[MAC + 1] = (v >> 16) & 0xFFFF
            self.holding[MAC + 2] = v & 0xFFFF

    def fijar_modelos(self, principal: str, esclavos: list[str]):
        with self._lock:
            for i, r in enumerate(texto_a_registros(principal, 12)):
                self.holding[MODELO_PRINCIPAL + i] = r
            for n in range(32):
                texto = esclavos[n] if n < len(esclavos) else "NONE"
                for i, r in enumerate(texto_a_registros(texto, 8)):
                    self.holding[MODELO_ESCLAVOS + 8 * n + i] = r

    def fijar_firmware(self, principal: int, esclavos: list[int]):
        with self._lock:
            self.holding[FW_PRINCIPAL] = principal
            for n in range(32):
                self.holding[FW_ESCLAVOS + n] = esclavos[n] if n < len(esclavos) else 0

    def expansor_sin_respuesta(self, indice: int = 0, activo: bool = True):
        """0x7587=1 y el bit del expansor en la máscara 0x7588."""
        with self._lock:
            if activo:
                self.holding[CODIGO_ERROR] = 1
                self.holding[MASCARA + 1] |= (1 << indice)
            else:
                self.holding[CODIGO_ERROR] = 0
                self.holding[MASCARA] = 0
                self.holding[MASCARA + 1] = 0

    def orden_incorrecto(self, codigo: bool = True, negociacion: bool = False):
        """0x7587=2 (orden incorrecto) y/o 0x758A=1 (negociación pendiente)."""
        with self._lock:
            self.holding[CODIGO_ERROR] = 2 if codigo else 0
            self.holding[NEGOCIACION] = 1 if negociacion else 0

    def restablecer_fabrica(self, reiniciar: bool = True):
        """Reload 5-10 s: la configuración vuelve a la de fábrica. Con
        `reiniciar`, el módulo se reinicia: salidas abiertas y conexiones
        cortadas."""
        with self._lock:
            self.holding.update(_FABRICA)
            if reiniciar:
                self.bobinas = [False] * 32
        if reiniciar:
            self.cerrar_conexiones()

    def precargar_configuracion(self, tiempo_desconexion_ds: int = 5, filtro_pt100: int = 1,
                                filtro_ai: int = 0):
        """Deja en holding la configuración de seguridad que escribe el enlace
        (MOD-07): la conexión la encuentra igual y no reinicia (ADB-04)."""
        with self._lock:
            self.holding[TIEMPO_DESCONEXION] = tiempo_desconexion_ds
            self.holding[MODO_FALLA] = 1
            self.holding[FILTRO_AI] = filtro_ai
            for i in range(32):
                self.holding[DO_FALLA + i] = 1
                self.holding[DO_ENCENDIDO + i] = 0
                self.holding[DO_MODO + i] = 0
            for i in range(16):
                self.holding[RANGO_AI + i] = 1
            for i in range(6):
                self.holding[PT_UNIDAD + i] = 0
                self.holding[PT_COMPENSACION + i] = 0
                self.holding[PT_FILTRO + i] = filtro_pt100
                self.holding[PT_DESHABILITADA + i] = 0
            self._config_activa = self._instantanea_config()

    def fijar_firmware_texto(self, texto: str):
        """0x0C2C: texto del firmware del principal (8 registros)."""
        with self._lock:
            for i, r in enumerate(texto_a_registros(texto, 8)):
                self.holding[FW_TEXTO + i] = r

    def fijar_credenciales_web(self, usuario: str, clave: str):
        with self._lock:
            for i, r in enumerate(texto_a_registros(usuario, 5)):
                self.holding[WEB_USUARIO + i] = r
            for i, r in enumerate(texto_a_registros(clave, 3)):
                self.holding[WEB_CLAVE + i] = r

    def credenciales_web(self) -> tuple[str, str]:
        with self._lock:
            u = [self.holding[WEB_USUARIO + i] for i in range(5)]
            c = [self.holding[WEB_CLAVE + i] for i in range(3)]
        return registros_a_texto_crudo(u), registros_a_texto_crudo(c)

    def fijar_0c37(self, valor: int):
        with self._lock:
            self.holding[BANDERA_FALLA] = valor & 0xFFFF
            self._ultimo_inc_0c37 = time.monotonic()

    def bandera_falla(self) -> int:
        """Valor crudo de 0x0C37 (contador desde la tanda 20, ADB-05)."""
        with self._lock:
            return self.holding[BANDERA_FALLA]

    def escrituras_bobinas(self) -> list[tuple[int, int, list]]:
        """Escrituras con las funciones 5 y 15."""
        with self._lock:
            return [w for w in self.escrituras if w[0] in (5, 15)]

    def reiniciando(self) -> bool:
        with self._lock:
            return (self._reiniciando_hasta is not None
                    and time.monotonic() < self._reiniciando_hasta)

    def _instantanea_config(self) -> dict:
        claves = [TIEMPO_DESCONEXION, MODO_FALLA] + [DO_FALLA + i for i in range(32)]
        return {k: self.holding[k] for k in claves}

    def _reiniciar(self):
        """Corre en el bucle del servidor (call_later) después de responder
        a la orden de reinicio."""
        with self._lock:
            if self.config_no_persiste:
                self.holding.update(_FABRICA)
            self.bobinas = [bool(self.holding[DO_ENCENDIDO + i]) for i in range(32)]
            self._config_activa = self._instantanea_config()
            self.reinicios += 1
            self._reiniciando_hasta = time.monotonic() + self.tiempo_reinicio_s
            self._ultima_peticion = self._reiniciando_hasta
            self._disparado = False
        server = self._server
        if server is not None:
            for prot in list(server.active_connections.values()):
                try:
                    prot.close()
                except Exception:
                    pass

    def _programar_reinicio(self):
        loop = self._loop
        if loop is not None:
            loop.call_later(0.05, self._reiniciar)

    def contador(self) -> int:
        with self._lock:
            return self.peticiones

    # ------------------------------------------------------------------
    # Servidor
    # ------------------------------------------------------------------

    def _temporizador(self):
        while self._corriendo:
            with self._lock:
                ahora = time.monotonic()
                # 0x0C37: contador +1 por segundo (ADB-05)
                while ahora - self._ultimo_inc_0c37 >= 1.0:
                    self._ultimo_inc_0c37 += 1.0
                    self.holding[BANDERA_FALLA] = (self.holding[BANDERA_FALLA] + 1) & 0xFFFF
                cfg = (self._config_activa if self.config_activa_tras_reinicio
                       else self.holding)
                limite = cfg[TIEMPO_DESCONEXION] * 0.1
                if (not self._disparado and cfg[MODO_FALLA] == 1
                        and ahora - self._ultima_peticion > limite):
                    self._disparado = True
                    self.cortes += 1
                    for i in range(32):
                        modo = cfg[DO_FALLA + i]
                        if modo == 1:
                            self.bobinas[i] = False
                        elif modo == 2:
                            self.bobinas[i] = True
            time.sleep(0.02)

    def _peticion(self, device_id: int):
        if self.silencio or (self._reiniciando_hasta is not None
                             and time.monotonic() < self._reiniciando_hasta):
            # El servidor (ignore_missing_devices) no contesta: el cliente
            # vence su timeout (también mientras el módulo se reinicia).
            raise NoSuchIdException("simulador en silencio")
        self.peticiones += 1
        self._ultima_peticion = time.monotonic()
        self._disparado = False

    def _bobinas_vistas(self) -> list[bool]:
        b = list(self.bobinas)
        for i, v in self.bobinas_atascadas.items():
            b[i] = v
        return b

    def _leer(self, device_id, fc, address, count):
        with self._lock:
            self._peticion(device_id)
            try:
                if fc in (1, 5, 15):
                    if address + count > 32:
                        return ExcCodes.ILLEGAL_ADDRESS
                    return self._bobinas_vistas()[address:address + count]
                if fc == 2:
                    if address + count > 16:
                        return ExcCodes.ILLEGAL_ADDRESS
                    return list(self.di[address:address + count])
                if fc == 4:
                    if 0 <= address and address + count <= 16:
                        return [_u16(self._corriente(i)) for i in range(address, address + count)]
                    if TEMP_INPUT <= address and address + count <= TEMP_INPUT + 6:
                        return [_u16(self.temperaturas[i - TEMP_INPUT])
                                for i in range(address, address + count)]
                    return ExcCodes.ILLEGAL_ADDRESS
                # holding (3, 6, 16)
                if fc in (6, 16) and address == REINICIO:
                    return [CLAVE_REINICIO] * count     # eco de la escritura (solo W)
                regs = []
                for a in range(address, address + count):
                    if a not in self.holding:
                        return ExcCodes.ILLEGAL_ADDRESS
                    regs.append(_u16(self.holding[a]))
                return regs
            except Exception:
                return ExcCodes.DEVICE_FAILURE

    def _corriente(self, canal: int) -> int:
        v = self.corrientes[canal]
        if self.holding.get(RANGO_AI + canal) == 1 and v < 3850:
            return 0
        return v

    def _escribir(self, device_id, fc, address, values):
        with self._lock:
            self._peticion(device_id)
            self.escrituras.append((fc, address, list(values)))
            if fc in (5, 15):
                if address + len(values) > 32:
                    return ExcCodes.ILLEGAL_ADDRESS
                for i, v in enumerate(values):
                    if self.bobinas_no_apagan and not v:
                        continue
                    self.bobinas[address + i] = bool(v)
                return None
            if fc in (6, 16) and address == REINICIO:
                # ADB-04: responde y se reinicia enseguida
                if len(values) == 1 and values[0] == CLAVE_REINICIO:
                    self._programar_reinicio()
                return None
            if fc in (6, 16):
                for i, v in enumerate(values):
                    a = address + i
                    if a not in _RANGO_ESCRITURA:
                        return ExcCodes.ILLEGAL_ADDRESS
                for i, v in enumerate(values):
                    a = address + i
                    if a in self.registros_ignorados:
                        continue            # escritura que no queda
                    minimo, maximo = _RANGO_ESCRITURA[a]
                    valor = _s16(v) if minimo < 0 else v
                    if minimo <= valor <= maximo:
                        self.holding[a] = valor
                    # fuera de rango: descarte silencioso, sin excepción
                return None
            return ExcCodes.ILLEGAL_FUNCTION


# ----------------------------------------------------------------------
# Ayudantes para las pruebas del enlace
# ----------------------------------------------------------------------

def config_para(sim: M31Simulado, **cambios):
    """ModbusLinkConfig apuntando al simulador, con tiempos cortos."""
    from autoclave.protocols.modbus_link_config import ModbusLinkConfig
    base = dict(ip=sim.host, puerto=sim.puerto, unit_id=sim.unit_id,
                periodo_sondeo_s=0.05, timeout_s=0.2, fallos_para_desconexion=3,
                reintento_conexion_s=0.2, presupuesto_conexion_s=5.0,
                tiempo_desconexion_modulo_ds=5, intentos_escritura_config=3,
                espera_reinicio_s=0.1, presupuesto_reinicio_s=3.0)
    base.update(cambios)
    return ModbusLinkConfig(**base)


def esperar(condicion, timeout: float = 5.0, paso: float = 0.02) -> bool:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(paso)
    return bool(condicion())


class TickLazo:
    """Simula el ControlLoop: marca el tick cada `periodo` mientras corre."""

    def __init__(self, enlace, periodo: float = 0.05):
        self._enlace = enlace
        self._periodo = periodo
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None

    def iniciar(self) -> "TickLazo":
        self._parar.clear()
        self._enlace.marcar_tick_control()
        self._hilo = threading.Thread(target=self._correr, daemon=True)
        self._hilo.start()
        return self

    def _correr(self):
        while not self._parar.is_set():
            self._enlace.marcar_tick_control()
            self._parar.wait(self._periodo)

    def detener(self):
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(2.0)

    def __enter__(self):
        return self.iniciar()

    def __exit__(self, *exc):
        self.detener()
