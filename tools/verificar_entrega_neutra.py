"""D9-7 (tanda 9): comprueba que la compilación no lleva datos precargados del banco.

Uso: python tools/verificar_entrega_neutra.py <carpeta dist/Autoclave>

Comprueba, en `_internal/autoclave/` de la carpeta compilada:
  1. `config/correo.json` es la plantilla neutra (`config/plantillas/correo_neutro.json`,
     byte a byte) y además no tiene remitente ni destinatarios;
  2. `cycles/` solo contiene `factory/` (ni `user/`, ni `defecto/`, ni archivos
     sueltos) y `factory/` tiene al menos un programa;
  3. la calibración Modbus es la neutra y no viaja la serial retirada (D8-3.18,
     T20-03; tools/verificar_calibracion_neutra.py).
Sale con 0 si todo se cumple, con 1 (y los motivos) si algo falla, con 2 si el
uso es incorrecto. La entrega no se publica si sale distinto de 0."""
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA_CORREO = RAIZ / "src" / "autoclave" / "config" / "plantillas" / "correo_neutro.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verificar_calibracion_neutra  # noqa: E402


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def fallas_correo(interno: Path) -> list[str]:
    correo = interno / "config" / "correo.json"
    if not correo.is_file():
        return [f"FALLA: no existe {correo}"]
    fallas = []
    if correo.read_bytes() != PLANTILLA_CORREO.read_bytes():
        fallas.append(f"FALLA: {correo} no es la plantilla neutra de correo "
                      f"(sha256 {_sha(correo)} frente a {_sha(PLANTILLA_CORREO)})")
    try:
        datos = json.loads(correo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return fallas + [f"FALLA: {correo} ilegible: {e}"]
    if not isinstance(datos, dict):
        return fallas + [f"FALLA: {correo} no es un objeto JSON"]
    if datos.get("remitente"):
        fallas.append(f"FALLA: el correo empaquetado tiene remitente ({datos['remitente']!r})")
    if datos.get("destinos"):
        fallas.append(f"FALLA: el correo empaquetado tiene {len(datos['destinos'])} destinatario(s)")
    return fallas


def fallas_ciclos(interno: Path) -> list[str]:
    ciclos = interno / "cycles"
    if not ciclos.is_dir():
        return [f"FALLA: no existe {ciclos}"]
    fallas = [f"FALLA: sobra {p.relative_to(interno)} (solo va cycles/factory)"
              for p in sorted(ciclos.iterdir()) if p.name != "factory"]
    if not list((ciclos / "factory").glob("*.json")):
        fallas.append(f"FALLA: {ciclos / 'factory'} sin programas de fábrica")
    return fallas


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    dist = Path(argv[1])
    interno = dist / "_internal" / "autoclave"
    fallas = fallas_correo(interno) + fallas_ciclos(interno)
    for f in fallas:
        print(f)
    calibracion = verificar_calibracion_neutra.main([argv[0], str(dist)])
    if fallas or calibracion != 0:
        return 1
    programas = sorted(p.name for p in (interno / "cycles" / "factory").glob("*.json"))
    print(f"OK: correo neutro (sha256 {_sha(interno / 'config' / 'correo.json')}) "
          f"y solo cycles/factory ({len(programas)} programas: {', '.join(programas)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
