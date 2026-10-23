# tests/u10a_capturas.py
#
# U10a (tanda 10): capturas de Preciclo y Ciclo en curso en es y en, a la
# resolución del banco CAP9 (1024x1638), con las 9 entradas en 3 grupos.
# Uso: PYTHONPATH=<worktree>/src python -X utf8 tests/u10a_capturas.py <antes|despues>
# (pytest no lo recoge). Deja los PNG en docs/informes/tanda10/capturas/u10a/.

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from tests.test_u10a_textos_caben_qml import PASOS, PUENTE  # noqa: E402
from tests.textos_caben_qml import revisar  # noqa: E402

CARPETA = RAIZ / "docs" / "informes" / "tanda10" / "capturas" / "u10a"
CORTO = {"PantallaPreciclo": "Preciclo", "PantallaCicloEnCurso": "Ciclo"}

if __name__ == "__main__":
    import autoclave
    print("autoclave:", autoclave.__file__)
    momento = sys.argv[1] if len(sys.argv) > 1 else "despues"
    CARPETA.mkdir(parents=True, exist_ok=True)
    for pantalla, corto in CORTO.items():
        for idioma in ("es", "en"):
            pasos = [dict(p, captura=str(CARPETA / f"U10a_{momento}_{corto}_{idioma}_grupo{n}.png"))
                     for n, p in enumerate(PASOS, 1)]
            r = revisar(pantalla, idioma, 1024, 1638, puente=PUENTE, pasos=pasos)
            n = sum(len(p["problemas"]) for p in r["pasos"])
            print(momento, pantalla, idioma, "problemas:", n, "avisos:", len(r["avisos"]))
