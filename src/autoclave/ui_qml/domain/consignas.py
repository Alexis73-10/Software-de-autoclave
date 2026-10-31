# ui_qml/domain/consignas.py
#
# Consignas de esterilización que se dibujan en la gráfica de los PDF de ciclos
# (D-14 de planeacion_ui_dual_pantalla.md, evidencia auditable): la temperatura
# de esterilización guardada con el ciclo (ciclos.temp_esterilizacion) y su
# presión de vapor saturado (p_saturacion_kpa, la misma función del control),
# solo en el tramo de la fase de esterilización.

from autoclave.core.runtime.steam import p_saturacion_kpa

# rango válido de p_saturacion_kpa (core/runtime/steam.py)
_T_MIN, _T_MAX = 99.0, 145.0


def consigna_esterilizacion(temp_esterilizacion, fases: list, t_fin_min: float) -> dict | None:
    """{"temp", "pres", "desde_min", "hasta_min"}, o None si no hay temperatura
    válida o el ciclo no llegó a la fase de esterilización. fases: inicios de
    fase (AcumuladorGrafica.inicios_de_fase); t_fin_min: último instante de la curva."""
    if isinstance(temp_esterilizacion, bool) or not isinstance(temp_esterilizacion, (int, float)):
        return None
    temp = float(temp_esterilizacion)
    if not _T_MIN <= temp <= _T_MAX:
        return None
    claves = [f.get("clave") for f in fases]
    if "esterilizacion" not in claves:
        return None
    i = claves.index("esterilizacion")
    desde = fases[i]["inicioMin"]
    hasta = fases[i + 1]["inicioMin"] if i + 1 < len(fases) else t_fin_min
    return {"temp": temp, "pres": p_saturacion_kpa(temp), "desde_min": desde, "hasta_min": hasta}
