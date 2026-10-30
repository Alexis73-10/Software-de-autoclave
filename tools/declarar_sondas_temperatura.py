# tools/declarar_sondas_temperatura.py
#
# Declara en installation_profile.json qué canales de temperatura tienen
# sonda instalada (adenda E0/E1, A-2). Un canal sin sonda no se vigila
# (sin ERROR_AI_* ni bloqueo). Mismo patrón que declarar_entradas_suministro.
#
# Uso (desde la raíz del repo o junto al .exe, con el software cerrado):
#   python tools/declarar_sondas_temperatura.py --instaladas temp_camara temp_ref
#   python tools/declarar_sondas_temperatura.py --instaladas temp_camara --perfil RUTA
#   python tools/declarar_sondas_temperatura.py --mostrar
#
# Los canales no listados quedan en False ("sin sonda"). temp_camara es la
# sonda de control y debe estar siempre en la lista. Antes de escribir muestra
# el cambio y pide escribir SI (--si lo omite). Deja respaldo .bak, valida y
# registra el cambio en `installation_profile_cambios.log` (auditoría).

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autoclave.installation.cambio_perfil import CambioCancelado, escribir_campo  # noqa: E402
from autoclave.installation.profile import (  # noqa: E402
    TEMPERATURE_PROBE_KEYS,
    normalizar_temperature_probes,
)

HERRAMIENTA = "declarar_sondas_temperatura"


def declarar(perfil: Path, instaladas: list[str], confirmado: bool = False) -> dict:
    """Escribe temperature_probes en `perfil`. Lanza ValueError si un canal no
    existe o el perfil queda inválido (p. ej. sin temp_camara);
    CambioCancelado si no se confirma."""
    desconocidas = sorted(set(instaladas) - set(TEMPERATURE_PROBE_KEYS))
    if desconocidas:
        raise ValueError(f"Canales desconocidos: {desconocidas}. "
                         f"Válidos: {list(TEMPERATURE_PROBE_KEYS)}")

    valor = {k: (k in instaladas) for k in TEMPERATURE_PROBE_KEYS}
    return escribir_campo(perfil, "temperature_probes", valor, HERRAMIENTA,
                          confirmado=confirmado)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", type=Path, default=None,
                        help="Ruta de installation_profile.json (por defecto, la del equipo)")
    parser.add_argument("--instaladas", nargs="*", default=None,
                        help=f"Canales con sonda, de: {', '.join(TEMPERATURE_PROBE_KEYS)}")
    parser.add_argument("--si", action="store_true", help="No pedir confirmación")
    parser.add_argument("--mostrar", action="store_true", help="Solo muestra el valor actual")
    args = parser.parse_args(argv)

    perfil = args.perfil
    if perfil is None:
        from autoclave.installation.storage import INSTALLATION_FILE
        perfil = INSTALLATION_FILE

    if args.mostrar or args.instaladas is None:
        data = json.loads(perfil.read_text(encoding="utf-8"))
        print(json.dumps(normalizar_temperature_probes(data.get("temperature_probes")), indent=2))
        return 0

    try:
        escrito = declarar(perfil, args.instaladas, confirmado=args.si)
    except (ValueError, CambioCancelado) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Perfil actualizado: {perfil}")
    print(json.dumps(escrito, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
