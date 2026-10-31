# tests/test_v8a_textos.py
#
# V8a (tanda 8): textos de catálogo pedidos en D8-5.

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
I18N = RAIZ / "src" / "autoclave" / "i18n"


def _cat(idioma: str) -> dict:
    return json.loads((I18N / f"{idioma}.json").read_text(encoding="utf-8"))


def test_d8_5_3_boton_registro_de_mantenimiento_dice_registrar():
    assert _cat("es")["opciones"]["mant_registrar"] == "Registrar"
    assert _cat("en")["opciones"]["mant_registrar"] == "Register"
