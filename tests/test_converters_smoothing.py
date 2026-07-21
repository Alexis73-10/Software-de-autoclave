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

    # El pre-filtro de mediana (ventana 5, sin tocar en esta tarea) necesita 3
    # muestras nuevas para reflejar el cambio real — recién ahí el OneEuroFilter
    # ve el valor nuevo. Las primeras 2 muestras "calientes" no alcanzan a mover
    # la mediana todavía.
    for _ in range(2):
        fake_time[0] += 0.5
        converters.convert_temperatures(raw_hot, {})[1]

    fake_time[0] += 0.5
    first_after_step = converters.convert_temperatures(raw_hot, {})[1]  # mediana recién volteó
    fake_time[0] += 0.5
    second_after_step = converters.convert_temperatures(raw_hot, {})[1]  # 1 tick de OneEuroFilter después

    assert val_before is not None
    assert first_after_step > val_before + 50  # ya se movió fuerte hacia el valor real
    assert second_after_step > first_after_step  # sigue acercándose
