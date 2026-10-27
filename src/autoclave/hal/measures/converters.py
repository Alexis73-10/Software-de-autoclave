# autoclave.core.converters.py

import math
import time
from typing import List, Dict, Optional
from autoclave.config.schema import CalibrationConfig
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)

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
# VALOR CRUDO (tanda 19, MOD-03; enlace único Modbus desde la tanda 20, T20-03)
# ==============================
# Módulos M31-U por Modbus TCP: temperatura en décimas de °C con signo (0 =
# 0,0 °C válido; la ausencia de sonda llega como None desde el enlace, que
# convierte los códigos de diagnóstico de las PT100); presión en µA (el umbral
# alto de 21000 queda activo). Sin calibración de fábrica completa no hay
# conversión: None (falla cerrada).
# Un canal crudo None (o no numérico, bool o no finito) da None en ese canal y
# reinicia su filtro; los demás canales no se afectan. Un índice que falta en
# la lista cruda cuenta como None.


def _crudo(raw) -> Optional[float]:
    """La cuenta cruda si es un número finito; None si no (bool incluido)."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    if not math.isfinite(raw):
        return None
    return raw


def _crudo_en(raw_ai, indice: int) -> Optional[float]:
    try:
        return _crudo(raw_ai[indice]) if indice < len(raw_ai) else None
    except (TypeError, IndexError, KeyError):
        return None


# ==============================
# CALIBRACIÓN DE FÁBRICA
# ==============================
def _factory_calibrate(raw_value: int, calib, full_scale: float,
                       is_pressure=False) -> Optional[float]:
    """Valor de ingeniería con la calibración de fábrica del canal. Sin una
    calibración completa: None (tanda 19, MOD-03; desde la tanda 20, T20-03,
    sin la escala raw/4095 del ADC de la tarjeta serial retirada).
    `full_scale` se conserva en la firma por compatibilidad; no se usa."""

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

    return None


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

# V19-s2-03 (revisión R de la tanda 19): rango físico plausible de la cuenta
# cruda de temperatura del módulo M31 (entero con signo en décimas de °C).
# Fuera de [-500, 2500] décimas (-50,0 a 250,0 °C) la cuenta no es una
# medición de la PT100 (sonda abierta o en corto, registro corrupto) y el
# canal queda sin valor: None y filtros reiniciados, igual que un None.
# Límites inclusive. DECISIÓN SIN CONFIRMAR.
_DECIMAS_PT100_MIN = -500
_DECIMAS_PT100_MAX = 2500


def _decimas_pt100_plausibles(raw) -> bool:
    try:
        return _DECIMAS_PT100_MIN <= raw <= _DECIMAS_PT100_MAX
    except TypeError:
        return False


def convert_temperatures(raw_ai: List[Optional[int]], config: Dict | CalibrationConfig) -> List[Optional[float]]:

    if isinstance(config, dict):
        factory_list = config.get("calibration", {}).get("factory", {}).get("temperature", [])
        user_list = config.get("calibration", {}).get("user", {}).get("temperature", [])
    else:
        factory_list = config.calibration.factory.temperature
        user_list = config.calibration.user.temperature

    timestamp = time.monotonic()
    temps = []

    for i in range(8):
        raw = _crudo_en(raw_ai, i)

        # Sin valor crudo (tanda 19, MOD-03): sin lectura y filtro reiniciado.
        # 0 décimas es 0,0 °C válido (sin centinela), pero una cuenta fuera del
        # rango físico plausible de la PT100 (V19-s2-03) se trata igual que un
        # None.
        if raw is None or not _decimas_pt100_plausibles(raw):
            _ma_temp[i].buffer.clear()
            _oe_temp[i].reset()
            temps.append(None)
            continue

        # 1. Pre-filtro: mediana ligera sobre valores crudos (rechaza picos)
        smoothed_raw = _ma_temp[i].update(raw)

        factory_calib = factory_list[i] if i < len(factory_list) else None
        user_calib    = user_list[i]    if i < len(user_list)    else None

        # 2. Calibración → valor en °C
        value = _factory_calibrate(smoothed_raw, factory_calib, 200.0)
        if value is None:
            # sin calibración de fábrica del canal: sin lectura
            _ma_temp[i].buffer.clear()
            _oe_temp[i].reset()
            temps.append(None)
            continue
        value = _user_calibrate(value, user_calib)

        # 3. Suavizado adaptativo: fuerte en reposo, rápido ante cambios reales
        value = _oe_temp[i].update(value, timestamp)

        temps.append(round(value, 1))

    return temps


# ==============================
# PRESIÓN — transductor sin señal (S1, tanda 8, D8-1.1)
# ==============================
# Los transmisores de presión son de 4-20 mA. Un lazo abierto (o en corto) da
# cuentas fuera del rango de medida; antes se calibraba y se recortaba con
# max(0.0, v) y el ciclo lo tomaba como 0 kPa válido (SEN-01 de la tanda 7).
# Ahora se decide sobre la cuenta CRUDA, antes de filtrar, calibrar y recortar:
#   umbral bajo = adc_min - margen_falla_bajo * (adc_max - adc_min)   (3,6 mA)
#   umbral alto = adc_max + margen_falla_alto * (adc_max - adc_min)   (21 mA)
# con adc_min = 4 mA y adc_max = 20 mA de la calibración de fábrica del canal.
# - La cuenta es en µA (Modbus) y el umbral alto de 21000 queda ACTIVO (tanda
#   19, MOD-03). El tope de saturación del ADC de 12 bits de la tarjeta serial
#   (D8-1.1) se retiró con ese enlace en la tanda 20 (T20-03).
# - Umbral bajo <= 0: piso de saturación en 0 antes de 3,6 mA. DECISIÓN SIN
#   CONFIRMAR (informe S1): se usa el piso de saturación, 0 cuentas = falla
#   (mismo criterio que la temperatura, raw == 0). Sin esto la detección baja
#   quedaría inactiva con la calibración actual (adc_min 5) y el lazo abierto
#   seguiría leyéndose como 0 kPa.
# - adc_falla_bajo / adc_falla_alto (opcionales) reemplazan los calculados.
# Hacen falta DEBOUNCE_LECTURAS_PRESION lecturas seguidas fuera para declarar
# la falla y otras tantas dentro para levantarla. En falla el canal entrega
# None ("sin lectura"), nunca 0.

DEBOUNCE_LECTURAS_PRESION = 3


class _DetectorLazo:
    """Debounce de la falla de un canal de presión."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.en_falla = False
        self.seguidas = 0           # lecturas seguidas en contra del estado actual
        self.ultimo: Optional[float] = None   # último valor entregado

    def sin_valor(self) -> None:
        """Canal sin valor crudo (tanda 19, MOD-03): sin lectura, sin contar
        como dentro ni fuera de rango (DECISIÓN SIN CONFIRMAR). Una falla ya
        declarada sigue declarada: se levanta con lecturas dentro de rango."""
        self.ultimo = None

    def actualizar(self, fuera: bool) -> None:
        if fuera != self.en_falla:
            self.seguidas += 1
            if self.seguidas >= DEBOUNCE_LECTURAS_PRESION:
                self.en_falla = fuera
                self.seguidas = 0
        else:
            self.seguidas = 0


_det_pres: List[_DetectorLazo] = [_DetectorLazo() for _ in range(8)]


def _campo(calib, nombre, defecto=None):
    if calib is None:
        return defecto
    if isinstance(calib, dict):
        valor = calib.get(nombre, defecto)
    else:
        valor = getattr(calib, nombre, defecto)
    return defecto if valor is None else valor


def umbrales_falla_presion(calib) -> tuple:
    """(bajo, alto) en cuentas crudas; None = esa detección queda inactiva. Un
    bajo <= 0 significa piso de saturación (0 cuentas = falla)."""
    adc_min = _campo(calib, "adc_min")
    adc_max = _campo(calib, "adc_max")
    if adc_min is None or adc_max is None or adc_max <= adc_min:
        return None, None
    span = adc_max - adc_min
    bajo = _campo(calib, "adc_falla_bajo")
    if bajo is None:
        bajo = adc_min - float(_campo(calib, "margen_falla_bajo", 0.025)) * span
    alto = _campo(calib, "adc_falla_alto")
    if alto is None:
        alto = adc_max + float(_campo(calib, "margen_falla_alto", 0.0625)) * span
    return bajo, alto


def _fuera_de_rango(raw, bajo, alto) -> bool:
    if bajo is None and alto is None:
        return False
    if bajo is not None and (raw < bajo or (bajo <= 0 and raw <= 0)):
        return True
    return alto is not None and raw > alto


# Piso calibrado (revisión ★ de S1, SAF-03/SEN-02). DECISIÓN SIN CONFIRMAR:
# con la calibración actual el umbral bajo en cuentas queda < 0 y solo 0
# cuentas exactas eran falla; la calibración de usuario del canal 0 (gain
# 1,364, offset -75,3) pone el 0 kPa real en ≈546 cuentas, así que cuentas
# residuales de un lazo abierto (1..~480) calibraban a presión negativa y el
# recorte max(0, v) las dejaba en 0 kPa válido. Complemento de la detección
# en cuentas: si la muestra cruda, calibrada (fábrica + usuario, sin filtrar
# ni recortar), queda por debajo de `pres_falla_bajo_kpa` (defecto -10 kPa;
# un transductor absoluto nunca lee presión negativa) cuenta como fuera de
# rango, con el mismo debounce. None lo desactiva. Se ajusta con la prueba
# de banco D-38.
PRES_FALLA_BAJO_KPA = -10.0


def _bajo_piso_calibrado(raw, factory_calib, user_calib) -> bool:
    if factory_calib is None:
        return False
    # explícito None = desactivado (por eso no se usa _campo)
    if isinstance(factory_calib, dict):
        piso = factory_calib.get("pres_falla_bajo_kpa", PRES_FALLA_BAJO_KPA)
    else:
        piso = getattr(factory_calib, "pres_falla_bajo_kpa", PRES_FALLA_BAJO_KPA)
    if piso is None:
        return False
    try:
        fabrica = _factory_calibrate(raw, factory_calib, 400.0, is_pressure=True)
        if fabrica is None:
            return False
        valor = _user_calibrate(fabrica, user_calib)
    except Exception:
        return False
    return valor < float(piso)


def presion_en_falla(indice: int) -> bool:
    """True si el canal de presión `indice` tiene la falla declarada."""
    return _det_pres[indice].en_falla


def reiniciar_presiones() -> None:
    """Estado inicial de los canales de presión (pruebas y recarga)."""
    for i in range(8):
        _det_pres[i].reset()
        _ma_pres[i].buffer.clear()
        _oe_pres[i].reset()


# ==============================
# PRESIÓN
# ==============================

def convert_pressures(raw_ai: List[Optional[int]], config: Dict | CalibrationConfig,
                      nueva_muestra: bool = True) -> List[Optional[float]]:
    """Presiones en kPa por canal; None = sin lectura (S1, D8-1.1).
    `nueva_muestra` False: la trama AI es la misma de la llamada anterior
    (Units también notifica por tramas DI/DO); no avanza el debounce ni los
    filtros y repite el último valor de cada canal."""

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
        raw = _crudo_en(raw_ai, raw_index)

        factory_calib = factory_list[i] if i < len(factory_list) else None
        user_calib    = user_list[i]    if i < len(user_list)    else None
        det = _det_pres[i]

        if not nueva_muestra:
            press.append(det.ultimo)
            continue

        # Sin valor crudo (tanda 19, MOD-03): sin lectura y filtros
        # reiniciados; el detector no cuenta esta muestra.
        if raw is None:
            det.sin_valor()
            _ma_pres[i].buffer.clear()
            _oe_pres[i].reset()
            press.append(None)
            continue

        # 0. Transductor sin señal, sobre la cuenta cruda (S1, D8-1.1)
        bajo, alto = umbrales_falla_presion(factory_calib)
        fuera = (_fuera_de_rango(raw, bajo, alto)
                 or _bajo_piso_calibrado(raw, factory_calib, user_calib))
        estaba_en_falla = det.en_falla
        det.actualizar(fuera)
        if det.en_falla:
            if not estaba_en_falla:
                logger.error("Presión canal %d: transductor sin señal (cuentas %s, umbrales %s/%s)",
                             i, raw, bajo, alto)
            _ma_pres[i].buffer.clear()
            _oe_pres[i].reset()
            det.ultimo = None
            press.append(None)
            continue
        if estaba_en_falla:
            logger.warning("Presión canal %d: transductor de vuelta en rango (cuentas %s)", i, raw)
        if fuera:
            # fuera de rango sin falla declarada todavía: la muestra no entra
            # al filtro; se repite el último valor (None si no hay)
            press.append(det.ultimo)
            continue

        # 1. Pre-filtro: mediana ligera sobre valores crudos
        smoothed_raw = _ma_pres[i].update(raw)

        # 2. Calibración → valor en kPa
        value = _factory_calibrate(smoothed_raw, factory_calib, 400.0, is_pressure=True)
        if value is None:
            # sin calibración de fábrica del canal: sin lectura
            _ma_pres[i].buffer.clear()
            _oe_pres[i].reset()
            det.ultimo = None
            press.append(None)
            continue
        value = _user_calibrate(value, user_calib)

        # 3. Suavizado adaptativo: fuerte en reposo, rápido ante cambios reales
        value = _oe_pres[i].update(value, timestamp)

        # 4. Clamp: la presión nunca es negativa
        value = max(0.0, value)

        det.ultimo = round(value, 1)
        press.append(det.ultimo)

    return press