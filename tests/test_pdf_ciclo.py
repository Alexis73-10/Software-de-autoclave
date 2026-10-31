# tests/test_pdf_ciclo.py
#
# PDF de un ciclo con gráfica y ticket (ui_qml/exportacion/pdf_ciclo.py). En
# subproceso: QPdfWriter/QPainter necesitan un QGuiApplication propio.

import json
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtPdf import QPdfDocument
    from autoclave.ui_qml.app import _cargar_fuentes
    from autoclave.ui_qml.exportacion.pdf_ciclo import generar_pdf

    salida, n_lineas, con_grafica = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "si"
    app = QGuiApplication([])
    _cargar_fuentes()
    t = [i / 6 for i in range(241)]
    grafica = {"t_min": t,
               "temp_camara": [40 + 94 * min(1, x / 15) if x != 5 else None for x in t],
               "temp_ref": [38 + 95 * min(1, x / 16) for x in t],
               "pres_camara": [101 + 203 * min(1, x / 15) for x in t]} if con_grafica else \
              {"t_min": [], "temp_camara": [], "temp_ref": [], "pres_camara": []}
    fases = [{"clave": "vacio", "inicioMin": 0.0}, {"clave": "calentamiento", "inicioMin": 9.0},
             {"clave": "esterilizacion", "inicioMin": 15.0}, {"clave": "secado", "inicioMin": 22.0}]
    textos = {"fases": {"vacio": "Vacío", "calentamiento": "Calentamiento",
                        "esterilizacion": "Esterilización", "secado": "Secado"},
              "series": {"temp_camara": "Temp Cámara", "temp_ref": "Temp Ref", "pres_camara": "Presión"},
              "eje_tiempo": "Tiempo (min)", "eje_temp": "°C", "eje_pres": "kPa",
              "sin_grafica": "Gráfica no disponible", "ticket": "Registro del ciclo"}
    datos = {"empresa": "Especifika S.A.S.", "titulo": "Ciclo N.º 001248 · Instrumental 134",
             "campos": [("Inicio", "15/09/2026  08:00"), ("Fin", "15/09/2026  08:40"),
                        ("Resultado", "Completado")]}
    ticket = "\n".join(f"C 00:{i // 60:02d}:{i % 60:02d} 0120.0 0200.0" for i in range(n_lineas))
    generar_pdf(salida, datos, ticket, grafica, fases, textos)
    doc = QPdfDocument()
    doc.load(salida)
    imagen = doc.render(0, doc.pagePointSize(0).toSize() * 2)
    imagen.save(salida + ".png")
    print(json.dumps({"paginas": doc.pageCount()}))
""")


def _generar(tmp_path, n_lineas, con_grafica=True):
    salida = tmp_path / "ciclo.pdf"
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(salida), str(n_lineas),
                        "si" if con_grafica else "no"],
                       capture_output=True, text=True, timeout=60,
                       env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr
    return salida, json.loads(r.stdout.strip().splitlines()[-1])


def test_pdf_de_una_pagina_con_grafica(tmp_path):
    salida, info = _generar(tmp_path, 40)
    assert salida.read_bytes().startswith(b"%PDF")
    assert info["paginas"] == 1
    assert (tmp_path / "ciclo.pdf.png").stat().st_size > 0


def test_ticket_largo_sigue_en_mas_paginas(tmp_path):
    _, info = _generar(tmp_path, 900)
    assert info["paginas"] >= 2


def test_sin_grafica(tmp_path):
    salida, info = _generar(tmp_path, 10, con_grafica=False)
    assert info["paginas"] == 1 and salida.read_bytes().startswith(b"%PDF")
