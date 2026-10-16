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
MODOS_LIQUIDO = (4, 5)


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


def errores_coherencia(parameters: dict) -> list[str]:
    """Reglas entre parámetros. Carga líquida (decisión 1.2): la descompresión
    debe ser modo 4 o 5."""
    errores = []
    try:
        tipo_carga = parameters["globals"]["tipo_carga"]["value"]
    except (KeyError, TypeError):
        tipo_carga = "solido"
    if tipo_carga == "liquido":
        try:
            modo = parameters["descompresion"]["modo"]["value"]
        except (KeyError, TypeError):
            modo = None
        if modo not in MODOS_LIQUIDO:
            errores.append("Carga líquida: la descompresión debe ser modo 4 o 5")
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
