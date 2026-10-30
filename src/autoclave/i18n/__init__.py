# i18n/__init__.py
#
# Catálogo único de textos visibles en español e inglés (planeacion_i18n.md
# §3.2-3.3, F1). Lo usan la UI QML (singleton I18n, bridge/i18n_qml.py) y el
# Python que arma textos para el operador (PDF, correo, mensajes de puentes).
#
# Claves "seccion.clave" (tercer nivel en opciones.secciones.*); listas como
# fecha.meses se leen con valor(). Placeholders con nombre: "{n}".
#
# Si falta una clave en el idioma pedido se devuelve el texto en español; si
# tampoco existe en español, la clave misma. En ambos casos se avisa en el log
# una sola vez por clave y nunca se devuelve "" (R-05).
#
# En F1 el idioma vigente es estado de este módulo ("es" por defecto); aún no
# se lee ni se guarda en la BD (F2).

import copy
import json
import logging
import os
import threading

from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

IDIOMA_BASE = "es"
IDIOMAS = ("es", "en")


def ruta_catalogo(idioma: str) -> str:
    return resource_path(f"autoclave/i18n/{idioma}.json")


_lock = threading.Lock()
_lock_carga = threading.Lock()   # R1 (I4 TMG-03): carga diferida una sola vez
_catalogos: dict | None = None
_idioma = IDIOMA_BASE
_avisadas: set = set()
_oyentes: list = []


def cargar() -> None:
    """Carga (o recarga) todos los catálogos. Falla si falta alguno: la UI no
    debe arrancar sin textos."""
    global _catalogos
    nuevos = {}
    for idioma in IDIOMAS:
        ruta = ruta_catalogo(idioma)
        if not os.path.isfile(ruta):
            raise FileNotFoundError(f"Falta el catálogo de textos '{idioma}': {ruta}")
        with open(ruta, encoding="utf-8") as f:
            nuevos[idioma] = json.load(f)
    with _lock:
        _catalogos = nuevos
        _avisadas.clear()


def _todos() -> dict:
    if _catalogos is None:
        with _lock_carga:
            if _catalogos is None:
                cargar()
    return _catalogos


def idioma() -> str:
    """Idioma vigente ("es" | "en")."""
    return _idioma


def fijar_idioma(nuevo: str) -> None:
    """Cambia el idioma vigente y avisa a los suscritos (p. ej. el singleton QML)."""
    global _idioma
    if nuevo not in IDIOMAS:
        raise ValueError(f"Idioma no soportado: {nuevo!r} (válidos: {', '.join(IDIOMAS)})")
    if nuevo == _idioma:
        return
    _idioma = nuevo
    for oyente in list(_oyentes):
        oyente(nuevo)


def al_cambiar_idioma(oyente) -> None:
    """Registra `oyente(idioma)`, llamado tras cada cambio de idioma."""
    _oyentes.append(oyente)


def catalogo(idioma_pedido: str | None = None) -> dict:
    """Copia del catálogo completo de un idioma (para quien recibe el dict
    entero, como los PDF). Sin respaldo al español por clave."""
    return copy.deepcopy(_todos()[idioma_pedido or _idioma])


def _buscar(cat: dict, clave: str):
    nodo = cat
    for parte in clave.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            return None
        nodo = nodo[parte]
    return nodo


def _avisar(clave: str, idioma_pedido: str, motivo: str) -> None:
    marca = (clave, idioma_pedido)
    with _lock:
        if marca in _avisadas:
            return
        _avisadas.add(marca)
    logger.warning("i18n: clave '%s' %s (idioma '%s')", clave, motivo, idioma_pedido)


def valor(clave: str, idioma_pedido: str | None = None):
    """Valor crudo de una clave (texto, lista u objeto), con respaldo al
    español. None (con aviso) si no existe en ningún idioma."""
    idioma_pedido = idioma_pedido or _idioma
    cats = _todos()
    v = _buscar(cats.get(idioma_pedido, {}), clave) if clave else None
    if v is not None:
        return v
    v = _buscar(cats[IDIOMA_BASE], clave) if clave else None
    if v is not None:
        if idioma_pedido != IDIOMA_BASE:
            _avisar(clave, idioma_pedido, "sin traducción; se usa el español")
        return v
    _avisar(clave, idioma_pedido, "no existe en el catálogo")
    return None


def existe(clave: str, idioma_pedido: str | None = None) -> bool:
    """True si la clave es un texto en el idioma pedido o en español. No avisa."""
    cats = _todos()
    for cat in (cats.get(idioma_pedido or _idioma, {}), cats[IDIOMA_BASE]):
        if isinstance(_buscar(cat, clave), str):
            return True
    return False


def sustituir(texto: str, params: dict, a_texto=str) -> str:
    """Reemplaza cada "{nombre}" por su valor convertido con `a_texto`."""
    for nombre, v in (params or {}).items():
        texto = texto.replace("{" + nombre + "}", a_texto(v))
    return texto


def t(clave: str, idioma: str | None = None, **params) -> str:
    """Texto de `clave` en `idioma` (o el vigente) con los placeholders
    sustituidos. Nunca devuelve "": sin texto, devuelve la clave."""
    return traducir(clave, idioma, params)


def traducir(clave: str, idioma_pedido: str | None, params: dict | None,
             a_texto=str) -> str:
    """Como t(), con los parámetros en un dict y conversión de valores elegible
    (el singleton QML convierte como JavaScript)."""
    v = valor(clave, idioma_pedido)
    if not isinstance(v, str) or v == "":
        if v is not None:
            _avisar(clave, idioma_pedido or _idioma, "no es un texto")
        return clave
    return sustituir(v, params, a_texto)
