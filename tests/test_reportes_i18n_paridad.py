"""Claves i18n de la pantalla Reportes: existencia, paridad es/en y vocabulario."""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
I18N = RAIZ / "src" / "autoclave" / "i18n"
CLAVES = RAIZ / "docs" / "informes" / "dashboard_reportes" / "claves_i18n_reportes.json"
PROHIBIDAS = re.compile(r"\b(conforme|apto)\b", re.IGNORECASE)


def _plano(o, p=""):
    for k, v in o.items():
        if isinstance(v, dict):
            yield from _plano(v, p + k + ".")
        else:
            yield p + k, v


def _textos(idioma):
    d = json.loads((I18N / f"{idioma}.json").read_text(encoding="utf-8"))
    return dict(_plano(d))


def test_claves_del_informe_en_ambos_idiomas():
    claves = json.loads(CLAVES.read_text(encoding="utf-8"))
    for idioma in ("es", "en"):
        textos = _textos(idioma)
        faltan = [k for k, v in claves[idioma].items() if textos.get(k) != v]
        assert not faltan, (idioma, faltan)


def test_paridad_reportes():
    es = {k for k in _textos("es") if k.startswith("reportes.")}
    en = {k for k in _textos("en") if k.startswith("reportes.")}
    assert es == en, sorted(es ^ en)


def test_reportes_sin_palabras_prohibidas():
    for idioma in ("es", "en"):
        for k, v in _textos(idioma).items():
            if k.startswith("reportes.") and isinstance(v, str):
                assert not PROHIBIDAS.search(v), (idioma, k, v)
