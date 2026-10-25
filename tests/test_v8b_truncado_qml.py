"""V8b (tanda 8, D8-5.4): la revisión de truncado de I4 (que corre en inglés,
test_i4_truncado_qml.py) también en español, a 1024 px de ancho: ninguna
pantalla recorta (elide) ni desborda un texto visible.

Capturas de todas las pantallas en es y en: `python tests/banco/v8b_capturas.py`
(las guarda en docs/informes/tanda8/capturas/v8b/)."""

import pytest

pytest.importorskip("PySide6")

from tests.banco.i4_truncado_banco import PANTALLAS, revisar  # noqa: E402


@pytest.mark.parametrize("pantalla", PANTALLAS)
def test_sin_textos_truncados_en_espanol_a_1024(pantalla):
    r = revisar(pantalla, "es")
    assert r["malos"] == [], r["malos"]
    assert r["vistos"] or pantalla == "IntroArranque", "la pantalla no mostró ningún texto: el banco no la cargó"
