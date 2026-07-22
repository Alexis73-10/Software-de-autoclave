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


def test_no_reformatea_secciones_no_tocadas(tmp_path):
    """Escribir un sensor no debe reflowear la indentacion de otras
    entradas/secciones del archivo (regresion: antes ruamel usaba su
    indent por defecto y reformateaba TODO el documento)."""
    path = _make_yaml(tmp_path)
    antes = path.read_text(encoding="utf-8").splitlines()

    write_user_calibration(path, "temperature", 1, 1.02, 3.5,
                            20.0, 21.1, 130.0, 129.8)

    despues = path.read_text(encoding="utf-8").splitlines()

    # La entrada de pressure (seccion no tocada) debe permanecer
    # byte-identica linea por linea.
    idx_pressure_antes = antes.index("    pressure:")
    idx_pressure_despues = despues.index("    pressure:")
    assert antes[idx_pressure_antes:] == despues[idx_pressure_despues:], (
        "la seccion 'pressure' (no tocada) cambio de formato"
    )

    # El comentario de sensor 0 (escrito a mano) no debe moverse de columna.
    linea_comentario = next(
        l for l in despues if "calibrado con 5 puntos" in l
    )
    assert linea_comentario.startswith("      #"), (
        f"el comentario existente cambio de indentacion: {linea_comentario!r}"
    )


def test_recalibrar_dos_veces_no_apila_comentarios(tmp_path):
    """Escribir dos veces sobre el mismo indice debe reemplazar el
    comentario de trazabilidad anterior, no apilarlo."""
    path = _make_yaml(tmp_path)

    write_user_calibration(path, "temperature", 1, 1.0, 0.0,
                            20.0, 20.0, 130.0, 130.0)
    write_user_calibration(path, "temperature", 1, 2.0, -1.0,
                            15.0, 15.5, 140.0, 139.0)

    texto = path.read_text(encoding="utf-8")
    # Solo debe quedar un comentario auto-generado para este sensor.
    assert texto.count("recalibrado") == 1
    # Y debe reflejar los datos de la SEGUNDA escritura, no la primera.
    assert "15.0->15.5" in texto or "15.0->15.5" in texto.replace(" ", "")
    assert "140.0->139.0" in texto or "140.0->139.0" in texto.replace(" ", "")

    # El comentario "hecho a mano" del sensor 0 sigue intacto.
    assert "calibrado con 5 puntos" in texto
