# tests/test_config.py
from autoclave.config.schema import AutoclaveConfig

def test_load_production_config():
    cfg = AutoclaveConfig.load("src/autoclave/config/production.yaml")

    # Validar comunicación
    assert cfg.serial.scan_pattern == "CH340"

    # Validar cantidad de sensores de temperatura
    assert len(cfg.sensors.temperature.sensors) == 8

    # Validar cantidad de sensores de presión
    assert len(cfg.sensors.pressure.sensors) == 8

    # Validar el primer sensor
    assert cfg.sensors.temperature.sensors[0].name == "Camara"

