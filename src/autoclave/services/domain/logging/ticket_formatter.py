# services/domain/logging/ticket_formatter.py
from datetime import datetime

_FASE = {
    "PH": "Pre-calent.",
    "PG": "Purga",
    "PV": "Pre-vacío",
    "H":  "Calentam.",
    "E":  "Estabiliz.",
    "S":  "Esteriliz.",
    "F":  "Fallo",
}

_W   = 48
_SEP = "=" * _W
_DIV = "-" * _W


def _hdr(lbl, val, lbl2, val2):
    return f"{lbl:<13}{val:<15}{lbl2:<10}{val2}"


def format_header(meta: dict) -> str:
    """Encabezado del ticket (todo lo previo a las filas de lecturas)."""
    numero   = meta["numero_ciclo"]
    serie    = meta.get("serie") or "--"
    nombre   = meta.get("nombre_ciclo") or meta.get("tipo_ciclo") or "--"
    operador = meta.get("operador") or "--"
    temp     = meta.get("temp_esterilizacion")
    tiempo   = meta.get("tiempo_esterilizacion")
    fi       = meta.get("fecha_inicio") or ""

    try:
        dt      = datetime.fromisoformat(fi)
        fecha_s = dt.strftime("%Y-%m-%d")
        hora_s  = dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        fecha_s = fi[:10]
        hora_s  = fi[11:19]

    temp_s   = f"{temp:.1f} C" if temp is not None else "--"
    tiempo_s = f"{int(tiempo)} min" if tiempo is not None else "--"

    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE MX-500".center(_W),
        _SEP,
        _hdr("Serie:",       serie,    "Ciclo N°:", f"{numero:05d}"),
        _hdr("Fecha:",       fecha_s,  "Hora:",     hora_s),
        _hdr("Tipo:",        nombre,   "Operador:", operador),
        _hdr("Temp. ester:", temp_s,   "Tiempo:",   tiempo_s),
        _DIV,
        f"  {'HORA':<10}{'FASE':<12}{'TEMP(C)':>8}  {'PRES(kPa)':>9}",
        _DIV,
    ]
    return "\n".join(lines)


def format_row(lectura: dict) -> str:
    """Una fila HORA/FASE/TEMP/PRES."""
    label = _FASE.get(lectura["fase_codigo"], lectura["fase_codigo"])
    tv    = lectura["temp_camara"]
    pv    = lectura["pres_camara"]
    t_s   = f"{tv:.1f}" if tv is not None else "--"
    p_s   = f"{pv:.1f}" if pv is not None else "--"
    return f"  {lectura['timestamp_rel']:<10}{label:<12}{t_s:>8}  {p_s:>9}"


def format_footer(resultado: str, fecha_fin: str) -> str:
    """Pie del ticket (todo lo posterior a las filas de lecturas)."""
    try:
        fin_s = datetime.fromisoformat(fecha_fin).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        fin_s = fecha_fin or "--"

    lines = [
        _DIV,
        f"Resultado:   {resultado or '--'}",
        f"Fin:         {fin_s}",
        _SEP,
        "",
    ]
    return "\n".join(lines)


def format_ticket(ciclo, lecturas) -> str:
    """Format cycle data as plain-text print ticket."""
    meta = {
        "numero_ciclo":          ciclo["numero_ciclo"],
        "serie":                 ciclo["serie"],
        "nombre_ciclo":          ciclo["nombre_ciclo"],
        "tipo_ciclo":            ciclo["tipo_ciclo"],
        "operador":              ciclo["operador"],
        "temp_esterilizacion":   ciclo["temp_esterilizacion"],
        "tiempo_esterilizacion": ciclo["tiempo_esterilizacion"],
        "fecha_inicio":          ciclo["fecha_inicio"],
    }
    parts = [format_header(meta)]
    parts += [format_row(r) for r in lecturas]
    parts.append(format_footer(ciclo["resultado"], ciclo["fecha_fin"]))
    return "\n".join(parts)
