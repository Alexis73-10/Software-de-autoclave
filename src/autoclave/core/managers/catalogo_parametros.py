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

# ── Límites físicos de presión (tanda 12, C-04 / C-05; kPa absolutos) ─────
# DEU-01 (tanda 16, D-DEU-1): estas cuatro constantes quedan SOLO como
# defectos. Los valores vigentes son los de Parámetros del equipo
# (global_params.json / system_params), que se leen con _limites() a través
# del ConfigManager que el backend fija con fijar_config_equipo() al arrancar;
# sin él (pruebas, herramientas, la interfaz) rigen estos defectos.
PRESION_FONDO_ESCALA = 400.0
# Suministro regulado a 40 psig: 40 × 6.894757 = 275.8 kPa manométricos, más
# 74.6 kPa de atmósfera local en Bogotá = 350.4 ≈ 350 kPa absolutos (a nivel
# del mar serían ≈ 377 kPa abs). Solo genera advertencias, nunca rechazo.
PRESION_SUMINISTRO = 350.0
# Válvulas de alivio (por debajo del fondo de escala): el rechazo es aquí
PRESION_ALIVIO_CAMARA = 385.0
PRESION_ALIVIO_CHAQUETA = 385.0
# C-04.2: máximo de presion_add_calentamiento / presion_add_esterilizacion
PRESION_ADD_MAX = 30
# C-04.4: valor al que la migración correctiva baja un presion_add_* > 30
PRESION_ADD_MIGRADA = 9.0
ORIGEN_MIGRACION_T12 = "migración tanda 12"
# C-05: consigna de chaqueta en CICLO y su banda fija (±10 kPa)
BANDA_CHAQUETA_KPA = 10.0
DELTA_TEMP_CHAQUETA_DEFECTO = 1.5      # °C (clase diferencia, 0–5)
MARGEN_FLUJO_CHAQUETA_DEFECTO = 15.0   # kPa (clase diferencia, 0–40)
TIMEOUT_EXCURSION_REFERENCIA_DEFECTO = 5   # min (int, 1–30), C-13.4
# Tanda 16 (VCH §5 y D-14.5): parámetros de programa nuevos
HISTERESIS_CIERRE_CAMARA_DEFECTO = 3.0     # kPa (clase diferencia, 1–10)
MAX_REINICIOS_EXPOSICION_DEFECTO = 3       # int, 0–10
# Tanda 28 (A14-M2): margen sobre la consigna para el corte de vapor_chaqueta
# en modo chaqueta (DECISIÓN SIN CONFIRMAR el defecto hasta el banco)
MARGEN_CHAQUETA_EST_DEFECTO = 8.0          # kPa (clase diferencia, 2–30)
# Tanda 28 (A12): prevacío, paso DECOMPRESION de cada pulso. La bomba arranca
# con pres <= atm + presion_inicio_vacio (antes atm + rango_presion_atm, el
# rango de cámara segura, que podía no alcanzarse nunca) y el paso tiene
# tiempo límite propio. Defectos DECISIÓN SIN CONFIRMAR.
PRESION_INICIO_VACIO_DEFECTO = 10.0        # kPa sobre la atmosférica (diferencia, 0–30)
TIMEOUT_DESCOMPRESION_DEFECTO = 5          # min (int, 1–30)
ORIGEN_MIGRACION_T28_A12 = "migración tanda 28 (A12)"
# Tanda 29 (T29-03, decisión de Cristian): DESCOMPRESION termina (modos 1 a 5,
# sólidos y líquidos) con pres <= atm + presion_fin_descompresion (antes atm +
# rango_presion_atm: el vapor residual la sostenía apenas encima). El modo 0
# no cambia. Defecto y rango DECISIÓN SIN CONFIRMAR hasta el banco.
PRESION_FIN_DESCOMPRESION_DEFECTO = 10.0   # kPa sobre la atmosférica (diferencia, 2–20)
ORIGEN_MIGRACION_T29_03 = "migración tanda 29 (T29-03)"
# Tanda 29 (T29-05): un programa sólido con descompresión 4 o 5 (enfriamiento
# de líquidos) pasa al modo del programa de fábrica si es sólido y válido; si
# no, a MODO_SOLIDO_SIN_DEFECTO (auditoría, SIS-06 y .bak).
ORIGEN_MIGRACION_T29_05 = "migración tanda 29 (T29-05)"

# ── P1 (tanda 16, D-14.1): coherencia de la salida de RECUPERACION ─────────
# Con vapor saturado, la temperatura más alta que permite el techo
# P_control_max = Psat(T_est) + presion_add_esterilizacion es Tsat(P_control_max).
# Si queda por debajo del umbral de salida de RECUPERACION (T_est +
# brecha_segura_temperatura + histéresis), el control nunca pasa a PWM. Se
# rechaza el programa si Tsat(techo) < T_est + brecha + histéresis + margen.
# DECISIÓN SIN CONFIRMAR (se reajusta con el banco): margen 0,3 K. La
# histéresis refleja _HIST_RECUP_TEMP_K de esterilizacion.py (una prueba
# verifica que coinciden; no se importa para no acoplar el catálogo a la fase).
HIST_SALIDA_RECUPERACION_K = 0.3
MARGEN_COHERENCIA_RECUPERACION_K = 0.3
CODIGO_COHERENCIA_RECUPERACION = "COHERENCIA_RECUPERACION"
# P2 (D-14.2): subida de presion_add_esterilizacion al mínimo de P1,
# redondeado hacia arriba a este paso (DECISIÓN SIN CONFIRMAR: 0,5 kPa). El
# paso 1 de P2 (brecha_segura_temperatura 0,3 → 1,0) lo retiró la tanda 28
# (A14-M3, decisión de Cristian): se aplicaba en cada carga y revertiría el 0,3.
PASO_MIGRACION_PRESION_ADD = 0.5
ORIGEN_MIGRACION_T16 = "migración tanda 16"
# A14-M3 (tanda 28, decisión de Cristian): brecha_segura_temperatura = 0,3 °C
# (defecto). Migración única al cargar: un programa con 1,0 (el valor de la
# tanda 12/16) pasa a 0,3; un valor distinto de 1,0 y 0,3 no se toca. La marca
# MARCA_MIGRACION_T28_M3 en la hoja del parámetro la hace idempotente: un 1,0
# fijado después a mano se conserva.
BRECHA_SEGURA_TEMPERATURA_DEFECTO = 0.3
BRECHA_SEGURA_ANTERIOR_T16 = 1.0
MARCA_MIGRACION_T28_M3 = "migrado_t28_m3"
ORIGEN_MIGRACION_T28_M3 = "migración tanda 28 (M3)"

# Códigos de rechazo (ErrorCoherencia.codigo) de los límites físicos
CODIGO_LIMITE_CAMARA = "LIMITE_PRESION_CAMARA"
CODIGO_LIMITE_CHAQUETA = "LIMITE_PRESION_CHAQUETA"
CODIGO_LIMITE_CONSIGNA = "LIMITE_CONSIGNA_CHAQUETA"
# Claves de las advertencias no bloqueantes (texto opciones.<clave> en i18n)
ADVERTENCIA_TECHO_CAMARA = "aviso_techo_sobre_suministro"
ADVERTENCIA_CHAQUETA_ABIERTA = "aviso_chaqueta_abierta"
# A14-M1 (tanda 28): la banda PWM de ESTERILIZACION, anclada a
# P_sp = Psat(T_est + brecha_segura_temperatura + 0,3), queda cerca del techo
# de control: P_sp + 1 > P_control_max - 5 (advertencia, no rechazo)
ADVERTENCIA_BANDA_PWM_TECHO = "aviso_banda_pwm_techo"
BANDA_PWM_ALTA_KPA = 1.0          # refleja _BANDA_PWM_ALTA de esterilizacion.py
MARGEN_BANDA_TECHO_KPA = 5.0

_PULSOS = ("a", "b", "c", "d")
_MODOS_ENFRIAMIENTO = ("modo_4", "modo_5")

# (fase, ruta) -> (mínimo, máximo); None = sin límite propio del catálogo
CATALOGO: dict[tuple[str, str], tuple] = {}


def _poner(fase: str, ruta: str, minimo, maximo, motivo: str) -> None:
    CATALOGO[(fase, ruta)] = (minimo, maximo, motivo)


# ── DEU-01 (tanda 16): proveedor de los límites del equipo ─────────────────
_config_equipo = None


def fijar_config_equipo(config) -> None:
    """DEU-01: el backend fija su ConfigManager al arrancar, ANTES de cargar
    los programas. Se guarda la referencia (no una copia): un cambio de los
    límites en Parámetros del equipo rige en la siguiente validación. None
    vuelve a los defectos."""
    global _config_equipo
    _config_equipo = config


def limites_presion_equipo():
    """Límites de presión vigentes (limites_equipo.LimitesPresion, kPa abs):
    los del equipo o, sin ConfigManager fijado, los defectos. Nunca lanza."""
    # import diferido: limites_equipo importa este módulo a nivel de módulo
    from autoclave.core.managers import limites_equipo
    return limites_equipo.limites_presion(_config_equipo)


_limites = limites_presion_equipo


def limites_para_mensaje() -> dict:
    """Valores de los límites del equipo para los textos de la pantalla
    (claves alivio_camara, alivio_chaqueta, suministro y fondo_escala)."""
    lim = _limites()
    return {"alivio_camara": round(lim.alivio_camara, 1),
            "alivio_chaqueta": round(lim.alivio_chaqueta, 1),
            "suministro": round(lim.suministro, 1),
            "fondo_escala": round(lim.fondo_escala, 1)}


# ── Presión absoluta (1–400 kPa) ───────────────────────────────────────────
_MOTIVO_PRESION_ABSOLUTA = "presión absoluta del modelo"
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
    _poner(_fase, _ruta, PRESION_MIN, PRESION_MAX, _MOTIVO_PRESION_ABSOLUTA)

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
# ── Tanda 12 ───────────────────────────────────────────────────────────────
for _fase, _ruta in (("calentamiento", "presion_add_calentamiento"),
                     ("esterilizacion", "presion_add_esterilizacion")):
    _poner(_fase, _ruta, 0, PRESION_ADD_MAX, "C-04.2 (tanda 12): techo de control, máximo 30 kPa")
_poner("globals", "delta_temp_chaqueta", 0, 5, "C-05.3 (tanda 12): consigna de chaqueta")
_poner("globals", "margen_flujo_chaqueta", 0, 40, "C-05.3 (tanda 12): consigna de chaqueta")
_poner("esterilizacion", "timeout_excursion_referencia", 1, 30,
       "C-13.4 (tanda 12): tiempo límite de una excursión de Referencia")
# ── Tanda 16 ───────────────────────────────────────────────────────────────
for _fase in ("calentamiento", "esterilizacion"):
    _poner(_fase, "histeresis_cierre_camara", 1, 10,
           "VCH §5 (tanda 16): reapertura de vapor_camara bajo el techo")
_poner("esterilizacion", "max_reinicios_exposicion", 0, 10,
       "D-14.5 (tanda 16): tope de reinicios de la exposición")
# ── Tanda 28 ───────────────────────────────────────────────────────────────
_poner("esterilizacion", "margen_chaqueta_est", 2, 30,
       "A14-M2 (tanda 28): margen del corte de vapor_chaqueta sobre la consigna")
_poner("prevacio", "presion_inicio_vacio", 2, 15,
       "A12 (tanda 28): presión sobre la atmosférica para arrancar el vacío del pulso")
_poner("prevacio", "timeout_descompresion", 1, 30,
       "A12 (tanda 28): tiempo límite del paso de descompresión del pulso")
# ── Tanda 29 ───────────────────────────────────────────────────────────────
_poner("descompresion", "presion_fin_descompresion", 2, 20,
       "T29-03 (tanda 29): presión sobre la atmosférica para terminar la descompresión")
# modo 0 de descompresión se conserva (enfriamiento natural, decisión 1.2)
_poner("descompresion", "modo", 0, 5, "modo 0 conservado (enfriamiento natural)")

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
# T29-05 (tanda 29): con carga sólida solo los modos 0 a 3; 4 y 5 son de
# enfriamiento de líquidos (contrapresión y agua de chaqueta)
MODOS_SOLIDO = (0, 1, 2, 3)
# D8-5.8: parámetros "modo" de los programas y sus valores válidos (se eligen
# de una lista, no se escriben). Orden de presentación.
MODOS_PARAMETRO = {
    ("secado", "modo"): (1, 2, 3),
    ("descompresion", "modo"): (0, 1, 2, 3, 4, 5),
}

MOTIVO_MODO_LIQUIDO = ("Carga líquida: solo se permiten los modos de descompresión 4, 5 y 0 "
                       "(descomprimir rápido con líquido caliente produce ebullición violenta)")
CODIGO_MODO_SOLIDO = "MODO_NO_PERMITIDO_SOLIDO"
MOTIVO_MODO_SOLIDO = ("Carga sólida: solo se permiten los modos de descompresión 0 a 3 "
                      "(los modos 4 y 5 son de enfriamiento de líquidos)")


class ErrorCoherencia(ValueError):
    """Reglas entre parámetros incumplidas. `codigo`: MODO_NO_PERMITIDO_LIQUIDO
    si el problema es el modo de descompresión con carga líquida;
    COHERENCIA_LIQUIDO para el resto de las reglas de carga líquida;
    LIMITE_PRESION_CAMARA (C-04.3), LIMITE_CONSIGNA_CHAQUETA (C-05.5) y
    LIMITE_PRESION_CHAQUETA (C-05.9) para los límites físicos de la tanda 12;
    COHERENCIA_RECUPERACION para P1 (tanda 16, D-14.1). `valor`: el máximo
    admisible (o la consigna calculada) del primer límite físico incumplido
    o, en P1, el presion_add_esterilizacion mínimo; None si no hay."""

    def __init__(self, errores: list[str], valor=None):
        super().__init__("; ".join(errores))
        self.errores = list(errores)
        self.codigo = codigo_coherencia(errores)
        self.valor = valor


# Prefijos de los mensajes de límites físicos (identifican su código)
_PREFIJO_CAMARA = "Límite de presión de cámara: "
_PREFIJO_CHAQUETA = "Límite de presión de chaqueta: "
_PREFIJO_CONSIGNA = "Límite de consigna de chaqueta: "
_PREFIJO_RECUPERACION = "Coherencia de recuperación: "


def codigo_coherencia(errores: list[str]) -> str:
    if MOTIVO_MODO_LIQUIDO in errores:
        return "MODO_NO_PERMITIDO_LIQUIDO"
    if MOTIVO_MODO_SOLIDO in errores:
        return CODIGO_MODO_SOLIDO
    if any(e.startswith("Carga líquida") for e in errores):
        return "COHERENCIA_LIQUIDO"
    if any(e.startswith(_PREFIJO_CAMARA) for e in errores):
        return CODIGO_LIMITE_CAMARA
    if any(e.startswith(_PREFIJO_CONSIGNA) for e in errores):
        return CODIGO_LIMITE_CONSIGNA
    if any(e.startswith(_PREFIJO_CHAQUETA) for e in errores):
        return CODIGO_LIMITE_CHAQUETA
    if any(e.startswith(_PREFIJO_RECUPERACION) for e in errores):
        return CODIGO_COHERENCIA_RECUPERACION
    return "COHERENCIA_LIQUIDO"


def modos_validos(parameters: dict, fase: str, path) -> list[int]:
    """Valores válidos de un parámetro "modo" (D8-5.8), ya filtrados por el
    tipo de carga del programa (D8-5.7); [] si no es un parámetro de modo."""
    ruta = ".".join(path) if not isinstance(path, str) else path
    modos = MODOS_PARAMETRO.get((fase, ruta))
    if modos is None:
        return []
    if fase == "descompresion":
        tipo = _valor(parameters, "globals", "tipo_carga", defecto="solido")
        if tipo == "liquido":
            return list(MODOS_LIQUIDO)
        if tipo == "solido":
            return list(MODOS_SOLIDO)        # T29-05
    return list(modos)
# Contrapresión mínima sobre P_sat(temperatura de esterilización) para carga
# líquida (SAF-05 de T11): bajo ella la carga hierve al empezar a enfriar
MARGEN_CONTRAPRESION_LIQUIDO = 30.0   # kPa


def limites(fase: str, path) -> tuple:
    """(mínimo, máximo) del catálogo para el parámetro; (None, None) si no
    tiene límite propio."""
    ruta = ".".join(path) if not isinstance(path, str) else path
    entrada = CATALOGO.get((fase, ruta))
    if not entrada:
        return (None, None)
    if entrada[2] == _MOTIVO_PRESION_ABSOLUTA:
        # DEU-01 (tanda 16): una presión absoluta no supera el fondo de escala
        # del transductor del equipo; nunca más que el límite del modelo
        # (DECISIÓN SIN CONFIRMAR: subir el fondo de escala no amplía el rango)
        return (entrada[0], min(entrada[1], _limites().fondo_escala))
    return (entrada[0], entrada[1])


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


def consigna_chaqueta(t_est, presion_add_est, delta=None, margen=None) -> float | None:
    """C-05.1/2 (tanda 12): consigna de presión de chaqueta en CICLO, kPa abs.
    consigna = max(Psat(T_est + delta), Psat(T_est) + presion_add_est + margen).
    None si T_est o presion_add_est no son numéricos o si T_est queda fuera
    del rango de la tabla de vapor (tanda 13); delta/margen ausentes o no
    numéricos toman su valor por defecto (1.5 °C / 15 kPa)."""
    if not (_num(t_est) and _num(presion_add_est)):
        return None
    delta = delta if _num(delta) else DELTA_TEMP_CHAQUETA_DEFECTO
    margen = margen if _num(margen) else MARGEN_FLUJO_CHAQUETA_DEFECTO
    psat_est, psat_delta = _psat(t_est), _psat(t_est + delta)
    if psat_est is None or psat_delta is None:
        return None
    return max(psat_delta, psat_est + presion_add_est + margen)


def consigna_chaqueta_programa(parameters: dict) -> float | None:
    """consigna_chaqueta con los valores del programa (None si faltan)."""
    return consigna_chaqueta(
        _valor(parameters, "esterilizacion", "temperatura_esterilizacion"),
        _valor(parameters, "esterilizacion", "presion_add_esterilizacion"),
        _valor(parameters, "globals", "delta_temp_chaqueta"),
        _valor(parameters, "globals", "margen_flujo_chaqueta"))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _psat(t):
    """Psat(t) en kPa, o None si t queda fuera del rango de IAPWS-IF97
    (tanda 13: p_saturacion_kpa lanza ValueError). Un programa con esa
    temperatura ya lo rechaza el catálogo; aquí no se evalúa la regla."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    try:
        return p_saturacion_kpa(t)
    except ValueError:
        return None


_RUTAS_CONSIGNA = (("esterilizacion", "temperatura_esterilizacion"),
                   ("esterilizacion", "presion_add_esterilizacion"),
                   ("globals", "delta_temp_chaqueta"), ("globals", "margen_flujo_chaqueta"))
_TECHOS_CAMARA = (("calentamiento", "temperatura_calentamiento", "presion_add_calentamiento"),
                  ("esterilizacion", "temperatura_esterilizacion", "presion_add_esterilizacion"))


def _evaluar_limites(parameters: dict) -> tuple[list, list]:
    """Límites físicos de la tanda 12, para todo tipo de carga:
    ([(mensaje de rechazo, valor)], [(clave de advertencia, mensaje, {(fase, parámetro)})]).
    - C-04.3: techo de cámara Psat(T) + presion_add_* >= alivio de cámara →
      rechazo (da el máximo admisible de presion_add_*); > suministro → advertencia.
    - C-05.5: consigna de chaqueta + 10 >= alivio de chaqueta → rechazo (da la
      consigna); > suministro → advertencia (vapor_chaqueta abierta en el ciclo).
    - C-05.9: presion_chaqueta + rango_presion_chaqueta: misma regla.
    - P1 (tanda 16, D-14.1): salida de RECUPERACION alcanzable bajo el techo
      (ver _evaluar_recuperacion); va al final (su código es el último).
    DEU-01 (tanda 16): alivios y suministro son los del equipo (_limites()).
    Valores ausentes o no numéricos no se evalúan (los marca el catálogo)."""
    lim = _limites()
    alivio_cam, alivio_chq, suministro = lim.alivio_camara, lim.alivio_chaqueta, lim.suministro
    rechazos, advertencias = [], []
    for fase, clave_t, clave_add in _TECHOS_CAMARA:
        t = _valor(parameters, fase, clave_t)
        add = _valor(parameters, fase, clave_add)
        if not (_num(t) and _num(add)):
            continue
        psat = _psat(t)
        if psat is None:
            continue
        techo = psat + add
        if techo >= alivio_cam:
            maximo = alivio_cam - psat
            rechazos.append((
                f"{_PREFIJO_CAMARA}Psat({t:g} °C) + {clave_add} = {techo:.1f} kPa alcanza el "
                f"alivio de cámara ({alivio_cam:.0f} kPa); {clave_add} debe ser "
                f"menor que {maximo:.1f} kPa", round(maximo, 1)))
        elif techo > suministro:
            advertencias.append((ADVERTENCIA_TECHO_CAMARA,
                f"{fase}: techo de cámara {techo:.1f} kPa sobre el suministro "
                f"({suministro:.0f} kPa): la cámara no alcanzará el techo de presión; "
                f"la válvula de vapor de cámara quedará abierta en ese tramo",
                {(fase, clave_t), (fase, clave_add)}))
    consigna = consigna_chaqueta_programa(parameters)
    if consigna is not None:
        alto = consigna + BANDA_CHAQUETA_KPA
        if alto >= alivio_chq:
            rechazos.append((
                f"{_PREFIJO_CONSIGNA}la consigna calculada de chaqueta es {consigna:.1f} kPa; "
                f"con la banda de ±{BANDA_CHAQUETA_KPA:.0f} kPa llega a {alto:.1f} kPa, sobre "
                f"el alivio de chaqueta ({alivio_chq:.0f} kPa)", round(consigna, 1)))
        elif alto > suministro:
            advertencias.append((ADVERTENCIA_CHAQUETA_ABIERTA,
                f"consigna de chaqueta {consigna:.1f} kPa (+{BANDA_CHAQUETA_KPA:.0f}) sobre el "
                f"suministro ({suministro:.0f} kPa): la válvula de vapor de chaqueta "
                f"quedará abierta durante el ciclo", set(_RUTAS_CONSIGNA)))
    pch = _valor(parameters, "globals", "presion_chaqueta")
    rango = _valor(parameters, "globals", "rango_presion_chaqueta")
    if _num(pch) and _num(rango):
        alto = pch + rango
        if alto >= alivio_chq:
            rechazos.append((
                f"{_PREFIJO_CHAQUETA}presion_chaqueta + rango_presion_chaqueta = {alto:g} kPa "
                f"alcanza el alivio de chaqueta ({alivio_chq:.0f} kPa); debe ser "
                f"menor que {alivio_chq:.0f} kPa", alivio_chq - rango))
        elif alto > suministro:
            advertencias.append((ADVERTENCIA_CHAQUETA_ABIERTA,
                f"presion_chaqueta + rango_presion_chaqueta = {alto:g} kPa sobre el suministro "
                f"({suministro:.0f} kPa): en preparación la válvula de vapor de "
                f"chaqueta quedará abierta",
                {("globals", "presion_chaqueta"), ("globals", "rango_presion_chaqueta")}))
    advertencias.extend(_evaluar_banda_pwm(parameters))
    rechazos.extend(_evaluar_recuperacion(parameters))
    return rechazos, advertencias


def consigna_pwm_esterilizacion(t_est, brecha) -> float | None:
    """A14-M1 (tanda 28): P_sp = Psat(T_est + brecha_segura_temperatura +
    histéresis de salida de RECUPERACION), kPa abs; la misma consigna que
    calcula EsterilizacionFase al entrar. None si faltan valores o fuera de
    IAPWS-IF97."""
    if not (_num(t_est) and _num(brecha)):
        return None
    return _psat(t_est + brecha + HIST_SALIDA_RECUPERACION_K)


_RUTAS_BANDA_PWM = {("esterilizacion", "temperatura_esterilizacion"),
                    ("esterilizacion", "brecha_segura_temperatura"),
                    ("esterilizacion", "presion_add_esterilizacion")}


def _evaluar_banda_pwm(parameters: dict) -> list:
    """A14-M1: advertencia no bloqueante si el borde alto de la banda PWM
    (P_sp + 1) queda a menos de 5 kPa del techo P_control_max = Psat(T_est) +
    presion_add_esterilizacion. Valores ausentes o no numéricos no se evalúan."""
    t = _valor(parameters, "esterilizacion", "temperatura_esterilizacion")
    brecha = _valor(parameters, "esterilizacion", "brecha_segura_temperatura")
    add = _valor(parameters, "esterilizacion", "presion_add_esterilizacion")
    p_sp = consigna_pwm_esterilizacion(t, brecha)
    psat = _psat(t) if _num(t) else None
    if p_sp is None or psat is None or not _num(add):
        return []
    alto, techo = p_sp + BANDA_PWM_ALTA_KPA, psat + add
    if alto <= techo - MARGEN_BANDA_TECHO_KPA:
        return []
    return [(ADVERTENCIA_BANDA_PWM_TECHO,
             f"esterilizacion: la banda de control llega a {alto:.1f} kPa (consigna "
             f"{p_sp:.1f} + {BANDA_PWM_ALTA_KPA:.0f}), a menos de {MARGEN_BANDA_TECHO_KPA:.0f} kPa "
             f"del techo de control ({techo:.1f} kPa): riesgo de sobreimpulso y de aislamientos "
             f"repetidos", set(_RUTAS_BANDA_PWM))]


def presion_add_minima_recuperacion(t_est, brecha) -> float | None:
    """P1 (tanda 16, D-14.1): presion_add_esterilizacion mínimo (kPa) para que
    Tsat(Psat(T_est) + presion_add) >= T_est + brecha + histéresis + margen, es
    decir Psat(T_est + brecha + 0,6) - Psat(T_est). None si T_est o la brecha
    no son numéricos o la temperatura queda fuera de IAPWS-IF97."""
    if not (_num(t_est) and _num(brecha)):
        return None
    psat_est = _psat(t_est)
    psat_salida = _psat(t_est + brecha + HIST_SALIDA_RECUPERACION_K
                        + MARGEN_COHERENCIA_RECUPERACION_K)
    if psat_est is None or psat_salida is None:
        return None
    return psat_salida - psat_est


# tolerancia numérica de la comparación de P1 (kPa)
_TOL_RECUPERACION_KPA = 1e-9


def _evaluar_recuperacion(parameters: dict) -> list:
    """P1 (tanda 16, D-14.1): [(mensaje, mínimo)] si
    Tsat(Psat(T_est) + presion_add_esterilizacion) < T_est +
    brecha_segura_temperatura + 0,3 (histéresis) + 0,3 (margen); se evalúa en
    la forma equivalente presion_add < presion_add_minima_recuperacion. El
    mínimo se da redondeado hacia arriba a 0,1 kPa, para que el valor que se
    lee en pantalla sí se acepte (DECISIÓN SIN CONFIRMAR). Valores ausentes o
    no numéricos no se evalúan (los marca el catálogo)."""
    t = _valor(parameters, "esterilizacion", "temperatura_esterilizacion")
    brecha = _valor(parameters, "esterilizacion", "brecha_segura_temperatura")
    add = _valor(parameters, "esterilizacion", "presion_add_esterilizacion")
    if not _num(add):
        return []
    minimo = presion_add_minima_recuperacion(t, brecha)
    if minimo is None or add >= minimo - _TOL_RECUPERACION_KPA:
        return []
    mostrado = math.ceil(round(minimo * 10, 6)) / 10
    umbral = t + brecha + HIST_SALIDA_RECUPERACION_K + MARGEN_COHERENCIA_RECUPERACION_K
    from autoclave.core.runtime.steam import t_saturacion_c
    try:
        tsat_techo = f"{t_saturacion_c(_psat(t) + add):.2f} °C"
    except ValueError:
        tsat_techo = "fuera de rango"
    return [(
        f"{_PREFIJO_RECUPERACION}con temperatura_esterilizacion {t:g} °C y "
        f"brecha_segura_temperatura {brecha:g} °C, el techo de control Psat(T) + "
        f"presion_add_esterilizacion ({add:g} kPa) da Tsat {tsat_techo}, bajo la salida "
        f"de RECUPERACION más el margen ({umbral:.2f} °C); presion_add_esterilizacion "
        f"debe ser al menos {mostrado:.1f} kPa", mostrado)]


def errores_recuperacion(parameters: dict) -> list[str]:
    """Rechazos de P1 (tanda 16, D-14.1)."""
    return [m for m, _ in _evaluar_recuperacion(parameters)]


def errores_limites_fisicos(parameters: dict) -> list[str]:
    """Rechazos de los límites físicos (C-04.3, C-05.5, C-05.9) y de P1
    (tanda 16), para todo tipo de carga."""
    return [m for m, _ in _evaluar_limites(parameters)[0]]


def valor_limite(parameters: dict):
    """Máximo admisible (o consigna) del primer límite físico incumplido o,
    si solo falla P1, el presion_add_esterilizacion mínimo."""
    rechazos = _evaluar_limites(parameters)[0]
    return rechazos[0][1] if rechazos else None


def advertencias_programa(parameters: dict, fase: str | None = None,
                          path=None) -> list[tuple[str, str]]:
    """Advertencias no bloqueantes (clave, mensaje): se guardan igual; se
    devuelven al guardar y se registran en el log al iniciar el ciclo. Con
    `fase`/`path`, solo las que dependen de ese parámetro (o de su vinculado
    temperatura_calentamiento ↔ temperatura_esterilizacion)."""
    advertencias = _evaluar_limites(parameters)[1]
    if fase is None:
        return [(c, m) for c, m, _ in advertencias]
    ruta = ".".join(path) if not isinstance(path, str) else path
    editados = {(fase, ruta)}
    if ruta in ("temperatura_calentamiento", "temperatura_esterilizacion"):
        editados |= {("calentamiento", "temperatura_calentamiento"),
                     ("esterilizacion", "temperatura_esterilizacion")}
    return [(c, m) for c, m, rutas in advertencias if rutas & editados]


def errores_coherencia(parameters: dict) -> list[str]:
    """Reglas entre parámetros: límites físicos de presión (tanda 12; con los
    del equipo desde la tanda 16, DEU-01) y coherencia de RECUPERACION (P1,
    tanda 16) para todo tipo de carga y, para carga líquida (decisión 1.2; SAF-05 y
    SAF-06 de T11; D8-5.7): descompresión modo 4, 5 o 0; sin prevacío ni secado (vacío
    sobre líquido caliente); sin apertura automática; contrapresión de
    enfriamiento de al menos P_sat(temperatura de esterilización) + 30 kPa."""
    limites_fisicos = errores_limites_fisicos(parameters)
    tipo_carga = _valor(parameters, "globals", "tipo_carga", defecto="solido")
    if tipo_carga != "liquido":
        # T29-05 (tanda 29): carga sólida solo con los modos 0 a 3
        if (tipo_carga == "solido"
                and _valor(parameters, "descompresion", "modo") in MODOS_CONTRAPRESION):
            return [MOTIVO_MODO_SOLIDO] + limites_fisicos
        return limites_fisicos
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
        t_est = _valor(parameters, "esterilizacion", "temperatura_esterilizacion")
        p_enfr = _valor(parameters, "descompresion", f"modo_{modo}", "presion_camara_enfriamiento")
        psat = _psat(t_est) if _num(t_est) else None
        if psat is not None and isinstance(p_enfr, (int, float)):
            minimo = psat + MARGEN_CONTRAPRESION_LIQUIDO
            if p_enfr < minimo:
                errores.append(f"Carga líquida: la contrapresión de enfriamiento debe ser al "
                               f"menos {minimo:.0f} kPa (P_sat + {MARGEN_CONTRAPRESION_LIQUIDO:.0f})")
    return errores + limites_fisicos


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
#                     operativos. Las calibraciones de campo anteriores a la tanda 20
#                     (hasta 75 kPa, 6 °C) cabían.
# Valores conservadores, DECISIÓN SIN CONFIRMAR de la tanda 2 (informe S3).
# Las recalibraciones reales anteriores a la tanda 20 (hasta 49 kPa y
# 1,2 °C en los puntos) cabían en aviso o en normal.
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
