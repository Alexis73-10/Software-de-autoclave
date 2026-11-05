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
# histéresis: reabre en cuanto la lectura vuelve a estar en o bajo el umbral
# (el PWM y el aislamiento ya espacian las órdenes).
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


def debe_cortar(pres_chaqueta, consigna, margen) -> bool:
    """True si vapor_chaqueta debe quedar OFF: sin lectura válida de
    pres_chaqueta, sin umbral calculable, o pres_chaqueta > consigna + margen."""
    umbral = umbral_kpa(consigna, margen)
    if umbral is None or not _numero(pres_chaqueta):
        return True
    return float(pres_chaqueta) > umbral
