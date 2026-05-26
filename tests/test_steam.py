from autoclave.core.steam import p_saturacion_kpa


def test_p_saturacion_100():
    result = p_saturacion_kpa(100)
    assert abs(result - 101.3) < 1.0, f"Esperado ~101.3 kPa, obtenido {result:.1f} kPa"


def test_p_saturacion_121():
    result = p_saturacion_kpa(121)
    assert abs(result - 205.0) < 1.0, f"Esperado ~205.0 kPa, obtenido {result:.1f} kPa"


def test_p_saturacion_134():
    result = p_saturacion_kpa(134)
    assert abs(result - 302.9) < 1.0, f"Esperado ~302.9 kPa, obtenido {result:.1f} kPa"


def test_p_saturacion_monotonica():
    """Presión de saturación debe crecer con la temperatura."""
    temps = [100, 110, 121, 130, 134, 140]
    presiones = [p_saturacion_kpa(t) for t in temps]
    for i in range(len(presiones) - 1):
        assert presiones[i] < presiones[i + 1]
