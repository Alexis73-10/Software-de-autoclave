# ui_qml/design/generate_tokens.py
#
# Genera Tokens.qml (singleton QML, §7.2 del plan de interfaz dual-pantalla)
# a partir de tokens.json — fuente única de color/tipografía/espaciado.
# Artefacto generado: prohibido editar Tokens.qml a mano.
#
# Uso: python -m autoclave.ui_qml.design.generate_tokens

import json
import re
import sys
from pathlib import Path

_TOKENS_JSON = Path("docs/files UI Especifika/tokens.json")
_TOKENS_QML = Path("src/autoclave/ui_qml/design/Tokens.qml")

# Grupos que no son tokens de diseño consumibles en runtime: "$meta" es
# metadata del archivo, "contrast" es auditoría WCAG (no se usa en pantalla),
# "colorDark" se fusiona sobre "color" en vez de exponerse aparte.
_EXCLUIDOS = {"$meta", "contrast", "colorDark"}


def _fusionar(base: dict, overrides: dict) -> dict:
    """Fusión profunda: overrides gana, sin mutar base. Ignora "$meta"
    dentro de overrides (metadata descriptiva, no un token)."""
    resultado = dict(base)
    for clave, valor in overrides.items():
        if clave == "$meta":
            continue
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = _fusionar(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def _property_var(nombre: str, valor) -> str:
    return f"    readonly property var {nombre}: ({json.dumps(valor, ensure_ascii=False)})"


_STOP_RE = re.compile(r"(rgba?\([^)]*\)|#[0-9A-Fa-f]{3,8})\s+(\d+(?:\.\d+)?)%")


def extraer_stops_gradiente(css: str) -> list:
    """Extrae los stops {position, color} de una cadena CSS linear-gradient/
    radial-gradient de tokens.json. Ignora los parámetros de forma (ángulo,
    centro, radios) que preceden al primer color — solo importan a QtQuick
    los stops en sí, no cómo se posiciona el degradado."""
    return [
        {"position": round(float(pos) / 100, 4), "color": color}
        for color, pos in _STOP_RE.findall(css)
    ]


def generar_tokens_qml(tokens: dict) -> str:
    """Genera el contenido de Tokens.qml a partir del dict parseado de
    tokens.json. Pura: no toca el filesystem.

    El grupo "color" se expone en dos tablas resueltas (_colorLight /
    _colorDark, esta última fusionando "colorDark" sobre "color") más una
    propiedad `color` que selecciona una u otra según el toggle `dark` —
    el cambio de tema conmuta la tabla activa sin recompilar (D-21). El
    resto de grupos (gradient, typography, space, ...) no varían con el
    tema y se exponen tal cual."""
    color_claro = tokens.get("color", {})
    color_oscuro = _fusionar(color_claro, tokens.get("colorDark", {}))

    lineas = [
        "pragma Singleton",
        "import QtQuick",
        "",
        "QtObject {",
        "    id: root",
        "",
        "    property bool dark: false",
        "",
    ]

    for nombre, valor in tokens.items():
        if nombre in _EXCLUIDOS:
            continue
        if nombre == "color":
            lineas.append("    readonly property var color: dark ? _colorDark : _colorLight")
            lineas.append(_property_var("_colorLight", color_claro))
            lineas.append(_property_var("_colorDark", color_oscuro))
            lineas.append("")
            continue
        lineas.append(_property_var(nombre, valor))
        if nombre == "gradient":
            stops = {clave: extraer_stops_gradiente(css) for clave, css in valor.items()}
            lineas.append(_property_var("gradientStops", stops))

    lineas.append("}")
    lineas.append("")
    return "\n".join(lineas)


def main() -> None:
    tokens = json.loads(_TOKENS_JSON.read_text(encoding="utf-8"))
    qml = generar_tokens_qml(tokens)
    _TOKENS_QML.parent.mkdir(parents=True, exist_ok=True)
    _TOKENS_QML.write_text(qml, encoding="utf-8")
    print(f"Generado {_TOKENS_QML} desde {_TOKENS_JSON}")


if __name__ == "__main__":
    sys.exit(main())
