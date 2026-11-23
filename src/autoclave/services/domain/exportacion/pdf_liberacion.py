# services/domain/exportacion/pdf_liberacion.py
#
# Modo fábrica, Etapa 4 (D-04, §7 de planeacion_modo_fabrica.md, PA-03): los
# PDF del paquete de liberación, con el escritor puro de pdf_basico.py (el
# backend no tiene Qt; ver E4-D1 en pdf_basico.py).
#
# - informe_pdf(datos): informe de liberación (equipo, versión, fecha,
#   ingeniero, calibración por sensor, parámetros, programas de fábrica,
#   ciclos de prueba, contadores, archivos ausentes y espacio de firma).
# - ciclo_pdf(datos): un ciclo de prueba con su gráfica (temperaturas a la
#   izquierda, presión de cámara a la derecha, divisiones de fase), sus
#   alarmas y el ticket (format_ticket, el mismo texto de la reimpresión).
#
# Los textos van en español: el informe es un registro interno de Especifika
# (DECISIÓN SIN CONFIRMAR, E4-D2). Solo dibuja: los datos los arma
# core/runtime/paquete_liberacion.py.

import math

from autoclave.services.domain.exportacion.pdf_basico import DocumentoPdf, Flujo

_GRIS = (0.33, 0.33, 0.33)
_CUADRICULA = (0.83, 0.83, 0.83)
_DIVISOR_FASE = (0.6, 0.6, 0.6)
# colores de las series (los de GraficaCiclo.qml)
_SERIES = (("temp_camara", "izq", (0.396, 0.6, 0.988), "Temperatura cámara (°C)"),
           ("temp_ref", "izq", (0.592, 0.196, 0.855), "Temperatura referencia (°C)"),
           ("temp_2_camara", "izq", (0.91, 0.537, 0.047), "Temperatura cámara 2 (°C)"),
           ("pres_camara", "der", (0.0, 0.8, 0.69), "Presión cámara (kPa abs)"))


def _txt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".") if math.isfinite(v) else str(v)
    return str(v)


def _par(etiqueta: str, valor, ancho: int = 28) -> str:
    return f"{etiqueta:<{ancho}} {_txt(valor)}"


# ── informe de liberación ───────────────────────────────────────────────
def informe_pdf(datos: dict) -> bytes:
    """`datos`: equipo {serie, modelo, tipo_instalacion, serial_original,
    modelo_original}, version_sw, fecha, ingeniero {usuario, nombre},
    calibracion [..], parametros [..], programas [..], ciclos [..],
    contadores {..}, ausentes [..]."""
    equipo = datos.get("equipo") or {}
    doc = DocumentoPdf(titulo="Informe de liberación de fábrica",
                       pie=f"Informe de liberación · {equipo.get('serie', '')}")
    f = Flujo(doc)
    f.titulo("Informe de liberación de fábrica")
    f.linea("Especifika S.A.S. · Software de control de autoclave", 9)
    f.seccion("Equipo")
    automatizado = equipo.get("tipo_instalacion") == "automatizacion"
    if automatizado:
        f.linea(_par("Serie original", equipo.get("serial_original")))
        f.linea(_par("Modelo original", equipo.get("modelo_original")))
        f.linea(_par("Serial Especifika", equipo.get("serie")))
        f.linea(_par("Modelo Especifika", equipo.get("modelo")))
        f.linea(_par("Tipo de instalación", "automatización"))
    else:
        f.linea(_par("Serie", equipo.get("serie")))
        f.linea(_par("Modelo", equipo.get("modelo")))
        f.linea(_par("Tipo de instalación", "fabricación"))
    f.linea(_par("Versión del software", datos.get("version_sw")))
    f.linea(_par("Fecha de liberación", datos.get("fecha")))
    ing = datos.get("ingeniero") or {}
    nombre = ing.get("nombre") or ""
    f.linea(_par("Ingeniero que libera",
                 f"{nombre} ({ing.get('usuario', '')})" if nombre else ing.get("usuario")))

    f.seccion("Calibración final por sensor")
    calibracion = datos.get("calibracion") or []
    if not calibracion:
        f.linea("Sin datos de calibración.")
    else:
        f.linea(f"{'Tipo':<12} {'Sensor':<26} {'Puerto':>6} {'Ganancia':>12} {'Offset':>12}  Polinomio",
                negrita=True)
        for c in calibracion:
            poly = c.get("poly")
            f.linea(f"{_txt(c.get('tipo')):<12} {_txt(c.get('sensor')):<26} "
                    f"{_txt(c.get('puerto')):>6} {_txt(c.get('gain')):>12} "
                    f"{_txt(c.get('offset')):>12}  "
                    f"{', '.join(_txt(x) for x in poly) if poly else '—'}")

    f.seccion("Parámetros finales del equipo")
    parametros = datos.get("parametros") or []
    if not parametros:
        f.linea("Sin parámetros.")
    for p in parametros:
        unidad = p.get("unidad") or ""
        f.linea(f"{_txt(p.get('clave')):<44} {_txt(p.get('valor'))} {unidad}".rstrip())

    f.seccion("Programas de fábrica")
    programas = datos.get("programas") or []
    if not programas:
        f.linea("Sin programas.")
    for prog in programas:
        f.separacion(3)
        f.linea(f"Programa {_txt(prog.get('numero'))}: {_txt(prog.get('nombre'))} "
                f"(id {_txt(prog.get('id'))})", negrita=True)
        if prog.get("error"):
            f.linea(f"No se pudo leer: {prog['error']}", sangria=2)
            continue
        for seccion, valores in (prog.get("parametros") or {}).items():
            if isinstance(valores, dict):
                for clave, valor in valores.items():
                    f.linea(f"{seccion}.{clave} = {_txt(_valor_param(valor))}", sangria=2)
            else:
                f.linea(f"{seccion} = {_txt(valores)}", sangria=2)
    otros = datos.get("otros_programas") or []
    if otros:
        f.separacion(3)
        f.linea("Otros programas (fuera del rango de fábrica 1–10):", negrita=True)
        for prog in otros:
            f.linea(f"{_txt(prog.get('numero'))}: {_txt(prog.get('nombre'))} (id {_txt(prog.get('id'))})",
                    sangria=2)

    f.seccion("Ciclos de prueba")
    ciclos = datos.get("ciclos") or []
    if not ciclos:
        f.linea("No se registraron ciclos.")
    else:
        f.linea(f"{'N.º':>6}  {'Programa':<24} {'Inicio':<19} {'Resultado':<12} Fallo / alarmas",
                negrita=True)
        for c in ciclos:
            alarmas = ", ".join(c.get("alarmas") or []) or "—"
            fallo = c.get("motivo_fallo") or ""
            if c.get("codigo_fallo"):
                fallo = f"{c['codigo_fallo']} {fallo}".strip()
            f.linea(f"{_txt(c.get('numero')):>6}  {_txt(c.get('programa'))[:24]:<24} "
                    f"{_txt(c.get('inicio'))[:19]:<19} {_txt(c.get('resultado') or 'sin resultado'):<12} "
                    f"{fallo or '—'} | alarmas: {alarmas}")

    f.seccion("Contadores al cierre")
    for clave, valor in (datos.get("contadores") or {}).items():
        f.linea(_par(clave, valor, 36))

    ausentes = datos.get("ausentes") or []
    if ausentes:
        f.seccion("Archivos ausentes en el paquete")
        for a in ausentes:
            f.linea(f"{a.get('ruta')}: {a.get('motivo')}")

    # PA-03: espacio de firma del ingeniero que libera y de quien aprueba
    f.espacio(260)          # las dos firmas en la misma página
    f.seccion("Firmas")
    for rol in ("Ingeniero que libera", "Aprobó"):
        f.espacio(100)
        f.y += 18
        doc.texto(f.margen, f.y, rol, 10, "negrita")
        for etiqueta in ("Nombre", "Fecha", "Firma"):
            f.y += 24
            doc.texto(f.margen, f.y, f"{etiqueta}:", 9, "normal")
            doc.linea(f.margen + 50, f.y + 2, f.margen + 330, f.y + 2, 0.5)
        f.y += 10
    return doc.bytes()


def _valor_param(valor):
    """Los parámetros de los programas a veces son {"value": x, ...}."""
    if isinstance(valor, dict) and "value" in valor:
        return valor["value"]
    return valor


# ── PDF de un ciclo ─────────────────────────────────────────────────────
def _escala(minimo: float, maximo: float, divisiones: int = 5) -> tuple[float, float, float]:
    if not math.isfinite(minimo) or not math.isfinite(maximo):
        return 0.0, 1.0, 0.2
    if maximo - minimo < 1e-9:
        minimo, maximo = minimo - 1, maximo + 1
    bruto = (maximo - minimo) / divisiones
    potencia = 10 ** math.floor(math.log10(bruto))
    paso = next(m * potencia for m in (1, 2, 2.5, 5, 10) if m * potencia >= bruto)
    return math.floor(minimo / paso) * paso, math.ceil(maximo / paso) * paso, paso


def _numero_eje(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _grafica(doc: DocumentoPdf, x: float, y: float, ancho: float, alto: float,
             lecturas: list) -> None:
    doc.rectangulo(x, y, ancho, alto, 0.6, _GRIS)
    tiempos = [r.get("t_s") for r in lecturas if isinstance(r.get("t_s"), (int, float))]
    if not tiempos:
        doc.texto(x + ancho / 2 - 50, y + alto / 2, "Sin lecturas de gráfica", 9, "normal", _GRIS)
        return
    t0, t1 = min(tiempos), max(tiempos)
    if t1 - t0 < 1:
        t1 = t0 + 1

    def valores(eje):
        return [r.get(k) for r in lecturas for k, e, *_ in _SERIES
                if e == eje and isinstance(r.get(k), (int, float)) and math.isfinite(r.get(k))]

    escalas = {}
    for eje in ("izq", "der"):
        v = valores(eje)
        escalas[eje] = _escala(min(v), max(v)) if v else (0.0, 1.0, 0.2)

    def px(t):
        return x + (t - t0) / (t1 - t0) * ancho

    def py(v, eje):
        lo, hi, _ = escalas[eje]
        return y + alto - (v - lo) / (hi - lo) * alto

    lo, hi, paso = escalas["izq"]
    n = int(round((hi - lo) / paso))
    for i in range(n + 1):
        v = lo + i * paso
        yy = py(v, "izq")
        doc.linea(x, yy, x + ancho, yy, 0.3, _CUADRICULA)
        doc.texto(x - 30, yy + 3, _numero_eje(v), 7, "normal", _GRIS)
    lo_d, hi_d, paso_d = escalas["der"]
    n_d = int(round((hi_d - lo_d) / paso_d))
    for i in range(n_d + 1):
        v = lo_d + i * paso_d
        doc.texto(x + ancho + 4, py(v, "der") + 3, _numero_eje(v), 7, "normal", _GRIS)
    # eje de tiempo en minutos
    _, t_hi, t_paso = _escala(0, (t1 - t0) / 60.0, 6)
    m = 0.0
    while m <= t_hi + 1e-9:
        xx = px(t0 + m * 60)
        if xx <= x + ancho + 0.5:
            doc.linea(xx, y + alto, xx, y + alto + 3, 0.4, _GRIS)
            doc.texto(xx - 6, y + alto + 12, _numero_eje(m), 7, "normal", _GRIS)
        m += t_paso
    doc.texto(x + ancho / 2 - 15, y + alto + 23, "minutos", 7, "normal", _GRIS)
    # divisiones de fase
    fase_previa = None
    for r in lecturas:
        fase = r.get("fase")
        t = r.get("t_s")
        if fase != fase_previa and fase_previa is not None and isinstance(t, (int, float)):
            xx = px(t)
            doc.linea(xx, y, xx, y + alto, 0.4, _DIVISOR_FASE, discontinua=True)
            doc.texto(xx + 2, y + 8, str(fase)[:14], 6, "normal", _GRIS)
        fase_previa = fase
    # series
    for clave, eje, color, _ in _SERIES:
        puntos = []
        for r in lecturas:
            t, v = r.get("t_s"), r.get(clave)
            if isinstance(t, (int, float)) and isinstance(v, (int, float)) and math.isfinite(v):
                puntos.append((px(t), py(v, eje)))
            else:
                puntos.append(None)
        doc.polilinea(puntos, 0.9, color)
    # leyenda (solo las series con lecturas)
    lx = x
    for clave, _, color, rotulo in _SERIES:
        if not any(isinstance(r.get(clave), (int, float)) for r in lecturas):
            continue
        doc.linea(lx, y - 6, lx + 14, y - 6, 1.5, color)
        doc.texto(lx + 17, y - 3.5, rotulo, 7, "normal")
        lx += 30 + len(rotulo) * 3.6


def ciclo_pdf(datos: dict) -> bytes:
    """`datos`: ciclo (fila de `ciclos`), grafica [lecturas_grafica],
    alarmas [filas de alarmas_historial], ticket (texto) y equipo."""
    ciclo = datos.get("ciclo") or {}
    numero = ciclo.get("numero_ciclo")
    doc = DocumentoPdf(titulo=f"Ciclo {numero}", pie=f"Ciclo {numero} · paquete de liberación")
    f = Flujo(doc)
    f.titulo(f"Ciclo {_txt(numero)} · {_txt(ciclo.get('nombre_ciclo'))}")
    f.linea(_par("Programa", f"{_txt(ciclo.get('numero_programa'))} {_txt(ciclo.get('nombre_ciclo'))}"))
    f.linea(_par("Inicio", _txt(ciclo.get("fecha_inicio"))[:19]))
    f.linea(_par("Fin", _txt(ciclo.get("fecha_fin"))[:19]))
    f.linea(_par("Resultado", ciclo.get("resultado") or "sin resultado"))
    if ciclo.get("motivo_fallo") or ciclo.get("codigo_fallo"):
        f.linea(_par("Fallo", f"{ciclo.get('codigo_fallo') or ''} {ciclo.get('motivo_fallo') or ''}".strip()))
    f.linea(_par("Operador", ciclo.get("operador")))
    f.linea(_par("Serie / modelo", f"{_txt(ciclo.get('serie'))} / {_txt(ciclo.get('modelo'))}"))
    f.linea(_par("Versión del software", ciclo.get("version_sw")))
    if ciclo.get("f0_final") is not None:
        f.linea(_par("F0 final (min)", ciclo.get("f0_final")))
    f.separacion(24)
    alto = 260
    f.espacio(alto + 50)
    _grafica(doc, f.margen + 32, f.y, f.ancho_util - 64, alto, datos.get("grafica") or [])
    f.y += alto + 32
    f.seccion("Alarmas del ciclo")
    alarmas = datos.get("alarmas") or []
    if not alarmas:
        f.linea("Sin alarmas.")
    for a in alarmas:
        f.linea(f"{_txt(a.get('aparecida'))[:19]}  {_txt(a.get('codigo')):<10} "
                f"{_txt(a.get('nivel')):<8} {_txt(a.get('titulo'))}"
                + (f" (resuelta {_txt(a.get('resuelta'))[:19]})" if a.get("resuelta") else ""))
    f.seccion("Ticket")
    # sin los renglones vacíos del final (avance de papel de la impresora)
    ticket = (datos.get("ticket") or "").rstrip()
    for renglon in ticket.splitlines() or ["(sin ticket)"]:
        f.linea(renglon, 8)
    return doc.bytes()
