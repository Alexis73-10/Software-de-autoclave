# tests/test_pdf_resumen.py
#
# PDF del resumen de ciclos por periodo (ui_qml/exportacion/pdf_resumen.py). En
# subproceso: QPdfWriter/QPainter necesitan un QGuiApplication propio.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtPdf import QPdfDocument
    from autoclave.ui_qml.app import _cargar_fuentes, cargar_textos
    from autoclave.ui_qml.domain.reporte_resumen import presentable
    from autoclave.ui_qml.exportacion.pdf_resumen import generar_pdf_resumen

    salida, n_programas, con_ciclos = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "si"
    app = QGuiApplication([])
    _cargar_fuentes()
    programas = [{"programa_id": f"p{i}", "programa_nombre": f"Programa {i}", "programa_numero": i + 1,
                  "total": 4, "completados": 2, "fallos": 1, "cancelados": 1, "sin_cierre": 0}
                 for i in range(n_programas)]
    total = 4 * n_programas if con_ciclos else 0
    r = {"totales": {"total": total, "completados": total // 2, "fallos": total // 4,
                     "cancelados": total // 4, "sin_cierre": 0},
         "por_programa": programas if con_ciclos else [],
         "causas_fallo": [{"causa": "FALLO_ESTERILIZACION", "cantidad": total // 4}] if con_ciclos else []}
    datos = {"empresa": "Especifika S.A.S. · Autoclave M · Serie S", "titulo": "Resumen de ciclos",
             "periodo": "Del 01/09/2026 al 30/09/2026", "resumen": presentable(r)}
    generar_pdf_resumen(salida, datos, cargar_textos()["reportes"])
    doc = QPdfDocument()
    doc.load(salida)
    doc.render(0, doc.pagePointSize(0).toSize() * 2).save(salida + ".png")
    print(json.dumps({"paginas": doc.pageCount()}))
""")


def _generar(tmp_path, n_programas, con_ciclos=True):
    salida = tmp_path / "resumen.pdf"
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(salida), str(n_programas),
                        "si" if con_ciclos else "no"],
                       capture_output=True, text=True, timeout=60,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr
    return salida, json.loads(r.stdout.strip().splitlines()[-1])


def test_resumen_de_una_pagina(tmp_path):
    salida, info = _generar(tmp_path, 3)
    assert salida.read_bytes().startswith(b"%PDF") and info["paginas"] == 1


def test_muchos_programas_siguen_en_otra_pagina(tmp_path):
    _, info = _generar(tmp_path, 60)
    assert info["paginas"] >= 2


def test_periodo_sin_ciclos(tmp_path):
    salida, info = _generar(tmp_path, 0, con_ciclos=False)
    assert info["paginas"] == 1 and salida.read_bytes().startswith(b"%PDF")
