import logging
import math
import time
from dataclasses import dataclass

from autoclave.installation.profile import numero_puertas


@dataclass(frozen=True)
class ResultadoBanda:
    debe_activar: bool
    fuera_por_debajo: bool
    fuera_por_encima: bool
    dentro_de_banda: bool


def evaluar_banda(actual: float, objetivo: float, rango: float, activar_si_bajo: bool) -> ResultadoBanda:
    """Evalua un control de banda con el objetivo como umbral de valvula.

    activar_si_bajo=True  -> la valvula sube el valor (ej. vapor_chaqueta): enciende si actual < objetivo.
    activar_si_bajo=False -> la valvula baja el valor (ej. agua_intercambiador): enciende si actual > objetivo.
    """
    limite_inf = objetivo - rango
    limite_sup = objetivo + rango
    debe_activar = actual < objetivo if activar_si_bajo else actual > objetivo
    return ResultadoBanda(
        debe_activar=debe_activar,
        fuera_por_debajo=actual < limite_inf,
        fuera_por_encima=actual > limite_sup,
        dentro_de_banda=limite_inf <= actual <= limite_sup,
    )


class ConfirmadorApagado:
    """Exige N ticks consecutivos de 'debe estar apagado' antes de confirmar
    el apagado real de una salida. Solo cubre el apagado — el encendido
    reacciona de inmediato, sin pasar por aqui."""

    def __init__(self, ticks_requeridos: int = 3):
        self._ticks_requeridos = ticks_requeridos
        self._contador = 0

    def confirmar(self, debe_estar_apagado: bool) -> bool:
        if debe_estar_apagado:
            self._contador += 1
        else:
            self._contador = 0
        return self._contador >= self._ticks_requeridos

    def reset(self):
        self._contador = 0

logger = logging.getLogger(__name__)


_TIEMPO_ESTABLE_DEFECTO_S = 5.0


def leer_tiempo_estable(config, fijo=None) -> float:
    """`tiempo_estable_alarma` vigente (s); se lee en cada uso para que un
    cambio en Parámetros del equipo aplique sin reiniciar (OPC-11). `fijo`:
    valor de pruebas. Sin valor o fuera de 0..3600, el de fábrica (TMG-03)."""
    v = fijo
    if v is None:
        try:
            v = config.get("tiempo_estable_alarma")
        except Exception:
            v = None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return _TIEMPO_ESTABLE_DEFECTO_S
    return v if math.isfinite(v) and 0 <= v <= 3600 else _TIEMPO_ESTABLE_DEFECTO_S


class CondicionSostenida:
    """T29-02 (tanda 29): True solo cuando la condición lleva `segundos`
    seguidos (time.monotonic); un tick sin la condición reinicia la cuenta.
    La usan PRE-03/PRE-04 fuera de ciclo para que el igualado normal de la
    cámara tras un ciclo no genere avisos."""

    def __init__(self):
        self._desde = None

    def evaluar(self, condicion: bool, segundos: float) -> bool:
        if not condicion:
            self._desde = None
            return False
        ahora = time.monotonic()
        if self._desde is None:
            self._desde = ahora
        return ahora - self._desde >= segundos

    def reset(self):
        self._desde = None


def puertas_confirmadas_cerradas(estado, profile, di_vigentes) -> bool:
    """T29-08 (tanda 29): todas las puertas instaladas (numero_puertas del
    perfil) con puerta_N_cerrada en 1 y la trama DI vigente; mismo criterio que
    ControlLoop.puertas_confirmadas_cerradas. Falla cerrada: sin dato, datos no
    vigentes o un error, False."""
    if di_vigentes is not True:
        return False
    try:
        di = estado.sensores_di
        for num in range(1, numero_puertas(profile) + 1):
            valor = di.get(f"puerta_{num}_cerrada")
            if not (valor is True or (type(valor) is int and valor == 1)):
                return False
        return True
    except Exception:
        logger.exception("No se pudo leer si las puertas están cerradas; se toman como abiertas")
        return False


# T1 (tanda 5, D-19 de planeacion_fin_de_ciclo_y_puertas.md): con carga líquida
# NUNCA se ventea con la descompresión rápida (ebullición súbita). Tras el
# reconocimiento de un ciclo COMPLETADO la cámara puede seguir presurizada y
# PREPARACION/PREPARADO la igualan: en líquidos lo hacen con la lenta.
# Falla segura (revisión T1, SEN-01/SEN-03): sin programa, sin tipo_carga o con
# error al leerlo, cuenta como líquido (misma regla que la recuperación de
# arranque, backend/context.py).
def carga_liquida(programas_seguridad, cycle) -> bool:
    try:
        programas = programas_seguridad() if programas_seguridad is not None else [cycle]
        programas = [p for p in (programas or []) if p is not None]
        if not programas:
            return True
        return any(p.get_param("globals", "tipo_carga", default=None) in (None, "liquido")
                   for p in programas)
    except Exception:
        if not getattr(carga_liquida, "_avisado", False):
            logger.exception("No se pudo saber si la carga es líquida: se ventea con la lenta")
            carga_liquida._avisado = True
        return True


def aplicar_venteo(estado_obj, set_do, quiere: bool, liquida: bool) -> None:
    """UNA sola decisión de venteo por tick (revisión T1, TMG T1-01-A/B/D):
    rápida en sólidos, lenta en líquidos, y la válvula contraria siempre
    cerrada. La lenta solo la cierra quien la abrió (`_lenta_por_liquido`),
    para no pisar a otro dueño de esa salida."""
    if quiere and liquida:
        set_do.descompresion_rapida_off()
        set_do.descompresion_lenta_on()
        estado_obj._lenta_por_liquido = True
        return
    if quiere:
        set_do.descompresion_rapida_on()
    else:
        set_do.descompresion_rapida_off()
    if getattr(estado_obj, "_lenta_por_liquido", False):
        set_do.descompresion_lenta_off()
        estado_obj._lenta_por_liquido = False


def cerrar_lenta_propia(estado_obj, set_do) -> None:
    """Sin dato de presión: si este estado abrió la lenta, la cierra."""
    if getattr(estado_obj, "_lenta_por_liquido", False):
        set_do.descompresion_lenta_off()
        estado_obj._lenta_por_liquido = False
