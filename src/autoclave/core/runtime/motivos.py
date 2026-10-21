# core/runtime/motivos.py
#
# I4 (tanda 6; planeacion_i18n.md D-22, §3.9): motivos de rechazo de puerta y
# de cámara no segura con CÓDIGO y PARÁMETROS.
#
# `Motivo` es un `str` (el mismo texto en español de siempre) que además lleva
# `codigo` y `valores`. Así la lógica de puertas y de cámara segura no cambia:
# quien compara, registra o concatena el motivo sigue viendo el mismo texto, y
# quien lo presenta (el backend al responder, el puente QML) puede armarlo en
# cualquier idioma y unidad. Los textos viven en i18n/<idioma>.json bajo
# `puerta.<codigo>`, con placeholders "{nombre}".
#
# Convención de valores: `pres` es presión absoluta en kPa y `temp` es °C; se
# presentan con el módulo de unidades. Los demás se insertan como texto.
# Nunca lanza: ante cualquier error se devuelve el texto en español.

import logging
import math
from types import MappingProxyType

from autoclave import i18n
from autoclave.core.runtime import unidades as u

logger = logging.getLogger(__name__)

PREFIJO = "puerta."


class Motivo(str):
    """Texto en español del motivo, con su código y sus parámetros."""

    codigo: str
    valores: MappingProxyType

    def __new__(cls, codigo: str, texto: str, **valores):
        obj = super().__new__(cls, texto)
        obj.codigo = codigo
        # R1 (I4 TMG-04): solo lectura, para que nadie altere un motivo ya emitido
        obj.valores = MappingProxyType(dict(valores))
        return obj

    def __reduce__(self):              # copy/deepcopy/pickle (revisión I4, SAF-01)
        return (_crear, (self.codigo, str(self), dict(self.valores)))


def _crear(codigo, texto, valores):
    return Motivo(codigo, texto, **valores)


# Códigos de motivo usados por ServicioPuertas, camara_segura, AdvancedDoor y
# el endpoint de puertas. La prueba de I4 verifica que cada uno tenga texto en
# es y en, con los mismos placeholders.
CODIGOS = (
    "desconocida", "paro", "estado_seguro", "sensor_temp_indeterminado",
    "error_evaluacion", "otra_puerta_abierta", "no_permitido_origen", "ya_cerrada",
    "estado_desconocido", "falta_config", "sin_presion_camara", "camara_presurizada",
    "sin_presion_empaque", "empaque_presurizado", "no_acepto", "ya_abierta",
    "en_movimiento", "bloqueada", "no_abierta", "sin_datos_vigentes", "sin_temp_camara",
    "sobrepresion", "vacio", "temp_alta", "no_permitida",
)


def codigo_de(motivo) -> str | None:
    c = getattr(motivo, "codigo", None)
    return c if isinstance(c, str) else None


def valores_json(motivo) -> dict:
    """Parámetros serializables (NaN/inf como None)."""
    salida = {}
    for k, v in (getattr(motivo, "valores", None) or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            salida[k] = None
        elif isinstance(v, (int, float, str, bool)) or v is None:
            salida[k] = v
        else:
            salida[k] = str(v)
    return salida


def _presentar(nombre, v, temperatura, presion, p_atm) -> str:
    if nombre == "pres" and isinstance(v, (int, float)) and not isinstance(v, bool):
        return u.formatear_pres(v, presion, p_atm)
    if nombre == "temp" and isinstance(v, (int, float)) and not isinstance(v, bool):
        return u.formatear_temp(v, temperatura)
    return "" if v is None else str(v)


def texto(motivo, idioma: str, temperatura: str = "C", presion: str = "kPa",
          p_atm: float | None = None) -> str:
    """Motivo en `idioma` y en las unidades dadas; sin código, el texto tal cual."""
    base = str(motivo) if motivo is not None else ""
    codigo = codigo_de(motivo)
    if not codigo:
        return base
    try:
        clave = PREFIJO + codigo
        if not i18n.existe(clave, idioma):
            return base
        valores = {k: _presentar(k, v, temperatura, presion, p_atm)
                   for k, v in (getattr(motivo, "valores", None) or {}).items()}
        return i18n.traducir(clave, idioma, valores)
    except Exception:
        logger.debug("motivo %s: no se pudo armar en %s", codigo, idioma, exc_info=True)
        return base


def por_idioma(motivo, temperatura: str = "C", presion: str = "kPa",
               p_atm: float | None = None) -> dict:
    """{"es": ..., "en": ...}; {} si el motivo no tiene código."""
    if not codigo_de(motivo):
        return {}
    return {idioma: texto(motivo, idioma, temperatura, presion, p_atm) for idioma in i18n.IDIOMAS}


def campos_respuesta(motivo, temperatura: str = "C", presion: str = "kPa",
                     p_atm: float | None = None) -> dict:
    """Campos extra de una respuesta HTTP: código, parámetros y textos."""
    codigo = codigo_de(motivo)
    if not codigo:
        return {}
    try:
        return {"motivo_codigo": codigo, "motivo_valores": valores_json(motivo),
                "motivo_textos": por_idioma(motivo, temperatura, presion, p_atm)}
    except Exception:
        return {"motivo_codigo": codigo}
