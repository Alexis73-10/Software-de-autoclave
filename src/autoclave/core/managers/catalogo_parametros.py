# core/managers/catalogo_parametros.py
#
# Catálogo de límites de seguridad de los parámetros del ciclo (especificación 1
# de endurecimiento, RB-05 y Anexo B; tanda 2026-10-14 §1.6, T10).
#
# Reglas aplicadas (§1.6 de la instrucción, prevalece sobre el borrador):
#   - presión absoluta: 1 a 400 kPa (límite del modelo);
#   - temperatura absoluta: dentro de los límites del modelo, 1 a 200 °C;
#   - tiempos y timeouts: mínimo 1 en su unidad, salvo los que admiten 0 como
#     "no se ejecuta" o "sin espera" (Anexo A.3);
#   - otros del Anexo A.1/A.2 con mínimo mayor que 0;
#   - NUNCA rechazar un valor actual de los programas de fábrica (lo verifica
#     tests/test_t10_endurecimiento.py sobre todos los JSON).
# El rango efectivo es la intersección del catálogo y el min/max del propio
# JSON del programa (D-6). La tabla aplicada se entrega en
# docs/informes/limites_catalogo.md.

import math

PRESION_MIN, PRESION_MAX = 1, 400           # kPa
TEMPERATURA_MIN, TEMPERATURA_MAX = 1, 200   # °C

_PULSOS = ("a", "b", "c", "d")
_MODOS_ENFRIAMIENTO = ("modo_4", "modo_5")

# (fase, ruta) -> (mínimo, máximo); None = sin límite propio del catálogo
CATALOGO: dict[tuple[str, str], tuple] = {}


def _poner(fase: str, ruta: str, minimo, maximo, motivo: str) -> None:
    CATALOGO[(fase, ruta)] = (minimo, maximo, motivo)


# ── Presión absoluta (1–400 kPa) ───────────────────────────────────────────
for _fase, _ruta in (
    ("globals", "presion_chaqueta"),
    ("precalentamiento", "presion_precalentamiento"),
    ("secado", "presion_alta_secado"),
    ("secado", "presion_baja_secado"),
    ("secado", "presion_chaqueta_secado"),
    ("descompresion", "modo_3.presion_cambio"),
    *[("descompresion", f"{m}.presion_camara_enfriamiento") for m in _MODOS_ENFRIAMIENTO],
    *[("prevacio", f"presion_{nivel}_pulso_{p}") for nivel in ("alta", "baja") for p in _PULSOS],
):
    _poner(_fase, _ruta, PRESION_MIN, PRESION_MAX, "presión absoluta del modelo")

# ── Temperatura absoluta (límites del modelo) ──────────────────────────────
for _fase, _ruta in (
    ("calentamiento", "temperatura_calentamiento"),
    ("esterilizacion", "temperatura_esterilizacion"),
    ("estabilizacion", "temperatura_estabilizacion"),
    ("finalizacion", "temp_max_apertura"),
    *[("descompresion", f"{m}.temperatura_enfriamiento") for m in _MODOS_ENFRIAMIENTO],
):
    _poner(_fase, _ruta, TEMPERATURA_MIN, TEMPERATURA_MAX, "temperatura del modelo")

# ── Tiempos y timeouts: mínimo 1 en su unidad ──────────────────────────────
for _fase, _ruta in (
    ("precalentamiento", "timeout_precalentamiento"),
    ("prevacio", "timeout_alto"),
    ("prevacio", "timeout_bajo"),
    ("calentamiento", "timeout_calentamiento"),
    ("calentamiento", "timeout_recuperacion_estabilizacion"),
    ("esterilizacion", "tiempo_esterilizacion"),
    ("secado", "timeout_pulso"),
    ("finalizacion", "timeout_temperatura"),
    ("estabilizacion", "timeout_recuperacion"),
    *[("descompresion", f"modo_{n}.timeout") for n in range(1, 6)],
    *[("descompresion", f"{m}.tiempo_apertura_chaqueta") for m in _MODOS_ENFRIAMIENTO],
):
    _poner(_fase, _ruta, 1, None, "tiempo: mínimo 1 en su unidad")

# ── Otros del Anexo A.1 con 0 sustituido en silencio ───────────────────────
_poner("calentamiento", "rango_temp_estabilizacion", 0.1, None, "Anexo A.1: 0 se sustituye")
_poner("secado", "modo", 1, 3, "Anexo A.1: 0 se sustituye")
_poner("secado", "rango_chaqueta_secado", 1, None, "Anexo A.1: 0 se sustituye")
_poner("globals", "rango_presion_chaqueta", 1, None, "Anexo A.1: banda de ancho cero")
# modo 0 de descompresión se conserva (enfriamiento natural, decisión 1.2)
_poner("descompresion", "modo", 0, 5, "modo 0 conservado (enfriamiento natural)")

# Tiempos donde 0 es válido y documentado (Anexo A.3): sin límite del catálogo
CERO_VALIDO = frozenset({
    ("precalentamiento", "tiempo_precalentamiento"),
    ("secado", "tiempo_secado"),
    ("descompresion", "tiempo_pre_despresurizacion"),
    ("finalizacion", "tiempo_espera_apertura"),
    ("calentamiento", "tiempo_estable_preesterilizacion"),
    ("estabilizacion", "tiempo_estabilizacion"),
})

TIPOS_CARGA = ("solido", "liquido")
# D8-5.7 (tanda 8, Cristian 22-oct 12:08): con carga líquida solo los modos de
# descompresión 4, 5 y 0 (en ese orden en la UI): descomprimir rápido con
# líquido caliente produce ebullición violenta. El 0 (natural) no abre ninguna
# válvula hasta llegar a la atmosférica y al final deja la lenta (líquidos).
MODOS_LIQUIDO = (4, 5, 0)
# Modos con enfriamiento y contrapresión (exigen la contrapresión mínima)
MODOS_CONTRAPRESION = (4, 5)
# Modo al que pasa la descompresión al elegir carga líquida (D8-5.7)
MODO_AL_PASAR_A_LIQUIDO = 4
# Al volver a sólido sin defecto sólido del programa (DECISIÓN SIN CONFIRMAR de D8-5.7)
MODO_SOLIDO_SIN_DEFECTO = 1
# D8-5.8: parámetros "modo" de los programas y sus valores válidos (se eligen
# de una lista, no se escriben). Orden de presentación.
MODOS_PARAMETRO = {
    ("secado", "modo"): (1, 2, 3),
    ("descompresion", "modo"): (0, 1, 2, 3, 4, 5),
}

MOTIVO_MODO_LIQUIDO = ("Carga líquida: solo se permiten los modos de descompresión 4, 5 y 0 "
                       "(descomprimir rápido con líquido caliente produce ebullición violenta)")


class ErrorCoherencia(ValueError):
    """Reglas entre parámetros incumplidas. `codigo`: MODO_NO_PERMITIDO_LIQUIDO
    si el problema es el modo de descompresión con carga líquida;
    COHERENCIA_LIQUIDO para el resto de las reglas de carga líquida."""

    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = list(errores)
        self.codigo = codigo_coherencia(errores)


def codigo_coherencia(errores: list[str]) -> str:
    return "MODO_NO_PERMITIDO_LIQUIDO" if MOTIVO_MODO_LIQUIDO in errores else "COHERENCIA_LIQUIDO"


def modos_validos(parameters: dict, fase: str, path) -> list[int]:
    """Valores válidos de un parámetro "modo" (D8-5.8), ya filtrados por el
    tipo de carga del programa (D8-5.7); [] si no es un parámetro de modo."""
    ruta = ".".join(path) if not isinstance(path, str) else path
    modos = MODOS_PARAMETRO.get((fase, ruta))
    if modos is None:
        return []
    if fase == "descompresion" and _valor(parameters, "globals", "tipo_carga", defecto="solido") == "liquido":
        return list(MODOS_LIQUIDO)
    return list(modos)
# Contrapresión mínima sobre P_sat(temperatura de esterilización) para carga
# líquida (SAF-05 de T11): bajo ella la carga hierve al empezar a enfriar
MARGEN_CONTRAPRESION_LIQUIDO = 30.0   # kPa


def limites(fase: str, path) -> tuple:
    """(mínimo, máximo) del catálogo para el parámetro; (None, None) si no
    tiene límite propio."""
    ruta = ".".join(path) if not isinstance(path, str) else path
    entrada = CATALOGO.get((fase, ruta))
    return (entrada[0], entrada[1]) if entrada else (None, None)


def rango_efectivo(hoja: dict, fase: str, path) -> tuple:
    """Intersección del min/max del JSON y del catálogo (D-6)."""
    cmin, cmax = limites(fase, path)
    jmin, jmax = hoja.get("min"), hoja.get("max")
    minimo = max(v for v in (jmin, cmin) if v is not None) if (jmin, cmin) != (None, None) else None
    maximo = min(v for v in (jmax, cmax) if v is not None) if (jmax, cmax) != (None, None) else None
    return minimo, maximo


def coercionar(hoja: dict, fase: str, path, valor):
    """Tipos estrictos (RB-05.3) y rango efectivo. Lanza ValueError con el
    motivo. bool: solo true/false JSON; int: sin parte decimal; float: sin NaN
    ni infinito; nunca cadenas numéricas; enum: uno de `options`."""
    nombre = path[-1] if not isinstance(path, str) else path.split(".")[-1]
    tipo = hoja.get("type") or "int"
    if tipo == "bool":
        if not isinstance(valor, bool):
            raise ValueError(f"'{nombre}' debe ser verdadero o falso")
        return valor
    if tipo == "enum":
        opciones = hoja.get("options") or []
        if not isinstance(valor, str) or valor not in opciones:
            raise ValueError(f"'{nombre}' debe ser uno de: {', '.join(opciones)}")
        return valor
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"'{nombre}' debe ser numérico")
    if isinstance(valor, float) and not math.isfinite(valor):
        raise ValueError(f"'{nombre}' no es un número finito")
    if tipo == "float":
        convertido = float(valor)
    else:
        if isinstance(valor, float):
            if not valor.is_integer():
                raise ValueError(f"'{nombre}' debe ser entero")
            valor = int(valor)
        convertido = int(valor)
    minimo, maximo = rango_efectivo(hoja, fase, path)
    if minimo is not None and convertido < minimo:
        raise ValueError(f"'{nombre}' fuera de rango (mínimo {minimo})")
    if maximo is not None and convertido > maximo:
        raise ValueError(f"'{nombre}' fuera de rango (máximo {maximo})")
    return convertido


def _hojas(parameters: dict):
    def recorrer(fase, nodo, path):
        if isinstance(nodo, dict) and "value" in nodo and not isinstance(nodo.get("value"), dict):
            yield fase, path, nodo
            return
        if isinstance(nodo, dict):
            for clave, sub in nodo.items():
                yield from recorrer(fase, sub, path + [clave])
    for fase, nodo in (parameters or {}).items():
        yield from recorrer(fase, nodo, [])


def _valor(parameters: dict, *ruta, defecto=None):
    nodo = parameters
    try:
        for clave in ruta:
            nodo = nodo[clave]
        return nodo["value"]
    except (KeyError, TypeError):
        return defecto


def errores_coherencia(parameters: dict) -> list[str]:
    """Reglas entre parámetros para carga líquida (decisión 1.2; SAF-05 y
    SAF-06 de T11; D8-5.7): descompresión modo 4, 5 o 0; sin prevacío ni secado (vacío
    sobre líquido caliente); sin apertura automática; contrapresión de
    enfriamiento de al menos P_sat(temperatura de esterilización) + 30 kPa."""
    if _valor(parameters, "globals", "tipo_carga", defecto="solido") != "liquido":
        return []
    errores = []
    modo = _valor(parameters, "descompresion", "modo")
    if modo not in MODOS_LIQUIDO:
        errores.append(MOTIVO_MODO_LIQUIDO)
    if any(_valor(parameters, "prevacio", f"conteo_pulso_{p}", defecto=0) for p in _PULSOS):
        errores.append("Carga líquida: sin pulsos de prevacío")
    if _valor(parameters, "secado", "tiempo_secado", defecto=0):
        errores.append("Carga líquida: sin secado (tiempo_secado = 0)")
    if _valor(parameters, "finalizacion", "apertura_automatica", defecto=False) is True:
        errores.append("Carga líquida: sin apertura automática")
    if modo in MODOS_CONTRAPRESION:
        from autoclave.core.runtime.steam import p_saturacion_kpa
        t_est = _valor(parameters, "esterilizacion", "temperatura_esterilizacion")
        p_enfr = _valor(parameters, "descompresion", f"modo_{modo}", "presion_camara_enfriamiento")
        if isinstance(t_est, (int, float)) and isinstance(p_enfr, (int, float)):
            minimo = p_saturacion_kpa(t_est) + MARGEN_CONTRAPRESION_LIQUIDO
            if p_enfr < minimo:
                errores.append(f"Carga líquida: la contrapresión de enfriamiento debe ser al "
                               f"menos {minimo:.0f} kPa (P_sat + {MARGEN_CONTRAPRESION_LIQUIDO:.0f})")
    return errores


def errores_programa(parameters: dict) -> list[str]:
    """Validación al cargar (RB-05.5): cada valor contra su tipo y rango
    efectivo, más las reglas de coherencia. Lista vacía = programa válido."""
    errores = []
    for fase, path, hoja in _hojas(parameters):
        try:
            coercionar(hoja, fase, path, hoja.get("value"))
        except ValueError as e:
            errores.append(f"{fase}.{'.'.join(path)}: {e}")
    return errores + errores_coherencia(parameters)


# ── Plausibilidad de la calibración de dos puntos (S3a, tanda 2) ───────────
#
# Pendiente T3 SAF-03 (a): la calibración no tenía límites. Por canal (con
# valores por tipo como base), sobre los puntos que carga el técnico (lo que
# mostraba el equipo y el valor del patrón) y sobre la recta resultante:
#   rango:            los cuatro valores deben caer en el rango físico del canal;
#   separacion_min:   los dos puntos, en "mostrado" Y en "real", al menos así de separados;
#   pendiente:        real_span / mostrado_span (ganancia relativa); <= 0 es una
#                     pendiente invertida y siempre se rechaza. Fuera de
#                     (pendiente_aviso) pide confirmación; fuera de (pendiente_max), rechazo;
#   correccion_*:     |real − mostrado| en los dos puntos y en los extremos del
#                     rango OPERATIVO (donde la recta extrapola): mayor que
#                     correccion_aviso pide confirmación explícita (queda auditada);
#                     mayor que correccion_max se rechaza siempre.
#   desviacion_*:     ACUMULADA (revisión S3a): cada calibración se mide contra lo
#                     mostrado, que ya lleva la calibración de usuario vigente; para
#                     que una serie de pasos pequeños no sume una deriva ilimitada,
#                     se mide también cuánto se aparta la calibración RESULTANTE
#                     (ganancia/offset) de la neutra (1, 0) en los extremos
#                     operativos. Las de calibration.yaml (hasta 75 kPa, 6 °C) caben.
# Valores conservadores, DECISIÓN SIN CONFIRMAR de la tanda 2 (informe S3).
# Las recalibraciones reales de calibration.yaml (hasta 49 kPa y 1,2 °C en los
# puntos) caben en aviso o en normal; ninguna se rechaza.
CALIBRACION_PLAUSIBLE = {
    "temperature": {"rango": (0.0, 200.0), "operativo": (0.0, 150.0), "separacion_min": 20.0,
                    "correccion_aviso": 5.0, "correccion_max": 15.0,
                    "desviacion_aviso": 12.0, "desviacion_max": 25.0,
                    "pendiente_aviso": (0.95, 1.05), "pendiente_max": (0.8, 1.25), "unidad": "°C"},
    "pressure":    {"rango": (-10.0, 450.0), "operativo": (0.0, 350.0), "separacion_min": 50.0,
                    "correccion_aviso": 25.0, "correccion_max": 90.0,
                    "desviacion_aviso": 90.0, "desviacion_max": 120.0,
                    "pendiente_aviso": (0.8, 1.25), "pendiente_max": (0.6, 1.7), "unidad": "kPa"},
}

# Ajustes por canal sobre el tipo. Cámara: estricta. Chaqueta y empaques: más
# holgados (sus calibraciones de campo corrigen hasta 49 kPa). Drenaje: rango
# propio. Las ranuras sin sensor (temperature[3] retirada, [5] sin sensor) no
# tienen nombre en map_temp: nunca llegan aquí.
CALIBRACION_PLAUSIBLE_CANAL = {
    ("temperature", "temp_camara"):   {"correccion_aviso": 3.0, "correccion_max": 10.0},
    ("temperature", "temp_2_camara"): {"correccion_aviso": 3.0, "correccion_max": 10.0},
    ("temperature", "temp_ref"):      {"correccion_aviso": 3.0, "correccion_max": 10.0},
    ("temperature", "temp_drenaje"):  {"rango": (0.0, 150.0), "operativo": (0.0, 130.0)},
    ("pressure", "pres_camara"):      {"correccion_max": 50.0},
}


def evaluar_desviacion_acumulada(tipo: str, ganancia: float, offset: float,
                                 sensor: str | None = None) -> tuple[str | None, str]:
    """Nivel (None | "aviso" | "rechazo") y motivo según cuánto se aparta la
    calibración de usuario resultante (ganancia, offset) de la neutra, en los
    extremos del rango operativo."""
    lim = limites_calibracion(tipo, sensor)
    if lim is None:
        return "rechazo", f"tipo de canal sin límites de calibración: {tipo!r}"
    if not (math.isfinite(ganancia) and math.isfinite(offset)):
        return "rechazo", "calibración resultante no finita"
    u = lim["unidad"]
    desvio = max(abs(ganancia * x + offset - x) for x in lim["operativo"])
    if desvio > lim["desviacion_max"]:
        return "rechazo", (f"la calibración acumulada se aparta {desvio:.1f} {u} de la neutra, más que "
                           f"el máximo ({lim['desviacion_max']:g} {u}): revise el sensor")
    if desvio > lim["desviacion_aviso"]:
        return "aviso", (f"la calibración acumulada se aparta {desvio:.1f} {u} de la neutra "
                         f"(aviso > {lim['desviacion_aviso']:g} {u}): confirme que es correcta")
    return None, ""


def limites_calibracion(tipo: str, sensor: str | None = None) -> dict | None:
    base = CALIBRACION_PLAUSIBLE.get(tipo)
    if base is None:
        return None
    return {**base, **CALIBRACION_PLAUSIBLE_CANAL.get((tipo, sensor), {})}


def evaluar_calibracion(tipo: str, puntos: dict, sensor: str | None = None) -> tuple[str | None, str]:
    """(None, "") si es plausible; ("aviso", motivo) si pide confirmación;
    ("rechazo", motivo) si no se puede aplicar. `puntos`: shown_low, real_low,
    shown_high, real_high."""
    lim = limites_calibracion(tipo, sensor)
    if lim is None:
        return "rechazo", f"tipo de canal sin límites de calibración: {tipo!r}"
    u = lim["unidad"]
    try:
        v = {k: float(puntos[k]) for k in ("shown_low", "real_low", "shown_high", "real_high")}
    except (KeyError, TypeError, ValueError):
        return "rechazo", "puntos de calibración incompletos o no numéricos"
    if not all(math.isfinite(x) for x in v.values()):
        return "rechazo", "puntos de calibración no finitos"
    bajo, alto = lim["rango"]
    fuera = [k for k, x in v.items() if not bajo <= x <= alto]
    if fuera:
        return "rechazo", (f"valores fuera del rango físico del canal ({bajo:g} a {alto:g} {u}): "
                           + ", ".join(fuera))
    span_mostrado = v["shown_high"] - v["shown_low"]
    span_real = v["real_high"] - v["real_low"]
    if abs(span_mostrado) < lim["separacion_min"] or abs(span_real) < lim["separacion_min"]:
        return "rechazo", (f"los dos puntos deben estar separados al menos "
                           f"{lim['separacion_min']:g} {u}, tanto en lo mostrado como en el patrón")
    pendiente = span_real / span_mostrado
    if pendiente <= 0:
        return "rechazo", "pendiente invertida: el patrón y el equipo deben subir en el mismo sentido"
    p_min, p_max = lim["pendiente_max"]
    if not p_min <= pendiente <= p_max:
        return "rechazo", (f"ganancia relativa {pendiente:.2f} fuera de {p_min:g} a {p_max:g}: "
                           "revise el sensor o el patrón")
    # corrección en los dos puntos y en los extremos operativos de la recta
    op_bajo, op_alto = lim["operativo"]
    def recta(x):
        return v["real_low"] + (x - v["shown_low"]) * pendiente
    correccion = max([abs(v["real_low"] - v["shown_low"]), abs(v["real_high"] - v["shown_high"])]
                     + [abs(recta(x) - x) for x in (op_bajo, op_alto)])
    if correccion > lim["correccion_max"]:
        return "rechazo", (f"corrección de {correccion:.1f} {u}, mayor que la máxima "
                           f"({lim['correccion_max']:g} {u}): revise el sensor o el patrón")
    a_min, a_max = lim["pendiente_aviso"]
    if correccion > lim["correccion_aviso"]:
        return "aviso", (f"corrección de {correccion:.1f} {u}, mayor que "
                         f"{lim['correccion_aviso']:g} {u}: confirme que es correcta")
    if not a_min <= pendiente <= a_max:
        return "aviso", (f"ganancia relativa {pendiente:.2f} fuera de {a_min:g} a {a_max:g}: "
                         "confirme que es correcta")
    return None, ""
