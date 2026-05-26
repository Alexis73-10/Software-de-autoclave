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


# Tests para _verificar_vapor_saturado() helper
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.base_fase import BaseFase


def _make_base_fase():
    estado = MagicMock()
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    alarms = MagicMock()
    # BaseFase no puede instanciarse directamente (update() es abstracto),
    # usamos una subclase mínima.
    class FaseTest(BaseFase):
        name = "TEST"
        def reset(self): pass
        def update(self): pass
    return FaseTest(estado, set_do, cycle, config, alarms)


def test_verificar_vapor_saturado_dentro_tolerancia():
    fase = _make_base_fase()
    # P_sat(134°C) ≈ 302.2 kPa — dentro de ±10 kPa → True
    assert fase._verificar_vapor_saturado(134.0, 302.2, 10.0) is True


def test_verificar_vapor_saturado_fuera_tolerancia_alta():
    fase = _make_base_fase()
    # P_real = 320 kPa, P_sat ≈ 302.2 → delta = 17.8 > 10 → False
    assert fase._verificar_vapor_saturado(134.0, 320.0, 10.0) is False


def test_verificar_vapor_saturado_fuera_tolerancia_baja():
    fase = _make_base_fase()
    # P_real = 285 kPa, P_sat ≈ 302.2 → delta = 17.2 > 10 → False
    assert fase._verificar_vapor_saturado(134.0, 285.0, 10.0) is False
