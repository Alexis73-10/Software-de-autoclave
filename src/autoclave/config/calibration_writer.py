"""
autoclave.config.calibration_writer
------------------------------------
Escribe de vuelta a calibration.yaml usando ruamel.yaml en modo round-trip,
preservando comentarios y formato existentes. Reemplaza por completo la
entrada del sensor calibrado (descarta poly/adc_min/etc previos) por un
mapping simple {gain, offset}.
"""

from datetime import date
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

_SECCION_POR_TIPO = {"temperature": "temperature", "pressure": "pressure"}


def write_user_calibration(
    yaml_path: str | Path,
    tipo: str,
    index: int,
    gain: float,
    offset: float,
    shown_low: float,
    real_low: float,
    shown_high: float,
    real_high: float,
) -> None:
    seccion = _SECCION_POR_TIPO[tipo]

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True

    yaml_path = Path(yaml_path)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    seq = data["calibration"]["user"][seccion]

    nuevo = CommentedMap()
    nuevo["gain"] = round(gain, 6)
    nuevo["offset"] = round(offset, 6)
    seq[index] = nuevo

    comentario = (
        f"Sensor {index} -- recalibrado {date.today().isoformat()} con 2 puntos "
        f"contra equipo patron: bajo {shown_low}->{real_low}, "
        f"alto {shown_high}->{real_high}."
    )
    seq.yaml_set_comment_before_after_key(index, before=comentario)

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
