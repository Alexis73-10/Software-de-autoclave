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

import json
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
           "operador": "Operador", "abs": "abs", "vacio": "v=inHg vacio",
           "no_esteril": "*** CARGA NO ESTÉRIL ***",
           "sin_datos": "Sin datos de la tarjeta"},
    "en": {"fecha": "Date", "hora": "Time", "serie": "Serial No", "modelo": "Model",
           "ciclo": "Cycle No.", "temp_ester": "Steril. temp.", "tiempo_ester": "Steril. time",
           "sin_bd": "NO OPERATOR / NO DB", "unidades": "Units", "temp_final": "Final temp.",
           "estado": "Status", "motivo": "Reason", "aviso": "Warning", "hora_fin": "End time",
           "operador": "Operator", "abs": "abs", "vacio": "v=inHg vacuum",
           "no_esteril": "*** LOAD NOT STERILE ***",
           "sin_datos": "No control board data"},
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


# Ancho del ticket térmico en columnas (el resumen por periodo usa el mismo).
ANCHO_TICKET = 24


def lineas_rotulo(rotulo: str, valor, ancho: int = ANCHO_TICKET) -> list[str]:
    """"Rótulo: valor" en una línea si cabe; si no, el rótulo solo y el valor
    debajo, en trozos de `ancho` (M1, tanda 7: "SPK-SAT 2000H2-LAB", 18
    caracteres, no cabe junto a "Modelo: " en 24 columnas y la impresora lo
    partía o el resumen lo cortaba)."""
    valor = "" if valor is None else str(valor)
    linea = f"{rotulo}: {valor}"
    if len(linea) <= ancho:
        return [linea]
    return [f"{rotulo}:"] + [valor[i:i + ancho] for i in range(0, len(valor), ancho)]


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
        *lineas_rotulo(_t(p, 'modelo'), meta.get('modelo', '')),
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
                   operador: str | None = None, p: Presentacion | None = None,
                   sin_datos_s: float | None = None) -> str:
    """Pie del ticket (todo lo posterior a las filas de lecturas).
    `sin_datos_s` (T2-a, tanda 7): segundos del ciclo sin datos de la tarjeta
    (tolerancia por DI vencida); se anota solo si hubo alguno."""
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
    # T2-c (tanda 7, decisión 1.3 de Cristian; antes P-9 solo INTERRUMPIDO):
    # todo ciclo que no terminó COMPLETADO (FALLO_*, CANCELADO, EMERGENCIA,
    # INTERRUMPIDO, SENSOR_AUSENTE...) lleva la marca, en vivo y al
    # reimprimir. Un resultado vacío o desconocido también (falla segura).
    # SAF-05 (revisión Q1): igualdad exacta; "COMPLETADO" es el único valor
    # real (CicloState lo fija en estado.fase_ciclo y CycleLogger cierra con él)
    if str(resultado or "") != "COMPLETADO":
        lines.append(_t(p, "no_esteril"))
    if f0_total is not None:
        lines.append(f"F0 total: {f0_total:.1f} min")
    if (isinstance(sin_datos_s, (int, float)) and not isinstance(sin_datos_s, bool)
            and sin_datos_s > 0):
        lines.append(f"{_t(p, 'sin_datos')}: {sin_datos_s:.0f} s")
    for aviso in avisos or []:
        lines.append(f"{_t(p, 'aviso')}: {aviso}")
    lines += [
        f"{_t(p, 'hora_fin')}: {hora_fin}",
        # O1 (tanda 3): el operador del ciclo; sin él queda la línea para firmar
        f"{_t(p, 'operador')}: {operador}" if operador else f"{_t(p, 'operador')}: ____________",
        "------------------------",
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)


def _f0_guardado(valor) -> float | None:
    """f0_final de la base: solo se guarda si el ciclo tenía F0 activo."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def leer_avisos_ticket(texto) -> tuple[float | None, list[str]]:
    """D8-2.14: (sin_datos_s, avisos) de la columna `avisos_ticket` de un ciclo
    guardado. Vacía, ausente o dañada: (None, []) — el ticket se reimprime
    como antes, sin esas líneas. Nunca lanza."""
    if not isinstance(texto, str) or not texto.strip():
        return None, []
    try:
        datos = json.loads(texto)
    except (TypeError, ValueError):
        return None, []
    if not isinstance(datos, dict):
        return None, []
    sin_datos = datos.get("sin_datos_s")
    if isinstance(sin_datos, bool) or not isinstance(sin_datos, (int, float)):
        sin_datos = None
    avisos = datos.get("avisos")
    avisos = [a for a in avisos if isinstance(a, str)] if isinstance(avisos, list) else []
    return sin_datos, avisos


def format_ticket(ciclo, lecturas, p: Presentacion | None = None) -> str:
    """Arma el ticket completo de un ciclo guardado (reimpresión). `p`: la
    presentación a usar (el PDF de la UI pasa la suya); None = la vigente."""
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

    p = p or presentacion_actual()       # una sola vez: todo el ticket igual
    # D8-2.14: las líneas de aviso del pie guardadas al cerrar el ciclo
    sin_datos_s, avisos = leer_avisos_ticket(_campo(ciclo, "avisos_ticket"))
    parts = [format_header(meta, p)]
    parts += [format_row(r, p) for r in lecturas]
    parts.append(format_footer(
        ciclo["resultado"], ciclo["fecha_fin"],
        temp_final=temp_final, motivo=motivo_ticket(
            _campo(ciclo, "codigo_fallo"), _campo(ciclo, "motivo_fallo"), p),
        f0_total=_f0_guardado(_campo(ciclo, "f0_final")),
        avisos=avisos or None,
        operador=_campo(ciclo, "operador") or None, p=p,
        sin_datos_s=sin_datos_s,
    ))
    return "\n".join(parts)
