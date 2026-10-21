# services/domain/reportes/resumen_periodo.py
#
# Resumen de ciclos de un periodo para la pantalla Reportes del Menú Principal:
# totales por resultado, desglose por programa y causas de fallo, a partir del
# conteo agrupado de DbManager.get_conteo_resultados. Los resultados se agrupan
# con la misma regla que el resto del sistema (progreso_ciclo.resultado):
# COMPLETADO, CANCELADO, fallo (cualquier otro cierre) y sin cierre (NULL o una
# fase en curso: un ciclo corriendo o un proceso interrumpido).
# También arma su ticket para la impresora térmica (24 columnas, como el del ciclo).

from datetime import date, datetime

from autoclave.core.runtime import progreso_ciclo

_ANCHO = 24
_LINEA = "-" * _ANCHO
_GRUPO = {"exitoso": "completados", "cancelado": "cancelados", "fallo": "fallos"}


def _conteo_vacio() -> dict:
    return {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0, "sin_cierre": 0}


def resumir(filas, numeros: dict) -> dict:
    """filas: {tipo_ciclo, nombre_ciclo, resultado, cantidad}; numeros: número de
    programa por tipo_ciclo (los programas actuales; None si ya no existe)."""
    totales = _conteo_vacio()
    programas: dict[str, dict] = {}
    causas: dict[str, int] = {}
    for f in filas:
        cantidad = int(f["cantidad"] or 0)
        tipo = f["tipo_ciclo"] or ""
        grupo = _GRUPO.get(progreso_ciclo.resultado(f["resultado"]), "sin_cierre")
        p = programas.setdefault(tipo, {
            "programa_id": tipo, "programa_nombre": f["nombre_ciclo"] or tipo,
            "programa_numero": numeros.get(tipo), **_conteo_vacio()})
        for conteo in (totales, p):
            conteo["total"] += cantidad
            conteo[grupo] += cantidad
        if grupo == "fallos":
            causas[f["resultado"]] = causas.get(f["resultado"], 0) + cantidad
    return {
        "totales": totales,
        "por_programa": sorted(programas.values(), key=lambda p: (-p["total"], p["programa_nombre"])),
        "causas_fallo": [{"causa": c, "cantidad": n}
                         for c, n in sorted(causas.items(), key=lambda c: (-c[1], c[0]))],
    }


def _fecha(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "---"


def _porcentaje(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


def _cortar(texto: str) -> str:
    return texto[:_ANCHO]


# I4 (tanda 6): rótulos por idioma (cp437: sin tildes en inglés)
_TXT = {
    "es": {"titulo": "RESUMEN DE CICLOS", "desde": "Desde", "hasta": "Hasta",
           "serie": "Num serie", "modelo": "Modelo", "impreso": "Impreso", "hora": "Hora",
           "completados": "Completados", "fallos": "Fallo", "cancelados": "Cancelados",
           "sin_cierre": "Sin cierre", "sin_ciclos": "Sin ciclos en el periodo",
           "por_programa": "POR PROGRAMA", "compl": "Compl.", "cancel": "Cancel.",
           "causas": "CAUSAS DE FALLO"},
    "en": {"titulo": "CYCLE SUMMARY", "desde": "From", "hasta": "To",
           "serie": "Serial No", "modelo": "Model", "impreso": "Printed", "hora": "Time",
           "completados": "Completed", "fallos": "Failed", "cancelados": "Cancelled",
           "sin_cierre": "Not closed", "sin_ciclos": "No cycles in the period",
           "por_programa": "BY PROGRAM", "compl": "Compl.", "cancel": "Cancel.",
           "causas": "FAILURE CAUSES"},
}


def _idioma(idioma: str | None) -> str:
    if idioma in _TXT:
        return idioma
    try:
        from autoclave.services.domain.logging.ticket_formatter import presentacion_actual
        return presentacion_actual().idioma
    except Exception:
        return "es"


def format_ticket_resumen(resumen: dict, desde: str, hasta: str, serie: str, modelo: str,
                          ahora: datetime | None = None, idioma: str | None = None) -> str:
    """Ticket del resumen; desde/hasta: primer y último día (ISO) del periodo."""
    ahora = ahora or datetime.now()   # sello de impresión (registro), no temporiza nada
    tx = _TXT[_idioma(idioma)]
    t = resumen["totales"]
    lineas = [
        " ", _LINEA, tx["titulo"],
        f"{tx['desde']}: {_fecha(desde)}", f"{tx['hasta']}: {_fecha(hasta)}",
        _cortar(f"{tx['serie']}: {serie}"), _cortar(f"{tx['modelo']}: {modelo}"),
        f"{tx['impreso']}: {ahora.strftime('%d/%m/%Y')}",
        f"{tx['hora']}:  {ahora.strftime('%H:%M:%S')}", _LINEA,
        f"Total: {t['total']}",
    ]
    for clave in ("completados", "fallos", "cancelados", "sin_cierre"):
        lineas.append(_cortar(f"{tx[clave]}: {t[clave]} ({_porcentaje(t[clave], t['total'])})"))
    if not t["total"]:
        lineas += [_LINEA, tx["sin_ciclos"]]
    if resumen["por_programa"]:
        lineas += [_LINEA, tx["por_programa"]]
        for p in resumen["por_programa"]:
            numero = f"{p['programa_numero']:02d} " if p["programa_numero"] else ""
            lineas += [
                _cortar(numero + p["programa_nombre"]),
                f"  Total: {p['total']}  {tx['compl']}: {p['completados']}"[:_ANCHO],
                f"  {tx['fallos']}: {p['fallos']}  {tx['cancel']}: {p['cancelados']}"[:_ANCHO],
                _cortar(f"  {tx['sin_cierre']}: {p['sin_cierre']}"),
            ]
    if resumen["causas_fallo"]:
        lineas += [_LINEA, tx["causas"]]
        for c in resumen["causas_fallo"]:
            cantidad = f": {c['cantidad']}"
            lineas.append(c["causa"][:_ANCHO - len(cantidad)] + cantidad)
    lineas += [_LINEA] + [""] * 5   # avance de papel para cortar sin abrir la tapa
    return "\n".join(lineas)
