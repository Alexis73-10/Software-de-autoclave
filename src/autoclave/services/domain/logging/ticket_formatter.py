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


def format_ticket(ciclo, lecturas) -> str:
    """Format cycle data as plain-text print ticket."""
    numero   = ciclo["numero_ciclo"]
    serie    = ciclo["serie"] or "--"
    nombre   = ciclo["nombre_ciclo"] or ciclo["tipo_ciclo"] or "--"
    operador = ciclo["operador"] or "--"
    resultado = ciclo["resultado"] or "--"
    temp     = ciclo["temp_esterilizacion"]
    tiempo   = ciclo["tiempo_esterilizacion"]

    fi = ciclo["fecha_inicio"] or ""
    ff = ciclo["fecha_fin"] or ""

    try:
        dt      = datetime.fromisoformat(fi)
        fecha_s = dt.strftime("%Y-%m-%d")
        hora_s  = dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        fecha_s = fi[:10]
        hora_s  = fi[11:19]

    try:
        fin_s = datetime.fromisoformat(ff).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        fin_s = ff or "--"

    temp_s   = f"{temp:.1f} C" if temp is not None else "--"
    tiempo_s = f"{int(tiempo)} min" if tiempo is not None else "--"

    def hdr(lbl, val, lbl2, val2):
        return f"{lbl:<13}{val:<15}{lbl2:<10}{val2}"

    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE MX-500".center(_W),
        _SEP,
        hdr("Serie:",        serie,    "Ciclo N°:", f"{numero:05d}"),
        hdr("Fecha:",        fecha_s,  "Hora:",     hora_s),
        hdr("Tipo:",         nombre,   "Operador:", operador),
        hdr("Temp. ester:",  temp_s,   "Tiempo:",   tiempo_s),
        _DIV,
        f"  {'HORA':<10}{'FASE':<12}{'TEMP(C)':>8}  {'PRES(kPa)':>9}",
        _DIV,
    ]

    for r in lecturas:
        label = _FASE.get(r["fase_codigo"], r["fase_codigo"])
        tv    = r["temp_camara"]
        pv    = r["pres_camara"]
        t_s   = f"{tv:.1f}" if tv is not None else "--"
        p_s   = f"{pv:.1f}" if pv is not None else "--"
        lines.append(
            f"  {r['timestamp_rel']:<10}{label:<12}{t_s:>8}  {p_s:>9}"
        )

    lines += [
        _DIV,
        f"Resultado:   {resultado}",
        f"Fin:         {fin_s}",
        _SEP,
        "",
    ]

    return "\n".join(lines)
