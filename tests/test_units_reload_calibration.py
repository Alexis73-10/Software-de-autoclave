import textwrap
from autoclave.hal.measures.units import Units


def test_reload_calibration_actualiza_config(tmp_path):
    yaml_a = tmp_path / "a.yaml"
    yaml_a.write_text(textwrap.dedent("""
        calibration:
          user:
            pressure:
              - gain: 1.0
                offset: 0.0
    """), encoding="utf-8")

    yaml_b = tmp_path / "b.yaml"
    yaml_b.write_text(textwrap.dedent("""
        calibration:
          user:
            pressure:
              - gain: 2.5
                offset: -10.0
    """), encoding="utf-8")

    units = Units(str(yaml_a))
    assert units._config.calibration.user.pressure[0].gain == 1.0
    assert units._config.calibration.user.pressure[0].offset == 0.0

    units.reload_calibration(str(yaml_b))
    assert units._config.calibration.user.pressure[0].gain == 2.5
    assert units._config.calibration.user.pressure[0].offset == -10.0
