# tools/secretos/generar_secretos.py
#
# LIC-01 (licencia L0): crea el archivo de secretos de activación con dos
# secretos aleatorios nuevos (32 bytes cada uno, `secrets.token_bytes`).
#
#     python tools\secretos\generar_secretos.py
#
# Ruta: %USERPROFILE%\Documents\especifika_secretos\activacion.json, o la de la
# variable de entorno ESPECIFIKA_SECRETOS. Se niega si el archivo ya existe
# (rotar de nuevo invalida todos los códigos del generador). No imprime los
# valores: solo la ruta y la huella corta de cada secreto, que debe coincidir
# con la que muestran la compilación y la página de administración del
# generador.

import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from autoclave.installation import secretos as _secretos  # noqa: E402


def generar(ruta: Path | None = None) -> int:
    ruta = Path(ruta) if ruta else _secretos.ruta_archivo_secretos()
    if ruta.exists():
        print(f"Ya existe {ruta}: no se sobrescribe. Si de verdad hay que rotar "
              f"otra vez, muévalo a otro lugar y vuelva a ejecutar.", file=sys.stderr)
        return 1
    instalacion, fabrica = secrets.token_bytes(32), secrets.token_bytes(32)
    contenido = {"version": _secretos.VERSION,
                 "instalacion": instalacion.hex(), "fabrica": fabrica.hex()}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # 'x': falla si otro proceso lo creó entre la comprobación y la escritura
    with open(ruta, "x", encoding="utf-8") as f:
        json.dump(contenido, f)
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass
    print(f"Archivo de secretos creado: {ruta}")
    print(f"Huella instalación: {_secretos.huella(instalacion)}")
    print(f"Huella fábrica:     {_secretos.huella(fabrica)}")
    print("Guarde una copia fuera de este PC (USB que no quede conectada).")
    return 0


if __name__ == "__main__":
    sys.exit(generar(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
