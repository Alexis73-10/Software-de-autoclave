# ui_qml/domain/recordar_usuario.py
#
# D9-12 (H9, tanda 9): "Recordar usuario" del inicio de sesión QML.
# Preferencia local de la interfaz: guarda SOLO el nombre de usuario (nunca la
# contraseña ni el token) en data/login_recordado.json, {"usuario": "..."}.
# El LoginController lo escribe solo tras credenciales válidas y lo borra si se
# entra con la casilla desmarcada. Un archivo ausente, dañado o con un nombre
# no válido se trata como "nada recordado" (nunca hace fallar el login).

import json
import logging
import os
from pathlib import Path

from autoclave.utils.paths import app_root

logger = logging.getLogger(__name__)

NOMBRE_ARCHIVO = "login_recordado.json"
USUARIO_MAX = 30   # el mismo tope del campo de usuario en Login.qml (TEC-D10)


def ruta_por_defecto() -> Path:
    return app_root() / "data" / NOMBRE_ARCHIVO


def _valido(usuario) -> str:
    """El nombre limpio si es recordable; "" si no."""
    if not isinstance(usuario, str):
        return ""
    usuario = usuario.strip()
    if not usuario or len(usuario) > USUARIO_MAX or not usuario.isprintable():
        return ""
    return usuario


def cargar(ruta: Path | None = None) -> str:
    ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""
    except (OSError, ValueError) as e:
        logger.warning("Usuario recordado no legible (%s): %s", ruta, type(e).__name__)
        return ""
    return _valido(datos.get("usuario")) if isinstance(datos, dict) else ""


def guardar(usuario: str, ruta: Path | None = None) -> None:
    usuario = _valido(usuario)
    if not usuario:
        return
    ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(ruta.suffix + ".tmp")
        temporal.write_text(json.dumps({"usuario": usuario}, ensure_ascii=False), encoding="utf-8")
        os.replace(temporal, ruta)
    except OSError as e:
        logger.warning("No se pudo recordar el usuario (%s): %s", ruta, type(e).__name__)


def olvidar(ruta: Path | None = None) -> None:
    ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
    try:
        ruta.unlink(missing_ok=True)
    except OSError as e:
        logger.warning("No se pudo olvidar el usuario recordado (%s): %s", ruta, type(e).__name__)
