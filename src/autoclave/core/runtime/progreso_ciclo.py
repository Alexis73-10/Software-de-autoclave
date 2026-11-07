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

# LLF (llenado de la barra de fases, HAZ-LLF-01 / REQ-36): una fase que no está
# "completada" nunca publica una fracción mayor que este tope, para que su
# círculo no se lea como fase cumplida (primera de las tres capas del tope).
TOPE_FRACCION_ACTIVA = 0.90

# Mismos tipos de pulso que PrevacioFase (_TIPOS en prevacio.py).
_TIPOS_PULSO = ("a", "b", "c", "d")


def fase_ui(fase_ciclo) -> str | None:
    """Fase de la UI para un fase_ciclo del backend; None si es un estado terminal."""
    return _FASE_BACKEND_A_UI.get(fase_ciclo)


def resultado(fase_ciclo) -> str | None:
    """Cómo terminó el ciclo, según fase_ciclo: None mientras corre una fase
    (o sin dato), "exitoso" (COMPLETADO), "cancelado" (CANCELADO) o "fallo"
    (cualquier otro cierre: FALLO_*, EMERGENCIA, SENSOR_AUSENTE, ...)."""
    if not fase_ciclo or fase_ciclo in _FASE_BACKEND_A_UI:
        return None
    if fase_ciclo == "COMPLETADO":
        return "exitoso"
    if fase_ciclo == "CANCELADO":
        return "cancelado"
    return "fallo"


# FC-06 (tanda 21): estado de la fase en que terminó un ciclo no exitoso
ESTADO_FALLIDA = "fallida"          # fallo y paro de emergencia
ESTADO_INTERRUMPIDA = "interrumpida"  # cancelación del operador


def fase_terminacion(filas_fases, fase_ciclo) -> str | None:
    """FC-06: fase de la UI en la que terminó el ciclo, o None si no se sabe.
    Con `FALLO_<FASE>` es esa fase; si no (cancelación, emergencia, sensor sin
    lectura, puerta, conexión...), la última fase registrada en ciclo_fases (la
    que estaba abierta al terminar y que cerró el CycleLogger)."""
    if isinstance(fase_ciclo, str) and fase_ciclo.startswith("FALLO_"):
        propia = fase_ui(fase_ciclo[len("FALLO_"):])
        if propia is not None:
            return propia
    ultima = None
    for fila in filas_fases or []:
        try:
            f = fase_ui(fila["fase"])
            inicio = fila["inicio_s"]
        except (KeyError, TypeError, IndexError):
            continue
        if f is None:
            continue
        clave = inicio if isinstance(inicio, (int, float)) and not isinstance(inicio, bool) else 0.0
        if ultima is None or clave >= ultima[0]:
            ultima = (clave, f)
    return ultima[1] if ultima is not None else None


def tipo_terminacion(fase_ciclo) -> str | None:
    """FC-13: "exitoso", "cancelado", "emergencia" o "fallo" según fase_ciclo;
    None mientras el ciclo corre. Un cierre desconocido es "fallo" (falla
    cerrada, como resultado())."""
    r = resultado(fase_ciclo)
    if r == "fallo" and fase_ciclo == "EMERGENCIA":
        return "emergencia"
    return r


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


def _segundos_validos(valor) -> bool:
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and valor == valor and valor not in (float("inf"), float("-inf")) and valor >= 0)


def _segundos_llf(valor) -> float | None:
    """LLF: `valor` como float finito >= 0, o None si no es un número de segundos
    convertible (p. ej. un int gigante que desborda float). Solo para el LLF."""
    if not _segundos_validos(valor):
        return None
    try:
        v = float(valor)
    except (OverflowError, ValueError, TypeError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _acotar(x: float) -> float:
    return round(min(max(x, 0.0), TOPE_FRACCION_ACTIVA), 4)


def fraccion_fase(estado, e_s, referencia_s, restante_propio_s=None, total_propio_s=None,
                  *, conteo_propio: bool = False) -> float | None:
    """LLF A-2: fracción de llenado (0..1) del círculo de una fase.

    - completada → 1.0; pendiente → 0.0; fallida, interrumpida o desconocido → None.
    - activa con `conteo_propio` (solo esterilización): 1 - restante/total
      acotado a [0, TOPE_FRACCION_ACTIVA]; si falta el restante o el total
      (o el total no es > 0) → 0.0.
    - activa sin conteo propio: e/(e + restante_fase(e, ref)) acotado a
      [0, TOPE_FRACCION_ACTIVA]; sin referencia válida > 0 → None.
    Una fase no completada nunca pasa de TOPE_FRACCION_ACTIVA."""
    if estado == "completada":
        return 1.0
    if estado == "pendiente":
        return 0.0
    if estado != "activa":
        return None
    if conteo_propio:
        rp, tp = _segundos_llf(restante_propio_s), _segundos_llf(total_propio_s)
        if rp is not None and tp is not None and tp > 0:
            q = rp / tp
            return _acotar(1.0 - q) if q == q and q != float("inf") else 0.0
        return 0.0
    ref = _segundos_llf(referencia_s)
    if ref is None or ref <= 0:
        return None
    e = _segundos_llf(e_s) or 0.0
    r = restante_fase(e, ref)
    if e + r <= 0:
        return 0.0
    return _acotar(e / (e + r))


def tiempo_restante(aplicables, fase_activa, e_activa: float, referencias,
                    restante_activa: float | None = None) -> float | None:
    """Restante total en segundos, o None si no se puede estimar (sin referencia
    para la fase activa o alguna siguiente, o fase activa fuera de las aplicables).

    `restante_activa` (E12, tanda 12, C-13.7): restante real de la fase
    activa cuando la fase lo conoce (esterilización: conteo de exposición,
    que una excursión de Referencia detiene y reinicia); entonces la fase
    activa no necesita referencia."""
    if fase_activa not in aplicables:
        return None
    pendientes = aplicables[aplicables.index(fase_activa):]
    usa_propio = _segundos_validos(restante_activa)
    necesarias = pendientes[1:] if usa_propio else pendientes
    if (not referencias and necesarias) or any(f not in (referencias or {}) for f in necesarias):
        return None
    if usa_propio:
        total = float(restante_activa)
        total += sum(referencias[f] for f in pendientes[1:])
        return total
    total = restante_fase(e_activa, referencias[fase_activa])
    total += sum(referencias[f] for f in pendientes[1:])
    return total


def armar_progreso(aplicables, filas_fases, fase_ciclo, transcurrido_s: float, referencias,
                   restante_exposicion_s: float | None = None, *,
                   total_exposicion_s: float | None = None) -> dict:
    """Cuerpo de GET /cycle/current/progress.

    filas_fases: registros de ciclo_fases del ciclo actual (fase backend,
    inicio_s, fin_s, duracion_s; fin_s None = fase en curso).
    restante_exposicion_s (E12, tanda 12, C-13.7): estado.exposicion_restante_s
    que publica ESTERILIZACION; con la esterilización activa reemplaza la
    estimación por historial de esa fase.
    total_exposicion_s (LLF A-1, solo por palabra clave): estado.exposicion_total_s;
    con el restante da la fracción y la referencia_s de la esterilización activa.
    Cada fase lleva además `fraccion` (fraccion_fase) y `referencia_s`.
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

    # FC-06 (tanda 21): en un ciclo que no terminó exitoso, la fase en que
    # terminó queda "fallida" (fallo, emergencia) o "interrumpida"
    # (cancelación); las anteriores, "completada"; las siguientes, "pendiente".
    # Antes la fase cortada (ya cerrada en ciclo_fases) aparecía completada.
    term = None
    res = resultado(fase_ciclo)
    if res in ("fallo", "cancelado"):
        term = fase_terminacion(filas_fases, fase_ciclo)
        if term in aplicables:
            corte = aplicables.index(term)
            estado_term = ESTADO_INTERRUMPIDA if res == "cancelado" else ESTADO_FALLIDA
            for i, item in enumerate(fases):
                if i < corte:
                    item["estado"] = "completada"
                elif i == corte:
                    item["estado"] = estado_term
                else:
                    item["estado"] = "pendiente"
                    item["duracion_s"] = None

    # LLF A-2: fracción de llenado y referencia por fase, con el estado
    # definitivo (después de FC-06). No cambia restante_s ni los demás campos.
    for item in fases:
        f, est = item["fase"], item["estado"]
        conteo_propio = (f == "esterilizacion" and est == "activa")
        try:
            ref = referencias.get(f) if isinstance(referencias, dict) else None
            ref_valida = _segundos_llf(ref)
            tot = _segundos_llf(total_exposicion_s)
            propio_valido = (conteo_propio and _segundos_llf(restante_exposicion_s) is not None
                             and tot is not None and tot > 0)
            item["fraccion"] = fraccion_fase(est, item["duracion_s"], ref_valida,
                                             restante_exposicion_s if conteo_propio else None,
                                             total_exposicion_s if conteo_propio else None,
                                             conteo_propio=conteo_propio)
            item["referencia_s"] = tot if propio_valido else ref_valida
        except Exception:   # el LLF nunca debe tumbar el endpoint
            item["fraccion"] = None
            item["referencia_s"] = None

    if activa is not None:
        propio = restante_exposicion_s if activa == "esterilizacion" else None
        restante = tiempo_restante(aplicables, activa, e_activa, referencias, propio)
    elif fase_ciclo == "COMPLETADO":
        restante = 0.0
    else:
        restante = None   # cancelado / fallo / emergencia: no hay estimación

    return {
        "fase_activa": activa,
        "resultado": res,
        # FC-06: fase de la UI en que terminó (None en curso, exitoso o sin dato)
        "fase_terminacion": term,
        "fases": fases,
        "transcurrido_s": transcurrido_s,
        "restante_s": restante,
    }


# ── T30-02 (tanda 30): progreso de la fase activa ───────────────────────
# Dato crudo (°C, kPa absolutos, segundos) del avance de la fase activa; el
# texto, las unidades de presentación y el idioma los pone la UI
# (ui_qml/domain/ciclo_en_curso.py). Nada de control lo lee.

_NIVEL_BAJO = ("DECOMPRESION", "VACIO_BAJO", "HOLD_BAJO", "APAGANDO_VACIO")


def _finito(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    v = float(valor)
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _param(cycle, *ruta, default=None):
    try:
        return cycle.get_param(*ruta, default=default)
    except Exception:
        return default


def _pulso_prevacio(estado, cycle) -> dict:
    """Pulso en curso / total del prevacío (suma de A, B, C y D) y nivel."""
    import re
    conteos = []
    for t in _TIPOS_PULSO:
        n = _finito(_param(cycle, "prevacio", f"conteo_pulso_{t}", default=0))
        conteos.append(max(0, int(n)) if n is not None else 0)
    total = sum(conteos)
    m = re.match(r"^\s*([A-Da-d])\s+(\d+)\s*/\s*(\d+)\s*$",
                 str(getattr(estado, "prevacio_progreso", "") or ""))
    pulso = None
    if m and total > 0:
        pulso = sum(conteos[:"abcd".index(m.group(1).lower())]) + int(m.group(2))
        pulso = pulso if 1 <= pulso <= total else None
    paso = getattr(estado, "sub_estado_ciclo", "")
    nivel = None
    if isinstance(paso, str) and paso:
        nivel = "bajo" if paso in _NIVEL_BAJO else "alto"
    return {"tipo": "prevacio", "pulso": pulso, "total": total if total > 0 else None,
            "nivel": nivel if pulso is not None else None}


def _margen_atm(config) -> float:
    v = _finito(config.get("rango_presion_atm")) if config is not None else None
    return v if v is not None and v > 0 else 20.0


def detalle_fase(fase_activa, estado, cycle, cap=None, config=None) -> dict | None:
    """`detalle_fase` de GET /cycle/current/progress: avance crudo de la fase
    activa, o None sin fase activa o ante cualquier error (nunca tumba el
    endpoint). `tipo`:
    - "presion": actual / objetivo en kPa abs (precalentamiento, descompresión);
    - "temperatura": actual / objetivo en °C (calentamiento, descompresión 4/5
      enfriando);
    - "prevacio": pulso, total, nivel ("bajo"|"alto");
    - "estabilizando": transcurrido_s / total_s de la ventana de estabilización;
    - "exposicion": transcurrido_s / total_s y, con F0 activo, f0 / f0_objetivo;
    - "tiempo": transcurrido_s / total_s (secado)."""
    try:
        if fase_activa not in FASES_UI or cycle is None:
            return None
        pres = getattr(estado, "sensores_pres", None) or {}
        temp = getattr(estado, "sensores_temp", None) or {}
        if fase_activa == "precalentamiento":
            return {"tipo": "presion", "actual": _finito(pres.get("pres_chaqueta")),
                    "objetivo": _finito(_param(cycle, "precalentamiento", "presion_precalentamiento"))}
        if fase_activa == "vacio":
            return _pulso_prevacio(estado, cycle)
        if fase_activa == "calentamiento":
            est_s, est_t = _finito(getattr(estado, "estabilizacion_s", None)),                 _finito(getattr(estado, "estabilizacion_total_s", None))
            if getattr(estado, "fase_en_sostenimiento", False) is True and est_s is not None                     and est_t is not None and est_t > 0:
                return {"tipo": "estabilizando", "transcurrido_s": est_s, "total_s": est_t}
            return {"tipo": "temperatura", "actual": _finito(temp.get("temp_camara")),
                    "objetivo": _finito(_param(cycle, "calentamiento", "temperatura_calentamiento"))}
        if fase_activa == "esterilizacion":
            total = _finito(getattr(estado, "exposicion_total_s", None))
            resto = _finito(getattr(estado, "exposicion_restante_s", None))
            det = {"tipo": "exposicion",
                   "transcurrido_s": max(0.0, total - resto) if total is not None and resto is not None else None,
                   "total_s": total, "f0": None, "f0_objetivo": None}
            f0_activo = bool(_param(cycle, "globals", "F0")) and (
                cap is None or bool(getattr(cap, "has_liquid_sensor", False)))
            if f0_activo:
                det["f0"] = _finito(getattr(estado, "f0_acumulado", None))
                det["f0_objetivo"] = _finito(_param(cycle, "globals", "F0_objetivo"))
            return det
        if fase_activa == "descompresion":
            modo = _param(cycle, "descompresion", "modo", default=0)
            if modo in (4, 5) and getattr(estado, "descompresion_enfriando", False) is True:
                return {"tipo": "temperatura", "actual": _finito(temp.get("temp_camara")),
                        "objetivo": _finito(_param(cycle, "descompresion", f"modo_{modo}",
                                                   "temperatura_enfriamiento", default=80.0))}
            atm = _finito(config.get("presion_admosferica")) if config is not None else None
            atm = atm if atm is not None else 101.3
            margen = _finito(_param(cycle, "descompresion", "presion_fin_descompresion"))
            if modo not in (1, 2, 3, 4, 5) or margen is None or margen <= 0:
                margen = _margen_atm(config)    # modo 0 y T29-03 sin parámetro válido
            return {"tipo": "presion", "actual": _finito(pres.get("pres_camara")),
                    "objetivo": atm + margen}
        # secado
        return {"tipo": "tiempo",
                "transcurrido_s": _finito(getattr(estado, "secado_transcurrido_s", None)),
                "total_s": _finito(getattr(estado, "secado_total_s", None))}
    except Exception:
        return None


# ── FC-13 (tanda 21): datos de la pantalla de fin de ciclo ───────────────

def _texto_o_none(valor) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def observaciones_de_avisos(avisos) -> list[dict]:
    """FC-08: [{sensor, hora, fase}] de las observaciones de Referencia sin
    lectura de estado.avisos_ciclo. `hora` "HH:MM" (reloj de pared, al
    detectarla); `fase` es la fase de la UI (FASES_UI) o None si no se sabe."""
    from autoclave.services.domain.logging.ticket_formatter import observaciones_referencia
    salida = []
    for o in observaciones_referencia(avisos if isinstance(avisos, list) else []):
        salida.append({"sensor": o["sensor"], "hora": o["hora"] or None,
                       "fase": fase_ui(o["fase"])})
    return salida


def armar_terminacion(fase_ciclo, fase_term, codigo, valores, motivo, hora_fin,
                      cancelado_por, avisos) -> dict | None:
    """FC-13: `terminacion` de GET /cycle/current/progress; None mientras el
    ciclo corre.

    {tipo: "fallo"|"emergencia"|"cancelado"|"exitoso", codigo, valores, motivo,
     fase, hora_fin, cancelado_por, observaciones}
    - codigo: código de la alarma causante (estado.codigo_fallo); emergencia
      SIS-01; fallo sin código conocido, None (y motivo el texto crudo).
    - valores: parámetros de la causa (dict, {} sin código).
    - fase: fase de la UI en que terminó (FC-06); None en exitoso.
    - hora_fin: ISO de pared del cierre (segundos) o None.
    - cancelado_por: usuario identificado que canceló (FC-12), solo en cancelado.
    - observaciones: [{sensor, hora, fase}] de Referencia sin lectura (FC-08)."""
    tipo = tipo_terminacion(fase_ciclo)
    if tipo is None:
        return None
    codigo = _texto_o_none(codigo)
    if tipo == "emergencia" and codigo is None:
        codigo = "SIS-01"
    if tipo in ("exitoso", "cancelado"):
        codigo = None
    return {
        "tipo": tipo,
        "codigo": codigo,
        "valores": dict(valores) if codigo is not None and isinstance(valores, dict) else {},
        "motivo": _texto_o_none(motivo) if tipo in ("fallo", "emergencia") else None,
        "fase": None if tipo == "exitoso" else fase_term,
        "hora_fin": _texto_o_none(hora_fin),
        "cancelado_por": _texto_o_none(cancelado_por) if tipo == "cancelado" else None,
        "observaciones": observaciones_de_avisos(avisos),
    }


def _valores_json(texto) -> dict:
    import json
    try:
        v = json.loads(texto) if isinstance(texto, str) and texto else {}
    except (TypeError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def alarmas_del_ciclo(filas, codigo_causa) -> list[dict]:
    """FC-13: `alarmas_ciclo` a partir de las filas de alarmas_historial del
    ciclo (orden aparecida ascendente). Se quita la fila de la causa: la más
    reciente con `codigo_causa` (la que activó el fallo). Cada elemento:
    {codigo, nivel, titulo, descripcion, valores, aparecida, resuelta};
    descripcion = descripcion_final si existe, si no descripcion_inicial."""
    filas = [f for f in (filas or []) if isinstance(f, dict)]
    quitar = None
    if isinstance(codigo_causa, str) and codigo_causa:
        for i in range(len(filas) - 1, -1, -1):
            if filas[i].get("codigo") == codigo_causa:
                quitar = i
                break
    salida = []
    for i, f in enumerate(filas):
        if i == quitar:
            continue
        salida.append({
            "codigo": f.get("codigo"),
            "nivel": f.get("nivel"),
            "titulo": f.get("titulo"),
            "descripcion": f.get("descripcion_final") or f.get("descripcion_inicial") or "",
            "valores": _valores_json(f.get("valores_json")),
            "aparecida": f.get("aparecida"),
            "resuelta": f.get("resuelta"),
        })
    return salida
