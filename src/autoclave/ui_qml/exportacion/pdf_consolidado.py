# ui_qml/exportacion/pdf_consolidado.py
#
# Reporte consolidado de un periodo (pestaña Consolidado de Reportes), en un solo
# PDF: portada con el resumen del periodo (pdf_resumen.dibujar_resumen) y el
# índice de ciclos con la página donde empieza cada uno, y luego las páginas de
# cada ciclo (pdf_ciclo.dibujar_ciclo: datos, gráfica con consignas y ticket).
#
# Las páginas de un ciclo dependen de lo largo de su ticket, así que se dibuja
# dos veces: la primera, en memoria, solo para saber en qué página empieza cada
# ciclo; la segunda escribe el archivo con esas páginas en el índice (el índice
# ocupa lo mismo en las dos, solo cambia el número).

from PySide6.QtCore import QBuffer, QIODevice

from autoclave.ui_qml.exportacion.pdf_ciclo import Documento, dibujar_ciclo
from autoclave.ui_qml.exportacion.pdf_resumen import dibujar_resumen, tabla
from autoclave.ui_qml.exportacion.textos import textos_ciclo
from autoclave.ui_qml.exportacion.unidades_pdf import textos_ejes

_PROPORCIONES_INDICE = [0.12, 0.15, 0.09, 0.28, 0.29, 0.07]


def _dibujar(destino, portada: dict, ciclos: list, textos: dict, paginas: list,
             avance) -> list[int]:
    """Dibuja el documento; devuelve la página donde empieza cada ciclo."""
    r = textos.get("reportes") or {}
    m = textos.get("menu") or {}
    t_ciclo = textos_ciclo(textos)
    inicios = []
    with Documento(destino, f"{portada.get('titulo', '')} · {portada.get('periodo', '')}") as doc:
        pg = dibujar_resumen(doc, portada, r)
        tabla(pg, r.get("indice", ""),
              [m.get("col_ciclo", ""), m.get("col_fecha", ""), m.get("col_hora", ""),
               m.get("col_programa", ""), m.get("col_resultado", ""), r.get("col_pagina", "")],
              _PROPORCIONES_INDICE,
              [c["indice"] + [str(paginas[i]) if paginas else ""] for i, c in enumerate(ciclos)],
              a_la_derecha={len(_PROPORCIONES_INDICE) - 1})
        for i, c in enumerate(ciclos):
            doc.nueva_pagina()
            inicios.append(doc.pagina)
            pres = c.get("presentacion")      # I4: ejes en las unidades del ciclo
            t = (textos_ejes(t_ciclo, pres.temperatura, pres.presion) if pres is not None
                 else t_ciclo)
            dibujar_ciclo(doc, c["datos"], c["ticket"], c["grafica"], c["fases"], t,
                          c.get("consigna"))
            avance(i + 1)
    return inicios


def generar_pdf_consolidado(ruta, portada: dict, ciclos: list, textos: dict, progreso=None) -> list[int]:
    """Escribe el consolidado en `ruta`; devuelve la página donde empieza cada ciclo.

    portada: {"empresa", "titulo", "periodo", "resumen"} (como pdf_resumen).
    ciclos: [{"datos", "ticket", "grafica", "fases", "consigna", "indice": [ciclo,
    fecha, hora, programa, resultado]}] en el orden del documento. textos: es.json
    completo. progreso(fracción 0-1): avance, para mostrarlo mientras se genera.
    """
    n = max(1, len(ciclos))
    avisar = progreso or (lambda f: None)

    memoria = QBuffer()
    memoria.open(QIODevice.WriteOnly)
    paginas = _dibujar(memoria, portada, ciclos, textos, [], lambda i: avisar(0.5 * i / n))
    memoria.close()
    inicios = _dibujar(ruta, portada, ciclos, textos, paginas, lambda i: avisar(0.5 + 0.5 * i / n))
    assert inicios == paginas, "el índice cambió de tamaño entre las dos pasadas"
    avisar(1.0)
    return inicios
