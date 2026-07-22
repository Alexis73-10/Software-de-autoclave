"""
autoclave.config.calibration_writer
------------------------------------
Escribe de vuelta a calibration.yaml usando ruamel.yaml en modo round-trip,
preservando comentarios y formato existentes. Reemplaza por completo la
entrada del sensor calibrado (descarta poly/adc_min/etc previos) por un
mapping simple {gain, offset}.
"""

import io
import re
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


def _patron_comentario_auto_previo(tipo: str, index: int) -> re.Pattern:
    """Construye el regex que detecta, en el TEXTO CRUDO del archivo (antes
    de parsearlo con ruamel), la linea de comentario auto-generada por una
    recalibracion anterior de este mismo sensor (mismo tipo + indice).

    Se elimina por texto plano -- y no navegando `seq.ca.items` de ruamel --
    porque ruamel no adjunta el comentario "before" de un item de secuencia
    de forma consistente: segun la posicion del indice, a veces queda en
    `seq.ca.items[index]`, a veces como comentario de fin de linea de la
    ULTIMA clave del item anterior (`seq[index - 1].ca.items[...][2]`), y
    si `index == 0` puede quedar en el slot de comentario de la propia
    clave padre en el mapping contenedor. Perseguir cada variante interna
    demostro ser fragil (solo funcionaba, por casualidad, para un indice
    especifico). Al quitar la linea del texto crudo ANTES de que ruamel
    la parsee, no importa donde ruamel la habria adjuntado: ya no esta.

    Se incluye el tipo (temperature/pressure) ademas del indice en el
    patron para no confundir, p.ej., el comentario auto de
    "pressure[3]" con el de "temperature[3]" -- ambas secciones reusan
    los mismos indices 0-7. El `(?!\\d)` evita que el indice 1 matchee
    tambien la linea del indice 10/11 (no ocurre hoy con brackets, pero
    se deja por robustez si el formato del comentario cambiara).
    """
    marcador = re.escape(_MARCADOR_AUTO)
    tipo_escapado = re.escape(tipo)
    return re.compile(
        rf"^[ \t]*#\s*{marcador}\s*Sensor\s+{tipo_escapado}\[{index}\](?!\d).*\n",
        re.MULTILINE,
    )


def _reemplazar_entrada_sensor(seq, index: int, gain: float, offset: float) -> None:
    """Reemplaza el contenido del item `index` de la secuencia por
    {gain, offset}, MUTANDO el mapping existente en vez de sustituirlo por
    un objeto `CommentedMap` nuevo.

    Motivo: ruamel puede adjuntar un comentario escrito a mano que
    (textualmente) precede al item SIGUIENTE como un comentario de fin de
    linea de la ULTIMA clave de ESTE item (`seq[index].ca.items[<ultima
    clave>][2]`) -- verificado empiricamente. Si se reemplaza `seq[index]`
    por un objeto `CommentedMap` nuevo, esa metadata de comentario se
    pierde junto con el objeto viejo, borrando silenciosamente una nota
    escrita a mano que en realidad pertenece al sensor siguiente. Mutar el
    mapping en el lugar (borrar sus claves viejas y asignar gain/offset)
    preserva su `.ca` y por lo tanto ese comentario.
    """
    viejo = seq[index]
    if isinstance(viejo, CommentedMap):
        for clave in list(viejo.keys()):
            del viejo[clave]
        viejo["gain"] = round(gain, 6)
        viejo["offset"] = round(offset, 6)
    else:
        # Defensivo: si el item no es un mapping (formato inesperado),
        # conservamos el comportamiento anterior de reemplazo directo.
        nuevo = CommentedMap()
        nuevo["gain"] = round(gain, 6)
        nuevo["offset"] = round(offset, 6)
        seq[index] = nuevo


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

    yaml_path = Path(yaml_path)

    # Quitar, en el texto CRUDO, cualquier comentario auto-generado que una
    # recalibracion anterior haya dejado para este mismo (tipo, index) --
    # antes de que ruamel llegue a parsear el archivo. Ver docstring de
    # _patron_comentario_auto_previo para el porque.
    texto_original = yaml_path.read_text(encoding="utf-8")
    texto_limpio = _patron_comentario_auto_previo(tipo, index).sub("", texto_original)

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    # Debe coincidir con el estilo real de calibration.yaml (ver constantes
    # arriba) para no reformatear secciones que este escritor no toca.
    yaml.indent(mapping=_INDENT_MAPPING, sequence=_INDENT_SEQUENCE, offset=_INDENT_OFFSET)

    data = yaml.load(io.StringIO(texto_limpio))

    seq = data["calibration"]["user"][seccion]

    _reemplazar_entrada_sensor(seq, index, gain, offset)

    comentario = (
        f"{_MARCADOR_AUTO} Sensor {tipo}[{index}] -- recalibrado {date.today().isoformat()} "
        f"con 2 puntos contra equipo patron: bajo {shown_low}->{real_low}, "
        f"alto {shown_high}->{real_high}."
    )
    seq.yaml_set_comment_before_after_key(index, before=comentario, indent=_COMENTARIO_INDENT)

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
