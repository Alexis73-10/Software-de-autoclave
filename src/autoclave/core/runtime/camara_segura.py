# core/runtime/camara_segura.py
#
# Condición "cámara segura" (planeacion_fin_de_ciclo_y_puertas.md §5, E2;
# tanda 2026-10-14 §1.1):
#
#   camara_segura = presión de cámara en [atm − rango_presion_atm, atm + rango_presion_atm]
#                   Y temperatura del sensor Principal ≤ temp_max_apertura
#
# Falla cerrada: sin lectura válida o sin configuración, NO es segura. La usan
# /status ("NO ABRIR"), la condición de inicio de ciclo (D-04), el interlock de
# apertura de puertas y "Apagar equipo" (§16).

import math

from autoclave.core.runtime.sensores_ciclo import temp_seguridad

CLAVE_ATM = "presion_admosferica"      # nombre real de la clave en global_params.json
CLAVE_RANGO = "rango_presion_atm"
CLAVE_TEMP_MAX = "temp_max_apertura"


def _numero(valor) -> float | None:
    """Número finito o None (bool no cuenta como número)."""
    if isinstance(valor, bool):
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def evaluar(estado, config, programas, profile=None) -> tuple[bool, str]:
    """(segura, motivo). `programas` (uno o una lista) deciden los sensores
    Principales: se toma el máximo y basta que falte uno para que no sea
    segura (temp_seguridad). None = temp_camara. El motivo es "" si es segura."""
    faltan = [c for c in (CLAVE_ATM, CLAVE_RANGO, CLAVE_TEMP_MAX)
              if _numero(config.get(c)) is None]
    if faltan:
        return False, f"Falta configuración: {', '.join(faltan)}"
    atm = _numero(config.get(CLAVE_ATM))
    rango = _numero(config.get(CLAVE_RANGO))
    temp_max = _numero(config.get(CLAVE_TEMP_MAX))

    pres = _numero(estado.sensores_pres.get("pres_camara"))
    if pres is None:
        return False, "Sin lectura válida de presión de cámara"
    temp = _numero(temp_seguridad(estado, programas, profile))
    if temp is None:
        return False, "Sin lectura válida de temperatura de cámara"
    if pres > atm + rango:
        return False, f"Sobrepresión en cámara ({pres:.0f} kPa)"
    if pres < atm - rango:
        return False, f"Cámara en vacío ({pres:.0f} kPa)"
    if temp > temp_max:
        return False, f"Temperatura demasiado alta ({temp:.0f} °C)"
    return True, ""
