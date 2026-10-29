# autoclave.protocols.modbus_link
# --------------------------------
# Enlace de E/S con los módulos Ebyte M31-U por Modbus TCP (tanda 19; ver
# docs/mis_plans/planeacion_enlace_modbus.md, MOD-02, MOD-03, MOD-06 a
# MOD-11). El PC es el maestro; cumple protocols.enlace.EnlaceES (handshake =
# conexión verificada; desde la tanda 20 es la única implementación).
#
# Un único hilo daemon de sondeo hace TODO el tráfico periódico: conexión
# verificada, lectura de entradas cada periodo_sondeo_s y diagnóstico cada
# 1 s. set_output() y all_off() escriben desde el hilo que los llama. El
# cliente síncrono de pymodbus no es seguro entre hilos: todo acceso pasa por
# _cliente_lock (MOD-11). Registrar una orden y escribirla es atómico
# respecto a otros escritores (_cmd_lock, TMG-03).
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
#
# Tanda 20 (T20-02, adenda_tanda_19_banco.md y decisiones_tanda_20.md):
#   - ADB-01: la lista de esclavos 0x0C80 incluye las E/S del principal como
#     esclavo ID 0; se esperan los IDs 0..n-1 de composicion_esperada y el
#     ID n debe ser NONE.
#   - ADB-02, corregido el 28-oct (FW-INF, alpha.4 en el equipo de pruebas):
#     0x0C1F y 0x0D80 codifican la versión como «vX.Y» (byte alto = parte
#     antes del punto, byte bajo = después; manual del principal V1.4, tabla
#     4.10: 0x0103 = v1.3), no como el último número del texto de firmware.
#     El equipo real dio principal 0x0103 y esclavos 0x0100 x4 y 0x0000, y la
#     lectura del byte bajo los declaraba «ilegibles» en cualquier caso.
#     La comprobación de firmware queda solo INFORMATIVA (log, diagnóstico e
#     Información del sistema; nunca TARJETA_VERSION_INCOMPATIBLE): el
#     manual de expansiones (6.3, punto 3) indica que con firmware
#     incompatible el conjunto no arranca, así que la compatibilidad la
#     impone el propio hardware. La composición (modelos y orden) sigue
#     bloqueando. Aprobado por Cristian el 28-oct; pendiente de M-2 saber a
#     qué esclavo corresponde cada posición de 0x0D80.
#   - ADB-04 (decisión 8): la configuración de seguridad se lee antes de
#     escribirla; si hubo que escribir algún bloque, 0F de apagado, reinicio
#     del módulo (0x0C1D = 0x5BB5), espera, reconexión, nueva lectura de la
#     identidad y relectura de toda la configuración sin escribir. Una
#     conexión cuyos registros ya coincidían no reinicia.
#     Corrector r1 (V20-s1-01..05; DECISIONES SIN CONFIRMAR hasta M-5b):
#     el reinicio exige evidencia (el módulo cerró la conexión o dejó de
#     responder tras la orden; una respuesta de excepción a 0x0C1D o un
#     módulo que sigue respondiendo es TARJETA_CONFIG_SEGURIDAD); una
#     escritura sin reinicio verificado queda pendiente
#     (_reinicio_pendiente); como mucho MAX_REINICIOS_SIN_VERIFICAR
#     reinicios seguidos sin verificación; antes del reinicio se confirman
#     las 32 salidas en 0 (fc01) y el reinicio exige reinicio_permitido()
#     (el contexto lo niega en CICLO).
#   - ADB-05: 0x0C37 no es bandera de falla: solo se lee y se registra su
#     valor crudo (diagnóstico y log); no se escribe, no se exige 0 y no
#     dispara TARJETA_WATCHDOG. El corte lo detectan la discrepancia (MOD-11)
#     y la reconexión (MOD-08).
#   - T20-04: leer_identidad() (sin hilo, sin escribir) para el rol
#     --rol configurar-modulo (estacion/configurar_modulo.py).

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
    from pymodbus.pdu import ExceptionResponse as _ExceptionResponse
except ImportError:     # pragma: no cover - el .spec lo incluye
    ModbusTcpClient = None  # type: ignore[assignment,misc]
    _ConnectionException = OSError  # type: ignore[assignment,misc]
    _ExceptionResponse = None  # type: ignore[assignment,misc]


# --- Mapa de datos (MOD-03) -------------------------------------------------
DIR_DI = 0x0000
N_DI = 16
DIR_DO = 0x0000
N_DO = 32
DIR_TEMP = 0x0DAC          # registros de entrada, PT100 1-6 (décimas de °C)
N_TEMP = 6
DIR_PRES = 0x0000          # registros de entrada, AI 1-16 del principal (µA)
# Tanda 23 (AIN-03): las 16 AI del principal (manual V1.4, §4.10.3: AI1 =
# 0x0000 … AI16 = 0x000F, contiguas). Antes 8.
N_PRES = 16
# Largo de la lista cruda "ai": RTD 1-6 en 0-5, 6-7 sin uso (None), AI 1-16
# en 8-23 (tanda 23, AIN-03; antes 16).
N_AI = 8 + N_PRES

# --- Parámetros básicos y diagnóstico (MOD-06, MOD-10) ----------------------
REG_FW_PRINCIPAL = 0x0C1F
REG_MODELO_PRINCIPAL = 0x0C20      # 12 registros
N_MODELO_PRINCIPAL = 12
REG_REINICIO = 0x0C1D              # ADB-04: escribir CLAVE_REINICIO reinicia el módulo
CLAVE_REINICIO = 0x5BB5
REG_FW_TEXTO = 0x0C2C              # ADB-02: firmware del principal como texto, 8 registros
N_FW_TEXTO = 8
REG_TIEMPO_DESCONEXION = 0x0C35
REG_MODO_FALLA = 0x0C36
# ADB-05: el manual lo describe como bandera 0/1 de falla por desconexión,
# pero en el banco se comporta como un contador (100 y 105 con 5 s de
# diferencia). Solo se lee y se registra.
REG_0C37 = 0x0C37
REG_MODELO_ESCLAVOS = 0x0C80       # 8 registros por esclavo
N_MODELO_ESCLAVO = 8
REG_FW_ESCLAVOS = 0x0D80           # 1 registro por esclavo
REG_MAC = 0x7534                   # 3 registros
REG_CODIGO_ERROR = 0x7587          # 0x7587, 0x7588-89 (máscara), 0x758A
REG_NEGOCIACION = 0x758A
REG_WEB_USUARIO = 0x758B           # T20-04: usuario de la página web, 5 registros
N_WEB_USUARIO = 5
REG_WEB_CLAVE = 0x7590             # T20-04: contraseña de la página web, 3 registros
N_WEB_CLAVE = 3

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
# 0x0C36: 1 = al vencer 0x0C35 las DO pasan a su estado de falla (MOD-07).
MODO_FALLA_ACTIVO = 1

# Códigos de diagnóstico de las PT100 (MOD-03): el canal se entrega None.
CODIGOS_PT100 = {
    32766: "sensor desconectado o cable roto",
    -32766: "cortocircuito",
    32765: "falla del chip",
    32767: "fuera de rango (alto)",
    -32768: "fuera de rango (bajo)",
    -32767: "canal deshabilitado",
}


# Alarmas de la conexión que salen en origen "operacion" cuando la conexión
# rehace una que estaba en operación (COM-03 en ciclo; V19-s3-04).
_ALARMAS_ORIGEN_CONFIG = frozenset({"TARJETA_CONFIG_SEGURIDAD", "TARJETA_MODULOS_ORDEN"})


class _FalloTransaccion(Exception):
    """Transacción Modbus sin respuesta válida (timeout, excepción del
    cliente o respuesta de excepción)."""


class _TraficoSuspendido(Exception):
    """La vigilancia del lazo (MOD-08) no permite tráfico en este momento."""


class FalloConexion(Exception):
    """Fallo de la conexión verificada o de leer_identidad().
    alarma: id de alarma (None si no se pudo abrir el socket).
    causa: "sin_conexion", "orden", "expansor", "composicion", "firmware",
    "config" u otra (para el rol configurar-modulo)."""

    def __init__(self, alarma: Optional[str], motivo: str, causa: Optional[str] = None):
        super().__init__(motivo)
        self.alarma = alarma
        self.motivo = motivo
        self.causa = causa


class _Detenido(Exception):
    """stop() durante la espera del reinicio del módulo (ADB-04)."""


def _s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def version_registro(reg: Optional[int]) -> Optional[tuple[int, int]]:
    """FW-INF: 0x0C1F / 0x0D80 dan «vX.Y» (byte alto X, byte bajo Y; manual
    del principal, tabla 4.10). 0 o sin dato -> None (sin versión)."""
    if not reg:
        return None
    reg &= 0xFFFF
    return (reg >> 8, reg & 0xFF)


def etiqueta_version(v: Optional[tuple[int, int]]) -> str:
    """Texto ASCII de una versión de registro: «v1.3», o «-» sin versión
    (ASCII porque el rol configurar-modulo lo entrega a Inno Setup)."""
    return f"v{v[0]}.{v[1]}" if v else "-"


def texto_a_registros(texto: str, n: int) -> list[int]:
    """Texto ASCII en n registros, 2 caracteres por registro, byte alto
    primero, relleno con NUL (inverso de _registros_a_texto)."""
    b = texto.encode("ascii")[: 2 * n].ljust(2 * n, b"\0")
    return [(b[2 * i] << 8) | b[2 * i + 1] for i in range(n)]


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
    # FW-D6 / MOD-08: vigilancia del tick del lazo de control.
    MARGEN_TICK_CONTROL = 1.5
    # Plan de protocolo §6.5: no se comparan los canales comandados hace menos.
    _TOLERANCIA_COMANDO_S = 1.0
    # MOD-10: periodo del diagnóstico de los módulos.
    PERIODO_DIAGNOSTICO_S = 1.0
    # all_off(): pausa entre lecturas de confirmación.
    _PAUSA_CONFIRMACION_S = 0.02
    # V20-s1-03: órdenes de reinicio seguidas sin que la configuración quede
    # verificada; al llegar, no se vuelve a escribir ni a reiniciar hasta una
    # conexión verificada o un reinicio del proceso. DECISIÓN SIN CONFIRMAR.
    MAX_REINICIOS_SIN_VERIFICAR = 2
    # V20-s1-01: ventana mínima para observar la evidencia del reinicio (se
    # usa max(espera_reinicio_s, esta)), pausa entre lecturas ligeras y
    # lecturas seguidas sin respuesta que cuentan como evidencia.
    # DECISIÓN SIN CONFIRMAR hasta M-5b.
    VENTANA_MIN_EVIDENCIA_REINICIO_S = 1.0
    _PAUSA_SONDEO_REINICIO_S = 0.02
    _SIN_RESPUESTA_EVIDENCIA = 2

    def __init__(
        self,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        config: Optional[ModbusLinkConfig] = None,
        reinicio_permitido: Optional[Callable[[], bool]] = None,
    ):
        self.config = config if config is not None else cargar_config()
        self.on_update = on_update
        # V20-s1-04: permiso para reiniciar el módulo (ADB-04). None = se
        # permite; el contexto del backend lo niega mientras la máquina esté en
        # CICLO. Si devuelve False o lanza, no se reinicia (falla cerrada).
        self.reinicio_permitido: Optional[Callable[[], bool]] = reinicio_permitido
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
            "ai": [None] * N_AI,
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
        self._suspendido = False
        # ADB-05: último valor de 0x0C37 registrado en el log (sin inundar).
        self._ultimo_0c37_log: Optional[float] = None
        self._valor_0c37_log: Optional[int] = None
        # ADB-04: reinicios del módulo con evidencia (diagnóstico).
        self._reinicios_modulo = 0
        # V20-s1-02: se escribió algún bloque de la configuración de seguridad
        # y todavía no hubo un reinicio con evidencia seguido de una relectura
        # correcta. Vive en memoria: un reinicio del PROCESO entre la escritura
        # y el reinicio del módulo la pierde, y tras él una configuración que
        # ya coincide no fuerza reinicio (riesgo residual).
        self._reinicio_pendiente = False
        # V20-s1-03: órdenes de reinicio enviadas sin verificación correcta.
        self._reinicios_sin_verificar = 0
        self._cliente_orden_reinicio = None   # V20-rr-01: cliente con el que se envió la orden
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
                "mascara_expansores": None, "falla_salidas": None, "registro_0c37": None,
                "reinicios_modulo": 0, "enlace": "modbus"}

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
            # RTD 1-6 en ai[0..5], ai[6..7] sin uso, AI 1-16 en ai[8..23] (AIN-03)
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
        # V19-s1-03: 0x0C35-0x0C37 en una sola transacción; 0x0C35 y 0x0C36
        # se comparan con lo escrito en la conexión (un Reload sin reinicio
        # los devuelve a fábrica sin cortar el TCP).
        tiempo, modo, crudo_0c37 = self._leer_holding(REG_TIEMPO_DESCONEXION, 3)
        with self.data_lock:
            self._modulos["codigo_error"] = codigo
            self._modulos["mascara_expansores"] = mascara
        # ADB-05: 0x0C37 solo se registra (no invalida ni da TARJETA_WATCHDOG)
        self._registrar_0c37(crudo_0c37, en_conexion=False)
        esperado = self.config.tiempo_desconexion_modulo_ds
        if tiempo != esperado or modo != MODO_FALLA_ACTIVO:
            self._invalidar_en_operacion(
                "TARJETA_CONFIG_SEGURIDAD",
                f"La configuración de seguridad de los módulos cambió en operación "
                f"(0x0C35={tiempo}, se espera {esperado}; 0x0C36={modo}, se espera "
                f"{MODO_FALLA_ACTIVO}).")
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

    # Con 0x0C37 cambiando cada segundo (contador en el banco), en operación se
    # registra como mucho una vez por este periodo.
    PERIODO_LOG_0C37_S = 60.0

    def _registrar_0c37(self, valor: int, en_conexion: bool) -> None:
        """ADB-05: valor crudo de 0x0C37 al diagnóstico y al log (INFO en la
        conexión y, si cambió, como mucho una vez por PERIODO_LOG_0C37_S en
        operación). No se escribe, no se exige 0 ni dispara alarmas."""
        with self.data_lock:
            # V20-s1-07: falla_salidas queda en None (clave conservada por la
            # API); el valor crudo solo en registro_0c37 (ADB-05)
            self._modulos["registro_0c37"] = valor
        ahora = time.monotonic()
        if en_conexion:
            logger.info("ModbusLink: registro 0x0C37 = %d (valor crudo; ADB-05, no es "
                        "bandera de falla)", valor)
        elif (valor != self._valor_0c37_log
              and (self._ultimo_0c37_log is None
                   or ahora - self._ultimo_0c37_log >= self.PERIODO_LOG_0C37_S)):
            logger.info("ModbusLink: registro 0x0C37 = %d en operación (antes %s; valor "
                        "crudo, ADB-05)", valor, self._valor_0c37_log)
        else:
            return
        self._valor_0c37_log = valor
        self._ultimo_0c37_log = ahora

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

        # 1. Socket TCP. Sin socket no hay evento: puerto_presente() False da
        # "desconectada" (sin socket abierto).
        if self._cliente is None or not self.data["port_open"]:
            if not self._abrir_socket():
                with self.data_lock:
                    self.data["port_open"] = False
                    self.data["data_alive"] = False
                self._notificar()
                return False

        try:
            tarjeta = self._pasos_conexion(fin)
        except _Detenido:
            logger.info("ModbusLink: conexión interrumpida por stop() durante el reinicio "
                        "del módulo")
            return False
        except _TraficoSuspendido:
            logger.warning("ModbusLink: conexión interrumpida por la vigilancia del lazo")
            self._apagar_tras_fallo_conexion()
            return False
        except FalloConexion as f:
            self._apagar_tras_fallo_conexion()
            # V19-s3-04: también TARJETA_MODULOS_ORDEN (paso 2) sale en
            # "operacion" si la conexión rehace una que estaba en operación.
            origen = (origen_config if f.alarma in _ALARMAS_ORIGEN_CONFIG
                      else "handshake")
            self._evento(origen, f.alarma, f.motivo)
            return False
        except Exception:
            self._apagar_tras_fallo_conexion()
            raise

        with self.data_lock:
            # V20-s1-05: un stop() durante la conexión no la da por verificada
            # ni encola «conectada».
            detenido = self._parar.is_set()
            if not detenido:
                self._discrepancia_tramas = 0
                self._reenvio_hecho = False
                self._discrepancia_reportada = False
                self._expansor_malas = 0
                self._expansor_reportado = False
                self._handshake_ok = True
                self._proxima_conexion = None
                self._reconexion_en_operacion = False
        if detenido:
            logger.info("ModbusLink: conexión no verificada: stop() durante la conexión")
            return False
        self._ultimo_diag = time.monotonic()
        logger.info("ModbusLink: conexión verificada con los módulos %s (firmware %s)",
                    tarjeta["id"], tarjeta["version"])
        self._evento("conectada", None, "Conexión verificada")
        self._notificar()
        return True

    def _apagar_tras_fallo_conexion(self) -> None:
        """V19-s1-01: una conexión fallida con el socket abierto envía de
        mejor esfuerzo un 0F con las 32 en 0 (sin confirmar), en todos los
        estados (como el 0F de all_off, ignora la vigilancia del lazo): los
        reintentos de conexión mantienen vivo el temporizador de desconexión
        del módulo y, sin esto, una salida en ON quedaría sin control.
        También antes del reinicio del módulo (ADB-04)."""
        if self._cliente is None:
            return
        with self._cmd_lock:
            ahora = time.monotonic()
            with self.data_lock:
                for ch in range(1, N_DO + 1):
                    self._registrar_comando(ch, False, ahora)
                self._sin_confirmar = set()
            try:
                self._tx("write_coils", DIR_DO, [False] * N_DO, forzar=True)
            except (_FalloTransaccion, _TraficoSuspendido) as e:
                logger.warning("ModbusLink: apagado tras la conexión fallida sin enviar (%s)",
                               e)

    def _paso_tx(self, fin: float, paso: str, fn, *args, **kwargs):
        if time.monotonic() >= fin:
            raise FalloConexion("TARJETA_SIN_TRAMA_VALIDA",
                                f"Se agotó el tiempo de la conexión ({paso}).", "sin_conexion")
        try:
            return fn(*args, **kwargs)
        except _FalloTransaccion as e:
            raise FalloConexion("TARJETA_SIN_TRAMA_VALIDA",
                                f"Sin respuesta Modbus de los módulos ({paso}: {e}).",
                                "sin_conexion") from None

    # ---------------------------------------------------------------------
    # Identidad de los módulos (pasos 2a-2c y MAC; T20-04)
    # ---------------------------------------------------------------------

    def leer_identidad(self, cerrar: bool = True) -> Dict[str, Any]:
        """T20-04: abre el socket, lee la identidad de los módulos (código de
        error y negociación, modelos, firmware y MAC, con la misma
        verificación que la conexión) y, con `cerrar`, desconecta. Sin hilo y
        sin escribir nada (ni bobinas, ni configuración, ni reinicio). Lanza
        FalloConexion (causa "sin_conexion" si no hay socket o respuesta);
        ante un fallo siempre desconecta."""
        if self.running:
            raise RuntimeError("leer_identidad() no se usa con el hilo de sondeo en marcha")
        if not self._abrir_socket():
            raise FalloConexion(None, f"No se pudo abrir {self.config.ip}:{self.config.puerto}.",
                                "sin_conexion")
        ok = False
        try:
            identidad = self._leer_identidad(time.monotonic()
                                             + self.config.presupuesto_conexion_s)
            ok = True
            return identidad
        finally:
            if cerrar or not ok:
                self._desconectar()

    def _leer_identidad(self, fin: float) -> Dict[str, Any]:
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
            raise FalloConexion("TARJETA_EXPANSOR_FUERA_DE_LINEA",
                                f"Módulo de expansión sin respuesta (0x7587={codigo}, "
                                f"máscara 0x{mascara:08X}).", "expansor")
        if codigo != 0 or negociacion != 0:
            logger.warning("ModbusLink: diagnóstico crudo 0x7587=%d 0x758A=%d", codigo,
                           negociacion)
            raise FalloConexion("TARJETA_MODULOS_ORDEN",
                                f"Orden de módulos incorrecto o negociación pendiente "
                                f"(0x7587={codigo}, 0x758A={negociacion}). Sin energía, "
                                f"revisar el orden de los módulos y negociar (doble "
                                f"pulsación de Reload).", "orden")

        # 2b. Modelos. ADB-01: el esclavo ID 0 son las E/S del principal; se
        # lee un esclavo más (ID n) y debe ser NONE.
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
                logger.warning("ModbusLink: modelo del esclavo ID %d con formato inesperado: %r",
                               i, crudos_esclavos[i])
                problemas.append(f"esclavo ID {i} ilegible")
                continue
            norm = normalizar_modelo(texto)
            if esperado is None:
                if norm != "NONE":
                    problemas.append(f"esclavo ID {i} sobrante ({texto})")
            elif norm == "NONE":
                problemas.append(f"falta el esclavo ID {i} ({esperado})")
            elif norm != esperado:
                problemas.append(f"esclavo ID {i} {texto} (se espera {esperado})")
        if problemas:
            raise FalloConexion("TARJETA_VERSION_INCOMPATIBLE",
                                "Composición de módulos distinta de la esperada: "
                                + "; ".join(problemas) + ".", "composicion")

        # 2c. Firmware (FW-INF, corrige ADB-02): solo informativo. Se lee y
        # se publica; nunca bloquea la conexión (ver cabecera).
        fw_p = self._paso_tx(fin, "firmware", self._leer_holding, REG_FW_PRINCIPAL, 1)[0]
        fw_e = self._paso_tx(fin, "firmware", self._leer_holding, REG_FW_ESCLAVOS, n)
        texto_fw = None
        try:
            texto_fw = _registros_a_texto(self._leer_holding(REG_FW_TEXTO, N_FW_TEXTO))
        except _FalloTransaccion as e:
            logger.info("ModbusLink: no se pudo leer el texto de firmware 0x0C2C (%s)", e)
        v_p = version_registro(fw_p)
        v_e = [version_registro(r) for r in fw_e]
        etiqueta_p = texto_fw or etiqueta_version(v_p)
        exp = [etiqueta_version(v) for v in v_e]
        version = f"{etiqueta_p} / " + ",".join(exp)
        # Comparación informativa (manual: principal >= cada expansión);
        # None si falta alguna versión para comparar.
        if v_p is None or any(v is None for v in v_e):
            compatible = None
        else:
            compatible = all(v <= v_p for v in v_e)
        with self.data_lock:
            self._modulos["firmware"] = {
                "principal": etiqueta_p, "registro_principal": etiqueta_version(v_p),
                "expansiones": exp, "crudo_principal": fw_p,
                "crudo_expansiones": list(fw_e), "texto_principal": texto_fw,
                "compatible": compatible}
        logger.info("ModbusLink: firmware (informativo) principal %s (0x0C1F=0x%04X, %s), "
                    "esclavos %s (0x0D80=%s)", texto_fw or "-", fw_p, etiqueta_version(v_p),
                    ",".join(exp), [f"0x{r:04X}" for r in fw_e])
        if compatible is False:
            logger.warning("ModbusLink: firmware de algún esclavo mayor que el del principal "
                           "(%s frente a %s); solo informativo: el M31 no arranca con una "
                           "combinación incompatible", ",".join(exp), etiqueta_version(v_p))

        # MAC (ADB-03: el ID del equipo es la MAC sin separadores)
        mac_regs = self._paso_tx(fin, "MAC", self._leer_holding, REG_MAC, 3)
        mac = "".join(f"{r & 0xFFFF:04X}" for r in mac_regs)
        with self.data_lock:
            self._modulos["mac"] = mac
        return {"modelo": principal, "composicion": [str(e) for e in esclavos[:n]],
                "n_modulos": n, "firmware": version, "mac": mac}

    # ---------------------------------------------------------------------
    # Pasos de la conexión verificada
    # ---------------------------------------------------------------------

    def _pasos_conexion(self, fin: float) -> Dict[str, Any]:
        # 2. Identidad (2a-2c y MAC)
        identidad = self._leer_identidad(fin)

        # 3. Configuración de seguridad (MOD-07); ADB-04 si hubo que escribir
        # en este intento o en uno anterior sin reinicio verificado (V20-s1-02)
        if self._reinicios_sin_verificar >= self.MAX_REINICIOS_SIN_VERIFICAR:
            # V20-s1-03: no se vuelve a escribir ni a reiniciar
            raise FalloConexion(
                "TARJETA_CONFIG_SEGURIDAD",
                f"Se ordenó reiniciar el módulo {self._reinicios_sin_verificar} veces sin que "
                f"la configuración de seguridad quedara verificada; no se vuelve a escribir ni "
                f"a reiniciar. Revisar el módulo y reiniciar el equipo.", "config")
        if not self._reinicio_es_permitido():
            # V20-rr-05: sin permiso de reinicio (CICLO) no se escribe nada en
            # el módulo: se comprueba en solo lectura; si difiere o hay un
            # reinicio pendiente, la conexión falla (diferido) sin escribir.
            motivo_diferido = ("Configuración de seguridad sin activar; escritura y reinicio "
                               "del módulo diferidos hasta salir del ciclo.")
            if self._reinicio_pendiente:
                raise FalloConexion("TARJETA_CONFIG_SEGURIDAD", motivo_diferido, "config")
            try:
                self._verificar_configuracion(fin)
            except FalloConexion as e:
                if e.alarma != "TARJETA_CONFIG_SEGURIDAD":
                    raise
                raise FalloConexion("TARJETA_CONFIG_SEGURIDAD",
                                    f"{motivo_diferido} ({e.motivo})", "config") from None
            escrito = False
        else:
            escrito = self._escribir_configuracion(fin)
        if escrito or self._reinicio_pendiente:
            if not escrito:
                logger.warning("ModbusLink: configuración escrita en un intento anterior sin "
                               "reinicio verificado del módulo; se reinicia (V20-s1-02)")
            fin = self._reiniciar_modulo(fin)
            identidad = self._leer_identidad(fin)
            self._verificar_configuracion(fin)
            self._reinicio_pendiente = False
            self._reinicios_sin_verificar = 0

        # 4. Apagar todo y confirmar. Bajo _cmd_lock (V19-s1-05): ningún
        # set_output se intercala entre el apagado y su confirmación.
        with self._cmd_lock:
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
            raise FalloConexion("TARJETA_SALIDAS_NO_APAGADAS",
                                f"Salidas encendidas tras el apagado: DO{', DO'.join(encendidas)}.")

        # 5. Identificación; al_conectar
        tarjeta = {"version": identidad["firmware"], "protocolo": "modbus-tcp",
                   "id": identidad["mac"]}
        with self.data_lock:
            self._tarjeta = dict(tarjeta)
        if self.al_conectar is not None:
            try:
                self.al_conectar(dict(tarjeta))
            except Exception as e:
                logger.warning("ModbusLink: error en al_conectar: %s", e)

        # 6. 0x0C37: solo se lee y se registra (ADB-05)
        crudo_0c37 = self._paso_tx(fin, "registro 0x0C37", self._leer_holding, REG_0C37, 1)[0]
        self._registrar_0c37(crudo_0c37, en_conexion=True)

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
            ("modo de falla por desconexión", REG_MODO_FALLA, [MODO_FALLA_ACTIVO]),
            ("rango de las AI", REG_RANGO_AI, [1] * 16),
            ("filtro de las AI", REG_FILTRO_AI, [c.filtro_ai]),
            ("unidad de las PT100", REG_PT_UNIDAD, [0] * 6),
            ("compensación de las PT100", REG_PT_COMPENSACION, [0] * 6),
            ("filtro de las PT100", REG_PT_FILTRO, [c.filtro_pt100] * 6),
            ("PT100 deshabilitadas", REG_PT_DESHABILITADA, [0] * 6),
        ]

    def _escribir_configuracion(self, fin: float) -> bool:
        """MOD-07 con ADB-04 (decisión 8 de la tanda 20): cada bloque se lee
        antes (03); si difiere, se escribe con 10, se relee y se compara
        exacto, hasta intentos_escritura_config veces. Devuelve True si se
        escribió algún bloque (la conexión reinicia entonces el módulo)."""
        escrito = False
        for nombre, direccion, valores in self._bloques_configuracion():
            leidos = self._paso_tx(fin, f"configuración: {nombre}", self._leer_holding,
                                   direccion, len(valores))
            if leidos == valores:
                continue
            logger.info("ModbusLink: configuración de seguridad distinta (%s, 0x%04X): se "
                        "escribe", nombre, direccion)
            escrito = True
            # V20-s1-02: antes de la primera escritura; solo se borra tras un
            # reinicio con evidencia y una relectura correcta
            self._reinicio_pendiente = True
            for _ in range(self.config.intentos_escritura_config):
                self._paso_tx(fin, f"configuración: {nombre}", self._tx,
                              "write_registers", direccion, list(valores))
                leidos = self._paso_tx(fin, f"configuración: {nombre}", self._leer_holding,
                                       direccion, len(valores))
                if leidos == valores:
                    break
            else:
                raise FalloConexion(
                    "TARJETA_CONFIG_SEGURIDAD",
                    f"No quedó verificada la configuración de seguridad ({nombre}, "
                    f"0x{direccion:04X}): se escribió {valores[:4]}{'…' if len(valores) > 4 else ''}"
                    f" y se leyó {(leidos or [])[:4]}.", "config")
        return escrito

    def _verificar_configuracion(self, fin: float) -> None:
        """ADB-04: tras el reinicio, relee toda la configuración SIN escribir;
        cualquier diferencia es TARJETA_CONFIG_SEGURIDAD."""
        for nombre, direccion, valores in self._bloques_configuracion():
            leidos = self._paso_tx(fin, f"configuración tras el reinicio: {nombre}",
                                   self._leer_holding, direccion, len(valores))
            if leidos != valores:
                raise FalloConexion(
                    "TARJETA_CONFIG_SEGURIDAD",
                    f"La configuración de seguridad no quedó tras el reinicio del módulo "
                    f"({nombre}, 0x{direccion:04X}): se espera "
                    f"{valores[:4]}{'…' if len(valores) > 4 else ''} y se leyó {leidos[:4]}.",
                    "config")

    def _reinicio_es_permitido(self) -> bool:
        fn = self.reinicio_permitido
        if fn is None:
            return True
        try:
            return bool(fn())
        except Exception as e:      # falla cerrada
            logger.warning("ModbusLink: error al consultar el permiso de reinicio (%s); no se "
                           "reinicia", e)
            return False

    def _orden_reinicio(self) -> str:
        """V20-s1-01: escribe 0x0C1D = 0x5BB5 (fc06) bajo _cliente_lock.
        Devuelve "aceptada", "rechazada" (respuesta de excepción Modbus),
        "no_enviada" (sin cliente conectado o error local al enviar, V20-rr-01)
        o "sin_respuesta" (timeout o cierre tras el envío: se toleran)."""
        with self._cliente_lock:
            cliente = self._cliente
            self._cliente_orden_reinicio = cliente
            if cliente is None or not getattr(cliente, "connected", True):
                return "no_enviada"
            try:
                resp = cliente.write_register(REG_REINICIO, CLAVE_REINICIO,
                                              device_id=self.config.unit_id)
            except OSError as e:
                # error local del envío: la orden no llegó al módulo
                logger.warning("ModbusLink: la orden de reinicio no se pudo enviar (%s: %s)",
                               type(e).__name__, e)
                return "no_enviada"
            except Exception as e:
                logger.info("ModbusLink: la orden de reinicio no tuvo respuesta (%s: %s)",
                            type(e).__name__, e)
                return "sin_respuesta"
        if _ExceptionResponse is not None and isinstance(resp, _ExceptionResponse):
            logger.warning("ModbusLink: el módulo rechazó la orden de reinicio: %r", resp)
            return "rechazada"
        if resp is None or resp.isError():
            return "sin_respuesta"
        return "aceptada"

    def _sondeo_reinicio(self) -> str:
        """V20-s1-01: lectura ligera (fc03, 1 registro) tras la orden de
        reinicio. "responde" (también con respuesta de excepción: el módulo
        está vivo), "cerrado" (el par cerró la conexión) o "sin_respuesta"."""
        with self._cliente_lock:
            cliente = self._cliente
            if cliente is None or cliente is not self._cliente_orden_reinicio:
                # V20-rr-01: el socket lo cerró otro hilo de este proceso (p. ej.
                # all_off con un fallo): no es evidencia de reinicio.
                return "ajeno"
            if not cliente.connected:
                return "cerrado"
            try:
                resp = cliente.read_holding_registers(REG_CODIGO_ERROR, count=1,
                                                      device_id=self.config.unit_id)
            except (OSError, _ConnectionException):
                return "cerrado"
            except Exception:
                return "cerrado" if not cliente.connected else "sin_respuesta"
        if _ExceptionResponse is not None and isinstance(resp, _ExceptionResponse):
            return "responde"
        if resp is None or resp.isError():
            return "sin_respuesta"
        return "responde"

    def _reiniciar_modulo(self, fin: float) -> float:
        """ADB-04 (decisión 8) con las correcciones r1 (V20-s1-01, -03, -04,
        -05; DECISIONES SIN CONFIRMAR hasta M-5b):
          1. sin reinicio_permitido() (en CICLO) no se reinicia y la conexión
             falla con TARJETA_CONFIG_SEGURIDAD (_reinicio_pendiente sigue);
          2. 0F forzado y lectura de las 32 bobinas (fc01): si alguna sigue en
             ON o la lectura falla, TARJETA_SALIDAS_NO_APAGADAS sin reiniciar;
          3. orden 0x0C1D = 0x5BB5: una respuesta de excepción es
             TARJETA_CONFIG_SEGURIDAD; timeout o cierre se toleran;
          4. evidencia del reinicio: lecturas ligeras durante
             max(espera_reinicio_s, VENTANA_MIN_EVIDENCIA_REINICIO_S); el par
             cierra la conexión o deja de responder _SIN_RESPUESTA_EVIDENCIA
             veces seguidas. Si sigue respondiendo todo ese tiempo:
             TARJETA_CONFIG_SEGURIDAD «el módulo no se reinició»;
          5. desconexión, resto de espera_reinicio_s (interrumpible por
             stop()) y reapertura del socket hasta presupuesto_reinicio_s.
        Devuelve el nuevo fin del intento. Solo corre dentro de la conexión
        verificada, con _handshake_ok en False (set_output rechazado)."""
        if not self._reinicio_es_permitido():
            logger.warning("ModbusLink: configuración de seguridad escrita; reinicio del módulo "
                           "diferido hasta salir del ciclo (V20-s1-04)")
            raise FalloConexion(
                "TARJETA_CONFIG_SEGURIDAD",
                "Configuración de seguridad escrita; reinicio del módulo diferido hasta salir "
                "del ciclo.", "config")

        logger.warning("ModbusLink: se escribió la configuración de seguridad; se apagan "
                       "todas las salidas (0F) y se reinicia el módulo para activarla "
                       "(ADB-04)")
        self._apagar_tras_fallo_conexion()
        try:
            leidas = list(self._tx("read_coils", DIR_DO, count=N_DO, forzar=True).bits)[:N_DO]
        except (_FalloTransaccion, _TraficoSuspendido) as e:
            raise FalloConexion(
                "TARJETA_SALIDAS_NO_APAGADAS",
                f"No se pudo confirmar el apagado de las salidas antes del reinicio del módulo "
                f"({e}); no se reinicia.") from None
        with self.data_lock:
            self.data["do"] = [1 if b else 0 for b in leidas] + [0] * (N_DO - len(leidas))
        if len(leidas) != N_DO or any(leidas):
            encendidas = [str(i + 1) for i, b in enumerate(leidas) if b]
            detalle = ("DO" + ", DO".join(encendidas)) if encendidas else "lectura incompleta"
            raise FalloConexion(
                "TARJETA_SALIDAS_NO_APAGADAS",
                f"Salidas encendidas antes del reinicio del módulo: {detalle}; no se "
                f"reinicia.")

        # V20-s1-03: cuenta toda orden enviada hasta una verificación correcta
        self._reinicios_sin_verificar += 1
        t_orden = time.monotonic()
        orden = self._orden_reinicio()
        if orden == "rechazada":
            raise FalloConexion(
                "TARJETA_CONFIG_SEGURIDAD",
                "El módulo rechazó la orden de reinicio (0x0C1D); la configuración de "
                "seguridad escrita no está activa.", "config")
        if orden == "no_enviada":
            raise FalloConexion(
                "TARJETA_CONFIG_SEGURIDAD",
                "La orden de reinicio del módulo (0x0C1D) no se pudo enviar; la configuración "
                "de seguridad escrita no está activa.", "config")

        ventana = max(self.config.espera_reinicio_s, self.VENTANA_MIN_EVIDENCIA_REINICIO_S)
        fin_ventana = t_orden + ventana
        evidencia: Optional[str] = None
        sin_respuesta = 0
        while True:
            if self._parar.is_set():
                raise _Detenido()
            estado = self._sondeo_reinicio()
            if estado == "ajeno":
                raise FalloConexion(
                    "TARJETA_CONFIG_SEGURIDAD",
                    "La conexión se cerró en este equipo mientras se comprobaba el reinicio "
                    "del módulo; no hay evidencia de reinicio.", "config")
            if estado == "cerrado":
                evidencia = "el módulo cerró la conexión"
            elif estado == "sin_respuesta":
                sin_respuesta += 1
                if sin_respuesta >= self._SIN_RESPUESTA_EVIDENCIA:
                    evidencia = "el módulo dejó de responder"
            else:
                sin_respuesta = 0
            if evidencia is not None or time.monotonic() >= fin_ventana:
                break
            if self._parar.wait(self._PAUSA_SONDEO_REINICIO_S):
                raise _Detenido()
        if evidencia is None:
            raise FalloConexion(
                "TARJETA_CONFIG_SEGURIDAD",
                f"El módulo no se reinició: siguió respondiendo {ventana:.1f} s después de la "
                f"orden de reinicio (0x0C1D, orden {orden}); la configuración de seguridad "
                f"escrita no está activa.", "config")
        logger.info("ModbusLink: reinicio del módulo comprobado (%s)", evidencia)

        with self.data_lock:
            self._reinicios_modulo += 1
            self._modulos["reinicios_modulo"] = self._reinicios_modulo
        self._desconectar()
        resto = t_orden + self.config.espera_reinicio_s - time.monotonic()
        if resto > 0 and self._parar.wait(resto):
            raise _Detenido()
        plazo = time.monotonic() + self.config.presupuesto_reinicio_s
        while True:
            if self._parar.is_set():
                raise _Detenido()
            if self._abrir_socket():
                try:
                    self._leer_holding(REG_CODIGO_ERROR, 4)
                    break
                except (_FalloTransaccion, _TraficoSuspendido):
                    pass
            if time.monotonic() >= plazo:
                raise FalloConexion("TARJETA_SIN_TRAMA_VALIDA",
                                    "El módulo no volvió a responder tras el reinicio "
                                    f"({self.config.presupuesto_reinicio_s:.0f} s).",
                                    "sin_conexion")
            if self._parar.wait(min(0.5, self.config.reintento_conexion_s)):
                raise _Detenido()
        # V20-s1-05: stop() entre la reapertura y la vuelta
        if self._parar.is_set():
            raise _Detenido()
        logger.info("ModbusLink: el módulo volvió tras el reinicio; se relee la identidad y "
                    "la configuración")
        return max(fin, plazo)

    # ---------------------------------------------------------------------
    # Contraseña web del módulo (T20-04)
    # ---------------------------------------------------------------------

    def escribir_credenciales_web(self, usuario: str, clave: str) -> bool:
        """T20-04: escribe usuario (0x758B, 5 registros) y contraseña (0x7590,
        3 registros) con la función 10 por el cliente de este enlace (bajo su
        candado) y los relee para comparar. True si ambos coinciden. Exige el
        socket abierto (leer_identidad(cerrar=False)). La contraseña nunca va
        al log ni a excepciones. RuntimeError con el hilo de sondeo en marcha
        (V20-s1-08)."""
        if self.running:
            raise RuntimeError("escribir_credenciales_web() no se usa con el hilo de sondeo "
                               "en marcha")
        regs_u = texto_a_registros(usuario, N_WEB_USUARIO)
        regs_c = texto_a_registros(clave, N_WEB_CLAVE)
        try:
            self._tx("write_registers", REG_WEB_USUARIO, regs_u)
            self._tx("write_registers", REG_WEB_CLAVE, regs_c)
            ok_u = self._leer_holding(REG_WEB_USUARIO, N_WEB_USUARIO) == regs_u
            ok_c = self._leer_holding(REG_WEB_CLAVE, N_WEB_CLAVE) == regs_c
        except (_FalloTransaccion, _TraficoSuspendido):
            logger.warning("ModbusLink: sin respuesta al escribir o releer las credenciales web")
            return False
        if not (ok_u and ok_c):
            logger.warning("ModbusLink: credenciales web releídas distintas (usuario %s, "
                           "contraseña %s)", "igual" if ok_u else "distinto",
                           "igual" if ok_c else "distinta")
        return ok_u and ok_c

    # ---------------------------------------------------------------------
    # Salidas (MOD-11)
    # ---------------------------------------------------------------------

    def _registrar_comando(self, channel: int, estado: bool, ahora: float) -> None:
        """Bajo data_lock. La tolerancia de 1 s cuenta desde
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
            # V19-s1-05: la conexión pudo invalidarse (y su paso 4 correr)
            # mientras se esperaba el candado.
            if not self._handshake_ok:
                return False
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
        """Algoritmo de discrepancia de MOD-11 (heredado del enlace serial retirado en la tanda 20)."""
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
