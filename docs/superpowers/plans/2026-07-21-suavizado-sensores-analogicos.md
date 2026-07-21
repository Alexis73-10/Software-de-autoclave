# Suavizado adaptativo de sensores analógicos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el EMA de un solo polo en `converters.py` por un filtro adaptativo (One Euro Filter) que suaviza fuerte en reposo y responde rápido ante cambios reales, para reducir el ruido de ±2°C/±5kPa reportado sin exceder la latencia de control de fases.

**Architecture:** Una clase `OneEuroFilter` nueva (por canal, 8 temperatura + 8 presión) reemplaza el uso de `_ema()` + `_prev_temp_values`/`_prev_pres_values`. El resto del pipeline (mediana pre-filtro, calibración fábrica/usuario, detección de desconexión) no cambia.

**Tech Stack:** Python puro (`math`, `time`), sin dependencias nuevas.

## Global Constraints

- Spec de referencia: `docs/superpowers/specs/2026-07-21-suavizado-sensores-analogicos-design.md`
- Solo se modifica `src/autoclave/hal/measures/converters.py` (ningún otro archivo del pipeline).
- La firma pública de `convert_temperatures()`/`convert_pressures()` no cambia (mismos parámetros, mismo tipo de retorno).
- No se agrega configuración externa (`calibration.yaml`/`schema.py`) para `mincutoff`/`beta` — quedan como constantes de módulo (YAGNI).
- No se agrega detección de desconexión a presión (fuera de alcance).
- Suite completa (`pytest tests/`) debe seguir pasando después de cada tarea.

---

### Task 1: Clase `OneEuroFilter`

**Files:**
- Modify: `src/autoclave/hal/measures/converters.py` (agregar clase, sin tocar el resto todavía)
- Test: `tests/test_one_euro_filter.py` (nuevo)

**Interfaces:**
- Produces: `class OneEuroFilter` con:
  - `__init__(self, mincutoff: float, beta: float, dcutoff: float = 1.0)`
  - `update(self, value: float, timestamp: float) -> float`
  - `reset(self) -> None`
  - Atributos públicos usados por tests/integración: `x_prev`, `dx_prev`, `t_prev`

- [ ] **Step 1: Escribir los tests que van a fallar**

Crear `tests/test_one_euro_filter.py`:

```python
import random
import statistics

import pytest

from autoclave.hal.measures.converters import OneEuroFilter


def test_flat_noisy_signal_is_smoothed():
    f = OneEuroFilter(mincutoff=0.05, beta=0.02)
    random.seed(42)
    t = 0.0
    dt = 0.5
    raw_values = []
    outputs = []
    for _ in range(60):
        t += dt
        v = 100.0 + random.uniform(-2.0, 2.0)
        raw_values.append(v)
        outputs.append(f.update(v, t))

    # Ignorar las primeras muestras (todavía convergiendo desde el arranque)
    raw_std = statistics.pstdev(raw_values[10:])
    out_std = statistics.pstdev(outputs[10:])
    assert out_std < raw_std * 0.5


def test_step_response_faster_than_legacy_ema():
    f = OneEuroFilter(mincutoff=0.05, beta=0.02)
    t = 0.0
    dt = 0.5
    value = 20.0
    for _ in range(20):
        t += dt
        value = f.update(20.0, t)

    legacy_alpha = 0.15
    legacy_value = 20.0
    target = 100.0
    start = 20.0
    threshold = start + 0.95 * (target - start)

    steps_oe = None
    steps_legacy = None
    for i in range(1, 61):
        t += dt
        value = f.update(target, t)
        legacy_value = legacy_alpha * target + (1 - legacy_alpha) * legacy_value
        if steps_oe is None and value >= threshold:
            steps_oe = i
        if steps_legacy is None and legacy_value >= threshold:
            steps_legacy = i

    assert steps_oe is not None
    assert steps_legacy is not None
    assert steps_oe < steps_legacy


def test_reset_clears_state_and_restarts_without_ramp():
    f = OneEuroFilter(mincutoff=0.05, beta=0.02)
    f.update(50.0, 1.0)
    f.update(52.0, 1.5)

    f.reset()

    assert f.x_prev is None
    assert f.dx_prev == 0.0
    assert f.t_prev is None

    result = f.update(80.0, 5.0)
    assert result == 80.0


def test_long_gap_snaps_to_new_value():
    f = OneEuroFilter(mincutoff=0.05, beta=0.02)
    f.update(20.0, 0.0)
    f.update(20.2, 0.5)

    # Gap de 60s (freeze del hilo / reconexión); el valor real ahora es 90.0
    result = f.update(90.0, 60.5)

    # alpha->1 a medida que dt crece: el filtro debe confiar mayormente en el
    # valor nuevo, no arrastrar el viejo (~20) con lag.
    assert result > 80.0
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `pytest tests/test_one_euro_filter.py -v`
Expected: FAIL — `ImportError: cannot import name 'OneEuroFilter'` (la clase no existe todavía).

- [ ] **Step 3: Implementar `OneEuroFilter` en `converters.py`**

Agregar `import math` al bloque de imports (tope del archivo):

```python
# autoclave.core.converters.py

import math
from typing import List, Dict, Optional
from autoclave.config.schema import CalibrationConfig
from collections import deque
import statistics
```

Agregar la clase nueva inmediatamente después de la clase `MedianFilter` (antes del bloque `# Estado interno de filtros`):

```python
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
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `pytest tests/test_one_euro_filter.py -v`
Expected: PASS (4 tests). Si `test_flat_noisy_signal_is_smoothed` da un margen ajustado, imprimir `raw_std`/`out_std` (`pytest -s`) y confirmar que la relación real sigue por debajo de 0.5 antes de continuar — no relajar el umbral sin verificar que sigue siendo una demostración real de suavizado.

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/hal/measures/converters.py tests/test_one_euro_filter.py
git commit -m "feat: agregar OneEuroFilter para suavizado adaptativo de sensores"
```

---

### Task 2: Integrar `OneEuroFilter` en `convert_temperatures`/`convert_pressures`

**Files:**
- Modify: `src/autoclave/hal/measures/converters.py`
- Test: `tests/test_converters_smoothing.py` (nuevo)

**Interfaces:**
- Consumes: `OneEuroFilter` de Task 1 (`update(value, timestamp)`, `reset()`).
- Produces: `convert_temperatures(raw_ai, config) -> List[Optional[float]]` y `convert_pressures(raw_ai, config) -> List[float]` con la misma firma que hoy, ahora usando `OneEuroFilter` internamente. Variables de módulo nuevas: `_oe_temp: List[OneEuroFilter]`, `_oe_pres: List[OneEuroFilter]` (8 instancias cada una), reemplazando a `_prev_temp_values`/`_prev_pres_values`.

- [ ] **Step 1: Escribir los tests de integración que van a fallar**

Crear `tests/test_converters_smoothing.py`:

```python
from autoclave.hal.measures import converters


def test_convert_temperatures_smooths_and_resets_on_disconnect():
    # Estado global compartido entre tests: resetear el canal 0 antes de empezar.
    converters._ma_temp[0].buffer.clear()
    converters._oe_temp[0].reset()

    raw_connected = [2048] + [0] * 15  # canal 0 con lectura válida fija

    first = converters.convert_temperatures(raw_connected, {})[0]
    second = converters.convert_temperatures(raw_connected, {})[0]

    assert first is not None
    assert second is not None
    assert abs(second - first) < 5.0  # lectura estable, no diverge

    disconnected = [0] * 16
    result = converters.convert_temperatures(disconnected, {})[0]

    assert result is None
    assert converters._oe_temp[0].t_prev is None  # reset() se invocó

    reconnected = converters.convert_temperatures(raw_connected, {})[0]
    assert reconnected is not None  # arranca directo, sin rampa ni error


def test_convert_pressures_uses_one_euro_filter():
    converters._ma_pres[0].buffer.clear()
    converters._oe_pres[0].reset()

    raw = [0] * 8 + [2048] + [0] * 7  # canal 0 de presión = índice 8

    first = converters.convert_pressures(raw, {})[0]
    second = converters.convert_pressures(raw, {})[0]

    assert first is not None and first >= 0.0
    assert second is not None and second >= 0.0


def test_convert_temperatures_tracks_real_change_within_two_ticks(monkeypatch):
    converters._ma_temp[1].buffer.clear()
    converters._oe_temp[1].reset()

    fake_time = [0.0]
    monkeypatch.setattr(converters.time, "monotonic", lambda: fake_time[0])

    raw_cold = [2000, 1024] + [0] * 6  # canal 1 = índice 1, valor "frío"
    raw_hot = [2000, 3500] + [0] * 6   # canal 1 ahora "caliente"

    for _ in range(6):
        fake_time[0] += 0.5
        val_before = converters.convert_temperatures(raw_cold, {})[1]

    fake_time[0] += 0.5
    first_after_step = converters.convert_temperatures(raw_hot, {})[1]
    fake_time[0] += 0.5
    second_after_step = converters.convert_temperatures(raw_hot, {})[1]

    assert val_before is not None
    assert first_after_step > val_before + 50  # ya se movió fuerte hacia el valor real
    assert second_after_step > first_after_step  # sigue acercándose
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `pytest tests/test_converters_smoothing.py -v`
Expected: FAIL — los tres tests fallan con `AttributeError: module 'autoclave.hal.measures.converters' has no attribute '_oe_temp'` (o `_oe_pres`), porque esas variables de módulo todavía no existen.

- [ ] **Step 3: Reemplazar el EMA por `OneEuroFilter` en `converters.py`**

Agregar `import time` junto al `import math` ya agregado en Task 1:

```python
import math
import time
from typing import List, Dict, Optional
from autoclave.config.schema import CalibrationConfig
from collections import deque
import statistics
```

Reemplazar todo el bloque `# Estado interno de filtros` (desde el comentario hasta el final de la función `_ema`, es decir las constantes `_prev_temp_values`/`_prev_pres_values`/`TEMP_ALPHA`/`PRES_ALPHA` y la función `_ema`) por:

```python
# ==============================
# Estado interno de filtros
# ==============================
# Pipeline: raw → MedianFilter(pre-filtro) → calibrar → OneEuroFilter(suavizado adaptativo)

_ma_temp: List[MedianFilter] = [MedianFilter(5) for _ in range(8)]   # pre-filtro ligero
_ma_pres: List[MedianFilter] = [MedianFilter(5) for _ in range(8)]   # pre-filtro ligero

# mincutoff: suavizado en reposo (más bajo = más suave). beta: qué tan rápido se
# relaja el suavizado cuando la derivada estimada indica un cambio real.
# Puntos de partida sin calibrar con datos reales — ver spec, sección
# "Valores iniciales de mincutoff/beta" para la pasada de calibración pendiente.
TEMP_MINCUTOFF = 0.05
TEMP_BETA = 0.02
PRES_MINCUTOFF = 0.1
PRES_BETA = 0.05
DCUTOFF = 1.0

_oe_temp: List[OneEuroFilter] = [
    OneEuroFilter(TEMP_MINCUTOFF, TEMP_BETA, DCUTOFF) for _ in range(8)
]
_oe_pres: List[OneEuroFilter] = [
    OneEuroFilter(PRES_MINCUTOFF, PRES_BETA, DCUTOFF) for _ in range(8)
]
```

(Se elimina la función `_ema` — ya no se usa en ningún lado del archivo.)

Modificar `convert_temperatures` — reemplazar desde `global _prev_temp_values` hasta el final del `for`:

```python
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
```

Modificar `convert_pressures` — mismo reemplazo:

```python
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
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `pytest tests/test_converters_smoothing.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Correr toda la suite existente para confirmar que no se rompió nada**

Run: `pytest tests/test_converters_realistic.py tests/test_flujo_unidades.py -v --collect-only`

(`test_flujo_unidades.py` es un script manual con loop infinito contra hardware real — usar `--collect-only` o excluirlo, no ejecutarlo. Solo correr de verdad `test_converters_realistic.py`.)

Run: `pytest tests/test_converters_realistic.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/hal/measures/converters.py tests/test_converters_smoothing.py
git commit -m "feat: reemplazar EMA fijo por OneEuroFilter en converters.py"
```

---

### Task 3: Suite completa y cierre

**Files:** ninguno nuevo — solo verificación.

- [ ] **Step 1: Correr toda la suite del proyecto**

Run: `pytest tests/ --ignore=tests/test_flujo_unidades.py -v`
Expected: todos los tests PASS (ninguna regresión fuera de `converters.py`).

- [ ] **Step 2: Si algo falla, diagnosticar antes de tocar código de otros módulos**

Dado que `convert_temperatures`/`convert_pressures` mantienen la misma firma y tipo de
retorno, no debería haber roturas fuera de `test_converters_realistic.py` y los tests
nuevos. Si aparece una falla en otro archivo, es señal de que algo dependía del
comportamiento interno viejo (`_prev_temp_values`, `TEMP_ALPHA`, etc.) — investigar con
`git grep` antes de asumir que hay que cambiar el diseño.

- [ ] **Step 3: Nota de seguimiento (no bloquea esta implementación)**

Dejar registrado (en el mensaje del commit final o como comentario para el usuario)
que `TEMP_MINCUTOFF`/`TEMP_BETA`/`PRES_MINCUTOFF`/`PRES_BETA` son valores de partida
sin calibrar contra datos reales del equipo, y que conviene loguear crudo+filtrado
durante un ciclo real (reposo + rampa de calentamiento) para ajustarlos.
