# utils/periodos.py
#
# Periodos de calendario del Historial del Menú Principal: el día, la semana de
# lunes a domingo o el mes del 1 al último día que contienen una fecha. Lo usan
# el backend (/cycle/list) y la UI QML (rótulo y flechas del periodo), para que
# ambos lados calculen el mismo rango. Solo fechas: el reloj de pared lo pone
# quien llama (`hoy`), nunca temporiza nada del proceso.

from datetime import date, timedelta

PERIODOS = ("dia", "semana", "mes")           # Historial y pantalla Reportes actual
PERIODOS_REPORTES = PERIODOS + ("anio",)      # /report/*: suma el año calendario (DR-H04)
# Cota del parámetro `fecha` de las rutas (ajuste revisión H, 2026-11-02): fuera de
# este intervalo el backend responde 422 en vez de desbordar al calcular el periodo.
FECHA_MINIMA = date(2000, 1, 1)
FECHA_MAXIMA = date(2100, 12, 31)


def rango(periodo: str, fecha: date) -> tuple[date, date]:
    """(primer día, primer día del periodo siguiente) del periodo que contiene `fecha`."""
    if periodo == "dia":
        return fecha, fecha + timedelta(days=1)
    if periodo == "semana":
        inicio = fecha - timedelta(days=fecha.weekday())
        return inicio, inicio + timedelta(days=7)
    if periodo == "mes":
        inicio = fecha.replace(day=1)
        return inicio, (inicio + timedelta(days=32)).replace(day=1)
    if periodo == "anio":
        return date(fecha.year, 1, 1), date(fecha.year + 1, 1, 1)
    raise ValueError(f"Periodo desconocido: {periodo!r}")


def es_actual(periodo: str, fecha: date, hoy: date) -> bool:
    """El periodo de `fecha` es el que contiene `hoy`."""
    return rango(periodo, fecha)[0] == rango(periodo, hoy)[0]


def desplazar(periodo: str, fecha: date, pasos: int, hoy: date) -> date:
    """Una fecha del periodo `pasos` periodos antes (negativo) o después del de
    `fecha`: su primer día, o `hoy` si llegaría al periodo actual o más allá."""
    inicio = rango(periodo, fecha)[0]
    if periodo == "dia":
        destino = inicio + timedelta(days=pasos)
    elif periodo == "semana":
        destino = inicio + timedelta(weeks=pasos)
    elif periodo == "anio":
        destino = date(inicio.year + pasos, 1, 1)
    else:
        meses = inicio.year * 12 + inicio.month - 1 + pasos
        destino = date(meses // 12, meses % 12 + 1, 1)
    return hoy if destino >= rango(periodo, hoy)[0] else destino
