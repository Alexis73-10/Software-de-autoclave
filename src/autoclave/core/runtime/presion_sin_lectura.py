# core/runtime/presion_sin_lectura.py
#
# S1 (tanda 8, D8-1): transductor de presión sin lectura.
#
# El convertidor (hal/measures/converters.py) decide sobre la cuenta cruda si
# el lazo 4-20 mA está abierto o en corto y entrega None ("sin lectura"),
# nunca 0. Este módulo reúne las reglas que usan los estados:
#   - qué canales de presión se vigilan: la cámara siempre; la chaqueta si
#     `io_enabled` la declara (si no se puede leer, se vigila: falla cerrada).
#     El empaque no entra aquí (el equipo de pruebas no tiene ese sensor; su
#     vigilancia sigue en PUE-03 / SEN-01 según el perfil);
#   - el código de alarma en ciclo (FALLO: SEN-04 / SEN-05) y fuera de ciclo
#     (bloquea el inicio: SEN-06 / SEN-07);
#   - el motivo de rechazo del inicio, con texto del catálogo i18n.

import functools
import logging

from autoclave.core.runtime.lectura import lectura_valida
from autoclave.state_machine.alarms.catalogo import SEN_04, SEN_05, SEN_06, SEN_07

logger = logging.getLogger(__name__)

CAMARA = "pres_camara"
CHAQUETA = "pres_chaqueta"

CODIGO_EN_CICLO = {CAMARA: SEN_04, CHAQUETA: SEN_05}
CODIGO_FUERA_DE_CICLO = {CAMARA: SEN_06, CHAQUETA: SEN_07}
# Código de rechazo de /cycle/start y su clave i18n
RECHAZO_INICIO = {
    CAMARA: ("PRESION_CAMARA_SIN_LECTURA", "ciclo.presion_camara_sin_lectura"),
    CHAQUETA: ("PRESION_CHAQUETA_SIN_LECTURA", "ciclo.presion_chaqueta_sin_lectura"),
}


@functools.lru_cache(maxsize=1)
def _ai_habilitadas() -> tuple | None:
    """AI de `io_enabled` del equipo activo; None si no se pudo leer."""
    try:
        from autoclave.core.runtime.io_names import leer_io_enabled
        ai = leer_io_enabled()["AI"]
    except Exception:
        logger.exception("Presión sin lectura: no se pudo leer io_enabled")
        return None
    return tuple(ai) if ai else None


def canales_vigilados(ai_habilitadas=...) -> list[str]:
    """Canales de presión cuya falta de lectura falla el ciclo o bloquea el
    inicio. `ai_habilitadas` (pruebas): lista de AI de io_enabled o None."""
    ai = _ai_habilitadas() if ai_habilitadas is ... else ai_habilitadas
    canales = [CAMARA]
    if ai is None or CHAQUETA in ai:
        canales.append(CHAQUETA)
    return canales


def sin_lectura(estado, canales) -> list[str]:
    """Canales de `canales` sin lectura válida (None o no finito)."""
    return [c for c in canales if not lectura_valida(estado.sensores_pres.get(c))]


def vigilar_fuera_de_ciclo(alarm_manager, estado, canales=None) -> list[str]:
    """D8-1.3 (PREPARACION / PREPARADO): activa SEN-06 / SEN-07 en los canales
    vigilados sin lectura y los resuelve en los que leen. Devuelve los canales
    sin lectura: el llamador no queda listo y no les pone además la alarma
    genérica de lectura inválida (SEN-01)."""
    from autoclave.state_machine.alarms.catalogo import nombre_legible
    if canales is None:
        try:
            canales = canales_vigilados()
        except Exception:
            logger.exception("Presión sin lectura: canales no evaluables; se vigilan todos")
            canales = [CAMARA, CHAQUETA]
    faltan = sin_lectura(estado, canales)
    for canal in canales:
        codigo = CODIGO_FUERA_DE_CICLO[canal]
        legible = nombre_legible(canal)
        if canal in faltan:
            alarm_manager.activar(codigo, origen=legible)
        else:
            alarm_manager.resolver(codigo, origen=legible)
    return faltan


def rechazo_inicio(estado, canales=None) -> tuple | None:
    """(código, motivo) para /cycle/start si algún canal vigilado no lee."""
    faltan = sin_lectura(estado, canales_vigilados() if canales is None else canales)
    if not faltan:
        return None
    codigo, clave = RECHAZO_INICIO[faltan[0]]
    from autoclave import i18n
    return codigo, i18n.t(clave)
