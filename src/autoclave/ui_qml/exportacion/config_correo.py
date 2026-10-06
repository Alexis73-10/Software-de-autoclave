# ui_qml/exportacion/config_correo.py
#
# Configuración del envío de ciclos por correo desde el Historial del Menú
# Principal. PROVISIONAL hasta la pantalla de Configuración (con usuario y
# contraseña, por construir): remitente, servidor SMTP y destinos por defecto
# se leen de config/correo.json; la contraseña de aplicación del remitente, del
# almacén de credenciales de Windows (keyring), en la misma entrada que usaba
# el diálogo de correo de PySide (ui_pyside/views/_email_dialog.py).
# TODO(configuracion): leer y editar esto desde la pantalla de Configuración.
#
# Guardar la contraseña:  python -m autoclave.ui_qml.exportacion.config_correo

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

RUTA = Path(resource_path("autoclave/config/correo.json"))
SERVICIO_KEYRING = "Especifika-Autoclave-Email"   # el mismo de _email_dialog.py

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def correo_valido(texto: str) -> bool:
    return bool(_CORREO.match(texto or ""))


def _contrasena_keyring(remitente: str) -> str | None:
    import keyring
    return keyring.get_password(SERVICIO_KEYRING, remitente)


@dataclass
class ConfigCorreo:
    remitente: str = ""
    servidor: str = ""
    puerto: int = 587
    destinos: list = field(default_factory=list)   # [{"nombre", "correo"}]
    contrasena: str | None = None

    @property
    def configurado(self) -> bool:
        return bool(self.remitente and self.servidor and self.contrasena)


def cargar(ruta: Path = RUTA, contrasena=_contrasena_keyring) -> ConfigCorreo:
    """Lee la configuración; un archivo ausente o dañado deja el correo sin
    configurar (el botón lo dice) en vez de fallar."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Configuración de correo no disponible (%s): %s", ruta, e)
        return ConfigCorreo()
    if not isinstance(datos, dict):
        return ConfigCorreo()

    destinos = [
        {"nombre": d["nombre"], "correo": d["correo"]}
        for d in datos.get("destinos") or []
        if isinstance(d, dict) and isinstance(d.get("nombre"), str) and d["nombre"]
        and correo_valido(d.get("correo"))
    ]
    remitente = datos.get("remitente") if isinstance(datos.get("remitente"), str) else ""
    puerto = datos.get("puerto")
    config = ConfigCorreo(
        remitente=remitente.strip(),
        servidor=str(datos.get("servidor_smtp") or "").strip(),
        puerto=puerto if isinstance(puerto, int) and not isinstance(puerto, bool) else 587,
        destinos=destinos,
    )
    if config.remitente:
        try:
            config.contrasena = contrasena(config.remitente) or None
        except Exception as e:
            logger.warning("No se pudo leer la contraseña del correo: %s", e)
    return config


def _guardar_contrasena() -> int:
    """Pide por consola la contraseña de aplicación del remitente y la guarda."""
    import getpass

    import keyring
    config = cargar(contrasena=lambda r: None)
    if not config.remitente:
        print(f"Falta el remitente en {RUTA}")
        return 1
    clave = getpass.getpass(f"Contraseña de aplicación de {config.remitente}: ")
    if not clave:
        print("No se guardó nada.")
        return 1
    keyring.set_password(SERVICIO_KEYRING, config.remitente, clave)
    print("Contraseña guardada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_guardar_contrasena())
