# ui_qml/exportacion/pdf_ciclo.py
#
# PDF de un ciclo del historial para enviarlo por correo (Historial del Menú
# Principal): A4 con los datos del ciclo, su gráfica (temperatura de cámara y de
# referencia en °C a la izquierda, presión en kPa a la derecha, divisiones de
# fase y, si se dan, las consignas de esterilización en trazo discontinuo, D-14)
# y debajo el ticket, el mismo texto de la impresora térmica
# (ticket_formatter.format_ticket), en columnas de ancho fijo.
#
# Documento lleva el escritor, el pintor y la cuenta de páginas; dibujar_ciclo
# pinta las páginas de un ciclo en cualquier Documento, para el PDF de un ciclo
# (generar_pdf) y para el reporte consolidado (pdf_consolidado.py).
#
# Dibuja con QPainter sobre QPdfWriter: necesita un QGuiApplication (fuentes),
# pero no el hilo de la GUI, así que se puede generar en un hilo de trabajo.
# Colores de las series: los de GraficaCiclo.qml.

import math
from pathlib import Path

from PySide6.QtCore import QIODevice, QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetricsF, QPageLayout, QPageSize,
                           QPainter, QPainterPath, QPdfWriter, QPen)

_DPI = 150
_MARGEN_MM = 12
_ALTO_GRAFICA_MM = 95

# clave de la serie, eje ("izq" °C / "der" kPa), color (GraficaCiclo.qml)
_SERIES = (("temp_camara", "izq", "#6599FC"),
           ("temp_ref", "izq", "#9732DA"),
           ("pres_camara", "der", "#00CCB0"))
# consignas de esterilización: mismo color de la serie que acompañan, más oscuro
_CONSIGNA = {"temp": QColor("#2F5FC4"), "pres": QColor("#00806E")}
_TINTA = QColor("#1A1A1A")
_SECUNDARIO = QColor("#555555")
_CUADRICULA = QColor("#D4D4D4")
_DIVISOR_FASE = QColor("#BCBCBC")
_FUENTE = "Montserrat"
_MONO = "mono"   # la de ancho fijo del sistema (el ticket se alinea por columnas)


def _mm(v: float) -> float:
    return v * _DPI / 25.4


def _escala_limpia(minimo: float, maximo: float, divisiones: int = 5) -> tuple[float, float, float]:
    """(desde, hasta, paso) redondos que cubren [minimo, maximo]."""
    if maximo <= minimo:
        maximo = minimo + 1
    bruto = (maximo - minimo) / divisiones
    potencia = 10 ** math.floor(math.log10(bruto))
    paso = next(f * potencia for f in (1, 2, 2.5, 5, 10) if f * potencia >= bruto)
    desde = math.floor(minimo / paso) * paso
    hasta = math.ceil(maximo / paso) * paso
    return desde, hasta, paso


def _escala_con_divisiones(minimo: float, maximo: float, divisiones: int) -> tuple[float, float, float]:
    """Escala redonda con exactamente `divisiones` (las de la cuadrícula del otro eje)."""
    if maximo <= minimo:
        maximo = minimo + 1
    bruto = (maximo - minimo) / divisiones
    potencia = 10 ** math.floor(math.log10(bruto))
    for f in (1, 2, 2.5, 5, 10, 20, 25, 50, 100):
        paso = f * potencia
        desde = math.floor(minimo / paso) * paso
        if desde + divisiones * paso >= maximo:
            return desde, desde + divisiones * paso, paso
    return minimo, maximo, (maximo - minimo) / divisiones


def _texto_numero(v: float) -> str:
    return f"{v:.0f}" if float(v).is_integer() else f"{v:g}"


class _Lienzo:
    def __init__(self, painter: QPainter, ancho: float, alto: float):
        self.p = painter
        self.ancho = ancho
        self.alto = alto

    def fuente(self, tam: float, negrita=False, familia=_FUENTE) -> QFontMetricsF:
        f = QFontDatabase.systemFont(QFontDatabase.FixedFont) if familia == _MONO else QFont(familia)
        f.setPointSizeF(tam)
        f.setBold(negrita)
        self.p.setFont(f)
        return QFontMetricsF(f, self.p.device())

    def texto(self, x, y, s, color=_TINTA, alineacion=Qt.AlignLeft, ancho=None):
        """Texto con la línea base en y; alineado a la izquierda, centro o derecha de x."""
        self.p.setPen(color)
        fm = QFontMetricsF(self.p.font(), self.p.device())
        w = fm.horizontalAdvance(s)
        if ancho is not None and w > ancho:
            s = fm.elidedText(s, Qt.ElideRight, ancho)
            w = fm.horizontalAdvance(s)
        if alineacion == Qt.AlignHCenter:
            x -= w / 2
        elif alineacion == Qt.AlignRight:
            x -= w
        self.p.drawText(QPointF(x, y), s)


class Documento:
    """PDF A4 en una ruta o un QIODevice, con su pintor, su lienzo y la página
    en curso (1 = la primera). Usar con `with`."""

    def __init__(self, destino, titulo: str = ""):
        self.writer = QPdfWriter(destino if isinstance(destino, QIODevice) else str(Path(destino)))
        self.writer.setResolution(_DPI)
        self.writer.setPageLayout(QPageLayout(
            QPageSize(QPageSize.A4), QPageLayout.Portrait,
            QMarginsF(_MARGEN_MM, _MARGEN_MM, _MARGEN_MM, _MARGEN_MM), QPageLayout.Millimeter))
        self.writer.setTitle(titulo)
        self.writer.setCreator("Especifika Autoclave")
        self.pagina = 1
        self._p = None
        self.l = None

    def __enter__(self):
        self._p = QPainter(self.writer)
        self.l = _Lienzo(self._p, self.writer.width(), self.writer.height())
        return self

    def __exit__(self, *exc):
        self._p.end()
        return False

    def nueva_pagina(self) -> None:
        self.writer.newPage()
        self.pagina += 1


def _encabezado(l: _Lienzo, datos: dict) -> float:
    """Título y datos del ciclo; devuelve la y donde termina."""
    fm = l.fuente(8)
    y = fm.ascent()
    l.texto(0, y, datos.get("empresa", ""), _SECUNDARIO)
    fm = l.fuente(16, negrita=True)
    y += _mm(3) + fm.ascent()
    l.texto(0, y, datos.get("titulo", ""))
    columnas = datos.get("campos", [])   # [(rótulo, valor)]
    if not columnas:
        return y + fm.descent()
    y += fm.descent() + _mm(5)
    ancho_col = l.ancho / len(columnas)
    fm_r = l.fuente(8)
    for i, (rotulo, _) in enumerate(columnas):
        l.texto(i * ancho_col, y + fm_r.ascent(), rotulo, _SECUNDARIO, ancho=ancho_col - _mm(3))
    y += fm_r.height() + _mm(1)
    fm_v = l.fuente(11, negrita=True)
    for i, (_, valor) in enumerate(columnas):
        l.texto(i * ancho_col, y + fm_v.ascent(), valor, ancho=ancho_col - _mm(3))
    return y + fm_v.height()


def _grafica(l: _Lienzo, marco: QRectF, grafica: dict, fases: list, textos: dict,
             consigna: dict | None = None) -> None:
    p = l.p
    t = grafica.get("t_min") or []
    p.setPen(QPen(_CUADRICULA, _mm(0.3)))
    p.setBrush(Qt.NoBrush)   # el documento puede venir con otro relleno (portada del consolidado)
    p.drawRect(marco)
    if not t:
        l.fuente(11)
        l.texto(marco.center().x(), marco.center().y(), textos.get("sin_grafica", ""),
                _SECUNDARIO, Qt.AlignHCenter)
        return

    def valores(eje):
        return [v for clave, e, _ in _SERIES if e == eje for v in grafica.get(clave) or []
                if v is not None]
    izq, der = valores("izq"), valores("der")
    if consigna:   # que las consignas queden dentro de la escala
        izq.append(consigna["temp"])
        der.append(consigna["pres"])
    y_izq = _escala_limpia(min(izq), max(izq)) if izq else (0, 1, 0.2)
    n_div = round((y_izq[1] - y_izq[0]) / y_izq[2])
    y_der = _escala_con_divisiones(min(der), max(der), n_div) if der else (0, 1, 1 / n_div)
    x_esc = _escala_limpia(0, max(t[-1], 1), 8)
    x_esc = (0, x_esc[1], x_esc[2])

    fm = l.fuente(7)
    # arriba, la franja con los nombres de fase y las unidades de cada eje
    area = QRectF(marco.left() + _mm(14), marco.top() + _mm(11),
                  marco.width() - _mm(28), marco.height() - _mm(11) - _mm(12))

    def px(v):
        return area.left() + (v - x_esc[0]) / (x_esc[1] - x_esc[0]) * area.width()

    def py(v, esc):
        return area.bottom() - (v - esc[0]) / (esc[1] - esc[0]) * area.height()

    # cuadrícula horizontal con las marcas de ambos ejes (mismas divisiones)
    for i in range(n_div + 1):
        v = y_izq[0] + i * y_izq[2]
        y = py(v, y_izq)
        p.setPen(QPen(_CUADRICULA, _mm(0.2)))
        p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        l.texto(area.left() - _mm(1.5), y + fm.ascent() / 2 - _mm(0.3), _texto_numero(v),
                _SECUNDARIO, Qt.AlignRight)
        l.texto(area.right() + _mm(1.5), y + fm.ascent() / 2 - _mm(0.3),
                _texto_numero(y_der[0] + i * y_der[2]), _SECUNDARIO)
    # marcas del tiempo (min)
    v = x_esc[0]
    while v <= x_esc[1] + 1e-9:
        x = px(v)
        p.setPen(QPen(_CUADRICULA, _mm(0.2)))
        p.drawLine(QPointF(x, area.bottom()), QPointF(x, area.bottom() + _mm(1)))
        l.texto(x, area.bottom() + _mm(1.5) + fm.ascent(), _texto_numero(v), _SECUNDARIO,
                Qt.AlignHCenter)
        v += x_esc[2]
    l.texto(area.center().x(), marco.bottom() - _mm(2), textos.get("eje_tiempo", ""),
            _SECUNDARIO, Qt.AlignHCenter)
    l.texto(marco.left() + _mm(2), area.top() - _mm(4), textos.get("eje_temp", ""), _SECUNDARIO)
    l.texto(marco.right() - _mm(2), area.top() - _mm(4), textos.get("eje_pres", ""),
            _SECUNDARIO, Qt.AlignRight)

    # divisiones de fase con su nombre arriba
    inicios = [f for f in fases if isinstance(f, dict)]
    for i, f in enumerate(inicios):
        x = px(f.get("inicioMin", 0))
        fin = px(inicios[i + 1]["inicioMin"]) if i + 1 < len(inicios) else area.right()
        if i > 0:
            p.setPen(QPen(_DIVISOR_FASE, _mm(0.3), Qt.DashLine))
            p.drawLine(QPointF(x, area.top() - _mm(7)), QPointF(x, area.bottom()))
        nombre = textos.get("fases", {}).get(f.get("clave"), "")
        l.texto((x + fin) / 2, area.top() - _mm(4), nombre, _SECUNDARIO,
                Qt.AlignHCenter, ancho=max(0.0, fin - x - _mm(1)))

    # series (un valor ausente corta la línea)
    p.save()
    p.setClipRect(area.adjusted(0, -_mm(1), 0, _mm(1)))
    for clave, eje, color in _SERIES:
        esc = y_izq if eje == "izq" else y_der
        camino, abierto = QPainterPath(), False
        for tm, v in zip(t, grafica.get(clave) or []):
            if v is None:
                abierto = False
                continue
            punto = QPointF(px(tm), py(v, esc))
            if abierto:
                camino.lineTo(punto)
            else:
                camino.moveTo(punto)
                abierto = True
        p.setPen(QPen(QColor(color), _mm(0.45)))
        p.setBrush(Qt.NoBrush)
        p.drawPath(camino)
    # consignas: solo en el tramo de esterilización
    if consigna:
        x0, x1 = px(consigna["desde_min"]), px(consigna["hasta_min"])
        for clave, esc in (("temp", y_izq), ("pres", y_der)):
            y = py(consigna[clave], esc)
            p.setPen(QPen(_CONSIGNA[clave], _mm(0.5), Qt.DashLine))
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
    p.restore()


def _leyenda(l: _Lienzo, x: float, y: float, textos: dict, con_consigna: bool) -> None:
    fm = l.fuente(8)
    entradas = [(textos.get("series", {}).get(c, c), QColor(color), Qt.SolidLine)
                for c, _, color in _SERIES]
    if con_consigna:
        entradas += [(textos.get("consignas", {}).get(c, c), _CONSIGNA[c], Qt.DashLine)
                     for c in ("temp", "pres")]
    for nombre, color, estilo in entradas:
        l.p.setPen(QPen(color, _mm(0.8), estilo))
        l.p.drawLine(QPointF(x, y - fm.ascent() / 3), QPointF(x + _mm(6), y - fm.ascent() / 3))
        l.texto(x + _mm(8), y, nombre)
        x += _mm(8) + fm.horizontalAdvance(nombre) + _mm(6)


def dibujar_ciclo(doc: Documento, datos: dict, ticket: str, grafica: dict, fases: list,
                  textos: dict, consigna: dict | None = None) -> None:
    """Pinta las páginas de un ciclo desde el inicio de la página en curso.

    datos: {"empresa", "titulo", "campos": [(rótulo, valor)]} ya formateados.
    ticket: texto del ticket (format_ticket). grafica: {t_min, temp_camara,
    temp_ref, pres_camara} (AcumuladorGrafica.datos); fases: inicios_de_fase.
    consigna: {"temp" °C, "pres" kPa, "desde_min", "hasta_min"} o None
    (domain/consignas.py). textos: {"fases": {clave: nombre}, "series": {clave:
    nombre}, "consignas": {"temp", "pres"}, "eje_tiempo", "eje_temp",
    "eje_pres", "sin_grafica", "ticket"}.
    """
    l = doc.l
    y = _encabezado(l, datos) + _mm(6)
    marco = QRectF(0, y, l.ancho, _mm(_ALTO_GRAFICA_MM))
    _grafica(l, marco, grafica, fases, textos, consigna)
    y = marco.bottom() + _mm(6)
    _leyenda(l, 0, y, textos, consigna is not None and bool(grafica.get("t_min")))
    y += _mm(10)

    fm = l.fuente(10, negrita=True)
    l.texto(0, y + fm.ascent(), textos.get("ticket", ""))
    y += fm.height() + _mm(3)

    # ticket en columnas de ancho fijo, de arriba abajo y luego a la derecha
    fm = l.fuente(8, familia=_MONO)
    lineas = ticket.rstrip("\n").split("\n")
    ancho_linea = max((fm.horizontalAdvance(s) for s in lineas), default=0)
    separacion = _mm(8)
    n_col = max(1, int((l.ancho + separacion) // (ancho_linea + separacion)))
    alto_linea = fm.lineSpacing()
    x_col, col, y_ini = 0.0, 0, y
    for s in lineas:
        if y + alto_linea > l.alto:
            col += 1
            if col >= n_col:
                doc.nueva_pagina()
                l.fuente(8, familia=_MONO)
                col, y_ini = 0, 0.0
            x_col = col * (ancho_linea + separacion)
            y = y_ini
        l.texto(x_col, y + fm.ascent(), s)
        y += alto_linea


def generar_pdf(ruta, datos: dict, ticket: str, grafica: dict, fases: list, textos: dict,
                consigna: dict | None = None) -> None:
    """Escribe el PDF de un ciclo en `ruta` (argumentos: dibujar_ciclo)."""
    with Documento(ruta, datos.get("titulo", "")) as doc:
        dibujar_ciclo(doc, datos, ticket, grafica, fases, textos, consigna)
