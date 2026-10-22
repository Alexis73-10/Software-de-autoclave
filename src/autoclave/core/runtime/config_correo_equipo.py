# core/runtime/config_correo_equipo.py
#
# Correo de ciclos del equipo (O2g, tanda 6): interruptor de envío y
# destinatarios guardados, editables desde OPCIONES › Conectividad (admin e
# ingeniero; decisión 1.9). Se guarda en data/correo_equipo.json:
#   {"envio_activo": true, "destinatarios": [{"nombre": "...", "correo": "..."}]}
# Sin archivo, rigen los destinos de fábrica de config/correo.json (semilla) y
# el envío activo: el comportamiento de siempre.
#
# El remitente, el servidor y el puerto siguen en config/correo.json y la
# contraseña del relay en el almacén de credenciales de Windows: nada de eso
# se edita ni se muestra aquí (la contraseña nunca sale del keyring).

import json
import re
import threading
from pathlib import Path

from autoclave.utils.archivos import escribir_texto_atomico

MAX_DESTINATARIOS = 10
MAX_NOMBRE = 40
MAX_CORREO = 254

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorCorreo(ValueError):
    def __init__(self, codigo: str, campo: str = ""):
        super().__init__(codigo)
        self.codigo = codigo
        self.campo = campo


def correo_valido(texto) -> bool:
    return isinstance(texto, str) and len(texto) <= MAX_CORREO and bool(_CORREO.match(texto))


def normalizar(destinatarios) -> list[dict]:
    """Valida y normaliza; lanza ErrorCorreo(codigo, campo)."""
    if not isinstance(destinatarios, list):
        raise ErrorCorreo("validacion", "destinatarios")
    if len(destinatarios) > MAX_DESTINATARIOS:
        raise ErrorCorreo("demasiados", "destinatarios")
    vistos, lista = set(), []
    for i, d in enumerate(destinatarios):
        if not isinstance(d, dict):
            raise ErrorCorreo("validacion", f"destinatarios[{i}]")
        correo = str(d.get("correo") or "").strip()
        nombre = str(d.get("nombre") or "").strip() or correo
        if not correo_valido(correo):
            raise ErrorCorreo("correo_invalido", f"destinatarios[{i}].correo")
        if len(nombre) > MAX_NOMBRE:
            raise ErrorCorreo("nombre_largo", f"destinatarios[{i}].nombre")
        if correo.lower() in vistos:
            raise ErrorCorreo("duplicado", f"destinatarios[{i}].correo")
        vistos.add(correo.lower())
        lista.append({"nombre": nombre, "correo": correo})
    return lista


class ConfigCorreoEquipo:
    def __init__(self, ruta, semilla=lambda: []):
        self._ruta = Path(ruta)
        self._semilla = semilla
        self._lock = threading.Lock()

    def leer(self) -> dict:
        try:
            datos = json.loads(self._ruta.read_text(encoding="utf-8"))
            activo = datos.get("envio_activo")
            return {"envio_activo": activo if isinstance(activo, bool) else True,
                    "destinatarios": normalizar(datos.get("destinatarios") or []),
                    "personalizado": True}
        except Exception:
            try:
                semilla = normalizar(list(self._semilla() or []))
            except Exception:
                semilla = []
            return {"envio_activo": True, "destinatarios": semilla, "personalizado": False}

    def guardar(self, envio_activo, destinatarios) -> dict:
        if not isinstance(envio_activo, bool):
            raise ErrorCorreo("validacion", "envio_activo")
        lista = normalizar(destinatarios)
        nuevo = {"envio_activo": envio_activo, "destinatarios": lista}
        with self._lock:
            escribir_texto_atomico(self._ruta, json.dumps(nuevo, ensure_ascii=False, indent=2))
        return {**nuevo, "personalizado": True}
