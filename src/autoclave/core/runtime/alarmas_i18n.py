# core/runtime/alarmas_i18n.py
#
# I1 (tanda 5; planeacion_i18n.md §3.8): textos de una alarma por idioma a
# partir de su CÓDIGO y sus PARÁMETROS. El catálogo de seguridad
# (state_machine/alarms/catalogo.py) sigue siendo la fuente de nivel, bloqueo
# y despeje, y de la descripción en español con la que se registra; aquí solo
# se presenta. Las plantillas viven en i18n/<idioma>.json →
# alarmas.<codigo>.{titulo, plantilla, accion} y usan formato de Python
# ({pres:.0f}) con los mismos campos que la plantilla del catálogo.
# Si falta algo, se usa el español del catálogo: una alarma nunca queda sin
# texto.

import logging
import math

from autoclave import i18n

logger = logging.getLogger(__name__)


def textos(definicion, valores: dict, idioma: str) -> dict:
    """{"titulo", "descripcion", "accion"} de la alarma en `idioma`."""
    codigo = definicion.codigo
    base = {"titulo": definicion.titulo, "accion": definicion.accion}
    try:
        base["descripcion"] = definicion.renderizar(valores)
    except Exception:
        base["descripcion"] = definicion.descripcion
    if idioma not in i18n.IDIOMAS:
        return base
    try:
        entrada = i18n.valor(f"alarmas.{codigo}", idioma)
    except Exception:                  # catálogo ilegible: /status no cae (revisión I1, M-1)
        _avisar_una_vez(f"catalogo:{idioma}", "Catálogo %s ilegible: alarmas en español", idioma)
        return base
    if not isinstance(entrada, dict):
        return base
    salida = dict(base)
    for campo in ("titulo", "accion"):
        if isinstance(entrada.get(campo), str):
            salida[campo] = entrada[campo]
    plantilla = entrada.get("plantilla")
    if isinstance(plantilla, str):
        try:
            salida["descripcion"] = plantilla.format(**valores)
        except Exception:
            _avisar_una_vez(f"{codigo}:{idioma}", "Alarma %s: plantilla %s incompleta; se usa el español",
                            codigo, idioma)
    return salida


_avisados: set = set()


def _avisar_una_vez(clave, mensaje, *args) -> None:
    if clave not in _avisados:
        _avisados.add(clave)
        logger.warning(mensaje, *args)


def por_idioma(definicion, valores: dict) -> dict:
    """Textos en todos los idiomas: {"es": {...}, "en": {...}}. Nunca lanza
    (revisión I1, B-2): ante cualquier error devuelve {}."""
    try:
        return {idioma: textos(definicion, valores or {}, idioma) for idioma in i18n.IDIOMAS}
    except Exception:
        _avisar_una_vez("por_idioma", "No se pudieron armar los textos de una alarma")
        return {}


def valores_json(valores: dict) -> dict:
    """Parámetros serializables (números y texto; lo demás como texto)."""
    salida = {}
    try:
        for k, v in (valores or {}).items():
            if isinstance(v, float) and not math.isfinite(v):
                salida[k] = None           # JSON sin NaN/inf (revisión I1, M-2)
            elif isinstance(v, (int, float, str, bool)) or v is None:
                salida[k] = v
            else:
                salida[k] = str(v)
    except Exception:
        return {}
    return salida


def motivo_fallo(codigo, valores, motivo, idioma: str) -> str | None:
    """I4 (tanda 6; planeacion_i18n.md §3.10): motivo de fallo de un ciclo
    guardado, en `idioma`, a partir de su código y sus parámetros (dict o el
    JSON de ciclos.valores_fallo): "CÓDIGO · título: descripción". Sin código
    del catálogo (ciclos antiguos o de texto libre) devuelve el motivo
    guardado tal cual. Nunca lanza."""
    try:
        from autoclave.state_machine.alarms.catalogo import CATALOGO
        definicion = CATALOGO.get(codigo or "")
        if definicion is None:
            return motivo or None
        if isinstance(valores, str):
            import json
            valores = json.loads(valores) if valores.strip() else {}
        if not isinstance(valores, dict):
            valores = {}
        if not valores and idioma == "es" and motivo:
            return motivo                  # sin parámetros: el texto registrado
        t = textos(definicion, valores, idioma)
        if not valores:
            return f"{definicion.codigo} · {t['titulo']}"
        return f"{definicion.codigo} · {t['titulo']}: {t['descripcion']}"
    except Exception:
        _avisar_una_vez("motivo_fallo", "No se pudo armar el motivo de fallo de un ciclo")
        return motivo or None
