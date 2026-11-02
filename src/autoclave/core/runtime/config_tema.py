# core/runtime/config_tema.py
#
# Modo oscuro (OSC-02): tema de la interfaz QML (data/tema.json = {"tema": "claro"}),
# al lado del idioma (config_idioma.py). Ausente, ilegible o inválido → claro.
# Es configuración de presentación, no dato de proceso: no va a la bitácora.

import json
import threading
from pathlib import Path

from autoclave.utils.archivos import escribir_texto_atomico

TEMAS = ("claro", "oscuro")
POR_DEFECTO = "claro"


class ConfigTema:
    def __init__(self, ruta):
        self._ruta = Path(ruta)
        self._lock = threading.Lock()

    def leer(self) -> str:
        try:
            v = json.loads(self._ruta.read_text(encoding="utf-8")).get("tema")
        except Exception:
            return POR_DEFECTO
        return v if v in TEMAS else POR_DEFECTO

    def guardar(self, tema: str) -> str:
        if tema not in TEMAS:
            raise ValueError(f"Tema inválido: {tema!r}")
        with self._lock:
            escribir_texto_atomico(self._ruta, json.dumps({"tema": tema}))
        return tema
