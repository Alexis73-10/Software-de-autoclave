# services/domain/logging/ticket_formatter.py
#
# Formato único de ticket de ciclo — compartido entre la impresión en tiempo
# real (CycleLogger, fila por fila mientras el ciclo corre) y la reimpresión
# de ciclos guardados en la DB (ciclos.py, con todos los datos disponibles
# de una vez). Ambos casos arman el mismo texto llamando a format_header(),
# format_row() (una vez por lectura) y format_footer() en orden.
#
# "Temp. final" (temperatura de la última lectura) sólo se conoce al cerrar
# el ciclo, así que vive en el pie — no se puede insertar antes de la tabla
# en un ticket que ya se imprimió en papel.

from datetime import datetime

from autoclave.state_machine.alarms.catalogo import CATALOGO


def motivo_ticket(codigo: str | None, motivo: str | None) -> str | None:
    """Línea de motivo del ticket térmico: solo código y título (spec §5.4).
    Ciclos anteriores al catálogo (sin codigo_fallo) conservan su motivo."""
    definicion = CATALOGO.get(codigo or "")
    if definicion is not None:
        return f"{definicion.codigo} - {definicion.titulo}"
    return motivo or None


def _campo(fila, clave):
    """Lee una clave de dict o sqlite3.Row; None si no existe."""
    try:
        return fila[clave]
    except (KeyError, IndexError):
        return None

_MESES = {
    1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC",
}


def format_header(meta: dict) -> str:
    """Encabezado del ticket (todo lo previo a las filas de lecturas)."""
    fi = meta.get("fecha_inicio") or ""
    try:
        t0          = datetime.fromisoformat(fi)
        fecha_str   = f"{t0.day:02d}/{_MESES[t0.month]}/{t0.year}"
        hora_inicio = t0.strftime("%H:%M:%S")
    except (ValueError, TypeError, KeyError):
        fecha_str = hora_inicio = "---"

    numero   = f"{meta.get('numero_ciclo', 0):06d}"
    temp_e   = meta.get("temp_esterilizacion") or ""
    tiempo_e = meta.get("tiempo_esterilizacion") or ""

    lines = [
        " ",
        "------------------------",
        f"Fecha: {fecha_str}",
        f"Hora:  {hora_inicio}",
        f"Num serie: {meta.get('serie', '')}",
        f"Modelo: {meta.get('modelo', '')}",
        f"SoftW.: {meta.get('version_sw', '')}",
        f"Ciclo No.: {numero}",
        meta.get("nombre_ciclo") or "",
        f"({meta.get('tipo_ciclo') or ''})",
        f"Temp. Ester.: {temp_e} C",
        f"Tiempo Ester.: {tiempo_e} min",
    ]
    # T8 (§7.6): ciclo sin base de datos, sin operador registrado
    if meta.get("sin_registro"):
        lines.append("SIN OPERADOR / SIN BD")
    lines.append("  Hora      C      kPa")
    return "\n".join(lines)


def format_row(lectura: dict) -> str:
    """Una fila HORA/FASE/TEMP/PRES."""
    fase = (lectura.get("fase_codigo") or " ").ljust(1)
    ts   = lectura.get("timestamp_rel") or ""
    tc   = lectura.get("temp_camara")
    pc   = lectura.get("pres_camara")
    tc_s = f"{tc:06.1f}" if tc is not None else " -----"
    pc_s = f"{pc:06.1f}" if pc is not None else " -----"
    return f"{fase} {ts} {tc_s} {pc_s}"


def format_footer(resultado: str, fecha_fin: str, temp_final=None, motivo: str | None = None,
                   f0_total: float | None = None, avisos: list | None = None,
                   operador: str | None = None) -> str:
    """Pie del ticket (todo lo posterior a las filas de lecturas)."""
    try:
        hora_fin = datetime.fromisoformat(fecha_fin).strftime("%H:%M:%S")
    except (ValueError, TypeError):
        hora_fin = "---"

    temp_final_s = f"{temp_final:.0f}" if temp_final is not None else "---"

    lines = [
        f"Temp. final: {temp_final_s} C",
        f"Estado: {resultado or ''}",
    ]
    if motivo:
        lines.append(f"Motivo: {motivo}")
    if f0_total is not None:
        lines.append(f"F0 total: {f0_total:.1f} min")
    for aviso in avisos or []:
        lines.append(f"Aviso: {aviso}")
    lines += [
        f"Hora fin: {hora_fin}",
        # O1 (tanda 3): el operador del ciclo; sin él queda la línea para firmar
        f"Operador: {operador}" if operador else "Operador: ____________",
        "------------------------",
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)


def format_ticket(ciclo, lecturas) -> str:
    """Arma el ticket completo de un ciclo guardado (reimpresión)."""
    meta = {
        "numero_ciclo":          ciclo["numero_ciclo"],
        "serie":                 ciclo["serie"],
        "modelo":                ciclo["modelo"],
        "version_sw":            ciclo["version_sw"],
        "nombre_ciclo":          ciclo["nombre_ciclo"],
        "tipo_ciclo":            ciclo["tipo_ciclo"],
        "temp_esterilizacion":   ciclo["temp_esterilizacion"],
        "tiempo_esterilizacion": ciclo["tiempo_esterilizacion"],
        "fecha_inicio":          ciclo["fecha_inicio"],
    }

    temp_final = None
    if lecturas:
        tc = lecturas[-1].get("temp_camara")
        if tc is not None:
            temp_final = tc

    parts = [format_header(meta)]
    parts += [format_row(r) for r in lecturas]
    parts.append(format_footer(
        ciclo["resultado"], ciclo["fecha_fin"],
        temp_final=temp_final, motivo=motivo_ticket(
            _campo(ciclo, "codigo_fallo"), _campo(ciclo, "motivo_fallo")),
        operador=_campo(ciclo, "operador") or None,
    ))
    return "\n".join(parts)
