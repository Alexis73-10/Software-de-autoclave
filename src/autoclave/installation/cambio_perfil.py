# autoclave/installation/cambio_perfil.py
#
# Escritura auditada de un campo de installation_profile.json desde las
# herramientas del ingeniero (tools/declarar_*.py). El perfil está `locked` y
# la aplicación no lo modifica: estas herramientas corren con el software
# cerrado (adenda E0/E1, A-6 / SAF-05).
#
# Cada cambio: valida el perfil resultante, pide confirmación, deja un
# respaldo `installation_profile.json.<fecha>.bak` y agrega una línea JSON a
# `installation_profile_cambios.log` (junto al perfil) con fecha, usuario del
# sistema, herramienta, campo, valor anterior y valor nuevo.

import getpass
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from autoclave.installation.profile import validate_profile_data

NOMBRE_REGISTRO = "installation_profile_cambios.log"


class CambioCancelado(Exception):
    """El ingeniero no confirmó el cambio (o no hay terminal para preguntar)."""


def ruta_registro(perfil: Path) -> Path:
    return perfil.with_name(NOMBRE_REGISTRO)


def confirmar(resumen: str, entrada: Callable[[str], str] | None = None) -> bool:
    """Muestra el resumen y pide escribir SI. Sin terminal (EOF) = no."""
    print(resumen)
    try:
        respuesta = (entrada or input)("¿Aplicar el cambio? Escriba SI para confirmar: ")
    except EOFError:
        return False
    return respuesta.strip().upper() == "SI"


def escribir_campo(perfil: Path, campo: str, valor: dict, herramienta: str,
                   confirmado: bool = False) -> dict:
    """Escribe `campo` = `valor` en el perfil. Lanza ValueError si el perfil
    quedaría inválido y CambioCancelado si no se confirma. Devuelve el valor
    escrito. Con `confirmado=True` no pregunta (opción --si)."""
    data = json.loads(perfil.read_text(encoding="utf-8"))
    antes = data.get(campo)
    data[campo] = valor

    errores = validate_profile_data(data)
    if errores:
        raise ValueError("El perfil quedaría inválido: " + "; ".join(errores))

    if not confirmado:
        resumen = (f"Perfil: {perfil}\nCampo: {campo}\n"
                   f"Antes:   {json.dumps(antes, ensure_ascii=False)}\n"
                   f"Después: {json.dumps(valor, ensure_ascii=False)}")
        if not confirmar(resumen):
            raise CambioCancelado("Cambio no confirmado: el perfil no se modificó")

    respaldo = perfil.with_name(f"{perfil.name}.{datetime.now():%Y%m%d-%H%M%S}.bak")
    shutil.copy2(perfil, respaldo)
    perfil.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    registro = {
        "fecha": datetime.now().isoformat(timespec="seconds"),   # sello de auditoría
        "usuario": _usuario(),
        "herramienta": herramienta,
        "perfil": str(perfil),
        "campo": campo,
        "antes": antes,
        "despues": valor,
        "respaldo": respaldo.name,
    }
    with ruta_registro(perfil).open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return valor


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "desconocido"
