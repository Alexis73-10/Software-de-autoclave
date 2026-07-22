import textwrap

import pytest

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


def _make_yaml_8_sensores(tmp_path):
    """Fixture con 8 sensores por tipo (indices 0-7), como el
    calibration.yaml real, para poder probar la logica de anti-apilado de
    comentarios en el primer indice, indices intermedios y el ultimo.

    El comentario escrito a mano se coloca en temperature[2], un indice
    que ningun test de este archivo recalibra, para poder verificar que
    sobrevive intacto sin que su presencia interfiera con los indices que
    si se recalibran (0, 1, 3, 5, 7)."""
    path = tmp_path / "calibration.yaml"

    def _items(indice_comentario=None):
        bloques = []
        for i in range(8):
            if i == indice_comentario:
                bloques.append(
                    "      # Sensor 0 -- calibrado con 5 puntos, no tocar sin patron"
                )
            bloques.append("      - gain: 1.0\n        offset: 0.0")
        return "\n".join(bloques)

    path.write_text(
        "calibration:\n"
        "  user:\n"
        "    temperature:\n"
        f"{_items(indice_comentario=2)}\n"
        "    pressure:\n"
        f"{_items()}\n",
        encoding="utf-8",
    )
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


@pytest.mark.parametrize(
    "tipo, index",
    [
        ("temperature", 0),  # primer indice
        ("temperature", 1),
        ("temperature", 5),  # indice intermedio
        ("temperature", 7),  # ultimo indice
        ("pressure", 0),  # primer indice
        ("pressure", 1),
        ("pressure", 5),  # indice intermedio
        ("pressure", 7),  # ultimo indice
    ],
)
def test_recalibrar_dos_veces_no_apila_comentarios(tmp_path, tipo, index):
    """Escribir dos veces sobre el mismo (tipo, index) debe reemplazar el
    comentario de trazabilidad anterior, no apilarlo -- verificado en el
    primer indice, indices intermedios y el ultimo, para ambos tipos de
    sensor (no solo el unico indice que "por casualidad" funcionaba antes
    de la correccion via texto plano)."""
    path = _make_yaml_8_sensores(tmp_path)

    write_user_calibration(path, tipo, index, 1.0, 0.0,
                            20.0, 20.0, 130.0, 130.0)
    write_user_calibration(path, tipo, index, 2.0, -1.0,
                            15.0, 15.5, 140.0, 139.0)

    texto = path.read_text(encoding="utf-8")

    # Solo debe quedar un comentario auto-generado para ESTE sensor
    # especifico (tipo + indice), no dos apilados.
    marcador_sensor = f"Sensor {tipo}[{index}]"
    apariciones = texto.count(marcador_sensor)
    assert apariciones == 1, (
        f"{tipo}[{index}]: se esperaban 1 comentario auto, se "
        f"encontraron {apariciones}:\n{texto}"
    )

    # Y debe reflejar los datos de la SEGUNDA escritura, no la primera.
    assert "15.0->15.5" in texto
    assert "140.0->139.0" in texto

    # El comentario "hecho a mano" (en temperature[2], indice no tocado
    # por ningun caso de este test) sigue intacto sin importar cual
    # (tipo, index) se haya recalibrado.
    assert "calibrado con 5 puntos" in texto


def test_no_confunde_mismo_indice_entre_tipos(tmp_path):
    """Un comentario auto en pressure[3] no debe confundirse con uno en
    temperature[3] (mismo indice, tipo distinto) -- ni al crearlo ni al
    reemplazarlo en una recalibracion posterior. Esto ejercita el motivo
    por el que el marcador incluye el tipo, no solo el indice."""
    path = _make_yaml_8_sensores(tmp_path)

    write_user_calibration(path, "temperature", 3, 1.0, 0.0,
                            20.0, 20.0, 130.0, 130.0)
    write_user_calibration(path, "pressure", 3, 1.3, -5.0,
                            10.0, 9.5, 300.0, 295.0)

    texto = path.read_text(encoding="utf-8")
    assert texto.count("Sensor temperature[3]") == 1
    assert texto.count("Sensor pressure[3]") == 1

    # Recalibrar pressure[3] de nuevo no debe tocar ni duplicar el
    # comentario de temperature[3] (mismo indice, tipo distinto).
    write_user_calibration(path, "pressure", 3, 2.0, -10.0,
                            5.0, 4.5, 350.0, 340.0)

    texto = path.read_text(encoding="utf-8")
    assert texto.count("Sensor temperature[3]") == 1
    assert texto.count("Sensor pressure[3]") == 1
    assert "5.0->4.5" in texto
    assert "calibrado con 5 puntos" in texto
