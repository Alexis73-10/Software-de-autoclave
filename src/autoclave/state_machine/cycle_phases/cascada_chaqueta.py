# state_machine/cycle_phases/cascada_chaqueta.py
#
# CAS-01 (tanda 33, docs/mis_plans/planeacion_control_cascada_chaqueta.md §3;
# decisiones de Cristian del 7-nov). Solo modo chaqueta: control en cascada
# de vapor_chaqueta. La presión de cámara decide el nivel y el nivel fija la
# consigna de chaqueta; la válvula es todo-nada con histéresis bajo la
# consigna.
#
# CRI-01 (tanda 35, docs/mis_plans/planeacion_cascada_integral.md §3): la
# consigna del nivel «banda» lleva acción integral. `dp` (kPa) es la
# diferencia de presión chaqueta–cámara que la cascada aprende:
#     dp += KI_CRI * (p_ref - pres_camara) * dt
#   acotada a [DP_MIN_KPA, tope_baja - p_ref], con dt del reloj monotonic que
#   pasa el llamador (`ahora`) recortado a 0..DT_MAX_S (un salto o una pausa
#   no integra de golpe). Valor inicial: `dp_inicial` (lo aprendido en
#   CALENTAMIENTO, herencia en ESTERILIZACION) o, sin él, margen_est
#   (margen_chaqueta_est del programa); acotado igual. Antiembalamiento
#   (integración condicional, corrección ALTA-1 de la revisión de seguridad):
#   no integra nada con `congelar` (el llamador sin medida válida, p. ej. sin
#   lectura del Principal), sin lectura de cámara o de chaqueta, con entradas
#   inválidas ni en el primer tick (dt 0); en el nivel «baja» (consigna
#   saturada en tope_baja) y con `solo_bajar` (el llamador fuerza OFF por
#   prevalencia: VCH-AIS aislado, inhibir_vapor_chaqueta) solo integra error
#   negativo: dp puede bajar, nunca subir. Lo mismo con el actuador saturado
#   (segunda revisión, MEDIA-A): válvula ON en el tick anterior, ese tick en
#   «banda» y pres_chaqueta <= consigna_anterior - HISTERESIS_KPA (la chaqueta
#   no llega, p. ej. sin suministro); sin historial no hay saturación. En «alta» la
#   integral sigue corriendo: con error negativo dp baja.
#
#   Nivel:
#     baja:  pres_camara < p_baja; por defecto p_ref - UMBRAL_BAJO_KPA. CRI-02
#            (ESTERILIZACION) pasa min(Psat(T_est) + brecha_segura_presion,
#            p_ref - 1); el componente nunca lo deja sobre
#            p_ref - MARGEN_P_BAJA_KPA (no se solapa con «alta»).
#     alta:  pres_camara > p_ref + UMBRAL_ALTO_KPA
#     banda: el resto.
#   Consigna:
#     tope_baja  = min(presion_max_chaqueta_control - MARGEN_DCHQ_KPA,
#                      presion_suministro_vapor)
#     baja  -> tope_baja (ajuste del 8-nov, autorizado por Cristian;
#              DECISIÓN SIN CONFIRMAR hasta el banco)
#     banda -> min(p_ref + dp, tope_baja). CRI-01 retira el límite
#              techo - 2 de este nivel: el techo de cámara lo protege VCH-AIS
#              (lo evalúa el llamador) y la válvula de alivio.
#     alta  -> sin consigna, vapor_chaqueta OFF forzado.
#     Si tope_baja < p_ref + 1 se advierte en el log una sola vez (se rearma
#     con reset(), una vez por fase).
#   Válvula: ON si pres_chaqueta <= consigna - HISTERESIS_KPA; OFF si
#     pres_chaqueta >= consigna; entre medio conserva el estado anterior. Al
#     cambiar de nivel se reevalúa con la nueva consigna en el mismo tick.
#   Falla cerrada (OFF, sin integrar): pres_camara o pres_chaqueta None, no
#     finita o <= 0; p_ref, margen_est, los límites o `ahora` no finitos;
#     p_baja dado y no finito.
#
# Todos los valores (histéresis 3, umbrales -2/+1, OFF en alta, KI_CRI,
# DP_MIN_KPA, DT_MAX_S) son DECISIÓN SIN CONFIRMAR hasta el banco.
#
# El componente es puro (sin E/S, hilos ni reloj propio): no toca salidas, la
# fase aplica la decisión. VCH-AIS, D-CHQ (estado.inhibir_vapor_chaqueta) y
# el corte duro de CICLO prevalecen y los evalúa el llamador. Log estándar,
# sin bitácora: una línea por cambio de nivel, por cambio de consigna fuera de
# «banda» o cuando dp se aleja más de UMBRAL_LOG_DP_KPA de la última línea;
# nunca por tick.

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HISTERESIS_KPA = 3.0
UMBRAL_BAJO_KPA = 2.0
UMBRAL_ALTO_KPA = 1.0
MARGEN_DCHQ_KPA = 10.0
# CRI-02: p_baja nunca sobre p_ref - este margen
MARGEN_P_BAJA_KPA = 1.0
# CRI-01 (DECISIÓN SIN CONFIRMAR hasta el banco)
KI_CRI = 0.15            # kPa de dp por kPa de error y por segundo
DP_MIN_KPA = 3.0
DT_MAX_S = 2.0
UMBRAL_LOG_DP_KPA = 2.0

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
    """Control en cascada de vapor_chaqueta (CAS-01, CRI-01). Una instancia
    por fase; guarda el estado de la válvula y la integral entre ticks."""

    def __init__(self, dp_inicial=None):
        self.reset(dp_inicial)

    def reset(self, dp_inicial=None) -> None:
        """Válvula cerrada, sin nivel ni consigna previos; rearma la
        advertencia de tope bajo. `dp_inicial` (CRI-01): valor de partida de
        la integral (None o no finito: margen_est en el primer tick)."""
        self.valvula = False
        self._nivel: str | None = None
        self._consigna: float | None = None
        self._advertido_tope = False
        self._dp_inicial = float(dp_inicial) if _numero(dp_inicial) else None
        self.dp: float | None = None
        self._t_ultimo: float | None = None
        self._dp_registrado: float | None = None

    def evaluar(self, pres_camara, pres_chaqueta, p_ref, margen_est,
                presion_max_chaqueta_control, presion_suministro_vapor, *,
                ahora, congelar: bool = False, solo_bajar: bool = False,
                p_baja=None) -> ResultadoCascada:
        """Evalúa un tick y devuelve la decisión de vapor_chaqueta.

        `ahora`: instante monotonic del tick (s). `congelar`: True si el
        llamador no tiene una medida válida (p. ej. sin lectura del Principal):
        la integral no cambia. `solo_bajar`: True si una prevalencia del
        llamador fuerza OFF (VCH-AIS aislado, inhibir_vapor_chaqueta): solo se
        integra error negativo. `p_baja`: umbral del nivel «baja» (None =
        p_ref - UMBRAL_BAJO_KPA)."""
        if not all(_numero(v) for v in (p_ref, margen_est,
                                        presion_max_chaqueta_control,
                                        presion_suministro_vapor, ahora)) \
                or (p_baja is not None and not _numero(p_baja)):
            self._t_ultimo = float(ahora) if _numero(ahora) else None
            return self._cerrar(MOTIVO_PARAMETROS_INVALIDOS, pres_camara, pres_chaqueta)
        ahora = float(ahora)
        if not _lectura_valida(pres_camara):
            self._t_ultimo = ahora
            return self._cerrar(MOTIVO_SIN_LECTURA_CAMARA, pres_camara, pres_chaqueta)
        if not _lectura_valida(pres_chaqueta):
            self._t_ultimo = ahora
            return self._cerrar(MOTIVO_SIN_LECTURA_CHAQUETA, pres_camara, pres_chaqueta)

        p_ref = float(p_ref)
        pc = float(pres_camara)
        pj = float(pres_chaqueta)
        tope_baja = self.tope_baja(presion_max_chaqueta_control, presion_suministro_vapor)
        if tope_baja < p_ref + UMBRAL_ALTO_KPA and not self._advertido_tope:
            self._advertido_tope = True
            logger.warning(
                "Cascada chaqueta: tope %.1f kPa bajo p_ref + %.1f (%.1f kPa); "
                "la consigna no supera el tope",
                tope_baja, UMBRAL_ALTO_KPA, p_ref + UMBRAL_ALTO_KPA)

        umbral_baja = p_ref - UMBRAL_BAJO_KPA if p_baja is None else float(p_baja)
        umbral_baja = min(umbral_baja, p_ref - MARGEN_P_BAJA_KPA)
        if pc < umbral_baja:
            nivel = NIVEL_BAJA
        elif pc > p_ref + UMBRAL_ALTO_KPA:
            nivel = NIVEL_ALTA
        else:
            nivel = NIVEL_BANDA

        # Antiembalamiento (revisión de seguridad ALTA-1): en «baja» la
        # consigna ya está saturada en tope_baja y con `solo_bajar` la
        # prevalencia del llamador impide actuar: solo se integra error
        # negativo (dp puede bajar, nunca subir). Segunda revisión, MEDIA-A:
        # tampoco sube con el actuador saturado (válvula ON en el tick
        # anterior y la chaqueta todavía en o bajo consigna_anterior -
        # HISTERESIS_KPA: p. ej. sin suministro, la chaqueta no llega)
        self._integrar(pc, p_ref, tope_baja, float(margen_est), ahora, congelar,
                       solo_bajar=(bool(solo_bajar) or nivel == NIVEL_BAJA
                                   or self.actuador_saturado(pj)))

        if nivel == NIVEL_BAJA:
            consigna = tope_baja
        elif nivel == NIVEL_ALTA:
            consigna = None
        else:
            consigna = min(p_ref + self.dp, tope_baja)

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

    def actuador_saturado(self, pres_chaqueta) -> bool:
        """MEDIA-A (segunda revisión de seguridad): True si la válvula quedó
        ON en el tick anterior y la chaqueta sigue en o bajo la consigna
        anterior - HISTERESIS_KPA (la válvula ya da todo y la chaqueta no
        llega). La consigna anterior cuenta solo si el tick anterior fue
        «banda» (la consigna que la integral mueve): tras «baja» la consigna
        era tope_baja, que no dice nada de la de banda, y en «baja» el error
        positivo ya no se integra (DECISIÓN SIN CONFIRMAR; con la consigna de
        «baja» el caso 11 del barrido CRI pasaba de COMPLETADO a CIC-04). Sin
        historial (primer tick, tras _cerrar o en «alta») o sin lectura
        válida: False."""
        return (self.valvula is True and self._nivel == NIVEL_BANDA
                and _numero(self._consigna)
                and _lectura_valida(pres_chaqueta)
                and float(pres_chaqueta) <= self._consigna - HISTERESIS_KPA)

    @staticmethod
    def cotas_dp(p_ref, tope_baja) -> tuple[float, float]:
        """CRI-01: (mínimo, máximo) de dp; el máximo nunca bajo el mínimo."""
        return DP_MIN_KPA, max(DP_MIN_KPA, float(tope_baja) - float(p_ref))

    def _integrar(self, pc, p_ref, tope_baja, margen_est, ahora, congelar,
                  solo_bajar=False) -> None:
        lo, hi = self.cotas_dp(p_ref, tope_baja)
        if self.dp is None:
            inicial = self._dp_inicial if self._dp_inicial is not None else margen_est
            self.dp = min(max(inicial, lo), hi)
            self._t_ultimo = ahora
            return
        if not congelar and self._t_ultimo is not None:
            dt = min(max(ahora - self._t_ultimo, 0.0), DT_MAX_S)
            incremento = KI_CRI * (p_ref - pc) * dt
            if not (solo_bajar and incremento > 0):
                self.dp += incremento
        self.dp = min(max(self.dp, lo), hi)
        self._t_ultimo = ahora

    @staticmethod
    def tope_baja(presion_max_chaqueta_control, presion_suministro_vapor) -> float:
        """Consigna máxima de chaqueta (kPa abs), la del nivel «baja» y techo
        de la de «banda»: no depende del techo de cámara (ajuste del 8-nov y
        CRI-01; DECISIÓN SIN CONFIRMAR hasta el banco)."""
        return min(float(presion_max_chaqueta_control) - MARGEN_DCHQ_KPA,
                   float(presion_suministro_vapor))

    def publicar(self) -> dict:
        """Solo lectura para estado.cascada_chaqueta: {nivel, consigna,
        valvula, dp}."""
        return {"nivel": self._nivel, "consigna": self._consigna,
                "valvula": self.valvula, "dp": self.dp}

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
        # en «banda» la consigna sigue a dp: la cuenta el umbral de dp
        cambio_consigna = nueva != anterior and nivel != NIVEL_BANDA
        cambio_dp = (self._dp_registrado is None
                     or abs(self.dp - self._dp_registrado) > UMBRAL_LOG_DP_KPA)
        if nivel != self._nivel or cambio_consigna or cambio_dp:
            logger.info(
                "Cascada chaqueta: pres_camara=%.1f pres_chaqueta=%.1f nivel=%s "
                "consigna=%s dp=%.1f",
                pc, pj, nivel, "—" if consigna is None else f"{consigna:.1f}", self.dp)
            self._dp_registrado = self.dp
        self._nivel = nivel
        self._consigna = consigna
