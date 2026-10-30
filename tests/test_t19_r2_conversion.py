# tests/test_t19_r2_conversion.py
#
# Revisión R de la tanda 19 (V19-s2-03): con el enlace Modbus, una cuenta cruda
# de temperatura fuera del rango físico plausible de la PT100 (menos de -500 o
# más de 2500 décimas; DECISIÓN SIN CONFIRMAR) se trata como sin valor: None y
# filtros del canal reiniciados, igual que un None. (El caso serial se borró:
# enlace retirado en la tanda 20, T20-03.)

from pathlib import Path

import pytest

from autoclave.config import load_config
from autoclave.hal.measures import converters

CAL_MODBUS = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "config" / "calibration_modbus.yaml"


@pytest.fixture(autouse=True)
def _filtros_limpios():
    def limpiar():
        converters.reiniciar_presiones()
        for i in range(8):
            converters._ma_temp[i].buffer.clear()
            converters._oe_temp[i].reset()
    limpiar()
    yield
    limpiar()


@pytest.fixture
def cfg_modbus():
    return load_config(CAL_MODBUS)


def _ai(temps):
    return list(temps) + [None] * (16 - len(temps))


@pytest.mark.req("MOD-03")
@pytest.mark.parametrize("decimas", [-501, -32768, 2501, 4095, 32767])
def test_modbus_cuenta_implausible_da_none(cfg_modbus, decimas):
    assert converters.convert_temperatures(_ai([decimas]), cfg_modbus)[0] is None


@pytest.mark.req("MOD-03")
@pytest.mark.parametrize("decimas,grados", [(-500, -50.0), (2500, 250.0), (1340, 134.0)])
def test_modbus_limites_plausibles_inclusive(cfg_modbus, decimas, grados):
    assert converters.convert_temperatures(_ai([decimas]), cfg_modbus)[0] == grados


@pytest.mark.req("MOD-03")
def test_modbus_cuenta_implausible_reinicia_filtros(cfg_modbus):
    """Igual que un None: tras la cuenta implausible, el filtro arranca de cero
    y la primera lectura válida sale sin arrastrar las anteriores."""
    for _ in range(5):
        converters.convert_temperatures(_ai([1340]), cfg_modbus)
    assert converters._ma_temp[0].buffer
    assert converters.convert_temperatures(_ai([30000]), cfg_modbus)[0] is None
    assert not converters._ma_temp[0].buffer
    # la siguiente lectura válida no arrastra las de 134 °C
    assert converters.convert_temperatures(_ai([1210]), cfg_modbus)[0] == 121.0
