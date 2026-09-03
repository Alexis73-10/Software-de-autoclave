# tests/test_generate_tokens_qml.py
import json
import pytest
from autoclave.ui_qml.design.generate_tokens import extraer_stops_gradiente, generar_tokens_qml


def _extraer_bloque_var(qml_text, nombre_propiedad):
    """Extrae y parsea como JSON el valor de `readonly property var <nombre>: (...)`.
    Usa raw_decode (no regex) para manejar correctamente objetos anidados."""
    marcador = f"readonly property var {nombre_propiedad}: ("
    assert marcador in qml_text, f"no se encontró property var {nombre_propiedad!r} en:\n{qml_text}"
    inicio = qml_text.index(marcador) + len(marcador)
    valor, _ = json.JSONDecoder().raw_decode(qml_text, inicio)
    return valor


@pytest.fixture
def tokens_minimos():
    return {
        "$meta": {"version": "1.0.0"},
        "color": {
            "primary": {"050": "#E2EDFE", "500": "#1168F6", "700": "#0D53C4"},
            "module": {"cycle": "#009933"},
            "surface": {"card": "#FFFFFF"},
        },
        "colorDark": {
            "$meta": "overrides",
            "primary": {"050": "#16273D", "500": "#4C8FFB"},
            "surface": {"card": "#16202B"},
        },
        "contrast": {"note": "excluido del QML"},
        "space": {"1": 4, "2": 8},
        "radius": {"xs": 4},
    }


def test_encabezado_pragma_singleton(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    assert qml.startswith("pragma Singleton\n")
    assert "import QtQuick" in qml
    assert "QtObject {" in qml


def test_expone_toggle_dark(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    assert "property bool dark: false" in qml


def test_color_selecciona_tabla_clara_u_oscura_segun_dark(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    assert "readonly property var color: dark ? _colorDark : _colorLight" in qml


def test_valor_no_sobrescrito_en_dark_se_mantiene_igual(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    claro = _extraer_bloque_var(qml, "_colorLight")
    oscuro = _extraer_bloque_var(qml, "_colorDark")
    assert claro["module"]["cycle"] == "#009933"
    assert oscuro["module"]["cycle"] == "#009933"


def test_valor_sobrescrito_en_dark_difiere_del_claro(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    claro = _extraer_bloque_var(qml, "_colorLight")
    oscuro = _extraer_bloque_var(qml, "_colorDark")
    assert claro["surface"]["card"] == "#FFFFFF"
    assert oscuro["surface"]["card"] == "#16202B"
    assert claro["primary"]["700"] == "#0D53C4"
    assert oscuro["primary"]["700"] == "#0D53C4"  # no overriden en dark, se conserva


def test_grupos_no_relacionados_con_color_se_exponen_verbatim(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    space = _extraer_bloque_var(qml, "space")
    radius = _extraer_bloque_var(qml, "radius")
    assert space == {"1": 4, "2": 8}
    assert radius == {"xs": 4}


def test_excluye_meta_y_contrast(tokens_minimos):
    qml = generar_tokens_qml(tokens_minimos)
    assert "contrast" not in qml
    assert "$meta" not in qml


# ── extraer_stops_gradiente ──────────────────────────────────────────────
# tokens.json solo trae los gradientes como cadena CSS. QtQuick/Qt5Compat
# necesitan los stops como lista {position, color} para construir un
# Gradient — de ahí este parser, consumido por generar_tokens_qml para
# emitir "gradientStops" sin que ningún componente tenga que declarar
# hexadecimales propios (§0.2 del sistema de diseño).

def test_extrae_stops_de_gradiente_lineal():
    css = "linear-gradient(135deg,#233348 0%,#2C4B70 55%,#3A6397 100%)"
    assert extraer_stops_gradiente(css) == [
        {"position": 0.0, "color": "#233348"},
        {"position": 0.55, "color": "#2C4B70"},
        {"position": 1.0, "color": "#3A6397"},
    ]


def test_extrae_stops_de_gradiente_radial_ignora_los_parametros_de_forma():
    css = "radial-gradient(90% 70% at 32% 34%,#63A3D8 0%,#3B669A 34%,#244463 62%,#1B222A 100%)"
    assert extraer_stops_gradiente(css) == [
        {"position": 0.0, "color": "#63A3D8"},
        {"position": 0.34, "color": "#3B669A"},
        {"position": 0.62, "color": "#244463"},
        {"position": 1.0, "color": "#1B222A"},
    ]


def test_extrae_stops_con_color_rgba():
    css = "linear-gradient(180deg,rgba(6,18,32,.46) 0%,rgba(6,18,32,0) 100%)"
    assert extraer_stops_gradiente(css) == [
        {"position": 0.0, "color": "rgba(6,18,32,.46)"},
        {"position": 1.0, "color": "rgba(6,18,32,0)"},
    ]


def test_generar_tokens_qml_expone_gradientstops(tokens_minimos):
    tokens_minimos["gradient"] = {
        "splash": "radial-gradient(90% 70% at 32% 34%,#63A3D8 0%,#1B222A 100%)"
    }
    qml = generar_tokens_qml(tokens_minimos)
    stops = _extraer_bloque_var(qml, "gradientStops")
    assert stops == {
        "splash": [
            {"position": 0.0, "color": "#63A3D8"},
            {"position": 1.0, "color": "#1B222A"},
        ]
    }
