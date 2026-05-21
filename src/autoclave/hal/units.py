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

from autoclave.hal import converters
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
        self._temperature: List[float] = [0.0] * 8
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

    def get_temperature(self, index: int) -> float:
        with self._lock:
            return self._temperature[index]

    def get_pressure(self, index: int) -> float:
        with self._lock:
            return self._pressure[index]

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def get_last_update(self) -> Optional[datetime]:
        with self._lock:
            return self._last_update
