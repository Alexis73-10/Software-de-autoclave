from dataclasses import dataclass


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
