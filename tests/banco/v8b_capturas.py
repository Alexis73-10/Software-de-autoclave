# tests/banco/v8b_capturas.py
#
# V8b (tanda 8, D8-5.4 y D8-5.11): capturas de todas las pantallas del banco
# de I4 en español y en inglés (1024x1638, offscreen, sin backend) y resumen
# de textos recortados o desbordados. Uso:
#
#     python tests/banco/v8b_capturas.py
#
# Deja V8b_<idioma>_<pantalla>.png y resumen.json en
# docs/informes/tanda8/capturas/v8b/.

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from tests.banco.i4_truncado_banco import PANTALLAS, revisar  # noqa: E402

CARPETA = RAIZ / "docs" / "informes" / "tanda8" / "capturas" / "v8b"

if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    resumen = {}
    for idioma in ("es", "en"):
        for nombre in PANTALLAS:
            r = revisar(nombre, idioma, captura=True, carpeta=CARPETA, prefijo="V8b")
            resumen[f"{idioma}/{nombre}"] = {"malos": r["malos"], "textos_vistos": len(r["vistos"])}
            print(idioma, nombre, json.dumps(r["malos"], ensure_ascii=False))
    (CARPETA / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
