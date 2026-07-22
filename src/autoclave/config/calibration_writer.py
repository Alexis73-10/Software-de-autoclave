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

# Estilo de indentacion del archivo real calibration.yaml (verificado empiricamente):
#   calibration:
#     user:
#       temperature:
#         - gain: 1.0      <- "-" a 2 espacios de la clave padre (offset)
#           offset: 0.0    <- claves del mapping alineadas con la 1ra tras "- "
# equivalente a yaml.indent(mapping=2, sequence=4, offset=2).
_INDENT_MAPPING = 2
_INDENT_SEQUENCE = 4
_INDENT_OFFSET = 2

# Columna (espacios) donde deben empezar los comentarios "before" de un item
# de secuencia bajo calibration.user.<seccion>, para alinearse con el "-".
# calibration: (0) -> user: (2) -> <seccion>: (4) -> "- " (6)
_COMENTARIO_INDENT = 6

# Marcador que identifica un comentario generado automaticamente por este
# escritor, para poder reemplazarlo (y solo a el) en recalibraciones
# posteriores sin tocar comentarios escritos a mano.
_MARCADOR_AUTO = "[calibracion-auto]"


def _es_comentario_auto(token) -> bool:
    """True si el CommentToken corresponde a un comentario generado por
    este escritor (identificado por _MARCADOR_AUTO), y no a texto escrito
    a mano."""
    valor = token.value.strip()
    if valor.startswith("#"):
        valor = valor[1:].strip()
    return valor.startswith(_MARCADOR_AUTO)


def _limpiar_comentario_auto_previo(seq, index: int) -> None:
    """Elimina, si existe, el/los comentario(s) auto-generados en una
    recalibracion anterior para este item de la secuencia, dejando
    intacto cualquier comentario que no lleve el marcador (documentacion
    escrita a mano, p.ej. la nota "Sensor 0 -- calibrado con 5 puntos...").
    """
    c = seq.ca.items.get(index)
    if not c or not c[1]:
        return
    restantes = [tok for tok in c[1] if tok is not None and not _es_comentario_auto(tok)]
    c[1] = restantes if restantes else None


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
    # Debe coincidir con el estilo real de calibration.yaml (ver constantes
    # arriba) para no reformatear secciones que este escritor no toca.
    yaml.indent(mapping=_INDENT_MAPPING, sequence=_INDENT_SEQUENCE, offset=_INDENT_OFFSET)

    yaml_path = Path(yaml_path)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    seq = data["calibration"]["user"][seccion]

    nuevo = CommentedMap()
    nuevo["gain"] = round(gain, 6)
    nuevo["offset"] = round(offset, 6)
    seq[index] = nuevo

    comentario = (
        f"{_MARCADOR_AUTO} Sensor {index} -- recalibrado {date.today().isoformat()} "
        f"con 2 puntos contra equipo patron: bajo {shown_low}->{real_low}, "
        f"alto {shown_high}->{real_high}."
    )
    _limpiar_comentario_auto_previo(seq, index)
    seq.yaml_set_comment_before_after_key(index, before=comentario, indent=_COMENTARIO_INDENT)

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
