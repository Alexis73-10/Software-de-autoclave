# services/domain/reportes/dashboard.py
#
# Funciones puras del dashboard de Reportes (REP-03/05/07/10/11, DR-H02/H03):
# estado de un día del calendario de ejecución, indicadores, duración media,
# serie por intervalos, periodo anterior y agrupaciones de alarmas y operadores.
# Sin base de datos ni UI: reciben filas (dict o sqlite3.Row) ya leídas. Las
# fechas de los ciclos son de reloj de pared (ISO local sin zona); aquí solo se
# comparan, nunca temporizan nada.

from datetime import date, datetime, timedelta

from autoclave.core.runtime import progreso_ciclo
from autoclave.services.domain.logging.ticket_formatter import ciclo_no_conforme
from autoclave.state_machine.alarms.catalogo import Nivel, codigo_visible

PERIODOS = ("dia", "semana", "mes", "anio")

# Estados del día en el calendario de ejecución (REP-07)
FUTURO = "futuro"
EN_CURSO = "en_curso"
SIN_OPERACION = "sin_operacion"
EXITO = "exito"
EXITO_FALLO_PREVIO = "exito_fallo_previo"
SIN_EXITO = "sin_exito"
FALTO = "falto"
NO_EJECUTADO = "no_ejecutado"

SIN_OPERADOR = "Sin operador"
MAX_OPERADORES = 5
DURACION_MAX_S = 24 * 3600


def _campo(fila, clave, defecto=None):
    try:
        valor = fila[clave]
    except (KeyError, IndexError, TypeError):
        return defecto
    return defecto if valor is None else valor


def _fecha_hora(iso) -> datetime | None:
    try:
        return datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- indicadores

def _grupo(fila) -> str:
    g = progreso_ciclo.resultado(_campo(fila, "resultado"))
    return {"exitoso": "completados", "cancelado": "cancelados", "fallo": "fallos"}.get(g, "sin_cierre")


def indicadores(filas) -> dict:
    """Totales por resultado (misma agrupación que resumen_periodo.resumir) y
    % de éxito entero (COMPLETADOS sobre el total; 0 sin ciclos)."""
    c = {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0, "sin_cierre": 0}
    for f in filas:
        c["total"] += 1
        c[_grupo(f)] += 1
    c["exito_pct"] = round(100 * c["completados"] / c["total"]) if c["total"] else 0
    return c


def duracion_media(filas) -> tuple[float | None, int]:
    """(segundos medios | None, excluidas). Solo ciclos COMPLETADOS con
    0 < duración <= 24 h (DR-H03); `excluidas` cuenta los COMPLETADOS que no
    cumplen (hora cambiada, fin ausente o ilegible). Los demás no cuentan."""
    duraciones, excluidas = [], 0
    for f in filas:
        if progreso_ciclo.resultado(_campo(f, "resultado")) != "exitoso":
            continue
        ini, fin = _fecha_hora(_campo(f, "fecha_inicio")), _fecha_hora(_campo(f, "fecha_fin"))
        if ini is None or fin is None:
            excluidas += 1
            continue
        seg = (fin - ini).total_seconds()
        if 0 < seg <= DURACION_MAX_S:
            duraciones.append(seg)
        else:
            excluidas += 1
    return (sum(duraciones) / len(duraciones) if duraciones else None), excluidas


# ---------------------------------------------------------------------- serie

def serie(filas, periodo: str, desde: date, hasta: date) -> list[dict]:
    """Puntos {etiqueta, inicio, total, completados, fallos} de [desde, hasta):
    dia → 24 horas del día `desde`; semana y mes → un punto por día; anio → por
    mes. `inicio` es ISO del comienzo del intervalo; `etiqueta` es la hora
    «HH», el día «YYYY-MM-DD» o el mes «YYYY-MM»."""
    if periodo not in PERIODOS:
        raise ValueError(f"Periodo desconocido: {periodo!r}")
    if periodo == "dia":
        base = datetime(desde.year, desde.month, desde.day)
        claves = [base + timedelta(hours=h) for h in range(24)]

        def clave_de(d):
            return d.replace(minute=0, second=0, microsecond=0)

        def etiqueta(k):
            return f"{k.hour:02d}"
    elif periodo == "anio":
        claves, d = [], date(desde.year, desde.month, 1)
        while d < hasta:
            claves.append(datetime(d.year, d.month, 1))
            d = (d + timedelta(days=32)).replace(day=1)

        def clave_de(d):
            return datetime(d.year, d.month, 1)

        def etiqueta(k):
            return f"{k.year:04d}-{k.month:02d}"
    else:
        claves = [datetime(desde.year, desde.month, desde.day) + timedelta(days=i)
                  for i in range((hasta - desde).days)]

        def clave_de(d):
            return datetime(d.year, d.month, d.day)

        def etiqueta(k):
            return k.strftime("%Y-%m-%d")
    puntos = {k: {"etiqueta": etiqueta(k), "inicio": k.isoformat(),
                  "total": 0, "completados": 0, "fallos": 0} for k in claves}
    for f in filas:
        ini = _fecha_hora(_campo(f, "fecha_inicio"))
        if ini is None:
            continue
        p = puntos.get(clave_de(ini))
        if p is None:
            continue
        p["total"] += 1
        g = _grupo(f)
        if g in ("completados", "fallos"):
            p[g] += 1
    return list(puntos.values())


# ------------------------------------------------------------ periodo anterior

def periodo_anterior(periodo: str, fecha: date) -> tuple[date, date]:
    """(primer día, primer día siguiente) del periodo de calendario inmediatamente
    anterior al que contiene `fecha` y del mismo tipo. Semana de lunes a domingo."""
    if periodo == "dia":
        return fecha - timedelta(days=1), fecha
    if periodo == "semana":
        inicio = fecha - timedelta(days=fecha.weekday())
        return inicio - timedelta(days=7), inicio
    if periodo == "mes":
        inicio = fecha.replace(day=1)
        return (inicio - timedelta(days=1)).replace(day=1), inicio
    if periodo == "anio":
        return date(fecha.year - 1, 1, 1), date(fecha.year, 1, 1)
    raise ValueError(f"Periodo desconocido: {periodo!r}")


# ------------------------------------------------------------------- calendario

def es_exito(intento) -> bool:
    """Éxito del calendario: COMPLETADO y no guardado como NO CONFORME (DR-D13)."""
    return (progreso_ciclo.resultado(_campo(intento, "resultado")) == "exitoso"
            and not ciclo_no_conforme(intento))


def estado_dia(intentos, n_dia: int, es_programa_1: bool, activo_id, hoy: date, dia: date) -> str:
    """Estado del día `dia` para un programa (REP-07), en el orden del plan.
    `intentos`: ciclos del programa con inicio ese día, ordenados por inicio
    (dicts con id, resultado, avisos_ticket); puede incluir el ciclo activo.
    `n_dia`: ciclos de cualquier programa iniciados ese día, sin el activo."""
    if dia > hoy:
        return FUTURO
    intentos = list(intentos or [])
    es_activo = [activo_id is not None and _campo(i, "id") == activo_id for i in intentos]
    if len(intentos) == 1 and es_activo[0]:
        return EN_CURSO
    reales = [i for i, a in zip(intentos, es_activo) if not a]
    if n_dia == 0 and not intentos:
        return SIN_OPERACION
    if reales:
        exitos = [k for k, i in enumerate(reales) if es_exito(i)]
        if not exitos:
            return SIN_EXITO
        ultimo = exitos[-1]
        # un no exitoso posterior a todos los éxitos no cambia el estado (DR-D12)
        previo = any(k not in exitos for k in range(ultimo))
        return EXITO_FALLO_PREVIO if previo else EXITO
    return FALTO if es_programa_1 else NO_EJECUTADO


def numero_programa_efectivo(ciclo, numeros: dict) -> int | None:
    """DR-H02: `numero_programa` del ciclo; si es NULL, el número actual de su
    `tipo_ciclo` en `numeros`; si tampoco existe, None."""
    n = _campo(ciclo, "numero_programa")
    if n is not None:
        return n
    return numeros.get(_campo(ciclo, "tipo_ciclo"))


# --------------------------------------------------------------------- listas

def _nivel(valor) -> Nivel | None:
    if isinstance(valor, Nivel):
        return valor
    try:
        return Nivel[str(valor)]
    except KeyError:
        return None


def agrupar_alarmas(filas) -> list[dict]:
    """[{codigo, codigo_visible, nivel, titulo, cantidad}] por código. Nivel: el
    más grave visto para ese código (nombre del catálogo; uno desconocido se
    conserva tal cual y va al final). Orden: nivel descendente, cantidad
    descendente y código."""
    grupos: dict[str, dict] = {}
    for f in filas:
        codigo = str(_campo(f, "codigo", ""))
        crudo = _campo(f, "nivel", "")
        n = _nivel(crudo)
        g = grupos.setdefault(codigo, {"codigo": codigo, "codigo_visible": codigo_visible(codigo),
                                       "nivel": str(crudo), "titulo": _campo(f, "titulo", ""),
                                       "cantidad": 0, "_n": None})
        g["cantidad"] += 1
        if n is not None and (g["_n"] is None or n.value > g["_n"].value):
            g["_n"] = n
            g["nivel"] = n.name
    salida = sorted(grupos.values(),
                    key=lambda g: (-(g["_n"].value if g["_n"] else 0), -g["cantidad"], g["codigo"]))
    for g in salida:
        del g["_n"]
    return salida


def agrupar_operadores(filas) -> dict:
    """{"operadores": [{operador, sin_operador, cantidad}] (máx. 5), "otros":
    None | {"operadores": n, "ciclos": m}}. Vacío = «Sin operador». Orden por
    cantidad descendente y nombre; el resto se resume en `otros`."""
    cuentas: dict[str, int] = {}
    for f in filas:
        nombre = str(_campo(f, "operador", "") or "").strip() or SIN_OPERADOR
        cuentas[nombre] = cuentas.get(nombre, 0) + 1
    orden = sorted(cuentas.items(), key=lambda c: (-c[1], c[0]))
    visibles, resto = orden[:MAX_OPERADORES], orden[MAX_OPERADORES:]
    return {
        "operadores": [{"operador": n, "sin_operador": n == SIN_OPERADOR, "cantidad": c}
                       for n, c in visibles],
        "otros": ({"operadores": len(resto), "ciclos": sum(c for _, c in resto)}
                  if resto else None),
    }
