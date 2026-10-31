"""I4 (tanda 6): en inglés, a 1024 px de ancho, ninguna pantalla QML trunca ni
desborda un texto visible. Con TANDA6_CAPTURAS=1 guarda también las capturas
I4_en_*.png (las es/en completas: `python tests/banco/i4_truncado_banco.py`)."""

import os

import pytest

pytest.importorskip("PySide6")

from tests.banco.i4_truncado_banco import PANTALLAS, revisar  # noqa: E402


@pytest.mark.parametrize("pantalla", PANTALLAS)
def test_sin_textos_truncados_en_ingles_a_1024(pantalla):
    r = revisar(pantalla, "en", captura=os.environ.get("TANDA6_CAPTURAS") == "1")
    assert r["malos"] == [], r["malos"]
    # IntroArranque es una animación: a los 0,7 s aún no muestra textos
    assert r["vistos"] or pantalla == "IntroArranque", "la pantalla no mostró ningún texto: el banco no la cargó"
