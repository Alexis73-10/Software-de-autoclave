# tools/declarar_entradas_suministro.py
#
# Declara en installation_profile.json qué entradas de suministro tiene
# cableadas el equipo (E1-1, CR-FC-02). Lo usa el ingeniero en la
# instalación: el perfil está `locked` y la aplicación no lo modifica.
#
# Uso (desde la raíz del repo o junto al .exe, con el software cerrado):
#   python tools/declarar_entradas_suministro.py --cableadas aire_comprimido
#   python tools/declarar_entradas_suministro.py --cableadas aire_comprimido --perfil RUTA
#   python tools/declarar_entradas_suministro.py --mostrar
#   python tools/declarar_entradas_suministro.py --cableadas --permitir-ninguna   (ninguna)
#
# Las entradas no listadas en --cableadas quedan en False ("no aplica").
# Una lista vacía (las cinco sin vigilar) exige --permitir-ninguna (A-6).
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
from autoclave.installation.profile import (  # noqa: E402
    SUPPLY_INPUT_KEYS,
    normalizar_supply_inputs,
)

HERRAMIENTA = "declarar_entradas_suministro"


def declarar(perfil: Path, cableadas: list[str], permitir_ninguna: bool = False,
             confirmado: bool = False) -> dict:
    """Escribe supply_inputs en `perfil`. Devuelve el diccionario escrito.
    Lanza ValueError si una clave no existe, si la lista está vacía sin
    `permitir_ninguna` o si el perfil queda inválido; CambioCancelado si no
    se confirma."""
    desconocidas = sorted(set(cableadas) - set(SUPPLY_INPUT_KEYS))
    if desconocidas:
        raise ValueError(f"Entradas desconocidas: {desconocidas}. Válidas: {list(SUPPLY_INPUT_KEYS)}")
    if not cableadas and not permitir_ninguna:
        raise ValueError("--cableadas sin entradas dejaría las cinco sin vigilar. "
                         "Si es lo correcto, agregue --permitir-ninguna.")

    valor = {k: (k in cableadas) for k in SUPPLY_INPUT_KEYS}
    return escribir_campo(perfil, "supply_inputs", valor, HERRAMIENTA, confirmado=confirmado)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", type=Path, default=None,
                        help="Ruta de installation_profile.json (por defecto, la del equipo)")
    parser.add_argument("--cableadas", nargs="*", default=None,
                        help=f"Entradas cableadas, de: {', '.join(SUPPLY_INPUT_KEYS)}")
    parser.add_argument("--permitir-ninguna", action="store_true",
                        help="Acepta --cableadas vacío (ninguna entrada vigilada)")
    parser.add_argument("--si", action="store_true", help="No pedir confirmación")
    parser.add_argument("--mostrar", action="store_true", help="Solo muestra el valor actual")
    args = parser.parse_args(argv)

    perfil = args.perfil
    if perfil is None:
        from autoclave.installation.storage import INSTALLATION_FILE
        perfil = INSTALLATION_FILE

    if args.mostrar or args.cableadas is None:
        data = json.loads(perfil.read_text(encoding="utf-8"))
        print(json.dumps(normalizar_supply_inputs(data.get("supply_inputs")), indent=2))
        return 0

    try:
        escrito = declarar(perfil, args.cableadas, permitir_ninguna=args.permitir_ninguna,
                           confirmado=args.si)
    except (ValueError, CambioCancelado) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Perfil actualizado: {perfil}")
    print(json.dumps(escrito, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
