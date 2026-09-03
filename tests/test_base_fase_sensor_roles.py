from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.base_fase import BaseFase


def _fase(sensores_temp, principal="temp_camara", referencia=None):
    estado = MagicMock()
    estado.sensores_temp = sensores_temp
    cycle = MagicMock()
    cycle.get_principal_sensor.return_value = principal
    cycle.get_referencia_sensor.return_value = referencia
    return BaseFase(estado, MagicMock(), cycle, MagicMock(), MagicMock(), MagicMock())


def test_temp_principal_lee_el_sensor_marcado_como_principal():
    fase = _fase({"temp_camara": 100.0, "temp_2_camara": 80.0}, principal="temp_2_camara")
    assert fase._temp_principal() == 80.0


def test_temp_principal_none_si_el_sensor_no_tiene_lectura():
    fase = _fase({"temp_camara": 100.0}, principal="temp_2_camara")
    assert fase._temp_principal() is None


def test_temp_referencia_none_si_no_hay_ninguna_configurada():
    fase = _fase({"temp_camara": 100.0}, referencia=None)
    assert fase._temp_referencia() is None


def test_temp_referencia_lee_el_sensor_marcado():
    fase = _fase({"temp_camara": 100.0, "temp_ref": 90.0}, referencia="temp_ref")
    assert fase._temp_referencia() == 90.0


def test_temp_control_usa_principal_sin_referencia_configurada():
    fase = _fase({"temp_camara": 100.0}, principal="temp_camara", referencia=None)
    assert fase._temp_control() == 100.0


def test_temp_control_usa_referencia_cuando_esta_configurada():
    fase = _fase(
        {"temp_camara": 100.0, "temp_2_camara": 80.0},
        principal="temp_2_camara", referencia="temp_camara",
    )
    assert fase._temp_control() == 100.0
