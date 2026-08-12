# autoclave.core.converters.py

import math
import time
from typing import List, Dict, Optional
from autoclave.config.schema import CalibrationConfig
from collections import deque
import statistics

class MovingAverage:
    def __init__(self, size: int = 5):
        self.size = size
        self.buffer = deque(maxlen=size)

    def update(self, value: float) -> float:
        self.buffer.append(value)
        mov= round((sum(self.buffer) / len(self.buffer)),2)
        return mov

class MedianFilter:
    def __init__(self, size: int = 5):
        self.size = size
        self.buffer = deque(maxlen=size)

    def update(self, value: float) -> float:
        self.buffer.append(value)
        return round(statistics.median(self.buffer), 2)

class OneEuroFilter:
    """Casiez et al. 2012. Suaviza fuerte cuando la señal está estática (ruido de
    fondo) y responde rápido cuando la derivada estimada indica un cambio real."""

    def __init__(self, mincutoff: float, beta: float, dcutoff: float = 1.0):
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self.x_prev: Optional[float] = None
        self.dx_prev: float = 0.0
        self.t_prev: Optional[float] = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def update(self, value: float, timestamp: float) -> float:
        if self.t_prev is None:
            self.x_prev = value
            self.t_prev = timestamp
            return value

        dt = max(timestamp - self.t_prev, 1e-3)  # piso: evita división por dt≈0

        dx = (value - self.x_prev) / dt
        a_d = self._alpha(self.dcutoff, dt)
        edx = a_d * dx + (1 - a_d) * self.dx_prev

        cutoff = self.mincutoff + self.beta * abs(edx)
        a = self._alpha(cutoff, dt)
        x_hat = a * value + (1 - a) * self.x_prev

        self.x_prev, self.dx_prev, self.t_prev = x_hat, edx, timestamp
        return x_hat

    def reset(self) -> None:
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

# ==============================
# Estado interno de filtros
# ==============================
# Pipeline: raw → MedianFilter(pre-filtro) → calibrar → OneEuroFilter(suavizado adaptativo)

_ma_temp: List[MedianFilter] = [MedianFilter(5) for _ in range(8)]   # pre-filtro ligero
_ma_pres: List[MedianFilter] = [MedianFilter(5) for _ in range(8)]   # pre-filtro ligero

# mincutoff: suavizado en reposo (más bajo = más suave). beta: qué tan rápido se
# relaja el suavizado cuando la derivada estimada indica un cambio real.
# TEMP_BETA subido de 0.02 a 0.06 (feedback de campo: la temperatura se sentía
# lenta para reaccionar). Barrido con datos sintéticos (rampa 2-8°C/min, DT=0.5s
# como el control loop real): reduce el lag de rampa en régimen establecido de
# ~2.4s a ~1.7s, mientras el ruido residual durante la rampa se mantiene bajo
# (<0.1°C) y el rechazo de ruido en reposo baja de ~67% a ~52% (std filtrada /
# std cruda pasa de 0.33 a 0.48) — sigue muy por debajo del EMA que reemplazó.
# TEMP_MINCUTOFF sin tocar: controla el suavizado en reposo y no fue lo reportado
# como lento.
TEMP_MINCUTOFF = 0.05
TEMP_BETA = 0.06
# PRES_MINCUTOFF bajado de 0.1 a 0.03, y luego a 0.01 (feedback de campo:
# incluso en 0.03 seguía saltando ~7-8kPa en esterilización, con presión
# sostenida y estable — es decir, en reposo real, no un cambio genuino).
# PRES_BETA se deja igual: controla la respuesta ante cambios reales
# (purga, vacío) y no fue reportado como problema.
PRES_MINCUTOFF = 0.01
PRES_BETA = 0.05
DCUTOFF = 1.0

_oe_temp: List[OneEuroFilter] = [
    OneEuroFilter(TEMP_MINCUTOFF, TEMP_BETA, DCUTOFF) for _ in range(8)
]
_oe_pres: List[OneEuroFilter] = [
    OneEuroFilter(PRES_MINCUTOFF, PRES_BETA, DCUTOFF) for _ in range(8)
]


# ==============================
# CALIBRACIÓN DE FÁBRICA
# ==============================
def _factory_calibrate(raw_value: int, calib, full_scale: float, is_pressure=False) -> float:

    if calib:
        adc_min = getattr(calib, "adc_min", None)
        adc_max = getattr(calib, "adc_max", None)

        if is_pressure:
            val_min = getattr(calib, "pres_min", None)
            val_max = getattr(calib, "pres_max", None)
        else:
            val_min = getattr(calib, "temp_min", None)
            val_max = getattr(calib, "temp_max", None)

        if None not in (adc_min, adc_max, val_min, val_max):
            if adc_max != adc_min:
                value = (raw_value - adc_min) * (val_max - val_min) / (adc_max - adc_min) + val_min
                gain   = getattr(calib, "gain",   1.0)
                offset = getattr(calib, "offset", 0.0)
                return value * gain + offset

    return (raw_value / 4095.0) * full_scale


# ==============================
# CALIBRACIÓN DE USUARIO
# ==============================

def _user_calibrate(value: float, calib) -> float:
    if calib:
        poly = getattr(calib, "poly", None)
        if poly and len(poly) >= 2:
            result = 0.0
            for coeff in poly:
                result = result * value + coeff
            return result
        gain = getattr(calib, "gain", 1.0)
        offset = getattr(calib, "offset", 0.0)
        return value * gain + offset
    return value


# ==============================
# TEMPERATURA
# ==============================

def convert_temperatures(raw_ai: List[int], config: Dict | CalibrationConfig) -> List[Optional[float]]:

    if isinstance(config, dict):
        factory_list = config.get("calibration", {}).get("factory", {}).get("temperature", [])
        user_list = config.get("calibration", {}).get("user", {}).get("temperature", [])
    else:
        factory_list = config.calibration.factory.temperature
        user_list = config.calibration.user.temperature

    timestamp = time.monotonic()
    temps = []

    for i in range(8):
        raw = raw_ai[i] if i < len(raw_ai) else 0

        # Sensor desconectado: ADC en 0 (cable a GND) o 4095 (cable al aire/VCC)
        if raw == 0 or raw >= 4095:
            _ma_temp[i].buffer.clear()
            _oe_temp[i].reset()
            temps.append(None)
            continue

        # 1. Pre-filtro: mediana ligera sobre valores crudos (rechaza picos del ADC)
        smoothed_raw = _ma_temp[i].update(raw)

        factory_calib = factory_list[i] if i < len(factory_list) else None
        user_calib    = user_list[i]    if i < len(user_list)    else None

        # 2. Calibración → valor en °C
        value = _factory_calibrate(smoothed_raw, factory_calib, 200.0)
        value = _user_calibrate(value, user_calib)

        # 3. Suavizado adaptativo: fuerte en reposo, rápido ante cambios reales
        value = _oe_temp[i].update(value, timestamp)

        temps.append(round(value, 1))

    return temps


# ==============================
# PRESIÓN
# ==============================

def convert_pressures(raw_ai: List[int], config: Dict | CalibrationConfig) -> List[float]:

    if isinstance(config, dict):
        factory_list = config.get("calibration", {}).get("factory", {}).get("pressure", [])
        user_list = config.get("calibration", {}).get("user", {}).get("pressure", [])
    else:
        factory_list = config.calibration.factory.pressure
        user_list = config.calibration.user.pressure

    timestamp = time.monotonic()
    press = []

    for i in range(8):
        raw_index = 8 + i
        raw = raw_ai[raw_index] if raw_index < len(raw_ai) else 0

        # 1. Pre-filtro: mediana ligera sobre valores crudos
        smoothed_raw = _ma_pres[i].update(raw)

        factory_calib = factory_list[i] if i < len(factory_list) else None
        user_calib    = user_list[i]    if i < len(user_list)    else None

        # 2. Calibración → valor en kPa
        value = _factory_calibrate(smoothed_raw, factory_calib, 400.0, is_pressure=True)
        value = _user_calibrate(value, user_calib)

        # 3. Suavizado adaptativo: fuerte en reposo, rápido ante cambios reales
        value = _oe_pres[i].update(value, timestamp)

        # 4. Clamp: la presión nunca es negativa
        value = max(0.0, value)

        press.append(round(value, 1))

    return press