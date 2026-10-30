"""
autoclave.config.completar_presion
----------------------------------
Tanda 23 (AIN-04): la calibración de presión pasa de 8 a 16 entradas (AI 1-16
del principal M31). Un archivo de calibración escrito antes (la copia de
`data/` de un equipo instalado, un respaldo) trae 8 entradas de presión: al
cargarlo se completa con las nominales para los canales 8-15, SIN tocar los
canales 0-7 (su calibración de fábrica y de usuario se conservan), y se deja
constancia en el log. La temperatura no cambia (8 entradas).

Nominal (MOD-04): 4000-20000 µA -> 0-400 kPa abs, adc_piso_senal 3850; la de
usuario, neutra. Riesgo AIN-R3: AI 09-16 quedan con calibración nominal hasta
calibrarlas en sitio.
"""

import copy
import logging

logger = logging.getLogger(__name__)

N_PRESION = 16
N_PRESION_ANTERIOR = 8

FABRICA_PRESION_NOMINAL = {"adc_min": 4000, "adc_max": 20000, "pres_min": 0, "pres_max": 400,
                           "adc_piso_senal": 3850, "gain": 1.0, "offset": 0.0}
USUARIO_PRESION_NOMINAL = {"gain": 1.0, "offset": 0.0}


def completar_presion(datos, origen: str = "") -> bool:
    """Completa en el mismo objeto (dict o CommentedMap de ruamel) las listas
    `calibration.factory.pressure` y `calibration.user.pressure` que tengan
    exactamente 8 entradas, agregando las nominales hasta 16. Devuelve True si
    cambió algo. Cualquier otra forma (sin sección, otro largo) no se toca:
    la validación de siempre decide."""
    try:
        cal = datos.get("calibration") if hasattr(datos, "get") else None
    except Exception:
        return False
    if not hasattr(cal, "get"):
        return False
    cambio = []
    for parte, nominal in (("factory", FABRICA_PRESION_NOMINAL), ("user", USUARIO_PRESION_NOMINAL)):
        seccion = cal.get(parte)
        lista = seccion.get("pressure") if hasattr(seccion, "get") else None
        if isinstance(lista, list) and len(lista) == N_PRESION_ANTERIOR:
            for _ in range(N_PRESION - N_PRESION_ANTERIOR):
                lista.append(copy.deepcopy(nominal))
            cambio.append(parte)
    if cambio:
        logger.warning("Calibración %s: presión con %d entradas; se completan los canales %d-%d "
                       "(AI %02d-%02d) con la nominal en %s, sin tocar los canales 0-%d "
                       "(tanda 23, AIN-04)", origen or "", N_PRESION_ANTERIOR,
                       N_PRESION_ANTERIOR, N_PRESION - 1, N_PRESION_ANTERIOR + 1, N_PRESION,
                       "/".join(cambio), N_PRESION_ANTERIOR - 1)
    return bool(cambio)
