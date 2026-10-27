"""D8-3.18 (tanda 8): comprueba que la compilación lleva la calibración NEUTRA.

Uso: python tools/verificar_calibracion_neutra.py <carpeta dist/Autoclave>

Compara, byte a byte, `_internal/autoclave/config/calibration.yaml` de la
carpeta compilada con `src/autoclave/config/plantillas/calibration_neutra.yaml`.
Tanda 19 (MOD-04): si la compilación trae además la calibración del enlace
Modbus (`calibration_modbus.yaml`), su calibración de usuario debe ser neutra
(gain 1.0, offset 0.0, sin polinomio, 8 sensores por tipo) y la de fábrica
debe tener los 8 canales de cada tipo; si no la trae, solo se avisa (con el
enlace Modbus el programa no podría sembrar su copia en data/).
Sale con 0 si todo está bien y con 1 (y el motivo) si algo falta o difiere: la
entrega no se publica con la calibración del banco."""
import hashlib
import sys
from pathlib import Path

PLANTILLA = (Path(__file__).resolve().parents[1]
             / "src" / "autoclave" / "config" / "plantillas" / "calibration_neutra.yaml")
NOMBRE_MODBUS = "calibration_modbus.yaml"


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def errores_modbus_neutra(ruta: Path) -> list[str]:
    """Motivos por los que `ruta` (calibration_modbus.yaml) no es neutra."""
    import yaml
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        cal = datos["calibration"]
        user, factory = cal["user"], cal["factory"]
    except Exception as e:
        return [f"{ruta} ilegible ({type(e).__name__})"]
    errores = []
    for tipo in ("temperature", "pressure"):
        sensores = user.get(tipo) if isinstance(user, dict) else None
        if not isinstance(sensores, list) or len(sensores) != 8:
            errores.append(f"usuario {tipo}: se esperaban 8 sensores")
        else:
            for i, s in enumerate(sensores):
                if s != {"gain": 1.0, "offset": 0.0}:
                    errores.append(f"usuario {tipo}[{i}] no es neutro: {s!r}")
        canales = factory.get(tipo) if isinstance(factory, dict) else None
        if not isinstance(canales, list) or len(canales) != 8:
            errores.append(f"fábrica {tipo}: se esperaban 8 canales")
    return errores


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    config = Path(argv[1]) / "_internal" / "autoclave" / "config"
    empaquetada = config / "calibration.yaml"
    if not empaquetada.is_file():
        print(f"FALLA: no existe {empaquetada}")
        return 1
    if empaquetada.read_bytes() != PLANTILLA.read_bytes():
        print(f"FALLA: {empaquetada} no es la plantilla neutra "
              f"(sha256 {_sha(empaquetada)} frente a {_sha(PLANTILLA)})")
        return 1
    print(f"OK: calibración neutra empaquetada (sha256 {_sha(empaquetada)})")
    modbus = config / NOMBRE_MODBUS
    if not modbus.is_file():
        print(f"AVISO: no existe {modbus} (calibración del enlace Modbus)")
        return 0
    errores = errores_modbus_neutra(modbus)
    if errores:
        print(f"FALLA: {modbus} no es neutra: " + "; ".join(errores))
        return 1
    print(f"OK: calibración Modbus neutra empaquetada (sha256 {_sha(modbus)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
