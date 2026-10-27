# autoclave.protocols.modbus_link
# --------------------------------
# Enlace de E/S con los módulos Ebyte M31-U por Modbus TCP (tanda 19; ver
# docs/mis_plans/planeacion_enlace_modbus.md, MOD-02, MOD-03, MOD-06 a
# MOD-11). El PC es el maestro; cumple protocols.enlace.EnlaceES con el mismo
# significado que SerialLink (handshake = conexión verificada).
#
# Un único hilo daemon de sondeo hace TODO el tráfico periódico: conexión
# verificada, lectura de entradas cada periodo_sondeo_s y diagnóstico cada
# 1 s. set_output() y all_off() escriben desde el hilo que los llama. El
# cliente síncrono de pymodbus no es seguro entre hilos: todo acceso pasa por
# _cliente_lock (MOD-11). Registrar una orden y escribirla es atómico
# respecto a otros escritores (_cmd_lock, como TMG-03 del serial).
#
# Vigilancia del lazo (MOD-08, regla principal): solo hay tráfico Modbus si
# el ControlLoop marcó un tick hace <= MARGEN_TICK_CONTROL o si ninguna salida
# está comandada ni leída en ON. Si no, se suspende todo el tráfico y el
# módulo, a los tiempo_desconexion_modulo_ds sin peticiones, pone las salidas
# en su estado de falla (apagadas, MOD-07). Única excepción: el 0F de
# all_off(), que lleva al estado seguro.
#
# No implementa lógica de control ni conversión de unidades: entrega los
# valores crudos (décimas de °C y µA); la conversión es de hal/measures.
#
# Tiempos: toda duración usa time.monotonic(); data["last_update"] es
# datetime.now() solo como sello informativo.
#
# TARJETA_REINICIO no se usa: los módulos no tienen contador de vida por
# Modbus; un reinicio del módulo corta la conexión TCP (MOD-09) y la
# reconexión rehace la configuración y el apagado.

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from autoclave.protocols.enlace import EventoTarjeta
from autoclave.protocols.modbus_link_config import (
    MAX_EXPANSIONES, ModbusLinkConfig, cargar_config, normalizar_modelo)
from autoclave.utils.logging import logger

try:    # MOD-13: solo el cliente síncrono
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ConnectionException as _ConnectionException
except ImportError:     # pragma: no cover - el .spec lo incluye
    ModbusTcpClient = None  # type: ignore[assignment,misc]
    _ConnectionException = OSError  # type: ignore[assignment,misc]


# --- Mapa de datos (MOD-03) -------------------------------------------------
DIR_DI = 0x0000
N_DI = 16
DIR_DO = 0x0000
N_DO = 32
DIR_TEMP = 0x0DAC          # registros de entrada, PT100 1-6 (décimas de °C)
N_TEMP = 6
DIR_PRES = 0x0000          # registros de entrada, AI 1-8 del principal (µA)
N_PRES = 8

# --- Parámetros básicos y diagnóstico (MOD-06, MOD-10) ----------------------
REG_FW_PRINCIPAL = 0x0C1F
REG_MODELO_PRINCIPAL = 0x0C20      # 12 registros
N_MODELO_PRINCIPAL = 12
REG_TIEMPO_DESCONEXION = 0x0C35
REG_MODO_FALLA = 0x0C36
REG_BANDERA_FALLA = 0x0C37
REG_MODELO_ESCLAVOS = 0x0C80       # 8 registros por esclavo
N_MODELO_ESCLAVO = 8
REG_FW_ESCLAVOS = 0x0D80           # 1 registro por esclavo
REG_MAC = 0x7534                   # 3 registros
REG_CODIGO_ERROR = 0x7587          # 0x7587, 0x7588-89 (máscara), 0x758A
REG_NEGOCIACION = 0x758A

# --- Configuración de seguridad (MOD-07) ------------------------------------
REG_DO_FALLA = 0x1B58
REG_DO_ENCENDIDO = 0x2904
REG_DO_MODO = 0x32C8
REG_RANGO_AI = 0x0DAC              # holding, 16 canales (1 = 4-20 mA)
REG_FILTRO_AI = 0x0DA2             # V19: un registro. DECISIÓN SIN CONFIRMAR (M-3)
REG_PT_UNIDAD = 0x39A4
REG_PT_COMPENSACION = 0x38A4
REG_PT_FILTRO = 0x3AA4
REG_PT_DESHABILITADA = 0x3BA4

# Códigos de diagnóstico de las PT100 (MOD-03): el canal se entrega None.
CODIGOS_PT100 = {
    32766: "sensor desconectado o cable roto",
    -32766: "cortocircuito",
    32765: "falla del chip",
    32767: "fuera de rango (alto)",
    -32768: "fuera de rango (bajo)",
    -32767: "canal deshabilitado",
}


class _FalloTransaccion(Exception):
    """Transacción Modbus sin respuesta válida (timeout, excepción del
    cliente o respuesta de excepción)."""


class _TraficoSuspendido(Exception):
    """La vigilancia del lazo (MOD-08) no permite tráfico en este momento."""


class _FalloConexion(Exception):
    def __init__(self, alarma: str, motivo: str):
        super().__init__(motivo)
        self.alarma = alarma
        self.motivo = motivo


def _s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _version(reg: int) -> tuple[int, int]:
    return (reg >> 8) & 0xFF, reg & 0xFF


def _texto_version(v: tuple[int, int]) -> str:
    return f"{v[0]}.{v[1]}"


def _registros_a_texto(regs: list[int]) -> Optional[str]:
    """2 caracteres por registro, byte alto primero (DECISIÓN SIN CONFIRMAR,
    M-2); recorta NUL y espacios. None si no es ASCII imprimible."""
    b = bytearray()
    for r in regs:
        b.append((r >> 8) & 0xFF)
        b.append(r & 0xFF)
    b = bytes(b).rstrip(b"\0").strip(b" ")
    if b"\0" in b or any(c < 0x20 or c > 0x7E for c in b):
        return None
    return b.decode("ascii").strip()


class ModbusLink:
    # FW-D6 / MOD-08: igual que SerialLink.
    MARGEN_TICK_CONTROL = 1.5
    # Plan de protocolo §6.5: no se comparan los canales comandados hace menos.
    _TOLERANCIA_COMANDO_S = 1.0
    # MOD-10: periodo del diagnóstico de los módulos.
    PERIODO_DIAGNOSTICO_S = 1.0
    # all_off(): pausa entre lecturas de confirmación.
    _PAUSA_CONFIRMACION_S = 0.02

    def __init__(
        self,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[ModbusLinkConfig] = None,
    ):
        self.config = config if config is not None else cargar_config()
        self.on_update = on_update
        # Callback(tarjeta) al verificar cada conexión (audit_log y
        # emparejamiento FW-D7). Corre en el hilo de sondeo.
        self.al_conectar: Optional[Callable[[Dict[str, Any]], None]] = None

        self.data_lock = threading.Lock()
        self._cliente_lock = threading.RLock()     # MOD-11: único acceso al cliente
        self._cmd_lock = threading.RLock()         # orden + escritura atómicas
        self._eventos_lock = threading.Lock()

        self._cliente: Optional[Any] = None
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self.running = False

        self.data: Dict[str, Any] = {
            "ai": [None] * 16,
            "ai_seq": 0,
            "di": [0] * 56,
            "do": [0] * 32,
            "port_open": False,
            "data_alive": False,
            "last_update": None,
        }
        self._ultima_di_mono: Optional[float] = None
        self._di_seq = 0
        self._ultima_ai_mono: Optional[float] = None

        # Transacciones fallidas (MOD-09; diagnóstico como líneas inválidas).
        self._fallos_total = 0
        self._fallos_consecutivos = 0

        self._puerto_presente = False
        self._handshake_ok = False
        self._conexion_pendiente = True
        self._proxima_conexion: Optional[float] = None
        # La próxima conexión rehace una conexión que estaba en operación
        # (invalidación, pérdida o suspensión): TARJETA_CONFIG_SEGURIDAD sale
        # con origen "operacion" (COM-03 en ciclo).
        self._reconexion_en_operacion = False
        # La próxima conexión sigue a una suspensión del tráfico (MOD-08):
        # 0x0C37 = 1 da TARJETA_WATCHDOG.
        self._tras_suspension = False
        self._suspendido = False
        self._ultimo_diag: Optional[float] = None

        self._tarjeta: Dict[str, Any] = {"version": None, "protocolo": None, "id": None}
        self._modulos: Dict[str, Any] = self._modulos_vacios()

        self._comandado: Dict[int, tuple[bool, float]] = {}
        self._sin_confirmar: set[int] = set()
        self._discrepancia_tramas = 0
        self._reenvio_hecho = False
        self._discrepancia_reportada = False

        self._expansor_malas = 0
        self._expansor_reportado = False
        self._pt100_codigo: list[Optional[int]] = [None] * N_TEMP

        self._eventos: list[EventoTarjeta] = []
        self._ultimo_tick_control: Optional[float] = None

    @staticmethod
    def _modulos_vacios() -> Dict[str, Any]:
        return {"modelos": None, "firmware": None, "mac": None, "codigo_error": None,
                "mascara_expansores": None, "falla_salidas": None, "enlace": "modbus"}

    # ---------------------------------------------------------------------
    # Ciclo de vida
    # ---------------------------------------------------------------------

    def start(self) -> None:
        if self.running:
            return
        logger.info("Iniciando ModbusLink (%s:%s, unidad %s)", self.config.ip,
                    self.config.puerto, self.config.unit_id)
        self.running = True
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="modbus-link", daemon=True)
        self._hilo.start()

    def stop(self) -> None:
        logger.info("Deteniendo ModbusLink")
        self.running = False
        self._parar.set()
        hilo = self._hilo
        if hilo is not None and hilo is not threading.current_thread():
            hilo.join(max(2.0, 4 * self.config.timeout_s + 1.0))
        self._desconectar(motivo="stop")

    # ---------------------------------------------------------------------
    # Interfaz EnlaceES: estado
    # ---------------------------------------------------------------------

    def edad_ultima_di(self, now: Optional[float] = None) -> Optional[float]:
        with self.data_lock:
            ultima = self._ultima_di_mono
        if ultima is None:
            return None
        return (time.monotonic() if now is None else now) - ultima

    def secuencia_ultima_di(self) -> Optional[int]:
        with self.data_lock:
            if self._ultima_di_mono is None:
                return None
            return self._di_seq

    def secuencia_ultima_ai(self) -> Optional[int]:
        with self.data_lock:
            if self._ultima_ai_mono is None:
                return None
            return self.data.get("ai_seq")

    def estado_ultima_ai(self) -> tuple[Optional[float], Optional[int]]:
        with self.data_lock:
            if self._ultima_ai_mono is None:
                return None, None
            return time.monotonic() - self._ultima_ai_mono, self.data.get("ai_seq")

    def edad_ultima_ai(self, now: Optional[float] = None) -> Optional[float]:
        with self.data_lock:
            ultima = self._ultima_ai_mono
        if ultima is None:
            return None
        return (time.monotonic() if now is None else now) - ultima

    def puerto_presente(self) -> bool:
        """El último intento de abrir el socket TCP tuvo éxito, aunque luego
        no haya respuesta. False antes del primer intento (falla cerrada)."""
        return self._puerto_presente

    def is_connected(self) -> bool:
        """Socket abierto, datos vivos y conexión verificada (MOD-02)."""
        with self.data_lock:
            return (self.data["port_open"] and self.data["data_alive"]
                    and self._handshake_ok)

    @property
    def handshake_completo(self) -> bool:
        return self._handshake_ok

    def tarjeta(self) -> Dict[str, Any]:
        with self.data_lock:
            return dict(self._tarjeta)

    def marcar_tick_control(self) -> None:
        """Lo llama ControlLoop.run() al completarse cada tick (MOD-08)."""
        self._ultimo_tick_control = time.monotonic()

    def expansor_fuera_de_linea(self) -> bool:
        return self._handshake_ok and self._expansor_reportado

    def solicitar_handshake(self) -> None:
        """Invalida la conexión verificada y la rehace en el próximo sondeo.
        Barato e idempotente (el ControlLoop puede llamarlo en cada tick):
        sin conexión verificada no hace nada, porque ya hay una conexión
        pendiente, en curso o esperando su reintento (sin ráfagas)."""
        with self.data_lock:
            if not self.data["port_open"] or not self._handshake_ok:
                return
            self._reconexion_en_operacion = True
            self._handshake_ok = False
            self._conexion_pendiente = True
        self._notificar()

    def tomar_eventos(self) -> list[EventoTarjeta]:
        with self._eventos_lock:
            eventos, self._eventos = self._eventos, []
        return eventos

    def get_state(self) -> Dict[str, Any]:
        with self.data_lock:
            return {k: (v.copy() if isinstance(v, list) else v) for k, v in self.data.items()}

    def get_diagnostico(self) -> Dict[str, Any]:
        with self.data_lock:
            modulos = dict(self._modulos)
            for k in ("modelos", "firmware"):
                if isinstance(modulos.get(k), dict):
                    modulos[k] = {kk: (list(vv) if isinstance(vv, list) else vv)
                                  for kk, vv in modulos[k].items()}
            return {
                "lineas_invalidas_total": self._fallos_total,
                "lineas_invalidas_consecutivas": self._fallos_consecutivos,
                "handshake_completo": self._handshake_ok,
                "tarjeta_st": None,
                "modulos": modulos,
            }

    # ---------------------------------------------------------------------
    # Eventos
    # ---------------------------------------------------------------------

    def _evento(self, origen: str, alarm_id: Optional[str], motivo: str) -> None:
        if alarm_id is not None:
            logger.warning("ModbusLink: %s (%s): %s", alarm_id, origen, motivo)
        with self._eventos_lock:
            self._eventos.append(EventoTarjeta(origen, alarm_id, motivo))

    def _invalidar_en_operacion(self, alarm_id: str, motivo: str) -> None:
        """Suceso de los módulos con la conexión verificada: se emite en
        origen "operacion" y la conexión se rehace (MOD-08, MOD-10)."""
        with self.data_lock:
            if not self._handshake_ok:
                return
            self._handshake_ok = False
            self._conexion_pendiente = True
            self._reconexion_en_operacion = True
        self._evento("operacion", alarm_id, motivo)
        self._notificar()

    def _notificar(self) -> None:
        if self.on_update:
            try:
                self.on_update(self.get_state())
            except Exception as e:
                logger.warning("ModbusLink: error en on_update: %s", e)

    # ---------------------------------------------------------------------
    # Vigilancia del lazo (MOD-08)
    # ---------------------------------------------------------------------

    def _tick_control_reciente(self, now: float) -> bool:
        ultimo = self._ultimo_tick_control
        return ultimo is not None and now - ultimo <= self.MARGEN_TICK_CONTROL

    def _hay_salidas_on(self, incluir_leidas: bool = True) -> bool:
        with self.data_lock:
            if any(est for est, _ in self._comandado.values()):
                return True
            return incluir_leidas and any(self.data["do"])

    def _trafico_permitido(self, now: Optional[float] = None,
                           incluir_leidas: bool = True) -> bool:
        if now is None:
            now = time.monotonic()
        return self._tick_control_reciente(now) or not self._hay_salidas_on(incluir_leidas)

    # ---------------------------------------------------------------------
    # Transacciones
    # ---------------------------------------------------------------------

    def _abrir_socket(self) -> bool:
        if ModbusTcpClient is None:
            logger.error("ModbusLink: pymodbus no está disponible")
            self._puerto_presente = False
            return False
        with self._cliente_lock:
            if self._cliente is not None:
                try:
                    self._cliente.close()
                except Exception:
                    pass
                self._cliente = None
            try:
                cliente = ModbusTcpClient(self.config.ip, port=self.config.puerto,
                                          timeout=self.config.timeout_s, retries=0)
                ok = bool(cliente.connect())
            except Exception as e:
                logger.warning("ModbusLink: error abriendo %s:%s: %s", self.config.ip,
                               self.config.puerto, e)
                ok = False
                cliente = None
            if not ok:
                if cliente is not None:
                    try:
                        cliente.close()
                    except Exception:
                        pass
                self._puerto_presente = False
                return False
            self._cliente = cliente
            self._puerto_presente = True
        with self.data_lock:
            self.data["port_open"] = True
            self.data["data_alive"] = False
            self.data["last_update"] = None
            # DI de la conexión anterior no vale: 0 = paro hasta el primer
            # sondeo de esta conexión (A-3)
            self.data["di"] = [0] * 56
            self._ultima_di_mono = None
            self._ultima_ai_mono = None
            self._fallos_consecutivos = 0
        logger.info("ModbusLink: socket abierto con %s:%s", self.config.ip, self.config.puerto)
        self._notificar()
        return True

    def _desconectar(self, motivo: str = "") -> None:
        with self._cliente_lock:
            cliente, self._cliente = self._cliente, None
            if cliente is not None:
                try:
                    cliente.close()
                except Exception:
                    pass
        with self.data_lock:
            if self._handshake_ok:
                self._reconexion_en_operacion = True
            estaba = self.data["port_open"]
            self.data["port_open"] = False
            self.data["data_alive"] = False
            self._ultima_di_mono = None
            self._ultima_ai_mono = None
            self._handshake_ok = False
            self._conexion_pendiente = False
            self._proxima_conexion = time.monotonic() + self.config.reintento_conexion_s
        if estaba and motivo:
            logger.warning("ModbusLink: conexión cerrada (%s)", motivo)
        self._notificar()

    def _tx(self, nombre: str, *args, forzar: bool = False, **kwargs):
        """Una transacción Modbus bajo _cliente_lock. Respeta la vigilancia
        del lazo salvo `forzar` (0F de all_off). Lanza _TraficoSuspendido o
        _FalloTransaccion; cuenta los fallos (MOD-09)."""
        with self._cliente_lock:
            if not forzar and not self._trafico_permitido():
                raise _TraficoSuspendido()
            cliente = self._cliente
            if cliente is None:
                raise _FalloTransaccion("sin conexión")
            # El cliente de pymodbus reabre solo el socket en la siguiente
            # petición. Un socket caído (p. ej. el módulo se reinició y perdió
            # su configuración, M-5) es pérdida inmediata: toda reconexión
            # pasa por la conexión verificada (DECISIÓN SIN CONFIRMAR).
            socket_caido = not cliente.connected
            resp = None
            if socket_caido:
                error = "socket TCP cerrado"
            else:
                try:
                    resp = getattr(cliente, nombre)(*args, device_id=self.config.unit_id,
                                                    **kwargs)
                    error = None
                    if resp is None or resp.isError():
                        error = f"respuesta de excepción {resp!r}"
                except Exception as e:
                    resp = None
                    error = f"{type(e).__name__}: {e}"
                    socket_caido = (not cliente.connected
                                    or isinstance(e, (OSError, _ConnectionException)))
            if error is None:
                with self.data_lock:
                    self._fallos_consecutivos = 0
                    self.data["data_alive"] = True
                    self.data["last_update"] = datetime.now()
                return resp
            with self.data_lock:
                self._fallos_total += 1
                self._fallos_consecutivos += 1
                consecutivos = self._fallos_consecutivos
            logger.info("ModbusLink: %s(%s) falló: %s [consecutivos=%d]", nombre,
                        ", ".join(str(a) for a in args[:1]), error, consecutivos)
            if socket_caido:
                logger.warning("ModbusLink: conexión TCP perdida (%s)", error)
                self._desconectar(motivo="socket TCP cerrado")
            elif consecutivos >= self.config.fallos_para_desconexion:
                logger.warning("ModbusLink: %d transacciones fallidas seguidas — "
                               "pérdida de comunicación", consecutivos)
                self._desconectar(motivo="transacciones fallidas")
            raise _FalloTransaccion(error)

    def _leer_holding(self, direccion: int, n: int) -> list[int]:
        regs = list(self._tx("read_holding_registers", direccion, count=n).registers)
        if len(regs) != n:
            raise _FalloTransaccion(f"se esperaban {n} registros en 0x{direccion:04X}")
        return regs

    # ---------------------------------------------------------------------
    # Hilo de sondeo
    # ---------------------------------------------------------------------

    def _bucle(self) -> None:
        while not self._parar.is_set():
            inicio = time.monotonic()
            try:
                self._paso(inicio)
            except Exception as e:      # salvaguarda: el hilo nunca muere
                logger.exception("ModbusLink: error en el sondeo: %s", e)
            espera = self.config.periodo_sondeo_s - (time.monotonic() - inicio)
            self._parar.wait(max(0.005, espera))

    def _paso(self, now: float) -> None:
        """Una pasada del hilo de sondeo (separada para probarla sin hilos)."""
        if not self._trafico_permitido(now):
            if not self._suspendido:
                self._suspendido = True
                logger.warning("ModbusLink: sin tick del lazo de control con salidas en "
                               "ON; se suspende el tráfico Modbus (MOD-08)")
            return
        if self._suspendido:
            self._suspendido = False
            logger.warning("ModbusLink: el lazo de control volvió; se rehace la "
                           "conexión verificada")
            with self.data_lock:
                self._tras_suspension = True
                if self._handshake_ok:
                    self._reconexion_en_operacion = True
                self._handshake_ok = False
                self._conexion_pendiente = True
            self._notificar()

        if not self._handshake_ok:
            vencido = (self._proxima_conexion is not None and now >= self._proxima_conexion)
            if self._conexion_pendiente or vencido:
                if not self._conectar_verificado():
                    with self.data_lock:
                        self._conexion_pendiente = False
                        self._proxima_conexion = (time.monotonic()
                                                  + self.config.reintento_conexion_s)
            return

        try:
            self._sondear()
            if (self._handshake_ok and (self._ultimo_diag is None
                                        or now - self._ultimo_diag >= self.PERIODO_DIAGNOSTICO_S)):
                self._ultimo_diag = now
                self._diagnosticar()
        except (_FalloTransaccion, _TraficoSuspendido):
            pass

    # ---------------------------------------------------------------------
    # Sondeo (MOD-03)
    # ---------------------------------------------------------------------

    def _sondear(self, completo: bool = False) -> bool:
        """Lee DI, DO, temperatura y presión. Con `completo`, cualquier fallo
        se propaga. Devuelve True si las cuatro lecturas salieron bien."""
        bien = 0
        try:
            di = list(self._tx("read_discrete_inputs", DIR_DI, count=N_DI).bits)[:N_DI]
            if len(di) != N_DI:
                raise _FalloTransaccion("DI incompleta")
            with self.data_lock:
                self.data["di"] = [1 if b else 0 for b in di] + [0] * (56 - N_DI)
                self._ultima_di_mono = time.monotonic()
                self._di_seq += 1
            bien += 1
        except _FalloTransaccion:
            if completo or not self.data["port_open"]:
                raise

        try:
            do = list(self._tx("read_coils", DIR_DO, count=N_DO).bits)[:N_DO]
            if len(do) != N_DO:
                raise _FalloTransaccion("DO incompleta")
            do = [1 if b else 0 for b in do]
            with self.data_lock:
                self.data["do"] = do
            bien += 1
            self._comparar_salidas(do)
        except _FalloTransaccion:
            if completo or not self.data["port_open"]:
                raise

        try:
            temp = list(self._tx("read_input_registers", DIR_TEMP, count=N_TEMP).registers)
            pres = list(self._tx("read_input_registers", DIR_PRES, count=N_PRES).registers)
            if len(temp) != N_TEMP or len(pres) != N_PRES:
                raise _FalloTransaccion("AI incompleta")
            ai = [self._temperatura(i, r) for i, r in enumerate(temp)] + [None, None]
            # El 0 (<3,85 mA) llega crudo: la falla de lazo es de Units (MOD-04).
            ai += [int(r) for r in pres]
            with self.data_lock:
                self.data["ai"] = ai
                self.data["ai_seq"] = self.data.get("ai_seq", 0) + 1
                self._ultima_ai_mono = time.monotonic()
            bien += 2
        except _FalloTransaccion:
            if completo or not self.data["port_open"]:
                raise
        finally:
            self._notificar()
        return bien == 4

    def _temperatura(self, canal: int, reg: int) -> Optional[int]:
        valor = _s16(reg)
        if valor in CODIGOS_PT100:
            if self._pt100_codigo[canal] != valor:
                self._pt100_codigo[canal] = valor
                logger.warning("ModbusLink: PT100 %d sin lectura: código %d (%s)",
                               canal + 1, valor, CODIGOS_PT100[valor])
            return None
        if self._pt100_codigo[canal] is not None:
            logger.info("ModbusLink: PT100 %d vuelve a leer (%d)", canal + 1, valor)
            self._pt100_codigo[canal] = None
        return valor

    # ---------------------------------------------------------------------
    # Diagnóstico en operación (MOD-10)
    # ---------------------------------------------------------------------

    def _diagnosticar(self) -> None:
        regs = self._leer_holding(REG_CODIGO_ERROR, 4)    # 7587, 7588-89, 758A
        codigo, mascara, negociacion = regs[0], (regs[1] << 16) | regs[2], regs[3]
        bandera = self._leer_holding(REG_BANDERA_FALLA, 1)[0]
        with self.data_lock:
            self._modulos["codigo_error"] = codigo
            self._modulos["mascara_expansores"] = mascara
            self._modulos["falla_salidas"] = bandera

        if bandera != 0:
            self._invalidar_en_operacion(
                "TARJETA_WATCHDOG",
                f"El módulo principal apagó las salidas por desconexión (0x0C37={bandera}).")
            return
        if codigo == 2 or negociacion != 0 or codigo not in (0, 1, 2):
            logger.warning("ModbusLink: diagnóstico crudo 0x7587=%d 0x758A=%d", codigo,
                           negociacion)
            self._invalidar_en_operacion(
                "TARJETA_MODULOS_ORDEN",
                f"Orden de módulos incorrecto o negociación pendiente "
                f"(0x7587={codigo}, 0x758A={negociacion}).")
            return
        if codigo == 1 or mascara != 0:
            self._expansor_malas += 1
            if self._expansor_malas >= 2 and not self._expansor_reportado:
                self._expansor_reportado = True
                self._evento("operacion", "TARJETA_EXPANSOR_FUERA_DE_LINEA",
                             f"Módulo de expansión sin respuesta (0x7587={codigo}, "
                             f"máscara 0x{mascara:08X}).")
        else:
            self._expansor_malas = 0
            self._expansor_reportado = False

    # ---------------------------------------------------------------------
    # Conexión verificada (MOD-06)
    # ---------------------------------------------------------------------

    def _conectar_verificado(self) -> bool:
        fin = time.monotonic() + self.config.presupuesto_conexion_s
        with self.data_lock:
            self._handshake_ok = False
            self._conexion_pendiente = False
            self._tarjeta = {"version": None, "protocolo": None, "id": None}
            origen_config = "operacion" if self._reconexion_en_operacion else "handshake"
            tras_suspension = self._tras_suspension

        # 1. Socket TCP. Sin socket no hay evento: puerto_presente() False da
        # "desconectada" (como un puerto serial ausente).
        if self._cliente is None or not self.data["port_open"]:
            if not self._abrir_socket():
                with self.data_lock:
                    self.data["port_open"] = False
                    self.data["data_alive"] = False
                self._notificar()
                return False

        try:
            tarjeta = self._pasos_conexion(fin, origen_config, tras_suspension)
        except _TraficoSuspendido:
            logger.warning("ModbusLink: conexión interrumpida por la vigilancia del lazo")
            return False
        except _FalloConexion as f:
            origen = origen_config if f.alarma == "TARJETA_CONFIG_SEGURIDAD" else "handshake"
            self._evento(origen, f.alarma, f.motivo)
            return False

        with self.data_lock:
            self._discrepancia_tramas = 0
            self._reenvio_hecho = False
            self._discrepancia_reportada = False
            self._expansor_malas = 0
            self._expansor_reportado = False
            self._handshake_ok = True
            self._proxima_conexion = None
            self._reconexion_en_operacion = False
            self._tras_suspension = False
        self._ultimo_diag = time.monotonic()
        logger.info("ModbusLink: conexión verificada con los módulos %s (firmware %s)",
                    tarjeta["id"], tarjeta["version"])
        self._evento("conectada", None, "Conexión verificada")
        self._notificar()
        return True

    def _paso_tx(self, fin: float, paso: str, fn, *args, **kwargs):
        if time.monotonic() >= fin:
            raise _FalloConexion("TARJETA_SIN_TRAMA_VALIDA",
                                 f"Se agotó el tiempo de la conexión ({paso}).")
        try:
            return fn(*args, **kwargs)
        except _FalloTransaccion as e:
            raise _FalloConexion("TARJETA_SIN_TRAMA_VALIDA",
                                 f"Sin respuesta Modbus de los módulos ({paso}: {e}).") from None

    def _pasos_conexion(self, fin: float, origen_config: str,
                        tras_suspension: bool) -> Dict[str, Any]:
        cfg = self.config
        esperadas = list(cfg.composicion_esperada["expansiones"])
        n = len(esperadas)

        # 2a. Código de error y negociación pendiente
        regs = self._paso_tx(fin, "diagnóstico", self._leer_holding, REG_CODIGO_ERROR, 4)
        codigo, mascara, negociacion = regs[0], (regs[1] << 16) | regs[2], regs[3]
        with self.data_lock:
            self._modulos["codigo_error"] = codigo
            self._modulos["mascara_expansores"] = mascara
        if codigo == 1 or (codigo == 0 and mascara != 0):
            raise _FalloConexion("TARJETA_EXPANSOR_FUERA_DE_LINEA",
                                 f"Módulo de expansión sin respuesta (0x7587={codigo}, "
                                 f"máscara 0x{mascara:08X}).")
        if codigo != 0 or negociacion != 0:
            logger.warning("ModbusLink: diagnóstico crudo 0x7587=%d 0x758A=%d", codigo,
                           negociacion)
            raise _FalloConexion("TARJETA_MODULOS_ORDEN",
                                 f"Orden de módulos incorrecto o negociación pendiente "
                                 f"(0x7587={codigo}, 0x758A={negociacion}). Sin energía, "
                                 f"revisar el orden de los módulos y negociar (doble "
                                 f"pulsación de Reload).")

        # 2b. Modelos
        crudo = self._paso_tx(fin, "modelo", self._leer_holding, REG_MODELO_PRINCIPAL,
                              N_MODELO_PRINCIPAL)
        principal = _registros_a_texto(crudo)
        esclavos: list[Optional[str]] = []
        crudos_esclavos = []
        for i in range(min(n + 1, MAX_EXPANSIONES)):
            r = self._paso_tx(fin, "modelo", self._leer_holding,
                              REG_MODELO_ESCLAVOS + N_MODELO_ESCLAVO * i, N_MODELO_ESCLAVO)
            crudos_esclavos.append(r)
            esclavos.append(_registros_a_texto(r))
        with self.data_lock:
            self._modulos["modelos"] = {"principal": principal, "expansiones": list(esclavos[:n])}

        problemas = []
        if principal is None:
            logger.warning("ModbusLink: modelo del principal con formato inesperado: %r", crudo)
            problemas.append("principal ilegible")
        elif normalizar_modelo(principal) != cfg.composicion_esperada["principal"]:
            problemas.append(f"principal {principal} (se espera "
                             f"{cfg.composicion_esperada['principal']})")
        for i, texto in enumerate(esclavos):
            esperado = esperadas[i] if i < n else None
            if texto is None:
                logger.warning("ModbusLink: modelo del esclavo %d con formato inesperado: %r",
                               i + 1, crudos_esclavos[i])
                problemas.append(f"expansión {i + 1} ilegible")
                continue
            norm = normalizar_modelo(texto)
            if esperado is None:
                if norm != "NONE":
                    problemas.append(f"expansión {i + 1} sobrante ({texto})")
            elif norm == "NONE":
                problemas.append(f"falta la expansión {i + 1} ({esperado})")
            elif norm != esperado:
                problemas.append(f"expansión {i + 1} {texto} (se espera {esperado})")
        if problemas:
            raise _FalloConexion("TARJETA_VERSION_INCOMPATIBLE",
                                 "Composición de módulos distinta de la esperada: "
                                 + "; ".join(problemas) + ".")

        # 2c. Firmware: el principal igual o más nuevo que cada expansión
        fw_p = self._paso_tx(fin, "firmware", self._leer_holding, REG_FW_PRINCIPAL, 1)[0]
        fw_e = self._paso_tx(fin, "firmware", self._leer_holding, REG_FW_ESCLAVOS, n)
        v_p = _version(fw_p)
        v_e = [_version(r) for r in fw_e]
        with self.data_lock:
            self._modulos["firmware"] = {"principal": _texto_version(v_p),
                                         "expansiones": [_texto_version(v) for v in v_e]}
        if fw_p == 0 or any(r == 0 for r in fw_e):
            logger.warning("ModbusLink: firmware con formato inesperado: principal=0x%04X "
                           "expansiones=%s", fw_p, [f"0x{r:04X}" for r in fw_e])
            raise _FalloConexion("TARJETA_VERSION_INCOMPATIBLE",
                                 "Versión de firmware ilegible en los módulos.")
        viejas = [f"expansión {i + 1} v{_texto_version(v)}" for i, v in enumerate(v_e)
                  if v > v_p]
        if viejas:
            raise _FalloConexion("TARJETA_VERSION_INCOMPATIBLE",
                                 f"El firmware del principal (v{_texto_version(v_p)}) es "
                                 f"más antiguo que el de: {', '.join(viejas)}.")

        # 3. Configuración de seguridad (MOD-07)
        self._escribir_configuracion(fin)

        # 4. Apagar todo y confirmar
        self._paso_tx(fin, "apagado", self._tx, "write_coils", DIR_DO, [False] * N_DO)
        leidas = list(self._paso_tx(fin, "apagado", self._tx, "read_coils", DIR_DO,
                                    count=N_DO).bits)[:N_DO]
        ahora = time.monotonic()
        with self.data_lock:
            self.data["do"] = [1 if b else 0 for b in leidas] + [0] * (N_DO - len(leidas))
            self._comandado = {ch: (False, ahora) for ch in range(1, N_DO + 1)}
            self._sin_confirmar = set()
        if len(leidas) != N_DO or any(leidas):
            encendidas = [str(i + 1) for i, b in enumerate(leidas) if b]
            raise _FalloConexion("TARJETA_SALIDAS_NO_APAGADAS",
                                 f"Salidas encendidas tras el apagado: DO{', DO'.join(encendidas)}.")

        # 5. MAC e identificación; al_conectar
        mac_regs = self._paso_tx(fin, "MAC", self._leer_holding, REG_MAC, 3)
        mac = "".join(f"{r & 0xFFFF:04X}" for r in mac_regs)
        version = (f"{_texto_version(v_p)} / "
                   + ", ".join(_texto_version(v) for v in v_e))
        tarjeta = {"version": version, "protocolo": "modbus-tcp", "id": mac}
        with self.data_lock:
            self._tarjeta = dict(tarjeta)
            self._modulos["mac"] = mac
        if self.al_conectar is not None:
            try:
                self.al_conectar(dict(tarjeta))
            except Exception as e:
                logger.warning("ModbusLink: error en al_conectar: %s", e)

        # 6. Bandera de falla por desconexión
        bandera = self._paso_tx(fin, "bandera de falla", self._leer_holding,
                                REG_BANDERA_FALLA, 1)[0]
        with self.data_lock:
            self._modulos["falla_salidas"] = bandera
        if bandera != 0:
            if tras_suspension:
                self._evento("operacion", "TARJETA_WATCHDOG",
                             "El módulo principal apagó las salidas por desconexión "
                             "mientras el lazo de control no respondía (0x0C37=1).")
            else:
                logger.warning("ModbusLink: el módulo venía de un corte por desconexión "
                               "(0x0C37=%d); las salidas ya estaban apagadas", bandera)
            # DECISIÓN SIN CONFIRMAR: se borra la bandera (registro escribible)
            # para detectar el próximo corte.
            self._paso_tx(fin, "bandera de falla", self._tx, "write_registers",
                          REG_BANDERA_FALLA, [0])

        # 7. Primer sondeo completo válido
        self._paso_tx(fin, "primer sondeo", self._sondear, True)
        return tarjeta

    def _bloques_configuracion(self) -> list[tuple[str, int, list[int]]]:
        c = self.config
        return [
            ("estado de falla de las DO", REG_DO_FALLA, [1] * 32),
            ("estado de las DO al encender", REG_DO_ENCENDIDO, [0] * 32),
            ("modo de las DO", REG_DO_MODO, [0] * 32),
            ("tiempo de desconexión", REG_TIEMPO_DESCONEXION, [c.tiempo_desconexion_modulo_ds]),
            ("modo de falla por desconexión", REG_MODO_FALLA, [1]),
            ("rango de las AI", REG_RANGO_AI, [1] * 16),
            ("filtro de las AI", REG_FILTRO_AI, [c.filtro_ai]),
            ("unidad de las PT100", REG_PT_UNIDAD, [0] * 6),
            ("compensación de las PT100", REG_PT_COMPENSACION, [0] * 6),
            ("filtro de las PT100", REG_PT_FILTRO, [c.filtro_pt100] * 6),
            ("PT100 deshabilitadas", REG_PT_DESHABILITADA, [0] * 6),
        ]

    def _escribir_configuracion(self, fin: float) -> None:
        """MOD-07: cada bloque con 10, leído con 03 y comparado exacto, hasta
        intentos_escritura_config veces. Nunca se confía en lo guardado."""
        for nombre, direccion, valores in self._bloques_configuracion():
            leidos: Optional[list[int]] = None
            for _ in range(self.config.intentos_escritura_config):
                self._paso_tx(fin, f"configuración: {nombre}", self._tx,
                              "write_registers", direccion, list(valores))
                leidos = self._paso_tx(fin, f"configuración: {nombre}", self._leer_holding,
                                       direccion, len(valores))
                if leidos == valores:
                    break
            else:
                raise _FalloConexion(
                    "TARJETA_CONFIG_SEGURIDAD",
                    f"No quedó verificada la configuración de seguridad ({nombre}, "
                    f"0x{direccion:04X}): se escribió {valores[:4]}{'…' if len(valores) > 4 else ''}"
                    f" y se leyó {(leidos or [])[:4]}.")

    # ---------------------------------------------------------------------
    # Salidas (MOD-11)
    # ---------------------------------------------------------------------

    def _registrar_comando(self, channel: int, estado: bool, ahora: float) -> None:
        """Bajo data_lock. Como SerialLink: la tolerancia de 1 s cuenta desde
        el último CAMBIO de estado comandado."""
        previo = self._comandado.get(channel)
        if previo is None or previo[0] != estado:
            self._comandado[channel] = (estado, ahora)

    def set_output(self, channel: int, state: bool) -> bool:
        if not isinstance(channel, int) or channel < 1 or channel > N_DO:
            return False
        if not self._handshake_ok:
            return False
        estado = bool(state)
        with self._cmd_lock:
            with self.data_lock:
                previo = self._comandado.get(channel)
                sin_cambio = (previo is not None and previo[0] == estado
                              and channel not in self._sin_confirmar)
            if sin_cambio:
                return True     # el lazo reafirma cada tick: solo se escriben los cambios
            ahora = time.monotonic()
            # MOD-08: encender exige tick reciente del lazo (DECISIÓN SIN
            # CONFIRMAR, más estricta que la compuerta); apagar sigue la
            # compuerta.
            if not self._tick_control_reciente(ahora) and (estado or self._hay_salidas_on()):
                logger.warning("ModbusLink: DO%d %s rechazada: sin tick reciente del lazo "
                               "de control (MOD-08)", channel, "ON" if estado else "OFF")
                return False
            with self.data_lock:
                self._registrar_comando(channel, estado, ahora)
                self._sin_confirmar.add(channel)
            try:
                self._tx("write_coil", channel - 1, estado)
            except (_FalloTransaccion, _TraficoSuspendido):
                return False
            with self.data_lock:
                self._sin_confirmar.discard(channel)
        return True

    def all_off(self, timeout: float = 1.0) -> bool:
        """0F con las 32 en 0 (siempre se envía si hay socket: lleva al estado
        seguro; DECISIÓN SIN CONFIRMAR) y lectura 01 hasta `timeout`. True
        solo si las 32 se leen en 0. Termina dentro de `timeout` (más, como
        mucho, la espera de una transacción en curso de otro hilo) y no se
        cuelga con el socket caído."""
        inicio = time.monotonic()
        fin = inicio + timeout
        with self._cmd_lock:
            ahora = time.monotonic()
            with self.data_lock:
                for ch in range(1, N_DO + 1):
                    self._registrar_comando(ch, False, ahora)
                self._sin_confirmar = set()
            try:
                self._tx("write_coils", DIR_DO, [False] * N_DO, forzar=True)
            except (_FalloTransaccion, _TraficoSuspendido) as e:
                logger.warning("ModbusLink: all_off sin enviar (%s)", e)
                return False
        while time.monotonic() + self.config.timeout_s <= fin:
            try:
                with self._cliente_lock:
                    # La confirmación solo si ya no hay salidas comandadas en ON.
                    if not self._trafico_permitido(incluir_leidas=False):
                        raise _TraficoSuspendido()
                    leidas = list(self._tx("read_coils", DIR_DO, count=N_DO,
                                           forzar=True).bits)[:N_DO]
                with self.data_lock:
                    self.data["do"] = [1 if b else 0 for b in leidas]
                if len(leidas) == N_DO and not any(leidas):
                    return True
            except (_FalloTransaccion, _TraficoSuspendido):
                if self._cliente is None:
                    break       # socket caído: no hay a quién preguntar
            time.sleep(self._PAUSA_CONFIRMACION_S)
        logger.warning("ModbusLink: all_off sin confirmar en %.1f s", timeout)
        return False

    def _comparar_salidas(self, do: list) -> None:
        """Mismo algoritmo que SerialLink._comparar_salidas (MOD-11)."""
        if not self._handshake_ok:
            return
        ahora = time.monotonic()
        with self.data_lock:
            distintas = [(ch, t) for ch, (est, t) in self._comandado.items()
                         if bool(do[ch - 1]) != est]
            difieren = sorted(ch for ch, t in distintas
                              if ahora - t >= self._TOLERANCIA_COMANDO_S)
            if distintas and not difieren:
                # Dentro de la tolerancia (orden reciente o recién reenviada):
                # no se cuenta ni se rearma el reenvío. Sin esto, la
                # tolerancia que sigue al reenvío borraba _reenvio_hecho y el
                # reenvío se repetía sin fin sin llegar nunca a la alarma.
                return
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
            logger.warning("ModbusLink: salidas %s distintas de lo comandado; reenvío único",
                           canales)
            with self._cmd_lock:
                for ch in estados:
                    with self.data_lock:
                        est = self._comandado[ch][0] if ch in self._comandado else None
                    if est is not None and self._handshake_ok:
                        try:
                            self._tx("write_coil", ch - 1, est)
                        except _TraficoSuspendido:
                            return
        elif reportar:
            if self.config.discrepancia_dispara_fallo:
                self._evento("operacion", "DISCREPANCIA_SALIDAS",
                             f"Las salidas {canales} no siguen lo comandado tras el reenvío.")
            else:
                logger.warning("ModbusLink: las salidas %s no siguen lo comandado tras el "
                               "reenvío (discrepancia_dispara_fallo=false: solo log)", canales)
