# tests/banco/hor_vertical_igual.py
#
# Tanda horizontal (9-nov): demuestra que el lienzo VERTICAL quedó idéntico al
# de dev. Captura todos los escenarios de tests/banco/hor_capturas.py a
# 1200x1920 (vertical) con el árbol de dev (--dev, un worktree de dev) y con
# este árbol, y compara las imágenes píxel a píxel. Se ignora solo la franja
# del reloj de la barra superior (y < 190), que cambia de minuto entre corridas.
# No es una prueba automática.
#
#   python tests/banco/hor_vertical_igual.py --dev <worktree de dev> [--escenarios a b]
#
# Deja resumen en docs/informes/horizontal/vertical_igual.json.

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
FRANJA_RELOJ = 190


def capturar(raiz: Path, destino: Path, escenarios, tamano: str) -> None:
    cmd = [sys.executable, str(RAIZ / "tests" / "banco" / "hor_capturas.py"), "--temas", "claro",
           "--tamano", tamano, "--destino", str(destino), "--raiz", str(raiz)]
    if escenarios:
        cmd += ["--escenarios", *escenarios]
    subprocess.run(cmd, check=False)


def comparar(a: Path, b: Path) -> dict:
    ia = np.asarray(Image.open(a).convert("RGB"), dtype=np.int16)
    ib = np.asarray(Image.open(b).convert("RGB"), dtype=np.int16)
    if ia.shape != ib.shape:
        return {"igual": False, "motivo": f"tamaño {ia.shape} vs {ib.shape}"}
    d = np.abs(ia - ib).max(axis=2)
    d[:FRANJA_RELOJ, :] = 0
    distintos = int((d > 8).sum())
    if distintos == 0:
        return {"igual": True}
    ys, xs = np.nonzero(d > 8)
    return {"igual": False, "pixeles": distintos,
            "caja": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", required=True)
    ap.add_argument("--escenarios", nargs="*", default=None)
    ap.add_argument("--tamano", default="1200x1920")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="hor_vertical_"))
    capturar(Path(a.dev), tmp / "dev", a.escenarios, a.tamano)
    capturar(RAIZ, tmp / "rama", a.escenarios, a.tamano)
    resumen = {}
    for f in sorted((tmp / "dev").glob("hor_claro_*.png")):
        g = tmp / "rama" / f.name
        nombre = f.stem[len("hor_claro_"):]
        resumen[nombre] = comparar(f, g) if g.exists() else {"igual": False, "motivo": "sin captura"}
        print(nombre, resumen[nombre])
    salida = RAIZ / "docs" / "informes" / "horizontal" / "vertical_igual.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"tamano": a.tamano, "carpeta": str(tmp), "resultado": resumen},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    malos = [n for n, r in resumen.items() if not r["igual"]]
    print("DISTINTOS:", malos or "ninguno")
    return 1 if malos else 0


if __name__ == "__main__":
    raise SystemExit(main())
