# ui_qml/exportacion/pdf_resumen.py
#
# PDF del resumen de ciclos de un periodo (pantalla Reportes) para enviarlo por
# correo: A4 con los totales por resultado (y una barra de proporciones), la
# tabla por programa y las causas de fallo. Mismo dibujo que pdf_ciclo.py
# (QPainter sobre QPdfWriter: necesita un QGuiApplication, no el hilo de la GUI).
# Colores de los resultados: los de la pantalla (Colores.qml).

from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from autoclave.ui_qml.exportacion.pdf_ciclo import _CUADRICULA, _DPI, _MARGEN_MM, _SECUNDARIO, _Lienzo, _encabezado, _mm

_COLOR = {"completados": QColor("#0D8C2C"), "fallos": QColor("#D00000"),
          "cancelados": QColor("#B35A00"), "sin_cierre": QColor("#8A8A8A")}


class _Pagina:
    """Lienzo con salto de página cuando lo siguiente no cabe."""

    def __init__(self, writer: QPdfWriter, lienzo: _Lienzo):
        self.writer = writer
        self.l = lienzo
        self.y = 0.0

    def reservar(self, alto: float) -> None:
        if self.y + alto > self.l.alto:
            self.writer.newPage()
            self.y = 0.0


def _totales(pg: _Pagina, resumen: dict, textos: dict) -> None:
    l = pg.l
    columnas = [("total", resumen["total"], "", None)] + [
        (t["clave"], t["cantidad"], t["porcentaje"], _COLOR.get(t["clave"])) for t in resumen["totales"]]
    ancho = l.ancho / len(columnas)
    pg.reservar(_mm(30))
    for i, (clave, cantidad, porcentaje, color) in enumerate(columnas):
        x = i * ancho
        fm = l.fuente(8)
        l.texto(x, pg.y + fm.ascent(), textos.get(clave, clave), _SECUNDARIO, ancho=ancho - _mm(2))
        fm2 = l.fuente(20, negrita=True)
        base = pg.y + fm.height() + _mm(1) + fm2.ascent()
        l.texto(x, base, cantidad, color or QColor("#1A1A1A"))
        if porcentaje:
            x_porcentaje = x + fm2.horizontalAdvance(cantidad) + _mm(2)
            l.fuente(9)
            l.texto(x_porcentaje, base, porcentaje, _SECUNDARIO)
    pg.y += _mm(17)
    # barra de proporciones por resultado
    alto = _mm(4)
    x = 0.0
    l.p.setPen(Qt.NoPen)
    for t in resumen["totales"]:
        w = l.ancho * t["fraccion"]
        if w > 0:
            l.p.setBrush(_COLOR.get(t["clave"], _CUADRICULA))
            l.p.drawRect(QRectF(x, pg.y, w, alto))
            x += w
    if x == 0:
        l.p.setBrush(_CUADRICULA)
        l.p.drawRect(QRectF(0, pg.y, l.ancho, alto))
    pg.y += alto + _mm(10)


def _tabla(pg: _Pagina, titulo: str, encabezados: list, proporciones: list, filas: list,
           colores: list | None = None) -> None:
    l = pg.l
    alto_fila = _mm(8)
    fm = l.fuente(11, negrita=True)
    pg.reservar(fm.height() + 3 * alto_fila)
    l.texto(0, pg.y + fm.ascent(), titulo)
    pg.y += fm.height() + _mm(2)

    def x_de(i):
        return sum(proporciones[:i]) * l.ancho

    def fila(valores, negrita, color_texto):
        pg.reservar(alto_fila)
        fm = l.fuente(9, negrita=negrita)
        base = pg.y + (alto_fila + fm.ascent() - fm.descent()) / 2
        for i, v in enumerate(valores):
            ancho = proporciones[i] * l.ancho - _mm(2)
            color = color_texto if color_texto is not None else (
                colores[i] if colores and colores[i] is not None else QColor("#1A1A1A"))
            if i == 0:
                l.texto(x_de(i), base, v, color, ancho=ancho)
            else:
                l.texto(x_de(i + 1) - _mm(2), base, v, color, Qt.AlignRight, ancho=ancho)
        pg.y += alto_fila
        l.p.setPen(QPen(_CUADRICULA, _mm(0.2)))
        l.p.drawLine(0, pg.y, l.ancho, pg.y)

    fila(encabezados, True, _SECUNDARIO)
    for valores in filas:
        fila(valores, False, None)
    pg.y += _mm(8)


def generar_pdf_resumen(ruta, datos: dict, textos: dict) -> None:
    """Escribe el PDF del resumen en `ruta`.

    datos: {"empresa", "titulo", "periodo", "resumen"} con resumen en la forma de
    ui_qml/domain/reporte_resumen.presentable. textos: sección "reportes" de es.json.
    """
    writer = QPdfWriter(str(Path(ruta)))
    writer.setResolution(_DPI)
    writer.setPageLayout(QPageLayout(
        QPageSize(QPageSize.A4), QPageLayout.Portrait,
        QMarginsF(_MARGEN_MM, _MARGEN_MM, _MARGEN_MM, _MARGEN_MM), QPageLayout.Millimeter))
    writer.setTitle(f"{datos.get('titulo', '')} · {datos.get('periodo', '')}")
    writer.setCreator("Especifika Autoclave")

    p = QPainter(writer)
    try:
        l = _Lienzo(p, writer.width(), writer.height())
        pg = _Pagina(writer, l)
        pg.y = _encabezado(l, {"empresa": datos.get("empresa", ""), "titulo": datos.get("titulo", "")})
        fm = l.fuente(12)
        pg.y += _mm(2)
        l.texto(0, pg.y + fm.ascent(), datos.get("periodo", ""), _SECUNDARIO)
        pg.y += fm.height() + _mm(8)

        resumen = datos["resumen"]
        _totales(pg, resumen, textos)
        if resumen["total"] == "0":
            fm = l.fuente(11)
            l.texto(0, pg.y + fm.ascent(), textos.get("sin_ciclos", ""), _SECUNDARIO)
            return

        claves = ("total", "completados", "fallos", "cancelados", "sin_cierre")
        _tabla(pg, textos.get("por_programa", ""),
               [textos.get("programa", "")] + [textos.get("col_" + c, c) for c in claves],
               [0.40, 0.12, 0.12, 0.12, 0.12, 0.12],
               [[f["programa"]] + [f[c] for c in claves] for f in resumen["por_programa"]],
               colores=[None, None] + [_COLOR[c] for c in claves[1:]])
        if resumen["causas"]:
            _tabla(pg, textos.get("causas_fallo", ""),
                   [textos.get("causa", ""), textos.get("cantidad", "")], [0.80, 0.20],
                   [[c["causa"], c["cantidad"]] for c in resumen["causas"]])
        else:
            fm = l.fuente(11, negrita=True)
            pg.reservar(fm.height() * 3)
            l.texto(0, pg.y + fm.ascent(), textos.get("causas_fallo", ""))
            pg.y += fm.height() + _mm(2)
            fm = l.fuente(10)
            l.texto(0, pg.y + fm.ascent(), textos.get("sin_fallos", ""), _SECUNDARIO)
    finally:
        p.end()
