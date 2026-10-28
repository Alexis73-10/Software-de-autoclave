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
import re
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


# X9 (tanda 9, D9-13.4): los rótulos del ticket viven en el catálogo
# (i18n/<idioma>.json → ticket_ciclo.*). Ticket de ancho fijo: se permiten
# abreviaturas solo aquí (DECISIÓN SIN CONFIRMAR de D9-13.4).
_SECCION = "ticket_ciclo."
_MESES_EN = {1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
             7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"}
_RESULTADOS = ("COMPLETADO", "CANCELADO", "INTERRUMPIDO", "EMERGENCIA", "FALLO",
               "SENSOR_AUSENTE")


# P4 (tanda 16, D-14.4): marca NO CONFORME de un ciclo. Se reconoce por el
# aviso que CicloState anotaba en estado.avisos_ciclo (C-13.7b) y que
# CycleLogger guarda en la columna avisos_ticket; no hay columna propia ni
# resultado nuevo (el resultado técnico sigue siendo COMPLETADO).
# FC-08 (tanda 21): ya no se escribe; solo lectura de ciclos guardados.
CLAVE_NO_CONFORME = "ticket_ciclo.no_conforme_referencia"


def avisos_no_conforme(avisos) -> bool:
    """True si la lista de avisos (texto o {"clave": ...}) trae la marca NO
    CONFORME. Nunca lanza."""
    try:
        return any(isinstance(a, dict) and a.get("clave") == CLAVE_NO_CONFORME
                   for a in (avisos or []))
    except Exception:
        return False


def ciclo_no_conforme(ciclo) -> bool:
    """True si el ciclo guardado (dict o sqlite3.Row de `ciclos`) quedó NO
    CONFORME, según su columna avisos_ticket. Sin columna, vacía o dañada:
    False. Nunca lanza."""
    try:
        _, avisos = leer_avisos_ticket(_campo(ciclo, "avisos_ticket"))
    except Exception:
        return False
    return avisos_no_conforme(avisos)


# FC-08 (tanda 21): observación del ciclo por una Referencia sin lectura (carga
# sólida). Reemplaza la marca NO CONFORME para los ciclos nuevos; los guardados
# con CLAVE_NO_CONFORME se siguen leyendo e imprimiendo como quedaron.
# Aviso: {"clave": CLAVE_OBSERVACION_REFERENCIA, "sensor", "hora" (HH:MM),
# "fase" (fase del backend, p. ej. "ESTERILIZACION")}.
CLAVE_OBSERVACION_REFERENCIA = "ticket_ciclo.observacion_referencia"
# FC-12 (tanda 21): usuario identificado que canceló el ciclo. Aviso:
# {"clave": CLAVE_CANCELADO_POR, "usuario"}.
CLAVE_CANCELADO_POR = "ticket_ciclo.cancelado_por"


def observaciones_referencia(avisos) -> list[dict]:
    """FC-08: [{sensor, hora, fase}] de las observaciones de Referencia de una
    lista de avisos, en orden. `fase` es la fase del backend tal como se
    guardó ("" si no se conoce). Nunca lanza; entradas mal formadas se omiten."""
    salida = []
    try:
        for a in avisos or []:
            if not (isinstance(a, dict) and a.get("clave") == CLAVE_OBSERVACION_REFERENCIA):
                continue
            salida.append({"sensor": str(a.get("sensor") or ""),
                           "hora": str(a.get("hora") or ""),
                           "fase": str(a.get("fase") or "")})
    except Exception:
        return []
    return salida


def ciclo_observaciones(ciclo) -> list[dict]:
    """FC-08: observaciones de Referencia de un ciclo guardado (columna
    avisos_ticket). Nunca lanza."""
    try:
        _, avisos = leer_avisos_ticket(_campo(ciclo, "avisos_ticket"))
    except Exception:
        return []
    return observaciones_referencia(avisos)


def _fase_ticket(fase, p: Presentacion) -> str:
    """Fase del backend en el idioma del ticket; sin traducción, tal cual."""
    try:
        from autoclave import i18n
        clave = _SECCION + "fase." + str(fase)
        if fase and i18n.existe(clave, p.idioma):
            return i18n.t(clave, p.idioma)
    except Exception:
        pass
    return str(fase or "---")


def _linea_aviso(aviso, p: Presentacion) -> str:
    """Una línea del pie para un aviso. La observación de Referencia (FC-08) y
    el usuario que canceló (FC-12) llevan su propio rótulo en vez de «Aviso»."""
    if isinstance(aviso, dict):
        clave = aviso.get("clave")
        try:
            if clave == CLAVE_OBSERVACION_REFERENCIA:
                from autoclave import i18n
                texto = i18n.t(clave, p.idioma, sensor=aviso.get("sensor") or "---",
                               hora=aviso.get("hora") or "--:--",
                               fase=_fase_ticket(aviso.get("fase"), p))
                return f"{_t(p, 'observacion')}: {texto}"
            if clave == CLAVE_CANCELADO_POR:
                return f"{_t(p, 'cancelado_por')}: {aviso.get('usuario') or '---'}"
        except Exception:
            return str(aviso)
    return f"{_t(p, 'aviso')}: {aviso_ticket(aviso, p)}"


def _t(p: Presentacion, clave: str, **params) -> str:
    from autoclave import i18n
    return i18n.t(_SECCION + clave, p.idioma, **params)


# X9 (D9-13.4): nombre de un programa de fábrica en el idioma vigente.
# (cycle_id, nombre guardado) -> clave del catálogo o None; lo fija el backend.
_resolutor_nombre = None


def fijar_resolutor_nombre(resolutor) -> None:
    global _resolutor_nombre
    _resolutor_nombre = resolutor


def nombre_ciclo(meta: dict, p: Presentacion) -> str:
    """El nombre guardado; si es el de un programa de fábrica sin cambiar,
    el del catálogo en el idioma del ticket (D-14). Nunca lanza."""
    nombre = meta.get("nombre_ciclo") or ""
    try:
        if _resolutor_nombre is not None:
            from autoclave import i18n
            clave = _resolutor_nombre(meta.get("tipo_ciclo") or "", nombre)
            if clave and i18n.existe(clave, p.idioma):
                return i18n.t(clave, p.idioma)
    except Exception:
        pass
    return nombre


def aviso_ticket(aviso, p: Presentacion) -> str:
    """Una línea de aviso del pie: texto (ciclos anteriores) o, desde X9,
    {"clave": ..., parámetros} armado en el idioma y la unidad del ticket
    (temperatura en °C guardada; el ticket es cp437, sin "°")."""
    if isinstance(aviso, str):
        return aviso
    try:
        from autoclave import i18n
        params = {k: v for k, v in aviso.items() if k != "clave"}
        # E12 (tanda 12, C-13.5): toda temperatura (temp, temp_min, temp_max)
        for k in [k for k in params if k == "temp" or k.startswith("temp_")]:
            v = params[k]
            params[k] = (f"{_temp(float(v), p):.1f} {_simbolo_t(p)}"
                         if isinstance(v, (int, float)) and not isinstance(v, bool) else "---")
        return i18n.t(str(aviso["clave"]), p.idioma, **params)
    except Exception:
        return str(aviso)


def _simbolo_t(p: Presentacion) -> str:
    return p.temperatura                 # "C" o "F" (cp437, sin °)


def _simbolo_p(p: Presentacion) -> str:
    return "psig" if p.presion == "psi" else p.presion


def _temp(v, p: Presentacion) -> float:
    return u.temp_a_mostrar(v, p.temperatura)


def resultado_ticket(resultado: str | None, p: Presentacion | None = None) -> str:
    """Resultado en el idioma del ticket. En español, el código tal cual (como
    siempre). X9 (D9-13.4): FALLO_<FASE> en inglés traduce también la fase."""
    p = p or presentacion_actual()
    r = resultado or ""
    if p.idioma == "es":
        return r
    try:
        from autoclave import i18n
        if r in _RESULTADOS:
            return _t(p, f"resultado.{r}")
        for clave in _RESULTADOS:
            if r.startswith(clave + "_"):
                fase = r[len(clave) + 1:]
                params = {}
                # FALLO_PUERTA_<n>_<causa> (CicloState._verificar_puertas)
                m = re.fullmatch(r"PUERTA_(\d+)_([A-Z_]+)", fase)
                if m:
                    fase, params = f"PUERTA_{m.group(2)}", {"n": m.group(1)}
                if i18n.existe(f"{_SECCION}fase.{fase}", p.idioma):
                    return _t(p, "resultado_fase", resultado=_t(p, f"resultado.{clave}"),
                              fase=_t(p, f"fase.{fase}", **params))
                return _t(p, f"resultado.{clave}") + r[len(clave):]
    except Exception:
        pass
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


def lineas_version(rotulo: str, valor, ancho: int = ANCHO_TICKET) -> list[str]:
    """Como `lineas_rotulo`, pero una versión larga (VER-05: "1.0.0-alpha.2.dev+g1a2b3c4",
    "1.0.0-alpha.1 (1a2b3c4)") se parte antes del "+" o del " (" en lugar de a
    ciegas en la columna `ancho`."""
    valor = "" if valor is None else str(valor)
    if len(f"{rotulo}: {valor}") <= ancho:
        return [f"{rotulo}: {valor}"]
    if len(valor) <= ancho:
        return [f"{rotulo}:", valor]
    for sep in (" (", "+"):
        i = valor.find(sep)
        if i > 0:
            trozos = [valor[:i], valor[i:].strip()]
            break
    else:
        trozos = [valor]
    return [f"{rotulo}:"] + [t[j:j + ancho] for t in trozos for j in range(0, len(t), ancho)]


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
        *lineas_version(_t(p, 'software'), meta.get('version_sw', '')),
        f"{_t(p, 'ciclo')}: {numero}",
        nombre_ciclo(meta, p),
        f"({meta.get('tipo_ciclo') or ''})",
        f"{_t(p, 'temp_ester')}: {temp_e} {st}",
        f"{_t(p, 'tiempo_ester')}: {tiempo_e} min",
    ]
    if p != _POR_DEFECTO:
        lines.append(unidades)
    # T8 (§7.6): ciclo sin base de datos, sin operador registrado
    if meta.get("sin_registro"):
        lines.append(_t(p, "sin_bd"))
    # P4 (D-14.4): en la reimpresión ya se sabe; el ticket en vivo lo lleva
    # en la primera línea del pie (el encabezado se imprime al iniciar)
    if meta.get("no_conforme"):
        lines.append(_t(p, "no_conforme_marca"))
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
    # P4 (tanda 16, D-14.4): primera línea destacada del pie, en vivo y al
    # reimprimir, cuando el ciclo quedó NO CONFORME (Referencia sin verificar)
    if avisos_no_conforme(avisos):
        lines.insert(0, _t(p, "no_conforme_marca"))
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
        lines.append(f"{_t(p, 'f0_total')}: {f0_total:.1f} min")
    if (isinstance(sin_datos_s, (int, float)) and not isinstance(sin_datos_s, bool)
            and sin_datos_s > 0):
        lines.append(f"{_t(p, 'sin_datos')}: {sin_datos_s:.0f} s")
    for aviso in avisos or []:
        lines.append(_linea_aviso(aviso, p))
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


def leer_avisos_ticket(texto) -> tuple[float | None, list]:
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
    # X9 (D9-13.4): también avisos con clave + parámetros
    avisos = ([a for a in avisos if isinstance(a, str)
               or (isinstance(a, dict) and isinstance(a.get("clave"), str))]
              if isinstance(avisos, list) else [])
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
        "no_conforme":           ciclo_no_conforme(ciclo),   # P4 (D-14.4)
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
