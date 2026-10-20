# core/runtime/config_idioma.py
#
# I1 (tanda 5): idioma vigente del equipo (data/idioma.json = {"idioma": "es"}).
# Ausente, ilegible o inválido → español (el comportamiento de siempre).

import json
import threading
from pathlib import Path

from autoclave.utils.archivos import escribir_texto_atomico

IDIOMAS = ("es", "en")
POR_DEFECTO = "es"


class ConfigIdioma:
    def __init__(self, ruta):
        self._ruta = Path(ruta)
        self._lock = threading.Lock()

    def leer(self) -> str:
        try:
            v = json.loads(self._ruta.read_text(encoding="utf-8")).get("idioma")
        except Exception:
            return POR_DEFECTO
        return v if v in IDIOMAS else POR_DEFECTO

    def guardar(self, idioma: str) -> str:
        if idioma not in IDIOMAS:
            raise ValueError(f"Idioma inválido: {idioma!r}")
        with self._lock:
            escribir_texto_atomico(self._ruta, json.dumps({"idioma": idioma}))
        return idioma
