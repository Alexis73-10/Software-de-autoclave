# tests/test_pdf_consolidado.py
#
# Reporte consolidado de un periodo (ui_qml/exportacion/pdf_consolidado.py):
# portada con el resumen y el índice (con la página de cada ciclo) y luego las
# páginas de cada ciclo con su gráfica y consignas. En subproceso: QPdfWriter
# necesita un QGuiApplication propio.

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
    from autoclave import i18n
    from autoclave.ui_qml.app import _cargar_fuentes
    from autoclave.ui_qml.domain.reporte_resumen import presentable
    from autoclave.ui_qml.exportacion.pdf_consolidado import generar_pdf_consolidado

    salida, n_ciclos, lineas_largo = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    app = QGuiApplication([])
    _cargar_fuentes()
    textos = i18n.catalogo("es")
    t = [i / 6 for i in range(241)]
    grafica = {"t_min": t, "temp_camara": [40 + 94 * min(1, x / 15) for x in t],
               "temp_ref": [38 + 95 * min(1, x / 16) for x in t],
               "pres_camara": [101 + 203 * min(1, x / 15) for x in t]}
    fases = [{"clave": "vacio", "inicioMin": 0.0}, {"clave": "esterilizacion", "inicioMin": 15.0},
             {"clave": "secado", "inicioMin": 22.0}]
    ciclos = []
    for i in range(n_ciclos):
        n = 40 if i != 1 else lineas_largo          # el segundo ciclo puede ocupar varias páginas
        ciclos.append({
            "datos": {"empresa": "E", "titulo": f"Ciclo N.º {i + 1:06d}", "campos": [("Inicio", "x")]},
            "ticket": "\n".join(f"C 00:00:{k % 60:02d} 0120.0 0200.0" for k in range(n)),
            "grafica": grafica, "fases": fases,
            "consigna": {"temp": 134.0, "pres": 304.0, "desde_min": 15.0, "hasta_min": 22.0},
            "indice": [f"{i + 1:06d}", "15/09/2026", "08:00", "02 · Instrumental 134", "Completado"],
        })
    portada = {"empresa": "E", "titulo": "Reporte consolidado", "periodo": "Del 01/09/2026 al 30/09/2026",
               "resumen": presentable({"totales": {"total": n_ciclos, "completados": n_ciclos}})}
    avances = []
    paginas = generar_pdf_consolidado(salida, portada, ciclos, textos, progreso=avances.append)
    doc = QPdfDocument()
    doc.load(salida)
    for p in (0, paginas[0] - 1 if paginas else 0):
        doc.render(p, doc.pagePointSize(p).toSize() * 2).save(f"{salida}.{p}.png")
    texto_portada = doc.getAllText(0).text()
    print(json.dumps({"paginas": doc.pageCount(), "inicios": paginas, "avances": avances,
                      "portada": texto_portada}))
""")


def _generar(tmp_path, n_ciclos, lineas_largo=40):
    salida = tmp_path / "consolidado.pdf"
    r = subprocess.run([sys.executable, "-c", _SCRIPT, str(salida), str(n_ciclos), str(lineas_largo)],
                       capture_output=True, text=True, encoding="utf-8", timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_portada_e_inicio_de_cada_ciclo(tmp_path):
    info = _generar(tmp_path, 3)
    # portada en la página 1; un ciclo corto por página
    assert info["inicios"] == [2, 3, 4] and info["paginas"] == 4
    assert "Reporte consolidado" in info["portada"] and "000003" in info["portada"]


def test_indice_con_la_pagina_real_de_un_ciclo_largo(tmp_path):
    info = _generar(tmp_path, 3, lineas_largo=1200)   # el segundo ocupa varias páginas
    inicios = info["inicios"]
    assert inicios[0] == 2 and inicios[1] == 3 and inicios[2] > 4
    assert info["paginas"] >= inicios[2]


def test_avance_por_ciclo(tmp_path):
    info = _generar(tmp_path, 2)
    assert info["avances"][-1] == 1.0 and info["avances"] == sorted(info["avances"])
