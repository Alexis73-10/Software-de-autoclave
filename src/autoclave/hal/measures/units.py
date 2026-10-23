"""
autoclave.core.units
---------------------
Representa el estado físico del autoclave.
Mantiene los valores crudos y convertidos, delegando la conversión
al módulo `converters.py` con soporte de calibración y suavizado.
"""

from __future__ import annotations
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from autoclave.hal.measures import converters
from autoclave.config import load_config
from autoclave.config.schema import AppConfig
import logging

logger=logging.getLogger(__name__)


class Units:
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
        self._pressure: List[float] = [0.0] * 8

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

            # 🧮 Aplicar conversión con calibración
            self._temperature = converters.convert_temperatures(self._raw_ai, self._config)
            self._pressure = converters.convert_pressures(self._raw_ai, self._config)

    def reload_calibration(self, config_path: str | Path) -> None:
        """Recarga factory+user calibration desde disco sin recrear Units
        ni tocar la conexion serial (SerialLink vive fuera de este objeto).
        Seguro de llamar mientras update_from_serial corre en otro hilo."""
        new_config = load_config(config_path)
        with self._lock:
            self._config = new_config

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

    def get_pressure(self, index: int) -> float:
        with self._lock:
            return self._pressure[index]

    def senal_presion_presente(self, index: int) -> bool:
        """D8-3.19 (tanda 8, revisión SEN-01/SEN-03 de E1): True solo si la
        cuenta ADC CRUDA del canal de presión `index` (la de la última trama,
        antes de la mediana, la calibración, el filtro y el recorte a 0)
        está por encima del `adc_min` de fábrica del canal (sin calibración
        de fábrica: por encima de 0). En el fondo del rango un lazo abierto
        no se distingue de un vacío absoluto: cuenta como "sin señal".
        Falla cerrada: índice o datos inválidos dan False. No sustituye la
        detección NAMUR de D8-1 (rama S1), que va en el convertidor."""
        try:
            i = int(index)
            if isinstance(index, bool) or not 0 <= i < 8:
                return False
            with self._lock:
                raw_ai = list(self._raw_ai)
                factory = list(self._config.calibration.factory.pressure)
            raw = raw_ai[8 + i] if 8 + i < len(raw_ai) else None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return False
            calib = factory[i] if i < len(factory) else None
            adc_min = getattr(calib, "adc_min", None)
            piso = adc_min if isinstance(adc_min, (int, float)) and not isinstance(adc_min, bool) else 0
            return raw > max(piso, 0)
        except Exception:
            logger.exception("No se pudo evaluar la señal cruda del canal de presión %s", index)
            return False

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def get_last_update(self) -> Optional[datetime]:
        with self._lock:
            return self._last_update
