"""
autoclave.core.units
---------------------
Representa el estado físico del autoclave.
Mantiene los valores crudos y convertidos, delegando la conversión
al módulo `converters.py` con soporte de calibración y suavizado.
"""

from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from autoclave.hal.measures import converters
from autoclave.config import load_config
from autoclave.config.schema import AppConfig
import logging

logger=logging.getLogger(__name__)


class Units:
    # D8-3.19 (revisión final SEN-01 de E1): tramas AI NUEVAS seguidas (ai_seq
    # de SerialLink; las líneas DI/DO/ST notifican con la misma AI y no
    # cuentan) con la cuenta ADC cruda de presión sobre adc_min antes de dar la
    # señal por presente. Igual a la profundidad de la mediana de presión
    # (converters._ma_pres): tras un lazo abierto la lectura filtrada no
    # refleja la presión real hasta que la mediana se llena de muestras con
    # señal. Con el firmware actual (AI cada 500 ms) son unos 2,5 s.
    TRAMAS_SENAL_PRESION = 5

    def __init__(self , config_path: Optional[str | Path] = None):
        """
        Inicializa el objeto Units.
        :param config_path: Ruta opcional al archivo YAML de configuración.
        """
        self._lock = threading.Lock()

        # 🔧 Cargar configuración (con calibraciones)
        if config_path:
            self._config: AppConfig = load_config(config_path)

        else: 
            self._config = AppConfig()  # configuración por defecto

        #logger(f"CONFIG CARGADA:, {self._config}")

        # aqui se inicializan los datos crudos
        self._raw_ai: List[int] = [0] * 16
        self._raw_di: List[int] = [0] * 56
        self._raw_do: List[int] = [0] * 32

        # aqui se inicializan los datos convertidos
        self._temperature: List[Optional[float]] = [None] * 8
        # S1 (tanda 8): sin lectura hasta la primera trama (None, nunca 0)
        self._pressure: List[Optional[float]] = [None] * 8
        # Número de la última trama AI convertida (ai_seq de SerialLink)
        self._ultimo_ai_seq = None
        # D8-3.19: tramas seguidas con señal cruda por canal de presión
        self._tramas_senal_pres: List[int] = [0] * 8
        # SAF-01/TMG-02 (re-revisión): instante monotónico en que cada canal
        # cumplió TRAMAS_SENAL_PRESION (None mientras no las cumple)
        self._senal_desde_mono: List[Optional[float]] = [None] * 8
        # ai_seq de la última trama AI contada (mismo criterio que S1)
        self._ultimo_ai_seq_senal = None

        # otros estados
        self._connected: bool = False
        self._last_update: Optional[datetime] = None

    # -------------------------------------------------------------------------
    # Actualización desde serial_link
    # -------------------------------------------------------------------------

    def update_from_serial(self, data: Dict[str, Any]):
        """
        Recibe los datos crudos del módulo serial_link y actualiza el estado interno.
        """
        with self._lock:
            self._raw_ai = data.get("ai", self._raw_ai)
            self._raw_di = data.get("di", self._raw_di)
            self._raw_do = data.get("do", self._raw_do)
            # SerialLink no tiene clave "connected" — se deriva de port_open + data_alive
            self._connected = data.get("port_open", False) and data.get("data_alive", False)
            self._last_update = data.get("last_update", datetime.now())

            ai_seq = data.get("ai_seq")
            # 🧮 Aplicar conversión con calibración
            # Tanda 19 (MOD-03): ai_seq 0 es el estado inicial del enlace, nunca
            # una trama AI real; sus valores no son lecturas. En serial son
            # ceros, que ya daban None por el centinela del ADC; con Modbus un
            # 0 sería 0,0 °C válido, así que se convierte como "sin valor".
            crudas_temp = self._raw_ai if ai_seq != 0 else [None] * 16
            self._temperature = converters.convert_temperatures(crudas_temp, self._config)
            # S1 (D8-1.1): el debounce del transductor cuenta tramas AI
            # nuevas; SerialLink también notifica por DI/DO con la misma AI.
            # Sin ai_seq (dobles de prueba, simulador) cada llamada cuenta.
            # TMG-02 (revisión ★): _notificar() llega desde varios hilos con
            # un get_state() tomado antes; una trama vieja o repetida
            # (ai_seq <= la última) no es muestra nueva. Un salto grande hacia
            # atrás es un contador reiniciado (otro SerialLink con la misma
            # Units): cuenta como nueva para no congelar la presión.
            # TMG-02 (re-revisión): ai_seq 0 es el estado inicial de
            # SerialLink (ai en ceros), nunca una trama AI real.
            nueva = (ai_seq != 0 and (ai_seq is None or self._ultimo_ai_seq is None
                     or ai_seq > self._ultimo_ai_seq
                     or ai_seq < self._ultimo_ai_seq - 100))
            if nueva and ai_seq is not None:
                self._ultimo_ai_seq = ai_seq
            self._pressure = converters.convert_pressures(self._raw_ai, self._config,
                                                          nueva_muestra=nueva)
            self._contar_senal_presion(data)

    def reload_calibration(self, config_path: str | Path) -> None:
        """Recarga factory+user calibration desde disco sin recrear Units
        ni tocar la conexion serial (SerialLink vive fuera de este objeto).
        Seguro de llamar mientras update_from_serial corre en otro hilo."""
        new_config = load_config(config_path)
        with self._lock:
            self._config = new_config
            # SEN-02 (re-revisión E1): el contador se acumuló con el adc_min
            # anterior; se vuelve a exigir TRAMAS_SENAL_PRESION con el nuevo
            self._reiniciar_senal_presion()

    # -------------------------------------------------------------------------
    # API pública
    # -------------------------------------------------------------------------

    def get_all(self) -> Dict[str, Any]:
        """Devuelve una copia completa del estado físico actual."""
        with self._lock:
            return {
                "temperature": self._temperature.copy(), # Lista de temperaturas en °C, se utiliza copy() para evitar modificaciones externas
                "pressure": self._pressure.copy(),
                "raw_ai": self._raw_ai.copy(),
                "raw_di": self._raw_di.copy(),
                "raw_do": self._raw_do.copy(),
                "connected": self._connected,
                "last_update": self._last_update, # Fecha y hora de la última actualización
            }

    def get_temperature(self, index: int) -> Optional[float]:
        with self._lock:
            return self._temperature[index]

    def get_pressure(self, index: int) -> Optional[float]:
        with self._lock:
            return self._pressure[index]

    def _piso_adc_presion(self, i: int):
        """Piso de señal presente del canal: `adc_piso_senal` de fábrica si
        está (tanda 19, MOD-04), si no `adc_min`; sin ninguno, 0."""
        factory = self._config.calibration.factory.pressure
        calib = factory[i] if i < len(factory) else None
        for campo in ("adc_piso_senal", "adc_min"):
            valor = getattr(calib, campo, None)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                return valor
        return 0

    def _reiniciar_senal_presion(self) -> None:
        """Con el lock tomado: ningún canal tiene señal confirmada."""
        self._tramas_senal_pres = [0] * 8
        self._senal_desde_mono = [None] * 8

    def _contar_senal_presion(self, data: Dict[str, Any]) -> None:
        """Con el lock tomado: una trama AI nueva más por canal.

        SEN-01 (re-revisión E1): SerialLink notifica por cada línea válida
        (AI, DI, DO, ST, ACK) con la misma AI; solo cuenta una trama cuyo
        `ai_seq` sea nuevo (mismo criterio que S1 para la mediana: 0 es el
        estado inicial, nunca una trama real; un salto grande hacia atrás es
        un contador reiniciado). Sin `ai_seq` (dobles de prueba, simulador)
        cada llamada cuenta. Una desconexión explícita (`port_open` False)
        reinicia los contadores (falla cerrada)."""
        if data.get("port_open", True) is False:
            self._reiniciar_senal_presion()
            return
        ai_seq = data.get("ai_seq")
        if ai_seq == 0:
            self._reiniciar_senal_presion()
            return
        if ai_seq is not None:
            ultimo = self._ultimo_ai_seq_senal
            if not (ultimo is None or ai_seq > ultimo or ai_seq < ultimo - 100):
                return                      # misma trama AI: no es muestra nueva
            self._ultimo_ai_seq_senal = ai_seq
        ahora = time.monotonic()
        for i in range(8):
            try:
                raw = self._raw_ai[8 + i] if 8 + i < len(self._raw_ai) else None
                ok = (isinstance(raw, (int, float)) and not isinstance(raw, bool)
                      and raw > max(self._piso_adc_presion(i), 0))
            except Exception:
                ok = False
            self._tramas_senal_pres[i] = self._tramas_senal_pres[i] + 1 if ok else 0
            if not ok:
                self._senal_desde_mono[i] = None
            elif self._tramas_senal_pres[i] == self.TRAMAS_SENAL_PRESION:
                self._senal_desde_mono[i] = ahora

    def senal_presion_presente(self, index: int, leido_mono=None) -> bool:
        """D8-3.19 (tanda 8, revisión SEN-01/SEN-03 de E1): True solo si la
        cuenta ADC CRUDA del canal de presión `index` (la de la última trama,
        antes de la mediana, la calibración, el filtro y el recorte a 0)
        está por encima del `adc_piso_senal` de fábrica del canal (tanda 19,
        MOD-04; si no está, `adc_min`; sin calibración de fábrica: por
        encima de 0) y que lo esté desde hace al menos
        TRAMAS_SENAL_PRESION actualizaciones seguidas. En el fondo del rango un lazo abierto
        no se distingue de un vacío absoluto: cuenta como "sin señal".
        `leido_mono` (SAF-01/TMG-02 de la re-revisión): instante monotónico,
        tomado ANTES de leer Units, de la presión que se va a evaluar; si se
        da, además se exige que sea posterior al instante en que la señal
        cumplió las tramas seguidas (la presión publicada ya refleja la
        mediana llena). Los dos llamadores de la compuerta lo pasan.
        Falla cerrada: índice o datos inválidos dan False. No sustituye la
        detección NAMUR de D8-1 (rama S1), que va en el convertidor."""
        try:
            i = int(index)
            if isinstance(index, bool) or not 0 <= i < 8:
                return False
            with self._lock:
                raw_ai = list(self._raw_ai)
                piso = self._piso_adc_presion(i)
                seguidas = self._tramas_senal_pres[i]
                desde = self._senal_desde_mono[i]
            raw = raw_ai[8 + i] if 8 + i < len(raw_ai) else None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return False
            # SEN-01 final: además, TRAMAS_SENAL_PRESION actualizaciones seguidas
            if not (raw > max(piso, 0) and seguidas >= self.TRAMAS_SENAL_PRESION):
                return False
            if leido_mono is None:
                return True
            if (isinstance(leido_mono, bool) or not isinstance(leido_mono, (int, float))
                    or desde is None):
                return False
            return leido_mono >= desde
        except Exception:
            logger.exception("No se pudo evaluar la señal cruda del canal de presión %s", index)
            return False

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def get_last_update(self) -> Optional[datetime]:
        with self._lock:
            return self._last_update
