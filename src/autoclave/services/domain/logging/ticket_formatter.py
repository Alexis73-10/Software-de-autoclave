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

from dataclasses import dataclass
from datetime import datetime

from autoclave.core.runtime import unidades as u
from autoclave.state_machine.alarms.catalogo import CATALOGO


# ── I3 (tanda 5): idioma y unidades vigentes al generar el ticket ─────────
# Los valores guardados siguen en °C y kPa absolutos; el ticket solo los
# presenta. El ticket es cp437: sin "°" (se imprime "C"/"F" como antes).

@dataclass(frozen=True)
class Presentacion:
    idioma: str = "es"
    temperatura: str = "C"
    presion: str = "kPa"
    p_atm: float | None = None


_POR_DEFECTO = Presentacion()
_proveedor = None          # callable -> Presentacion (lo fija el backend al arrancar)


def fijar_proveedor(proveedor) -> None:
    global _proveedor
    _proveedor = proveedor


def presentacion_actual() -> Presentacion:
    """La vigente; ante cualquier error, español en °C y kPa (nunca lanza)."""
    try:
        p = _proveedor() if _proveedor is not None else _POR_DEFECTO
        u.validar(p.temperatura, p.presion)
        return p if p.idioma in ("es", "en") else _POR_DEFECTO
    except Exception:
        return _POR_DEFECTO


_TXT = {
    "es": {"fecha": "Fecha", "hora": "Hora", "serie": "Num serie", "modelo": "Modelo",
           "ciclo": "Ciclo No.", "temp_ester": "Temp. Ester.", "tiempo_ester": "Tiempo Ester.",
           "sin_bd": "SIN OPERADOR / SIN BD", "unidades": "Unidades", "temp_final": "Temp. final",
           "estado": "Estado", "motivo": "Motivo", "aviso": "Aviso", "hora_fin": "Hora fin",
           "operador": "Operador", "abs": "abs", "vacio": "v=inHg vacio"},
    "en": {"fecha": "Date", "hora": "Time", "serie": "Serial No", "modelo": "Model",
           "ciclo": "Cycle No.", "temp_ester": "Steril. temp.", "tiempo_ester": "Steril. time",
           "sin_bd": "NO OPERATOR / NO DB", "unidades": "Units", "temp_final": "Final temp.",
           "estado": "Status", "motivo": "Reason", "aviso": "Warning", "hora_fin": "End time",
           "operador": "Operator", "abs": "abs", "vacio": "v=inHg vacuum"},
}
_MESES_EN = {1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
             7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"}
_RESULTADOS_EN = {"COMPLETADO": "COMPLETED", "CANCELADO": "CANCELLED", "INTERRUMPIDO": "INTERRUPTED",
                  "EMERGENCIA": "EMERGENCY", "FALLO": "FAILED"}


def _t(p: Presentacion, clave: str) -> str:
    return _TXT.get(p.idioma, _TXT["es"])[clave]


def _simbolo_t(p: Presentacion) -> str:
    return p.temperatura                 # "C" o "F" (cp437, sin °)


def _simbolo_p(p: Presentacion) -> str:
    return "psig" if p.presion == "psi" else p.presion


def _temp(v, p: Presentacion) -> float:
    return u.temp_a_mostrar(v, p.temperatura)


def resultado_ticket(resultado: str | None, p: Presentacion | None = None) -> str:
    p = p or presentacion_actual()
    r = resultado or ""
    if p.idioma != "en":
        return r
    for clave, valor in _RESULTADOS_EN.items():
        if r.startswith(clave):
            return valor + r[len(clave):]
    return r


def motivo_ticket(codigo: str | None, motivo: str | None,
                  p: Presentacion | None = None) -> str | None:
    """Línea de motivo del ticket térmico: solo código y título (spec §5.4),
    en el idioma vigente. Ciclos anteriores al catálogo (sin codigo_fallo)
    conservan su motivo."""
    definicion = CATALOGO.get(codigo or "")
    if definicion is not None:
        titulo = definicion.titulo
        idioma = (p or presentacion_actual()).idioma
        if idioma != "es":
            try:
                from autoclave.core.runtime import alarmas_i18n
                titulo = alarmas_i18n.textos(definicion, {}, idioma)["titulo"]
            except Exception:
                pass
        return f"{definicion.codigo} - {titulo}"
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


def format_header(meta: dict, p: Presentacion | None = None) -> str:
    """Encabezado del ticket (todo lo previo a las filas de lecturas)."""
    p = p or presentacion_actual()
    meses = _MESES_EN if p.idioma == "en" else _MESES
    fi = meta.get("fecha_inicio") or ""
    try:
        t0          = datetime.fromisoformat(fi)
        fecha_str   = f"{t0.day:02d}/{meses[t0.month]}/{t0.year}"
        hora_inicio = t0.strftime("%H:%M:%S")
    except (ValueError, TypeError, KeyError):
        fecha_str = hora_inicio = "---"

    numero   = f"{meta.get('numero_ciclo', 0):06d}"
    temp_e   = meta.get("temp_esterilizacion")
    if p.temperatura != "C" and temp_e not in (None, ""):
        try:                             # siempre se guarda en °C (también como texto)
            temp_e = f"{_temp(float(temp_e), p):.1f}"
        except (TypeError, ValueError):
            temp_e = "---"               # nunca un valor en °C con símbolo F
    temp_e   = "" if temp_e is None else temp_e
    tiempo_e = meta.get("tiempo_esterilizacion") or ""
    st, sp = _simbolo_t(p), _simbolo_p(p)
    # I3: la cabecera dice las unidades usadas (kPa/bar/mbar absolutos; psig con "v" = inHg de vacío)
    unidades = f"{_t(p, 'unidades')}: {st}, {sp}" + (f" {_t(p, 'abs')}" if p.presion != "psi"
                                                    else f" ({_t(p, 'vacio')})")

    lines = [
        " ",
        "------------------------",
        f"{_t(p, 'fecha')}: {fecha_str}",
        f"{_t(p, 'hora')}:  {hora_inicio}",
        f"{_t(p, 'serie')}: {meta.get('serie', '')}",
        f"{_t(p, 'modelo')}: {meta.get('modelo', '')}",
        f"SoftW.: {meta.get('version_sw', '')}",
        f"{_t(p, 'ciclo')}: {numero}",
        meta.get("nombre_ciclo") or "",
        f"({meta.get('tipo_ciclo') or ''})",
        f"{_t(p, 'temp_ester')}: {temp_e} {st}",
        f"{_t(p, 'tiempo_ester')}: {tiempo_e} min",
    ]
    if p != _POR_DEFECTO:
        lines.append(unidades)
    # T8 (§7.6): ciclo sin base de datos, sin operador registrado
    if meta.get("sin_registro"):
        lines.append(_t(p, "sin_bd"))
    lines.append(f"  {_t(p, 'hora'):<4}      {st}      {sp}")
    return "\n".join(lines)


def _pres_fila(pc, p: Presentacion) -> str:
    if pc is None:
        return " -----"
    if p.presion == "kPa":
        return f"{pc:06.1f}"
    valor, simbolo = u.pres_a_mostrar(pc, p.presion, p.p_atm)
    if valor is None:
        return " -----"                 # psi sin P_atm: nunca un número inventado
    d = u.DECIMALES.get(simbolo, 1)
    texto = f"{valor:06.{d}f}" if d else f"{valor:06.0f}"
    return texto + ("v" if simbolo == "inHg" else "")


def format_row(lectura: dict, p: Presentacion | None = None) -> str:
    """Una fila HORA/FASE/TEMP/PRES."""
    p = p or presentacion_actual()
    fase = (lectura.get("fase_codigo") or " ").ljust(1)
    ts   = lectura.get("timestamp_rel") or ""
    tc   = lectura.get("temp_camara")
    pc   = lectura.get("pres_camara")
    tc_s = f"{_temp(tc, p):06.1f}" if tc is not None else " -----"
    pc_s = _pres_fila(pc, p)
    return f"{fase} {ts} {tc_s} {pc_s}"


def format_footer(resultado: str, fecha_fin: str, temp_final=None, motivo: str | None = None,
                   f0_total: float | None = None, avisos: list | None = None,
                   operador: str | None = None, p: Presentacion | None = None) -> str:
    """Pie del ticket (todo lo posterior a las filas de lecturas)."""
    p = p or presentacion_actual()
    try:
        hora_fin = datetime.fromisoformat(fecha_fin).strftime("%H:%M:%S")
    except (ValueError, TypeError):
        hora_fin = "---"

    temp_final_s = f"{_temp(temp_final, p):.0f}" if temp_final is not None else "---"

    lines = [
        f"{_t(p, 'temp_final')}: {temp_final_s} {_simbolo_t(p)}",
        f"{_t(p, 'estado')}: {resultado_ticket(resultado, p)}",
    ]
    if motivo:
        lines.append(f"{_t(p, 'motivo')}: {motivo}")
    if f0_total is not None:
        lines.append(f"F0 total: {f0_total:.1f} min")
    for aviso in avisos or []:
        lines.append(f"{_t(p, 'aviso')}: {aviso}")
    lines += [
        f"{_t(p, 'hora_fin')}: {hora_fin}",
        # O1 (tanda 3): el operador del ciclo; sin él queda la línea para firmar
        f"{_t(p, 'operador')}: {operador}" if operador else f"{_t(p, 'operador')}: ____________",
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

    p = presentacion_actual()            # una sola vez: todo el ticket igual
    parts = [format_header(meta, p)]
    parts += [format_row(r, p) for r in lecturas]
    parts.append(format_footer(
        ciclo["resultado"], ciclo["fecha_fin"],
        temp_final=temp_final, motivo=motivo_ticket(
            _campo(ciclo, "codigo_fallo"), _campo(ciclo, "motivo_fallo"), p),
        operador=_campo(ciclo, "operador") or None, p=p,
    ))
    return "\n".join(parts)
