# tools/generar_assets_arranque.py
#
# Genera los PNG con alfa de la intro de arranque (planeacion_animacion_arranque.md
# §5.6 y §7): la intro no usa blur en tiempo real, así que el halo y las volutas
# se renderizan aquí una vez y se versionan en assets/fondos/.
#
#   halo_arranque.png  512 x 512   radial fondoCieloNucleo (#5C97DB) -> transparente
#   voluta_vapor.png   256 x 512   blanca, alfa suave (la intro la usa a opacidad <= 6 %)
#
# Uso (desde la raíz del repo):
#   python tools/generar_assets_arranque.py
#   python tools/generar_assets_arranque.py --destino OTRA_CARPETA

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

DESTINO = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "assets" / "fondos"

# Colores.fondoCieloNucleo (qml/Tema/Colores.qml)
CIELO_NUCLEO = (0x5C, 0x97, 0xDB)


def halo(lado: int = 512) -> Image.Image:
    """Núcleo opaco que se desvanece hasta 0 en el borde del círculo inscrito."""
    c = (lado - 1) / 2
    y, x = np.mgrid[0:lado, 0:lado]
    r = np.hypot(x - c, y - c) / (lado / 2)            # 0 en el centro, 1 en el borde
    alfa = np.exp(-(r / 0.42) ** 2)                    # caída gaussiana suave
    alfa *= np.clip((1 - r) / 0.15, 0, 1)              # llega a 0 exacto antes del borde
    rgba = np.zeros((lado, lado, 4), np.uint8)
    rgba[..., :3] = CIELO_NUCLEO
    rgba[..., 3] = np.round(alfa * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def voluta(ancho: int = 256, alto: int = 512) -> Image.Image:
    """Hilo de vapor vertical: manchas gaussianas a lo largo de una curva en S,
    más anchas y tenues hacia arriba."""
    y, x = np.mgrid[0:alto, 0:ancho].astype(float)
    alfa = np.zeros((alto, ancho))
    for i in range(48):
        s = i / 47                                      # 0 abajo, 1 arriba
        cy = alto * (0.92 - 0.84 * s)
        cx = ancho * (0.5 + 0.18 * np.sin(s * 2.6 * np.pi))
        radio = ancho * (0.07 + 0.16 * s)
        peso = np.sin(np.pi * min(1.0, s * 1.15)) ** 0.8   # nace y se disipa
        alfa = np.maximum(alfa, peso * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * radio ** 2)))
    # sin bordes duros en el contorno de la imagen
    borde = np.minimum.reduce([x, ancho - 1 - x, y, alto - 1 - y]) / 24
    alfa *= np.clip(borde, 0, 1)
    rgba = np.full((alto, ancho, 4), 255, np.uint8)
    rgba[..., 3] = np.round(alfa / alfa.max() * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Genera los PNG de la intro de arranque")
    parser.add_argument("--destino", type=Path, default=DESTINO)
    args = parser.parse_args(argv)
    args.destino.mkdir(parents=True, exist_ok=True)
    halo().save(args.destino / "halo_arranque.png", optimize=True)
    voluta().save(args.destino / "voluta_vapor.png", optimize=True)
    print(f"PNG generados en {args.destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
