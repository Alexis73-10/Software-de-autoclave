# state_machine/cycle_phases/cascada_chaqueta.py
#
# CAS-01 (tanda 33, docs/mis_plans/planeacion_control_cascada_chaqueta.md §3;
# decisiones de Cristian del 7-nov). Solo modo chaqueta: control en cascada
# de vapor_chaqueta. La presión de cámara decide el nivel y el nivel fija la
# consigna de chaqueta; la válvula es todo-nada con histéresis bajo la
# consigna.
#
#   Nivel (umbrales iguales a la banda PWM de A14-M1):
#     baja:  pres_camara < p_ref - UMBRAL_BAJO_KPA
#     alta:  pres_camara > p_ref + UMBRAL_ALTO_KPA
#     banda: el resto.
#   Consigna:
#     tope  = min(p_techo - MARGEN_TECHO_KPA,
#                 presion_max_chaqueta_control - MARGEN_DCHQ_KPA,
#                 presion_suministro_vapor)
#     baja  -> tope
#     banda -> min(p_ref + margen_est, tope)
#     alta  -> sin consigna, vapor_chaqueta OFF forzado.
#     Si tope < p_ref + 1 se usa tope igual (nunca se supera el techo) y se
#     advierte en el log una sola vez (se rearma con reset(), una vez por fase).
#   Válvula: ON si pres_chaqueta <= consigna - HISTERESIS_KPA; OFF si
#     pres_chaqueta >= consigna; entre medio conserva el estado anterior. Al
#     cambiar de nivel se reevalúa con la nueva consigna en el mismo tick.
#   Falla cerrada: OFF si pres_camara o pres_chaqueta es None, no finita o
#     <= 0, o si p_ref, p_techo, margen_est o los límites no son finitos.
#
# Todos los valores (histéresis 3, margen de techo 2, umbrales -2/+1, OFF en
# alta) son DECISIÓN SIN CONFIRMAR hasta el banco.
#
# El componente es puro (sin E/S ni hilos): no toca salidas, la fase aplica la
# decisión. VCH-AIS, D-CHQ (estado.inhibir_vapor_chaqueta) y el corte duro de
# CICLO prevalecen y los evalúa el llamador. Log estándar, sin bitácora: una
# línea por cambio de nivel o de consigna, nunca por tick.

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HISTERESIS_KPA = 3.0
MARGEN_TECHO_KPA = 2.0
UMBRAL_BAJO_KPA = 2.0
UMBRAL_ALTO_KPA = 1.0
MARGEN_DCHQ_KPA = 10.0

NIVEL_BAJA = "baja"
NIVEL_BANDA = "banda"
NIVEL_ALTA = "alta"
NIVEL_SIN_DATOS = "sin_datos"

MOTIVO_SIN_LECTURA_CAMARA = "sin_lectura_camara"
MOTIVO_SIN_LECTURA_CHAQUETA = "sin_lectura_chaqueta"
MOTIVO_PARAMETROS_INVALIDOS = "parametros_invalidos"
MOTIVO_CAMARA_ALTA = "camara_alta"
MOTIVO_BAJO_CONSIGNA = "bajo_consigna"
MOTIVO_CONSIGNA_ALCANZADA = "consigna_alcanzada"
MOTIVO_HISTERESIS = "histeresis"


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _lectura_valida(v) -> bool:
    """Lectura de presión utilizable: número finito y mayor que 0."""
    return _numero(v) and float(v) > 0


def _texto(v) -> str:
    return f"{float(v):.1f}" if _numero(v) else f"sin lectura ({v!r})"


@dataclass(frozen=True)
class ResultadoCascada:
    """Decisión de un tick: decision True = vapor_chaqueta ON."""
    decision: bool
    nivel: str
    consigna: float | None
    motivo: str


class CascadaChaqueta:
    """Control en cascada de vapor_chaqueta (CAS-01). Una instancia por fase;
    guarda el estado de la válvula entre ticks."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """Válvula cerrada, sin nivel ni consigna previos; rearma la
        advertencia de tope bajo."""
        self.valvula = False
        self._nivel: str | None = None
        self._consigna: float | None = None
        self._advertido_tope = False

    def evaluar(self, pres_camara, pres_chaqueta, p_ref, p_techo, margen_est,
                presion_max_chaqueta_control,
                presion_suministro_vapor) -> ResultadoCascada:
        """Evalúa un tick y devuelve la decisión de vapor_chaqueta."""
        if not all(_numero(v) for v in (p_ref, p_techo, margen_est,
                                        presion_max_chaqueta_control,
                                        presion_suministro_vapor)):
            return self._cerrar(MOTIVO_PARAMETROS_INVALIDOS, pres_camara, pres_chaqueta)
        if not _lectura_valida(pres_camara):
            return self._cerrar(MOTIVO_SIN_LECTURA_CAMARA, pres_camara, pres_chaqueta)
        if not _lectura_valida(pres_chaqueta):
            return self._cerrar(MOTIVO_SIN_LECTURA_CHAQUETA, pres_camara, pres_chaqueta)

        p_ref = float(p_ref)
        tope = self.tope(p_techo, presion_max_chaqueta_control, presion_suministro_vapor)
        if tope < p_ref + UMBRAL_ALTO_KPA and not self._advertido_tope:
            self._advertido_tope = True
            logger.warning(
                "Cascada chaqueta: tope %.1f kPa bajo p_ref + %.1f (%.1f kPa); "
                "se usa el tope (nunca se supera el techo)",
                tope, UMBRAL_ALTO_KPA, p_ref + UMBRAL_ALTO_KPA)

        pc = float(pres_camara)
        pj = float(pres_chaqueta)
        if pc < p_ref - UMBRAL_BAJO_KPA:
            nivel, consigna = NIVEL_BAJA, tope
        elif pc > p_ref + UMBRAL_ALTO_KPA:
            nivel, consigna = NIVEL_ALTA, None
        else:
            nivel, consigna = NIVEL_BANDA, min(p_ref + float(margen_est), tope)

        if consigna is None:
            self.valvula = False
            motivo = MOTIVO_CAMARA_ALTA
        elif pj <= consigna - HISTERESIS_KPA:
            self.valvula = True
            motivo = MOTIVO_BAJO_CONSIGNA
        elif pj >= consigna:
            self.valvula = False
            motivo = MOTIVO_CONSIGNA_ALCANZADA
        else:
            motivo = MOTIVO_HISTERESIS
        self._registrar(nivel, consigna, pc, pj)
        return ResultadoCascada(self.valvula, nivel, consigna, motivo)

    @staticmethod
    def tope(p_techo, presion_max_chaqueta_control, presion_suministro_vapor) -> float:
        """Consigna máxima de chaqueta (kPa abs)."""
        return min(float(p_techo) - MARGEN_TECHO_KPA,
                   float(presion_max_chaqueta_control) - MARGEN_DCHQ_KPA,
                   float(presion_suministro_vapor))

    def publicar(self) -> dict:
        """Solo lectura para estado.cascada_chaqueta: {nivel, consigna, valvula}."""
        return {"nivel": self._nivel, "consigna": self._consigna, "valvula": self.valvula}

    def _cerrar(self, motivo: str, pres_camara, pres_chaqueta) -> ResultadoCascada:
        self.valvula = False
        cambio = self._nivel != NIVEL_SIN_DATOS
        self._nivel = NIVEL_SIN_DATOS
        self._consigna = None
        if cambio:
            logger.info(
                "Cascada chaqueta: pres_camara=%s pres_chaqueta=%s nivel=%s "
                "consigna=— (%s), vapor_chaqueta OFF",
                _texto(pres_camara), _texto(pres_chaqueta), NIVEL_SIN_DATOS, motivo)
        return ResultadoCascada(False, NIVEL_SIN_DATOS, None, motivo)

    def _registrar(self, nivel: str, consigna: float | None, pc: float, pj: float) -> None:
        anterior = None if self._consigna is None else round(self._consigna, 1)
        nueva = None if consigna is None else round(consigna, 1)
        if nivel != self._nivel or nueva != anterior:
            logger.info(
                "Cascada chaqueta: pres_camara=%.1f pres_chaqueta=%.1f nivel=%s consigna=%s",
                pc, pj, nivel, "—" if consigna is None else f"{consigna:.1f}")
        self._nivel = nivel
        self._consigna = consigna
