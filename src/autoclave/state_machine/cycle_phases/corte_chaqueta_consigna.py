# state_machine/cycle_phases/corte_chaqueta_consigna.py
#
# A14-M2 (tanda 28, aprobado por Cristian; el defecto de margen_chaqueta_est
# queda SIN CONFIRMAR hasta el banco). Solo modo chaqueta, solo en
# CALENTAMIENTO (incluida ESTABLE_PREESTERILIZACION) y ESTERILIZACION:
# vapor_chaqueta se fuerza OFF cuando pres_chaqueta > consigna +
# margen_chaqueta_est.
#   - ESTERILIZACION: consigna = P_sp (A14-M1).
#   - CALENTAMIENTO: P_sp todavía no existe; consigna equivalente =
#     Psat(T_obj) + presion_add_calentamiento (el techo de la fase).
# Es un AND con la decisión de la fase y con el corte D-CHQ: nunca los
# reemplaza ni enciende nada. Sin lectura válida de pres_chaqueta, o sin
# consigna o margen utilizables, corta (falla cerrada, como D-CHQ). Sin
# histéresis por diseño: reabre en cuanto la lectura vuelve a estar en o bajo
# el umbral. Las fases lo evalúan en cada tick en que piden vapor_chaqueta ON
# (tramo ON del PWM de ESTERILIZACION desde H1, RECUPERACION y CALENTAMIENTO),
# así que con una presión de chaqueta ruidosa alrededor del umbral la válvula
# puede conmutar en cada tick (un fc05 por cambio). Añadir histéresis o
# enclavar el corte por tramo es DECISIÓN PENDIENTE de Cristian y debe medirse
# en banco (hoja de pruebas, bloque T28).
#
# M2-REC-01 (7-nov, decisión de Cristian): en ESTERILIZACION el corte no
# aplica mientras la cámara necesita vapor (RECUPERACION o pres_camara bajo la
# banda PWM), porque con la chaqueta cargada sobre el umbral bloqueaba la única
# fuente de vapor y la cámara caía hasta CIC-04 (ciclos 21 y 23 de SN260001).
# CALENTAMIENTO no cambia (hallazgo en docs/informes/m2_recuperacion/).
#
# El componente es puro: las fases lo consultan en cada tick.

import math

MARGEN_DEFECTO_KPA = 8.0
MARGEN_RANGO_KPA = (2.0, 30.0)


def _numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def margen_kpa(cycle) -> float:
    """esterilizacion.margen_chaqueta_est (kPa), recortado a 2–30; sin un
    valor numérico finito, el defecto (8 kPa). Un error al leer el programa
    también da el defecto."""
    try:
        valor = cycle.get_param("esterilizacion", "margen_chaqueta_est",
                                default=MARGEN_DEFECTO_KPA)
    except Exception:
        valor = None
    if not _numero(valor):
        return MARGEN_DEFECTO_KPA
    bajo, alto = MARGEN_RANGO_KPA
    return float(min(max(float(valor), bajo), alto))


def umbral_kpa(consigna, margen) -> float | None:
    """consigna + margen, o None si alguno no es un número finito."""
    if not (_numero(consigna) and _numero(margen)):
        return None
    return float(consigna) + float(margen)


def texto_lectura(pres) -> str:
    """Lectura de pres_chaqueta para el log (nunca lanza)."""
    return f"{float(pres):.1f}" if _numero(pres) else f"sin lectura ({pres!r})"


MOTIVO_RECUPERACION = "recuperacion"
MOTIVO_BAJO_BANDA = "bajo_banda"


def motivo_exencion(en_recuperacion, pres_camara, consigna, banda_baja) -> str | None:
    """M2-REC-01 (7-nov, decisión de Cristian; solo ESTERILIZACION): motivo
    por el que la cámara necesita vapor y el corte por consigna no aplica en
    este tick, o None. "recuperacion" si la fase está en RECUPERACION;
    "bajo_banda" si pres_camara < consigna - banda_baja (solo con lectura y
    consigna numéricas). Sin histéresis."""
    if en_recuperacion is True:
        return MOTIVO_RECUPERACION
    if (_numero(pres_camara) and _numero(consigna) and _numero(banda_baja)
            and float(pres_camara) < float(consigna) - float(banda_baja)):
        return MOTIVO_BAJO_BANDA
    return None


def debe_cortar(pres_chaqueta, consigna, margen, camara_necesita_vapor=False) -> bool:
    """True si vapor_chaqueta debe quedar OFF: sin lectura válida de
    pres_chaqueta, sin umbral calculable, o pres_chaqueta > consigna + margen.
    M2-REC-01: con camara_necesita_vapor True el umbral no corta, pero sin
    lectura válida o sin umbral se sigue cortando (falla cerrada). La exención
    nunca anula el aislamiento VCH-AIS ni el corte D-CHQ: los evalúa la fase y
    CICLO aparte."""
    umbral = umbral_kpa(consigna, margen)
    if umbral is None or not _numero(pres_chaqueta):
        return True
    if camara_necesita_vapor is True:
        return False
    return float(pres_chaqueta) > umbral
