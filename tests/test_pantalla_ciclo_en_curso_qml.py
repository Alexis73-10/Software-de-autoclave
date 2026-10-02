# tests/test_pantalla_ciclo_en_curso_qml.py
#
# Pantalla de ciclo en curso, Fase 2 (planeacion_pantalla_ciclo_en_curso.md):
# textos en es.json, carga sin avisos QML con los datos de ejemplo y alto
# flexible (la gráfica absorbe el espacio en 9:16 sin mover lo de arriba).

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"
ES_JSON = RAIZ_QML.parent / "assets" / "textos" / "es.json"
ARCHIVOS = [RAIZ_QML / "Pantallas" / "PantallaCicloEnCurso.qml",
            RAIZ_QML / "Componentes" / "GraficaCiclo.qml"]


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_es_json_trae_las_claves_que_usa(archivo):
    textos = json.loads(ES_JSON.read_text(encoding="utf-8"))
    usadas = re.findall(r'tx\("(\w+)",\s*"(\w+)"\)', archivo.read_text(encoding="utf-8"))
    assert usadas
    faltantes = [f"{s}.{c}" for s, c in usadas if not isinstance(textos.get(s, {}).get(c), str)]
    assert faltantes == []


def test_es_json_nombra_las_seis_fases_de_la_ui():
    from autoclave.core.runtime.progreso_ciclo import FASES_UI
    textos = json.loads(ES_JSON.read_text(encoding="utf-8"))
    assert set(textos["fases"]) == set(FASES_UI)


def test_es_json_estado_en_ejecucion():
    textos = json.loads(ES_JSON.read_text(encoding="utf-8"))
    assert textos["estados"]["ejecutando"] == "En ejecución"


_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, es_json, ancho, alto = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    app = QGuiApplication([])
    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    engine.setInitialProperties({"textosJson": json.load(open(es_json, encoding="utf-8"))})
    engine.load(QUrl.fromLocalFile(qml_dir + "/Pruebas/PruebaCicloEnCurso.qml"))
    ventana = engine.rootObjects()[0]
    ventana.setWidth(ancho); ventana.setHeight(alto)
    QTest.qWait(300)

    def uno(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")][0]
    pantalla, grafica = uno("PantallaCicloEnCurso"), uno("GraficaCiclo")
    print(json.dumps({
        "avisos": avisos,
        "pantalla": [pantalla.width(), pantalla.height()],
        "grafica_y": grafica.y(), "grafica_alto": grafica.height(),
        "eje_x": grafica.property("ejeX").toVariant() if hasattr(grafica.property("ejeX"), "toVariant") else grafica.property("ejeX"),
    }))
""")


def _cargar(ancho, alto):
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), str(ES_JSON), str(ancho), str(alto)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_carga_sin_avisos_qml():
    salida = _cargar(600, 960)
    assert salida["avisos"] == []
    assert salida["eje_x"] == {"maximo": 40, "paso": 5}


def test_alto_flexible_en_9_16_lo_absorbe_la_grafica():
    base = _cargar(600, 960)      # 5:8, el lienzo de diseño
    alto = _cargar(540, 960)      # 9:16: mismo alto, menos ancho
    assert alto["avisos"] == []
    # el lienzo llena la ventana (sin franjas arriba y abajo)
    assert alto["pantalla"] == pytest.approx([540, 960])
    # la gráfica empieza en el mismo punto del mockup y crece en alto
    escala = 540 / 600
    assert alto["grafica_y"] == pytest.approx(base["grafica_y"] * escala, abs=1)
    assert alto["grafica_alto"] > base["grafica_alto"] * escala + 50
