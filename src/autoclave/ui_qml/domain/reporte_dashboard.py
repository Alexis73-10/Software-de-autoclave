# ui_qml/domain/reporte_dashboard.py
#
# Dashboard de Reportes (planeacion_dashboard_reportes.md §5-§9): arma, a partir
# de GET /report/dashboard y GET /report/calendar, todo lo que la pantalla
# dibuja: textos del periodo, indicadores con comparación, dona, serie de la
# gráfica de área (puntos normalizados 0..1), programas, calendario, alarmas,
# operadores y (con datos ya cargados) mantenimiento. QML solo dibuja.
#
# Reglas de la planeación que viven aquí:
# - Colores: SIEMPRE claves del módulo de tema (Tema/Colores), nunca
#   hexadecimales; la clave es el nombre de la propiedad de Colores.
# - DR-H01: ningún texto dice «conforme» ni «apto»; el calendario muestra el
#   resultado del ciclo (`reportes.cal_leyenda`).
# - Frontera de confianza como reporte_resumen.py: un dato ausente o mal
#   formado cuenta como 0 / vacío y no tumba el resto.
# - Textos por claves i18n `reportes.*`; `t(clave, idioma, **params)` es
#   inyectable (por defecto autoclave.i18n.t, que devuelve la clave si falta).

import calendar
from datetime import date, timedelta

from autoclave import i18n
from autoclave.ui_qml.domain.fin_de_ciclo import _textos_alarma
from autoclave.ui_qml.domain.resumen_sistema import SIN_DATO, formatear_numero_programa
from autoclave.state_machine.alarms.catalogo import codigo_visible

UMBRAL_EXITO_PROGRAMA = 95          # % desde el que la barra del programa es verde (REP-06)
MAX_ALARMAS = 8                     # REP-10
SERIES_RESULTADO = ("completados", "fallos", "cancelados", "sin_cierre")

# Claves de tema (propiedades de Tema/Colores.qml)
C_BUENO = "menuVerdeTexto"
C_MALO = "peligroTexto"
C_NEUTRO = "textoSecundario"

_COLOR_RESULTADO = {"completados": "menuVerde", "fallos": "peligroTexto",
                    "cancelados": "menuNaranja", "sin_cierre": "textoGuia"}

# Estado del día -> aspecto. `relleno`/`borde`/`punto`: claves de tema ("" = ninguno);
# `forma` distingue sin depender del tono (REP-07). Claves que Colores.qml aún no
# tiene (la pantalla las añade): exitoFondo.
ESTADOS_DIA = ("exito", "exito_fallo_previo", "sin_exito", "falto", "no_ejecutado",
               "sin_operacion", "en_curso", "futuro")
_ASPECTO_DIA = {
    "exito":              {"forma": "relleno",        "relleno": "exitoFondo",   "borde": "menuVerde",   "punto": "", "grosor": 1, "punteado": False},
    "exito_fallo_previo": {"forma": "relleno_punto",  "relleno": "exitoFondo",   "borde": "menuVerde",   "punto": "peligroTexto", "grosor": 1, "punteado": False},
    "sin_exito":          {"forma": "solido",         "relleno": "peligroTexto", "borde": "peligroTexto", "punto": "", "grosor": 1, "punteado": False},
    "falto":              {"forma": "borde_grueso",   "relleno": "fondoTarjeta", "borde": "peligroTexto", "punto": "", "grosor": 3, "punteado": False},
    "no_ejecutado":       {"forma": "gris",           "relleno": "bordeDivisor", "borde": "bordeCampo",  "punto": "", "grosor": 1, "punteado": False},
    "sin_operacion":      {"forma": "punteado",       "relleno": "",             "borde": "bordeCampo",  "punto": "", "grosor": 1, "punteado": True},
    "en_curso":           {"forma": "azul",           "relleno": "accionPrimario", "borde": "accionPrimario", "punto": "", "grosor": 1, "punteado": False},
    "futuro":             {"forma": "deshabilitado",  "relleno": "",             "borde": "bordeDivisor", "punto": "", "grosor": 1, "punteado": False},
}
_ORDEN_CONTEO = ("exito", "exito_fallo_previo", "sin_exito", "falto", "no_ejecutado",
                 "sin_operacion", "en_curso")

_NIVELES = ("FALLO_CRITICO", "ALARMA", "AVISO", "INFORMATIVO")     # de mayor a menor
_COLOR_NIVEL = {"FALLO_CRITICO": "alarmaAlta", "ALARMA": "alarmaMedia",
                "AVISO": "alarmaBaja", "INFORMATIVO": "alarmaBaja"}
_CLAVE_NIVEL = {"FALLO_CRITICO": "reportes.nivel_fallo_critico", "ALARMA": "reportes.nivel_alarma",
                "AVISO": "reportes.nivel_aviso", "INFORMATIVO": "reportes.nivel_informativo"}


# ── ayudantes de frontera ────────────────────────────────────────────────

def _t_defecto(clave, idioma=None, **params):
    return i18n.t(clave, idioma, **params)


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _lista(v) -> list:
    return v if isinstance(v, list) else []


def _entero(v) -> int:
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return max(v, 0)
    if isinstance(v, float) and v == v and v not in (float("inf"), float("-inf")):
        return max(int(round(v)), 0)
    return 0


def _num(v):
    """float finito o None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v == v and v not in (float("inf"), float("-inf")) else None


def _fecha(iso) -> date | None:
    if not isinstance(iso, str):
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def _texto(v) -> str:
    return v if isinstance(v, str) else ""


def _lista_i18n(clave, respaldo, idioma):
    try:
        v = i18n.valor(clave, idioma)
        if isinstance(v, list) and len(v) == len(respaldo) and all(isinstance(x, str) for x in v):
            return tuple(v)
    except Exception:
        pass
    return respaldo


_DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
_MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
          "Septiembre", "Octubre", "Noviembre", "Diciembre")
_MESES_C = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _calendario_textos(idioma):
    return (_lista_i18n("fecha.dias", _DIAS, idioma),
            _lista_i18n("fecha.meses_largos", _MESES, idioma),
            _lista_i18n("fecha.meses", _MESES_C, idioma))


def _dm(d: date, idioma) -> str:
    """Día y mes numéricos: 26/10 (es) o 10/26 (en)."""
    return f"{d.month:02d}/{d.day:02d}" if _es_en(idioma) else f"{d.day:02d}/{d.month:02d}"


def _dmy(d: date, idioma) -> str:
    return f"{d.month:02d}/{d.day:02d}/{d.year}" if _es_en(idioma) else f"{d.day:02d}/{d.month:02d}/{d.year}"


def _es_en(idioma) -> bool:
    return str(idioma or i18n.idioma()).lower().startswith("en")


def _mes_texto(meses, d: date, idioma, minuscula=False) -> str:
    m = meses[d.month - 1]
    return m.lower() if minuscula and not _es_en(idioma) else m


# ── periodo ──────────────────────────────────────────────────────────────

def titulo_periodo(periodo, desde: date, hasta: date, idioma, t=_t_defecto) -> str:
    """«Octubre 2026», «Semana del 26/10 al 01/11», «Lunes 2 de noviembre», «2026»."""
    dias, meses, _ = _calendario_textos(idioma)
    if periodo == "anio":
        return str(desde.year)
    if periodo == "dia":
        return t("reportes.dash_titulo_dia", idioma, dia=dias[desde.weekday()], d=desde.day,
                 mes=_mes_texto(meses, desde, idioma, True), anio=desde.year)
    if periodo == "semana":
        return t("reportes.dash_titulo_semana", idioma, desde=_dm(desde, idioma), hasta=_dm(hasta, idioma))
    return f"{_mes_texto(meses, desde, idioma)} {desde.year}"


def _periodo_anterior_rango(periodo, desde: date) -> tuple[date, date]:
    from autoclave.utils import periodos
    ini = periodos.desplazar(periodo, desde, -1, desde)   # hoy=desde: nunca topa con el actual
    a, b = periodos.rango(periodo, ini)
    return a, b - timedelta(days=1)


def encabezado(respuesta_dashboard, idioma, t=_t_defecto) -> dict:
    r = _dict(respuesta_dashboard)
    periodo = r.get("periodo") if r.get("periodo") in ("dia", "semana", "mes", "anio") else ""
    desde, hasta = _fecha(r.get("desde")), _fecha(r.get("hasta"))
    if not periodo or desde is None:
        return {"periodo": periodo, "titulo": "", "rango": "", "comparado": ""}
    hasta = hasta or desde
    ant = _dict(r.get("anterior"))
    a_desde = _fecha(ant.get("desde"))
    a_hasta = _fecha(ant.get("hasta"))
    if a_desde is None:
        a_desde, a_hasta = _periodo_anterior_rango(periodo, desde)
    rango = _dmy(desde, idioma) if desde == hasta else \
        t("reportes.dash_rango", idioma, desde=_dmy(desde, idioma), hasta=_dmy(hasta, idioma))
    comparado = t("reportes.dash_comparado", idioma,
                  periodo=titulo_periodo(periodo, a_desde, a_hasta or a_desde, idioma, t))
    return {"periodo": periodo, "titulo": titulo_periodo(periodo, desde, hasta, idioma, t),
            "rango": rango, "comparado": comparado}


# ── serie (REP-05) ───────────────────────────────────────────────────────

def _eje_y(maximo: int) -> dict:
    """Eje y entero autoajustado: paso 'bonito' (1, 2, 5, 10, 20, 50...) con a lo
    sumo 4 intervalos; el máximo es múltiplo del paso y nunca menor que el dato."""
    if maximo <= 0:
        return {"max": 4, "paso": 1, "marcas": [{"valor": v, "y": v / 4} for v in range(5)]}
    paso = 1
    escala = 1
    while True:
        for base in (1, 2, 5):
            paso = base * escala
            if -(-maximo // paso) <= 4:
                tope = -(-maximo // paso) * paso
                return {"max": tope, "paso": paso,
                        "marcas": [{"valor": v, "y": v / tope} for v in range(0, tope + 1, paso)]}
        escala *= 10


def _x(i, n):
    return 0.5 if n <= 1 else i / (n - 1)


def serie(respuesta_dashboard, idioma, t=_t_defecto) -> dict:
    r = _dict(respuesta_dashboard)
    periodo = r.get("periodo")
    filas = [_dict(p) for p in _lista(r.get("serie")) if isinstance(p, dict)]
    n = len(filas)
    dias, meses, cortos = _calendario_textos(idioma)
    maximo = max([_entero(p.get("total")) for p in filas] or [0])
    eje = _eje_y(maximo)
    puntos = []
    for i, p in enumerate(filas):
        total, comp, fallos = _entero(p.get("total")), _entero(p.get("completados")), _entero(p.get("fallos"))
        inicio = _fecha(p.get("inicio"))
        etiqueta = _texto(p.get("etiqueta"))
        if periodo == "dia":
            rotulo = f"{etiqueta[:2]}:00"
        elif periodo == "anio" and inicio:
            rotulo = f"{_mes_texto(meses, inicio, idioma)} {inicio.year}"
        elif inicio:
            rotulo = f"{dias[inicio.weekday()][:3]} {inicio.day} {cortos[inicio.month - 1]}"
        else:
            rotulo = etiqueta
        puntos.append({"x": _x(i, n), "y_total": total / eje["max"], "y_completados": comp / eje["max"],
                       "con_fallo": fallos > 0, "total": total, "completados": comp, "fallos": fallos,
                       "etiqueta": etiqueta, "rotulo": rotulo})
    return {"vacia": maximo == 0, "puntos": puntos, "eje_y": eje, "eje_x": _eje_x(periodo, filas, idioma),
            "color_total": "accionPrimario", "color_completados": "menuVerde", "color_fallo": "peligroTexto"}


def _eje_x(periodo, filas, idioma) -> list:
    n = len(filas)
    _, meses, cortos = _calendario_textos(idioma)
    marcas = []
    for i, p in enumerate(filas):
        inicio = _fecha(p.get("inicio"))
        etiqueta = _texto(p.get("etiqueta"))
        if periodo == "dia":
            if i % 6 == 0:
                marcas.append((i, f"{etiqueta[:2]}:00"))
        elif periodo == "anio" and inicio:
            marcas.append((i, cortos[inicio.month - 1].capitalize()))
        elif periodo == "semana" and inicio:
            marcas.append((i, str(inicio.day)))
        elif inicio and (inicio.day == 1 or inicio.day % 5 == 0):
            marcas.append((i, str(inicio.day)))
    return [{"x": _x(i, n), "texto": txt} for i, txt in marcas]


# ── indicadores (REP-03) ─────────────────────────────────────────────────

def _normalizar(valores: list) -> list:
    n = len(valores)
    mx = max(valores or [0])
    return [{"x": _x(i, n), "y": (v / mx if mx > 0 else 0.0)} for i, v in enumerate(valores)]


def _comparacion(delta, bueno_si, unidad, t, idioma):
    """delta None = sin comparación posible. bueno_si: 'sube' | 'baja' | None (neutro)."""
    if delta is None:
        return {"disponible": False, "texto": "", "flecha": "ninguna", "color": C_NEUTRO}
    if delta == 0:
        flecha, color, signo = "igual", C_NEUTRO, ""
    else:
        flecha = "arriba" if delta > 0 else "abajo"
        signo = "+" if delta > 0 else "−"
        color = C_NEUTRO
        if bueno_si == "sube":
            color = C_BUENO if delta > 0 else C_MALO
        elif bueno_si == "baja":
            color = C_BUENO if delta < 0 else C_MALO
    texto = f"{signo}{abs(delta)}" if delta else "0"
    if unidad:
        texto += " " + t(unidad, idioma)
    return {"disponible": True, "texto": texto, "flecha": flecha, "color": color}


def indicadores(respuesta_dashboard, idioma, t=_t_defecto) -> list:
    r = _dict(respuesta_dashboard)
    ind = _dict(r.get("indicadores"))
    ant = r.get("indicadores_anterior")
    ant = ant if isinstance(ant, dict) else None
    serie_filas = [_dict(p) for p in _lista(r.get("serie"))]

    total = _entero(ind.get("total"))
    comp = _entero(ind.get("completados"))
    fallos = _entero(ind.get("fallos"))
    exito = _entero(ind.get("exito_pct"))
    dur = _num(ind.get("duracion_media_s"))
    minutos = round(dur / 60) if dur is not None else None
    excl = _entero(ind.get("duraciones_excluidas"))

    d_total = None if ant is None else total - _entero(ant.get("total"))
    d_exito = None if ant is None else exito - _entero(ant.get("exito_pct"))
    d_fallos = None if ant is None else fallos - _entero(ant.get("fallos"))
    a_dur = _num(ant.get("duracion_media_s")) if ant is not None else None
    d_dur = None if (ant is None or dur is None or a_dur is None) else minutos - round(a_dur / 60)

    totales = [_entero(p.get("total")) for p in serie_filas]
    exitos = [(_entero(p.get("completados")) / _entero(p.get("total")) if _entero(p.get("total")) else 0.0)
              for p in serie_filas]
    acum, s = [], 0
    for p in serie_filas:
        s += _entero(p.get("fallos"))
        acum.append(s)

    sin_datos = ant is None
    texto_sin = t("reportes.dash_sin_anterior", idioma)

    def tarjeta(clave, valor, pie, comp_, mini):
        c = dict(comp_)
        c["sin_datos"] = sin_datos
        c["texto_sin_datos"] = texto_sin if sin_datos else ""
        return {"clave": clave, "titulo": t(f"reportes.ind_{clave}", idioma), "valor": valor,
                "pie": pie, "comparacion": c, "mini": mini}

    return [
        tarjeta("ciclos", str(total), "", _comparacion(d_total, None, "", t, idioma), _normalizar(totales)),
        tarjeta("exito", f"{exito}%", t("reportes.ind_exito_pie", idioma, n=comp, total=total),
                _comparacion(d_exito, "sube", "reportes.unidad_pp", t, idioma),
                _normalizar([round(100 * e) for e in exitos])),
        tarjeta("fallos", str(fallos),
                t("reportes.ind_fallos_pie", idioma, cancelados=_entero(ind.get("cancelados")),
                  sin_cierre=_entero(ind.get("sin_cierre"))),
                _comparacion(d_fallos, "baja", "", t, idioma), _normalizar(acum)),
        tarjeta("duracion", (t("reportes.dash_min", idioma, n=minutos) if minutos is not None else SIN_DATO),
                (t("reportes.ind_duracion_excluidas", idioma, n=excl) if excl > 0 else ""),
                _comparacion(d_dur, None, "reportes.unidad_min", t, idioma), []),
    ]


# ── dona (REP-04) ────────────────────────────────────────────────────────

def dona(respuesta_dashboard, idioma, t=_t_defecto) -> dict:
    ind = _dict(_dict(respuesta_dashboard).get("indicadores"))
    total = _entero(ind.get("total"))
    porciones, acum = [], 0.0
    for c in SERIES_RESULTADO:
        n = _entero(ind.get(c))
        f = n / total if total else 0.0
        porciones.append({"clave": c, "rotulo": t(f"reportes.dona_{c}", idioma), "cantidad": n,
                          "porcentaje": f"{round(100 * f)}%", "fraccion": f, "inicio": acum,
                          "color": _COLOR_RESULTADO[c]})
        acum += f
    exito = _entero(ind.get("exito_pct"))
    return {"vacia": total == 0, "total": total, "centro": f"{exito}%" if total else "",
            "texto_vacio": t("reportes.dona_sin_ciclos", idioma) if total == 0 else "",
            "color_vacio": "bordeCampo", "porciones": porciones}


# ── programas (REP-06) ───────────────────────────────────────────────────

def programas(respuesta_dashboard, idioma, t=_t_defecto) -> list:
    filas = [p for p in _lista(_dict(respuesta_dashboard).get("por_programa")) if isinstance(p, dict)]
    out = []
    for p in filas:
        total = _entero(p.get("total"))
        comp = _entero(p.get("completados"))
        pct = round(100 * comp / total) if total else 0
        partes = []
        for clave, k in (("fallos", "reportes.prog_fallos"), ("cancelados", "reportes.prog_cancelados"),
                         ("sin_cierre", "reportes.prog_sin_cierre")):
            n = _entero(p.get(clave))
            if n:
                partes.append(t(k, idioma, n=n))
        nombre = _texto(p.get("programa_nombre"))
        out.append({"numero": formatear_numero_programa(p.get("programa_numero")), "nombre": nombre,
                    "detalle": " · ".join(partes) if partes else t("reportes.prog_sin_incidencias", idioma),
                    "total": total, "exito_pct": pct, "ancho": (comp / total) if total else 0.0,
                    "color": "menuVerde" if pct >= UMBRAL_EXITO_PROGRAMA else "menuNaranja"})
    out.sort(key=lambda x: -x["total"])
    return out


# ── alarmas (REP-10) ─────────────────────────────────────────────────────

def alarmas(respuesta_dashboard, idioma, t=_t_defecto, maximo=MAX_ALARMAS) -> dict:
    filas = [a for a in _lista(_dict(respuesta_dashboard).get("alarmas")) if isinstance(a, dict)]

    def rango_nivel(a):
        n = a.get("nivel")
        return _NIVELES.index(n) if n in _NIVELES else 0    # desconocido = el más llamativo, como en fila()

    ordenadas = sorted(filas, key=lambda a: (rango_nivel(a), -_entero(a.get("cantidad"))))
    total = sum(_entero(a.get("cantidad")) for a in filas)

    def fila(a):
        codigo = _texto(a.get("codigo"))
        titulo = _textos_alarma(codigo, {}, idioma, _texto(a.get("titulo"))).get("titulo") or _texto(a.get("titulo"))
        nivel = a.get("nivel") if a.get("nivel") in _NIVELES else "FALLO_CRITICO"   # ante la duda, lo más llamativo
        return {"codigo": codigo, "codigo_visible": _texto(a.get("codigo_visible")) or codigo_visible(codigo) or codigo,
                "titulo": titulo or codigo, "nivel": nivel, "nivel_rotulo": t(_CLAVE_NIVEL[nivel], idioma),
                "color": _COLOR_NIVEL[nivel], "cantidad": _entero(a.get("cantidad"))}

    todas = [fila(a) for a in ordenadas]
    niveles = []
    for n in _NIVELES:
        c = sum(f["cantidad"] for f in todas if f["nivel"] == n)
        niveles.append({"nivel": n, "rotulo": t(_CLAVE_NIVEL[n], idioma), "cantidad": c,
                        "fraccion": c / total if total else 0.0, "color": _COLOR_NIVEL[n]})
    return {"total": total, "filas": todas[:maximo], "todas": todas, "hay_mas": len(todas) > maximo,
            "texto_ver_todas": t("reportes.alarmas_ver_todas", idioma), "niveles": niveles,
            "vacia": not todas, "texto_vacio": t("reportes.alarmas_vacia", idioma) if not todas else ""}


# ── operadores (REP-11) ──────────────────────────────────────────────────

def _iniciales(nombre: str) -> str:
    partes = [p for p in nombre.replace(".", " ").replace("_", " ").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()


def operadores(respuesta_dashboard, idioma, t=_t_defecto) -> dict:
    r = _dict(respuesta_dashboard)
    filas = [o for o in _lista(r.get("operadores")) if isinstance(o, dict)]
    mayor = max([_entero(o.get("cantidad")) for o in filas] or [0])
    out = []
    for o in filas:
        sin = o.get("sin_operador") is True or not _texto(o.get("operador")).strip()
        nombre = t("reportes.oper_sin_operador", idioma) if sin else _texto(o.get("operador")).strip()
        c = _entero(o.get("cantidad"))
        out.append({"nombre": nombre, "iniciales": "?" if sin else _iniciales(nombre), "sin_operador": sin,
                    "cantidad": c, "fraccion": c / mayor if mayor else 0.0})
    otros = r.get("operadores_otros")
    otros_p = None
    if isinstance(otros, dict) and _entero(otros.get("ciclos")) > 0:
        otros_p = {"texto": t("reportes.oper_otros", idioma, n=_entero(otros.get("operadores"))),
                   "cantidad": _entero(otros.get("ciclos"))}
    return {"filas": out, "otros": otros_p, "vacia": not out, "texto_vacio": t("reportes.oper_vacia", idioma) if not out else ""}


# ── calendario (REP-07) ──────────────────────────────────────────────────

def _celda(d: dict, idioma, t, en_periodo) -> dict:
    estado = d["estado"]
    a = _ASPECTO_DIA[estado]
    f = d["fecha"]
    return {"vacia": False, "fecha": f.isoformat(), "dia": f.day, "estado": estado,
            "estado_rotulo": t(f"reportes.estado_{estado}", idioma), "intentos": d["intentos"],
            "exitos": d["exitos"], "en_periodo": en_periodo, "tocable": estado != "futuro", **a}


def _dias(cal) -> list:
    out = []
    for d in _lista(_dict(cal).get("dias")):
        d = _dict(d)
        f = _fecha(d.get("fecha"))
        estado = d.get("estado")
        if f is None:
            continue
        if estado not in ESTADOS_DIA:
            estado = "sin_operacion"      # desconocido: lo más neutro, nunca «éxito»
        out.append({"fecha": f, "estado": estado, "intentos": _entero(d.get("intentos")),
                    "exitos": _entero(d.get("exitos"))})
    return out


def _semanas(dias_mes: list, anio: int, mes: int, idioma, t, en_periodo) -> list:
    """Cuadrícula lunes a domingo: lista de semanas, cada una de 7 celdas (vacía = relleno)."""
    por_fecha = {d["fecha"]: d for d in dias_mes}
    primero = date(anio, mes, 1)
    ultimo = date(anio, mes, calendar.monthrange(anio, mes)[1])
    semanas, fila = [], [{"vacia": True}] * primero.weekday()
    d = primero
    while d <= ultimo:
        info = por_fecha.get(d)
        fila.append(_celda(info, idioma, t, en_periodo(d)) if info else {"vacia": True})
        if len(fila) == 7:
            semanas.append(fila)
            fila = []
        d += timedelta(days=1)
    if fila:
        semanas.append(fila + [{"vacia": True}] * (7 - len(fila)))
    return semanas


def _conteo(dias: list, idioma, t) -> list:
    out = []
    for e in _ORDEN_CONTEO:
        out.append({"estado": e, "rotulo": t(f"reportes.estado_{e}", idioma),
                    "cantidad": sum(1 for d in dias if d["estado"] == e), **_ASPECTO_DIA[e]})
    return out


def _resumen_mes(dias_mes: list, idioma, t) -> tuple[bool, str]:
    """(habilitado, resumen). Sin datos = ningún día con operación registrada."""
    if all(d["estado"] in ("futuro", "sin_operacion") for d in dias_mes):
        return False, t("reportes.mes_sin_datos", idioma)
    previo = sum(1 for d in dias_mes if d["estado"] == "exito_fallo_previo")
    sin = sum(1 for d in dias_mes if d["estado"] in ("sin_exito", "falto"))
    partes = []
    if previo:
        partes.append(t("reportes.mes_con_fallo_previo", idioma, n=previo))
    if sin:
        partes.append(t("reportes.mes_sin_exito", idioma, n=sin))
    return True, " · ".join(partes) if partes else t("reportes.mes_sin_novedad", idioma)


def calendario(respuesta_dashboard, respuesta_calendario, idioma, t=_t_defecto) -> dict:
    d = _dict(respuesta_dashboard)
    c = _dict(respuesta_calendario)
    periodo = d.get("periodo") or c.get("periodo")
    desde = _fecha(d.get("desde")) or _fecha(c.get("desde"))
    hasta = _fecha(d.get("hasta")) or _fecha(c.get("hasta")) or desde
    dias = _dias(c)
    dias_nombres, meses, cortos = _calendario_textos(idioma)
    progs = []
    for p in _lista(c.get("programas")):
        p = _dict(p)
        num = formatear_numero_programa(p.get("numero"))
        nombre = _texto(p.get("nombre"))
        progs.append({"numero": p.get("numero") if isinstance(p.get("numero"), int) else 0,
                      "numero_texto": num, "nombre": nombre,
                      "etiqueta": " · ".join(x for x in (num if num != SIN_DATO else "", nombre) if x) or SIN_DATO})
    sel = c.get("programa") if isinstance(c.get("programa"), int) and not isinstance(c.get("programa"), bool) else None
    etiqueta_sel = next((p["etiqueta"] for p in progs if p["numero"] == sel), "")

    def en_periodo(f):
        return desde is not None and desde <= f <= (hasta or desde)

    base = {"periodo": periodo or "", "programas": progs, "programa": sel, "programa_etiqueta": etiqueta_sel,
            "sin_programas": not progs, "texto_sin_programas": t("reportes.cal_sin_programas", idioma) if not progs else "",
            "dias_semana": [x[:3] for x in dias_nombres], "leyenda": t("reportes.cal_leyenda", idioma),
            "texto_toque_dia": t("reportes.cal_toque_dia", idioma),
            "leyenda_estados": [{"estado": e, "rotulo": t(f"reportes.estado_{e}", idioma), **_ASPECTO_DIA[e]}
                                for e in _ORDEN_CONTEO]}
    if not dias:
        return {**base, "vista": "anio" if periodo == "anio" else "mes", "titulo": "", "conteo": _conteo([], idioma, t),
                "semanas": [], "meses": []}
    if periodo == "anio":
        anio = dias[0]["fecha"].year
        meses_out = []
        for m in range(1, 13):
            dm = [x for x in dias if x["fecha"].month == m and x["fecha"].year == anio]
            if not dm:
                hab, res = False, t("reportes.mes_sin_datos", idioma)
            else:
                hab, res = _resumen_mes(dm, idioma, t)
            meses_out.append({"mes": m, "anio": anio, "nombre": meses[m - 1], "nombre_corto": cortos[m - 1],
                              "habilitado": hab, "resumen": res,
                              "semanas": _semanas(dm, anio, m, idioma, t, lambda f: True)})
        return {**base, "vista": "anio", "titulo": str(anio), "anio": anio, "conteo": _conteo(dias, idioma, t),
                "semanas": [], "meses": meses_out}
    ref = dias[0]["fecha"]
    mes_dias = [x for x in dias if (x["fecha"].year, x["fecha"].month) == (ref.year, ref.month)]
    visibles = mes_dias if periodo == "mes" else [x for x in mes_dias if en_periodo(x["fecha"])]
    return {**base, "vista": "mes", "titulo": f"{meses[ref.month - 1]} {ref.year}", "anio": ref.year, "mes": ref.month,
            "conteo": _conteo(visibles, idioma, t),
            "semanas": _semanas(mes_dias, ref.year, ref.month, idioma, t, en_periodo), "meses": []}


def panel_dia(respuesta_day_cycles, idioma, t=_t_defecto, n_otros=None) -> dict:
    """Panel del día (REP-07): fecha, estado, explicación e intentos en orden de inicio.
    `respuesta_day_cycles` = GET /report/day-cycles; `ciclos` se entregan tal cual los
    arma resumen_sistema.ciclo_presentable en el puente (aquí solo el encabezado).
    `n_otros`: ciclos de cualquier programa ese día, solo para explicar «faltó»."""
    r = _dict(respuesta_day_cycles)
    f = _fecha(r.get("fecha"))
    estado = r.get("estado") if r.get("estado") in ESTADOS_DIA else "sin_operacion"
    dias, meses, _ = _calendario_textos(idioma)
    titulo = ""
    if f is not None:
        titulo = t("reportes.dash_titulo_dia", idioma, dia=dias[f.weekday()], d=f.day,
                   mes=_mes_texto(meses, f, idioma, True), anio=f.year)
    return {"fecha": f.isoformat() if f else "", "titulo": titulo, "estado": estado,
            "estado_rotulo": t(f"reportes.estado_{estado}", idioma),
            "explicacion": (t("reportes.expl_falto_n", idioma, n=n_otros)
                            if estado == "falto" and isinstance(n_otros, int) and n_otros > 0
                            else t(f"reportes.expl_{estado}", idioma)), **_ASPECTO_DIA[estado]}


# ── mantenimiento (REP-09) ───────────────────────────────────────────────

def mantenimiento(mant, registros, desde: date | None, hasta: date | None, idioma, t=_t_defecto) -> dict:
    """`mant` = GET /maintenance; `registros` = lista de GET /maintenance/records o None
    si no se pudo leer (ese endpoint pide rol: sin sesión el técnico, los
    correctivos y los repuestos quedan sin dato). Los correctivos y las
    solicitudes de repuesto se cuentan en [desde, hasta]."""
    m = _dict(mant)
    cfg = _dict(m.get("configuracion"))
    intervalo = _entero(cfg.get("intervalo_ciclos"))
    restantes = m.get("ciclos_restantes")
    restantes = restantes if isinstance(restantes, int) and not isinstance(restantes, bool) else None
    estado = m.get("estado")
    disponible = estado in ("ok", "proximo", "vencido") and intervalo > 0 and restantes is not None
    desde_ultimo = max(intervalo - restantes, 0) if disponible else None
    fraccion = min(desde_ultimo / intervalo, 1.0) if disponible else 0.0
    if not disponible:
        proximo = SIN_DATO
    elif restantes >= 0:
        proximo = t("reportes.mant_proximo", idioma, n=restantes)
    else:
        proximo = t("reportes.mant_vencido_por", idioma, n=-restantes)
    color = C_MALO if estado == "vencido" else ("menuNaranja" if estado == "proximo" else "menuVerde")

    recs = None if registros is None else [r for r in _lista(registros) if isinstance(r, dict)]
    ultimo_fecha = _fecha(m.get("ultimo_fecha"))
    prev = next((r for r in (recs or []) if r.get("tipo") == "preventivo"), None)
    hay_preventivo = ultimo_fecha is not None and (m.get("ultimo_tipo") == "preventivo" or prev is not None)
    ultimo = None
    if hay_preventivo:
        ultimo = {"fecha": _dmy(ultimo_fecha, idioma),
                  "tecnico": _texto(prev.get("usuario")) if prev else ""}

    def en_rango(r):
        f = _fecha(r.get("fecha"))
        return f is not None and desde is not None and desde <= f <= (hasta or desde)

    correctivos = repuestos = None
    if recs is not None:
        enp = [r for r in recs if en_rango(r)]
        correctivos = sum(1 for r in enp if r.get("tipo") == "correctivo")
        repuestos = sum(1 for r in enp if "repuesto" in _texto(r.get("observaciones")).lower()
                        or "spare" in _texto(r.get("observaciones")).lower())
    return {"disponible": disponible, "intervalo_ciclos": intervalo, "desde_ultimo": desde_ultimo,
            "fraccion": fraccion, "color": color, "estado": estado if isinstance(estado, str) else "",
            "anillo_texto": f"{desde_ultimo} / {intervalo}" if disponible else SIN_DATO,
            "anillo_titulo": t("reportes.mant_anillo", idioma), "proximo": proximo,
            "ultimo_preventivo": ultimo,
            "ultimo_texto": (t("reportes.mant_ultimo", idioma, fecha=ultimo["fecha"],
                               tecnico=ultimo["tecnico"] or SIN_DATO) if ultimo
                             else t("reportes.mant_sin_preventivo", idioma)),
            "registros_disponibles": recs is not None, "correctivos": correctivos, "repuestos": repuestos,
            "correctivos_texto": SIN_DATO if correctivos is None else str(correctivos),
            "repuestos_texto": SIN_DATO if repuestos is None else str(repuestos)}


# ── entrada principal ────────────────────────────────────────────────────

def presentable(respuesta_dashboard, respuesta_calendario, idioma, t=_t_defecto) -> dict:
    """Todo el dashboard listo para QML. Entradas ausentes o mal formadas dan
    secciones vacías (nunca excepción). Mantenimiento y panel del día se arman
    aparte (`mantenimiento`, `panel_dia`): vienen de otras consultas."""
    r = respuesta_dashboard if isinstance(respuesta_dashboard, dict) else None
    return {"valido": r is not None,
            "encabezado": encabezado(r, idioma, t),
            "indicadores": indicadores(r, idioma, t),
            "dona": dona(r, idioma, t),
            "serie": serie(r, idioma, t),
            "programas": programas(r, idioma, t),
            "calendario": calendario(r, respuesta_calendario, idioma, t),
            "causas": [{"causa": c["causa"], "cantidad": _entero(c.get("cantidad"))}
                       for c in _lista(_dict(r).get("causas_fallo"))
                       if isinstance(c, dict) and isinstance(c.get("causa"), str)],
            "alarmas": alarmas(r, idioma, t),
            "operadores": operadores(r, idioma, t)}
