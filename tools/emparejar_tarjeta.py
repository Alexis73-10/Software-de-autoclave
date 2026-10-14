# tools/emparejar_tarjeta.py
#
# Registra en installation_profile.json el ID de la tarjeta de E/S (ESP32)
# emparejada con el equipo (FW-D7, planeacion_firmware_1_5.md). Lo usa el
# ingeniero en la instalación: el perfil está `locked` y la aplicación no lo
# modifica. El ID es la MAC de fábrica del chip, 12 dígitos hexadecimales, que
# la tarjeta informa al arrancar (`BOOT 1.0.0 2 <ID>`, monitor serie a 115200)
# y que se muestra en Información del sistema.
#
# Uso (desde la raíz del repo o junto al .exe, con el software cerrado):
#   python tools/emparejar_tarjeta.py --id A1B2C3D4E5F6
#   python tools/emparejar_tarjeta.py --id A1B2C3D4E5F6 --perfil RUTA
#   python tools/emparejar_tarjeta.py --mostrar
#
# En la versión 1.0 una tarjeta distinta o sin registrar es solo una
# advertencia no bloqueante (audit_log + Información del sistema).
# Antes de escribir muestra el cambio y pide escribir SI (--si lo omite).
# Conserva el resto de campos del perfil tal cual, deja una copia
# `installation_profile.json.<fecha>.bak`, valida antes de escribir y
# registra el cambio en `installation_profile_cambios.log` (auditoría).

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autoclave.installation.cambio_perfil import CambioCancelado, escribir_campo  # noqa: E402
from autoclave.installation.profile import board_id_valido  # noqa: E402

HERRAMIENTA = "emparejar_tarjeta"


def emparejar(perfil: Path, id_tarjeta: str, confirmado: bool = False) -> str:
    """Escribe board_id en `perfil`. Devuelve el ID escrito (en mayúscula).
    Lanza ValueError si el ID no es válido o el perfil queda inválido;
    CambioCancelado si no se confirma."""
    ident = id_tarjeta.strip().upper()
    if not board_id_valido(ident):
        raise ValueError(f"ID de tarjeta inválido {id_tarjeta!r}: se esperan 12 dígitos "
                         f"hexadecimales (ej. A1B2C3D4E5F6)")
    return escribir_campo(perfil, "board_id", ident, HERRAMIENTA, confirmado=confirmado)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", type=Path, default=None,
                        help="Ruta de installation_profile.json (por defecto, la del equipo)")
    parser.add_argument("--id", dest="id_tarjeta", default=None,
                        help="ID de la tarjeta (12 dígitos hex, del BOOT o de Información del sistema)")
    parser.add_argument("--si", action="store_true", help="No pedir confirmación")
    parser.add_argument("--mostrar", action="store_true", help="Solo muestra el valor actual")
    args = parser.parse_args(argv)

    perfil = args.perfil
    if perfil is None:
        from autoclave.installation.storage import INSTALLATION_FILE
        perfil = INSTALLATION_FILE

    if args.mostrar or args.id_tarjeta is None:
        data = json.loads(perfil.read_text(encoding="utf-8"))
        print(data.get("board_id") or "sin registrar")
        return 0

    try:
        escrito = emparejar(perfil, args.id_tarjeta, confirmado=args.si)
    except (ValueError, CambioCancelado) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Perfil actualizado: {perfil}")
    print(f"board_id: {escrito}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
