# core/managers/limites_equipo.py
#
# F1 (tanda 16): lectores de los parámetros del equipo nuevos de la tanda
# (global_params.json, Parámetros del equipo). Mismo patrón que
# EsterilizacionFase._pausa_max_s: el valor vigente del ConfigManager se
# recorta a su rango; si falta o no es numérico, vale el defecto.
#
#   DEU-01 (D-DEU-1): límites físicos de presión, kPa absolutos. Las
#     constantes de catalogo_parametros.py quedan solo como defectos.
#     Coherencia: suministro < alivio (cámara y chaqueta) <= fondo de escala.
#     Si los valores vigentes no la cumplen (no debería pasar: el
#     ConfigManager rechaza el cambio que la rompe), rigen los cuatro
#     defectos (DECISIÓN SIN CONFIRMAR: un juego coherente conocido antes que
#     uno mezclado).
#   D-CHQ: presion_max_chaqueta_control, corte único de la chaqueta (SAF-09 y
#     VCH-CHQ), defecto 375, rango 300 a alivio de chaqueta - 10.
#   VCH-AIS (VCH §4.5): timeout_aislamiento_camara (min), max_aislamientos_camara
#     y ventana_aislamientos_camara (min).

import logging
import math
from dataclasses import dataclass

from autoclave.core.managers import catalogo_parametros as cp

logger = logging.getLogger(__name__)

# (defecto, mínimo, máximo)
RANGO_LIMITE_PRESION = (100.0, 1000.0)
DEFECTOS_LIMITES = {
    "presion_fondo_escala": cp.PRESION_FONDO_ESCALA,
    "presion_suministro_vapor": cp.PRESION_SUMINISTRO,
    "presion_alivio_camara": cp.PRESION_ALIVIO_CAMARA,
    "presion_alivio_chaqueta": cp.PRESION_ALIVIO_CHAQUETA,
}
CLAVES_LIMITES = tuple(DEFECTOS_LIMITES)

PRESION_MAX_CHAQUETA_DEFECTO = 375.0
PRESION_MAX_CHAQUETA_MIN = 300.0
# el máximo es el alivio de chaqueta menos este margen
MARGEN_CORTE_BAJO_ALIVIO = 10.0

TIMEOUT_AISLAMIENTO = (3, 1, 10)          # min
MAX_AISLAMIENTOS = (6, 2, 20)
VENTANA_AISLAMIENTOS = (15, 5, 60)        # min


def _numero(valor) -> bool:
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and math.isfinite(valor))


def _leer(config, clave):
    try:
        return config.get(clave) if config is not None else None
    except Exception:
        logger.debug("Parámetro del equipo %s no legible", clave, exc_info=True)
        return None


def leer_recortado(config, clave: str, defecto, minimo, maximo, entero: bool = False):
    """Valor vigente de `clave` recortado a [minimo, maximo]; sin un valor
    numérico finito, `defecto`. Nunca lanza."""
    valor = _leer(config, clave)
    if not _numero(valor):
        return int(defecto) if entero else float(defecto)
    valor = min(max(float(valor), minimo), maximo)
    return int(round(valor)) if entero else valor


@dataclass(frozen=True)
class LimitesPresion:
    fondo_escala: float
    suministro: float
    alivio_camara: float
    alivio_chaqueta: float


_ULTIMO_INCOHERENTE = None

LIMITES_DEFECTO = LimitesPresion(cp.PRESION_FONDO_ESCALA, cp.PRESION_SUMINISTRO,
                                 cp.PRESION_ALIVIO_CAMARA, cp.PRESION_ALIVIO_CHAQUETA)


def limites_coherentes(fondo, suministro, alivio_camara, alivio_chaqueta) -> bool:
    """D-DEU-1: suministro < alivio <= fondo de escala (para los dos alivios)."""
    if not all(_numero(v) for v in (fondo, suministro, alivio_camara, alivio_chaqueta)):
        return False
    return all(suministro < alivio <= fondo for alivio in (alivio_camara, alivio_chaqueta))


def limites_presion(config) -> LimitesPresion:
    """DEU-01: límites físicos de presión del equipo (kPa abs). Sin config
    (pruebas, herramientas fuera del backend), los defectos."""
    if config is None:
        return LIMITES_DEFECTO
    bajo, alto = RANGO_LIMITE_PRESION
    v = {c: leer_recortado(config, c, d, bajo, alto) for c, d in DEFECTOS_LIMITES.items()}
    limites = LimitesPresion(v["presion_fondo_escala"], v["presion_suministro_vapor"],
                             v["presion_alivio_camara"], v["presion_alivio_chaqueta"])
    if not limites_coherentes(limites.fondo_escala, limites.suministro,
                              limites.alivio_camara, limites.alivio_chaqueta):
        # R (tanda 16, V16-s3-06): el corte lo consulta en cada tick; un log por juego
        global _ULTIMO_INCOHERENTE
        if limites != _ULTIMO_INCOHERENTE:
            _ULTIMO_INCOHERENTE = limites
            logger.error("Límites de presión del equipo incoherentes %s: rigen los de fábrica",
                         limites)
        return LIMITES_DEFECTO
    return limites


def presion_max_chaqueta_control(config) -> float:
    """D-CHQ: corte de vapor_chaqueta (kPa abs), recortado a 300 a
    alivio de chaqueta - 10; sin valor válido, 375 (también recortado)."""
    alto = limites_presion(config).alivio_chaqueta - MARGEN_CORTE_BAJO_ALIVIO
    bajo = min(PRESION_MAX_CHAQUETA_MIN, alto)
    return leer_recortado(config, "presion_max_chaqueta_control",
                          min(PRESION_MAX_CHAQUETA_DEFECTO, alto), bajo, alto)


def timeout_aislamiento_camara_s(config) -> float:
    d, lo, hi = TIMEOUT_AISLAMIENTO
    return leer_recortado(config, "timeout_aislamiento_camara", d, lo, hi) * 60.0


def max_aislamientos_camara(config) -> int:
    d, lo, hi = MAX_AISLAMIENTOS
    return leer_recortado(config, "max_aislamientos_camara", d, lo, hi, entero=True)


def ventana_aislamientos_camara_s(config) -> float:
    d, lo, hi = VENTANA_AISLAMIENTOS
    return leer_recortado(config, "ventana_aislamientos_camara", d, lo, hi) * 60.0
