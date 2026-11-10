# tests/banco/resp_hojas.py
#
# Tanda responsive (10-nov): a partir de una carpeta de tests/banco/resp_capturas.py
# arma, por tamaño y tema, una hoja de contacto con todas las pantallas
# (hoja_<WxH>_<tema>.png) y copias reducidas de cada captura
# (<WxH>/<tema>_<escenario>.png, lado mayor --lado px), para el informe. No es
# una prueba automática.
#
#   python tests/banco/resp_hojas.py <carpeta de capturas> <destino> [--lado 720]

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("origen")
    ap.add_argument("destino")
    ap.add_argument("--lado", type=int, default=720)
    ap.add_argument("--hoja", type=int, default=360, help="lado mayor de cada miniatura en la hoja")
    ap.add_argument("--escenarios", nargs="*", default=None, help="solo estos (por defecto, todos)")
    a = ap.parse_args()
    origen, destino = Path(a.origen), Path(a.destino)
    destino.mkdir(parents=True, exist_ok=True)
    for carpeta in sorted(p for p in origen.iterdir() if p.is_dir() and "@" in p.name):
        tam = carpeta.name[:-2] if carpeta.name.endswith("@1") else carpeta.name.replace("@", "_a_")
        for tema in ("claro", "oscuro"):
            fs = sorted(carpeta.glob(f"hor_{tema}_*.png"))
            if a.escenarios:
                fs = [f for f in fs if f.stem[len(f"hor_{tema}_"):] in a.escenarios]
            if not fs:
                continue
            (destino / tam).mkdir(exist_ok=True)
            ims = []
            for f in fs:
                im = Image.open(f).convert("RGB")
                esc = f.stem[len(f"hor_{tema}_"):]
                r = a.lado / max(im.size)
                im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS).save(
                    destino / tam / f"{tema}_{esc}.png", optimize=True)
                ims.append((esc, im))
            w, h = ims[0][1].size
            s = a.hoja / max(w, h)
            tw, th = round(w * s), round(h * s)
            cols = 6 if w < h else 4
            filas = (len(ims) + cols - 1) // cols
            hoja = Image.new("RGB", (cols * (tw + 8), filas * (th + 22)), "white")
            d = ImageDraw.Draw(hoja)
            for i, (esc, im) in enumerate(ims):
                x, y = (i % cols) * (tw + 8), (i // cols) * (th + 22)
                hoja.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 20))
                d.text((x, y + 4), esc, fill="black")
            hoja.save(destino / f"hoja_{tam}_{tema}.png", optimize=True)
            print("hoja", tam, tema, len(ims))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
