"""D8-3.18 (tanda 8): comprueba que la compilación lleva la calibración NEUTRA.

Uso: python tools/verificar_calibracion_neutra.py <carpeta dist/Autoclave>

Compara, byte a byte, `_internal/autoclave/config/calibration.yaml` de la
carpeta compilada con `src/autoclave/config/plantillas/calibration_neutra.yaml`.
Sale con 0 si son iguales y con 1 (y el motivo) si falta o difiere: la entrega
no se publica con la calibración del banco."""
import hashlib
import sys
from pathlib import Path

PLANTILLA = (Path(__file__).resolve().parents[1]
             / "src" / "autoclave" / "config" / "plantillas" / "calibration_neutra.yaml")


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    empaquetada = Path(argv[1]) / "_internal" / "autoclave" / "config" / "calibration.yaml"
    if not empaquetada.is_file():
        print(f"FALLA: no existe {empaquetada}")
        return 1
    if empaquetada.read_bytes() != PLANTILLA.read_bytes():
        print(f"FALLA: {empaquetada} no es la plantilla neutra "
              f"(sha256 {_sha(empaquetada)} frente a {_sha(PLANTILLA)})")
        return 1
    print(f"OK: calibración neutra empaquetada (sha256 {_sha(empaquetada)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
