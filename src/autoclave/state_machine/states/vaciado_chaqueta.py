# state_machine/states/vaciado_chaqueta.py
#
# Vaciado de chaqueta tras un ciclo de líquidos con enfriamiento modo 4/5.
#
# Al confirmar un ciclo COMPLETADO de carga líquida (tipo_carga distinto de
# "solido" o ilegible) con descompresion.modo 4 o 5, CicloState lo arma
# (PENDIENTE) y deja vapor_chaqueta y descompresion_chaqueta en OFF. En
# PREPARADO, la primera puerta vista abierta (DI vigente y
# puerta_N_cerrada == 0) lo pasa a EN_CURSO: vapor_chaqueta ON (con lectura de
# pres_chaqueta, bajo el corte D-CHQ y con suministro) y descompresion_chaqueta
# en pulsos de _PULSO_S abierta / _PULSO_S cerrada durante _DURACION_S. Al
# cumplirse, con todas las puertas cerradas o ante una cancelación pasa a
# HECHO (descompresion_chaqueta OFF) y no se repite en ese ciclo.
#
# Vive en estado.vaciado_chaqueta (EstadoAutoclave), no en la StateMachine,
# porque set_active_cycle la reconstruye. CicloState.reset() lo vuelve a
# INACTIVO; un reinicio del PC lo pierde (fail-safe). Reloj: time.monotonic(),
# pasado por el llamador.

import logging

logger = logging.getLogger(__name__)

INACTIVO = "INACTIVO"
PENDIENTE = "PENDIENTE"
EN_CURSO = "EN_CURSO"
HECHO = "HECHO"

_PULSO_S = 5.0
_DURACION_S = 30.0


def valvula_abierta(transcurrido_s: float) -> bool:
    """descompresion_chaqueta abierta en el instante `transcurrido_s` desde
    el inicio del vaciado: pulsos de _PULSO_S abierta / _PULSO_S cerrada,
    cerrada desde _DURACION_S."""
    if transcurrido_s < 0 or transcurrido_s >= _DURACION_S:
        return False
    return int(transcurrido_s // _PULSO_S) % 2 == 0


def terminado(transcurrido_s: float) -> bool:
    return transcurrido_s >= _DURACION_S


class VaciadoChaqueta:

    def __init__(self):
        self.estado = INACTIVO
        self._t0 = None

    @property
    def activo(self) -> bool:
        """PENDIENTE o EN_CURSO: dueño de vapor_chaqueta y descompresion_chaqueta
        en PREPARADO (la chaqueta no queda lista)."""
        return self.estado in (PENDIENTE, EN_CURSO)

    def armar(self) -> None:
        self.estado = PENDIENTE
        self._t0 = None
        logger.info("Vaciado de chaqueta: pendiente hasta la primera apertura de puerta")

    def iniciar(self, ahora: float) -> None:
        self.estado = EN_CURSO
        self._t0 = ahora
        logger.info("Vaciado de chaqueta: puerta abierta, inicia (%.0f s)", _DURACION_S)

    def transcurrido(self, ahora: float) -> float:
        return 0.0 if self._t0 is None else ahora - self._t0

    def terminar(self, motivo: str) -> None:
        """Pasa a HECHO (no se repite en este ciclo). Las salidas las apaga
        el llamador."""
        if self.estado != HECHO:
            logger.info("Vaciado de chaqueta: termina (%s)", motivo)
        self.estado = HECHO
        self._t0 = None

    def limpiar(self) -> None:
        self.estado = INACTIVO
        self._t0 = None


def de_estado(estado):
    """El VaciadoChaqueta de `estado`, o None si no hay uno."""
    v = getattr(estado, "vaciado_chaqueta", None)
    return v if isinstance(v, VaciadoChaqueta) else None


def cancelar_en(estado, motivo: str, set_do=None) -> None:
    """Cancela un vaciado PENDIENTE o EN_CURSO (pasa a HECHO, sin reintento).
    Con `set_do`, apaga descompresion_chaqueta y vapor_chaqueta."""
    v = de_estado(estado)
    if v is None or not v.activo:
        return
    v.terminar(f"cancelado: {motivo}")
    if set_do is not None:
        set_do.descompresion_chaqueta_off()
        set_do.vapor_chaqueta_off()


def limpiar_en(estado, set_do=None) -> None:
    """Vuelve a INACTIVO; si estaba EN_CURSO, cierra descompresion_chaqueta."""
    v = de_estado(estado)
    if v is None:
        return
    if v.estado == EN_CURSO and set_do is not None:
        set_do.descompresion_chaqueta_off()
    v.limpiar()
