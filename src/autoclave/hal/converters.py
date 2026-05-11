# autoclave.core.converters.py

from typing import List, Dict
from src.autoclave.config.schema import CalibrationConfig
from collections import deque

class MovingAverage:
    def __init__(self, size: int = 5):
        self.size = size
        self.buffer = deque(maxlen=size)

    def update(self, value: float) -> float:
        self.buffer.append(value)
        mov= round((sum(self.buffer) / len(self.buffer)),2)
        return mov
# ==============================
# Estado interno (EMA)
# ==============================
_ma_temp: List[MovingAverage] = [MovingAverage(10) for _ in range(8)]
_c_temp: List[MovingAverage] = [MovingAverage(10) for _ in range(8)]
_ma_pres: List[MovingAverage] = [MovingAverage(10) for _ in range(8)]
_c_pres: List[MovingAverage] = [MovingAverage(10) for _ in range(8)]

_prev_temp_values: List[float] = [0.0] * 8
_prev_pres_values: List[float] = [0.0] * 8

TEMP_ALPHA = 0.3
PRES_ALPHA = 0.3


# ==============================
# EMA FILTER
# ==============================

def _ema(previous: float, new_value: float, alpha: float) -> float:
    ema = round((alpha * new_value + (1 - alpha) * previous),2)

    return ema


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
                return (raw_value - adc_min) * (val_max - val_min) / (adc_max - adc_min) + val_min

    return (raw_value / 4095.0) * full_scale


# ==============================
# CALIBRACIÓN DE USUARIO
# ==============================

def _user_calibrate(value: float, calib) -> float:
    """
    Aplica calibración de usuario (gain/offset).
    """

    if calib:
        gain = getattr(calib, "gain", 1.0)
        offset = getattr(calib, "offset", 0.0)
        #print(f"gain: {gain}, offset: {offset}")

        calib_user = value * gain + offset

        return calib_user

    return value


# ==============================
# TEMPERATURA
# ==============================

def convert_temperatures(raw_ai: List[int], config: Dict | CalibrationConfig) -> List[float]:

    if isinstance(config, dict):
        factory_list = config.get("calibration", {}).get("factory", {}).get("temperature", [])
        user_list = config.get("calibration", {}).get("user", {}).get("temperature", [])
    else:
        factory_list = config.calibration.factory.temperature
        user_list = config.calibration.user.temperature

    global _prev_temp_values

    temps = []

    for i in range(8):
        raw = raw_ai[i] if i < len(raw_ai) else 0
        average =_ma_temp[i].update(raw)
        factory_calib = factory_list[i] if i < len(factory_list) else None
        user_calib = user_list[i] if i < len(user_list) else None

        # 1. Factory
        value = _factory_calibrate(average, factory_calib, 200.0)

        # 2. User
        value = _user_calibrate(value, user_calib)

        # 3. EMA (suavizado final)
        value = _ema(_prev_temp_values[i], value, TEMP_ALPHA)

        value = _c_temp[i].update(value)

        _prev_temp_values[i] = value
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

    global _prev_pres_values

    press = []

    for i in range(8):
        raw_index = 8 + i
        raw = raw_ai[raw_index] if raw_index < len(raw_ai) else 0
        average =_ma_pres[i].update(raw)
        factory_calib = factory_list[i] if i < len(factory_list) else None
        user_calib = user_list[i] if i < len(user_list) else None

        # 1. Factory
        value = _factory_calibrate(average, factory_calib, 400.0, is_pressure=True)
        #print(f"fabrica {value}")

        # 2. User
        value = _user_calibrate(value, user_calib)
        #print(f"usuario {value}")

        # 3. EMA final
        value = _ema(_prev_pres_values[i], value, PRES_ALPHA)

        value = _c_pres[i].update(value)

        if value <= 0:
            value = 0
        
        _prev_pres_values[i] = value
        press.append(round(value, 1))

    return press