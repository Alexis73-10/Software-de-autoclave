import textwrap
from autoclave.config.calibration_writer import write_user_calibration


def _make_yaml(tmp_path):
    path = tmp_path / "calibration.yaml"
    path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              # Sensor 0 -- calibrado con 5 puntos, no tocar sin patron
              - poly: [2.046e-05, -0.00511265, 1.35714148, -3.74342417]
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.3466
                offset: -67.11
              - gain: 1.3466
                offset: -67.11
    """), encoding="utf-8")
    return path


def test_reemplaza_poly_por_gain_offset(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "temperature", 0, 1.010345, 1.090435,
                            20.0, 20.0, 131.3, 132.5)

    from ruamel.yaml import YAML
    yaml = YAML(typ="safe")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    entry = data["calibration"]["user"]["temperature"][0]
    assert entry["gain"] == 1.010345
    assert entry["offset"] == 1.090435
    assert "poly" not in entry


def test_no_toca_otros_sensores(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "pressure", 0, 1.261721, -64.583518,
                            12.0, 9.54, 322.0, 300.0)

    from ruamel.yaml import YAML
    yaml = YAML(typ="safe")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    # sensor 1 de pressure no cambio
    assert data["calibration"]["user"]["pressure"][1]["gain"] == 1.3466
    # sensor 1 de temperature (gain/offset simple) no cambio
    assert data["calibration"]["user"]["temperature"][1]["gain"] == 1.0


def test_preserva_comentarios_existentes(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "pressure", 0, 1.261721, -64.583518,
                            12.0, 9.54, 322.0, 300.0)

    texto = path.read_text(encoding="utf-8")
    assert "calibrado con 5 puntos" in texto


def test_agrega_comentario_de_trazabilidad(tmp_path):
    path = _make_yaml(tmp_path)
    write_user_calibration(path, "pressure", 0, 1.261721, -64.583518,
                            12.0, 9.54, 322.0, 300.0)

    texto = path.read_text(encoding="utf-8")
    assert "12.0" in texto and "300.0" in texto
