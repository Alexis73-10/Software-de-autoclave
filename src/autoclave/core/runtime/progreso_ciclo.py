# Progreso del ciclo para la pantalla de ciclo en curso
# (docs/mis_plans/planeacion_pantalla_ciclo_en_curso.md §6 B1/B4 y §7).
#
# Módulo puro, sin hardware ni BD: traduce fase_ciclo a las 6 fases de la UI,
# decide qué fases aplican al programa y estima el tiempo restante a partir de
# las duraciones por fase del último ciclo COMPLETADO del mismo programa.
# Los tiempos que recibe son segundos de reloj monotónico (C-01).

FASES_UI = ("precalentamiento", "vacio", "calentamiento",
            "esterilizacion", "descompresion", "secado")

_FASE_BACKEND_A_UI = {
    "PRECALENTAMIENTO": "precalentamiento",
    "PRE_VACIO":        "vacio",
    "CALENTAMIENTO":    "calentamiento",
    "ESTERILIZACION":   "esterilizacion",
    "DESCOMPRESION":    "descompresion",
    "SECADO":           "secado",
}

# Cuando la fase activa supera su duración de referencia, su restante pasa a
# EXTENSION_MIN y se renueva cada vez que se agota, hasta el cambio de fase (§7 regla 2).
EXTENSION_MIN = 5
_EXTENSION_S = EXTENSION_MIN * 60.0

# Mismos tipos de pulso que PrevacioFase (_TIPOS en prevacio.py).
_TIPOS_PULSO = ("a", "b", "c", "d")


def fase_ui(fase_ciclo) -> str | None:
    """Fase de la UI para un fase_ciclo del backend; None si es un estado terminal."""
    return _FASE_BACKEND_A_UI.get(fase_ciclo)


def _numero(valor) -> float:
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def fases_aplicables(cycle, cap) -> list[str]:
    """Fases de la UI que el programa va a ejecutar, en orden.

    Replica las condiciones de salto de cada fase (test_progreso_ciclo verifica
    que coinciden con su update()): precalentamiento con tiempo 0, prevacío sin
    bomba o con todos los conteos de pulso en 0, secado sin bomba o con tiempo 0.
    Calentamiento, esterilización y descompresión siempre corren.
    """
    tiene_vacio = bool(getattr(cap, "has_vacuum", False))
    aplica = {
        "precalentamiento": _numero(cycle.get_param("precalentamiento", "tiempo_precalentamiento")) != 0,
        "vacio": tiene_vacio and any(
            int(_numero(cycle.get_param("prevacio", f"conteo_pulso_{t}"))) > 0 for t in _TIPOS_PULSO),
        "calentamiento": True,
        "esterilizacion": True,
        "descompresion": True,
        "secado": tiene_vacio and _numero(cycle.get_param("secado", "tiempo_secado")) != 0,
    }
    return [f for f in FASES_UI if aplica[f]]


def restante_fase(e: float, d_ref: float) -> float:
    """Restante de la fase activa con e segundos transcurridos y referencia d_ref."""
    if e < d_ref:
        return d_ref - e
    return _EXTENSION_S - ((e - d_ref) % _EXTENSION_S)


def tiempo_restante(aplicables, fase_activa, e_activa: float, referencias) -> float | None:
    """Restante total en segundos, o None si no se puede estimar (sin referencia
    para la fase activa o alguna siguiente, o fase activa fuera de las aplicables)."""
    if not referencias or fase_activa not in aplicables:
        return None
    pendientes = aplicables[aplicables.index(fase_activa):]
    if any(f not in referencias for f in pendientes):
        return None
    total = restante_fase(e_activa, referencias[fase_activa])
    total += sum(referencias[f] for f in pendientes[1:])
    return total


def armar_progreso(aplicables, filas_fases, fase_ciclo, transcurrido_s: float, referencias) -> dict:
    """Cuerpo de GET /cycle/current/progress.

    filas_fases: registros de ciclo_fases del ciclo actual (fase backend,
    inicio_s, fin_s, duracion_s; fin_s None = fase en curso).
    """
    activa = fase_ui(fase_ciclo)
    duraciones: dict[str, float] = {}
    inicio_activa = None
    for fila in filas_fases:
        f = fase_ui(fila["fase"])
        if f is None:
            continue
        if fila["fin_s"] is None:
            if f == activa:
                inicio_activa = fila["inicio_s"]
            continue
        duraciones[f] = duraciones.get(f, 0.0) + fila["duracion_s"]

    e_activa = max(0.0, transcurrido_s - inicio_activa) if inicio_activa is not None else 0.0

    fases = []
    for f in aplicables:
        if f == activa:
            fases.append({"fase": f, "estado": "activa", "duracion_s": e_activa})
        elif f in duraciones:
            fases.append({"fase": f, "estado": "completada", "duracion_s": duraciones[f]})
        else:
            fases.append({"fase": f, "estado": "pendiente", "duracion_s": None})

    if activa is not None:
        restante = tiempo_restante(aplicables, activa, e_activa, referencias)
    elif fase_ciclo == "COMPLETADO":
        restante = 0.0
    else:
        restante = None   # cancelado / fallo / emergencia: no hay estimación

    return {
        "fase_activa": activa,
        "fases": fases,
        "transcurrido_s": transcurrido_s,
        "restante_s": restante,
    }
