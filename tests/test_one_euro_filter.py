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
