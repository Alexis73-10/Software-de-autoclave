# tests/test_hor_d_contraste.py
#
# Tanda horizontal, grupo D (ronda 2): contraste WCAG en el tema oscuro del
# texto de los botones y chips de Opciones con relleno distinto del de acción
# primaria (naranja, verde, rojo de peligro, gris secundario). En horizontal
# ese texto va con Colores.fondoTarjeta (blanco en claro, igual que
# textoSobreAccion, así el claro no cambia; azul marino en oscuro). En el
# vertical oscuro sigue el blanco: preexistente, pendiente de decisión.

import re
from pathlib import Path

import pytest

from tests.test_tema_oscuro import _colores, _contraste

QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas"

# (archivo, relleno, mínimo): texto de 20 a 28 px de diseño seminegrita;
# 22 px o menos es texto normal (4,5:1), 24 px o más, grande (3:1)
PARES = [
    ("OpcionesCalibracionAtm.qml", "peligroTexto", 3.0),        # Cancelar (28 px)
    ("OpcionesCalibracionAtm.qml", "textoSecundario", 3.0),     # Descartar (28 px)
    ("OpcionesCalibracionSensor.qml", "menuNaranja", 4.5),      # Restaurar (22 px)
    ("OpcionesEntradasSalidas.qml", "peligroTexto", 4.5),       # Salir del modo prueba, apagar (22 px)
    ("OpcionesReasignacion.qml", "textoSecundario", 4.5),       # Descartar (21 px)
    ("OpcionesReasignacion.qml", "menuNaranja", 4.5),           # Restaurar fábrica (21 px)
    ("OpcionesReasignacion.qml", "peligroTexto", 4.5),          # Aplicar (21 px)
    ("OpcionesRespaldo.qml", "menuVerde", 4.5),                 # chip Válido (20 px)
]


@pytest.mark.parametrize("archivo,relleno,minimo", PARES)
def test_texto_sobre_relleno_en_oscuro_cumple_wcag(archivo, relleno, minimo):
    c = _colores()
    texto = (QML / archivo).read_text(encoding="utf-8")
    # el relleno se usa en el archivo y el texto horizontal va con fondoTarjeta
    assert f"Colores.{relleno}" in texto
    assert re.search(r"Escala\.horizontal\b[^\n]*\n?[^\n]*Colores\.fondoTarjeta", texto)
    antes = _contraste(c["textoSobreAccion"][1], c[relleno][1])
    despues = _contraste(c["fondoTarjeta"][1], c[relleno][1])
    assert despues >= minimo, (archivo, relleno, round(antes, 2), round(despues, 2))
    assert despues > antes


def test_el_claro_no_cambia():
    # en claro, fondoTarjeta es el mismo blanco que textoSobreAccion
    c = _colores()
    assert c["fondoTarjeta"][0] == c["textoSobreAccion"][0] == "#FFFFFFFF"
