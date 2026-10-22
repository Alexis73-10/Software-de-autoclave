# tests/test_o3_entradas_mostradas_qml.py
#
# O3 (tanda 6): Preciclo y Ciclo en curso muestran las entradas mostradas del
# programa (UiBridge.entradasMostradas) y la gráfica dibuja esas series
# (UiBridge.seriesGrafica) con leyenda y unidad. Al cambiar de programa cambian;
# "—" sin lectura no rompe la pantalla. Guarda capturas 1200x1920 si se pide
# con O3_CAPTURAS=<carpeta>.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]

PROGRAMA_A = {
    "entradas": [
        {"clave": "temp_camara", "tipo": "temp", "valor": "121.0", "unidad": "°C", "enUso": True},
        {"clave": "pres_chaqueta", "tipo": "pres", "valor": "250.0", "unidad": "kPa", "enUso": True},
        {"clave": "temp_drenaje", "tipo": "temp", "valor": "—", "unidad": "°C", "enUso": True},
    ],
    "series": [
        {"clave": "temp_camara", "entrada": "temp_camara", "color": "#6599FC", "eje": "izquierdo",
         "unidad": "°C", "registrada": True},
        {"clave": "pres_chaqueta", "entrada": "pres_chaqueta", "color": "#9732DA", "eje": "derecho",
         "unidad": "kPa", "registrada": False},
        {"clave": "temp_drenaje", "entrada": "temp_drenaje", "color": "#00CCB0", "eje": "izquierdo",
         "unidad": "°C", "registrada": False},
    ],
}
PROGRAMA_B = {
    "entradas": [
        {"clave": "pres_camara", "tipo": "pres", "valor": "2.05", "unidad": "bar", "enUso": True},
        {"clave": "temp_referencia", "tipo": "temp", "valor": "—", "unidad": "°F", "enUso": False},
    ],
    "series": [
        {"clave": "pres_camara", "entrada": "pres_camara", "color": "#6599FC", "eje": "derecho",
         "unidad": "bar", "registrada": True},
        {"clave": "temp_ref", "entrada": "temp_referencia", "color": "#9732DA", "eje": "izquierdo",
         "unidad": "°F", "registrada": True},
    ],
}

_SCRIPT = textwrap.dedent(r"""
    import json, os, sys
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes

    PANTALLA = sys.argv[1]
    PASOS = json.loads(sys.argv[2])
    CAPTURAS = os.environ.get("O3_CAPTURAS", "")
    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        QtObject {
            id: puenteFalso; objectName: "puente"
            property bool connected: true
            property string programa: "INSTRUMENTAL 134"
            property string cicloActivo: "02"
            property string tempEsterilizacion: "134.0"
            property string tiempoEsterilizacion: "4"
            property string tiempoSecado: "15"
            property string machineState: "PREPARADO"
            property var entradasMostradas: []
            property var seriesGrafica: []
        }
        %s { objectName: "pantalla"; anchors.fill: parent; datosVigentes: true; puente: puenteFalso }
    }
    ''' % PANTALLA
    ruta = f"{QML_DIR}/_prueba_o3_entradas.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.load(QUrl := __import__("PySide6.QtCore", fromlist=["QUrl"]).QUrl.fromLocalFile(ruta))
    finally:
        os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    puente = w.findChild(QObject, "puente")
    pantalla = w.findChild(QObject, "pantalla")

    def textos():
        r = []
        def rec(it):
            for h in it.childItems():
                if not h.isVisible():
                    continue
                if h.inherits("QQuickText"):
                    r.append(h.property("text"))
                rec(h)
        rec(pantalla)
        return r

    pasos = []
    for i, paso in enumerate(PASOS):
        puente.setProperty("entradasMostradas", paso["entradas"])
        puente.setProperty("seriesGrafica", paso["series"])
        QTest.qWait(300)
        pasos.append(textos())
        if CAPTURAS and paso.get("captura"):
            w.grabWindow().save(os.path.join(CAPTURAS, paso["captura"]))
    print("RESULTADO=" + json.dumps({"avisos": avisos, "pasos": pasos}, ensure_ascii=False))
""")


def _correr(pantalla, pasos):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + str(_RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, pantalla,
                        json.dumps(pasos, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=_RAIZ,
                       timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout + p.stderr
    return json.loads(linea[len("RESULTADO="):])


PASOS = {
    "PantallaPreciclo": [dict(PROGRAMA_A, captura="O3_Preciclo_programa_A.png"),
                         dict(PROGRAMA_B, captura="O3_Preciclo_programa_B.png"),
                         {"entradas": [], "series": []}],
    "PantallaCicloEnCurso": [dict(PROGRAMA_A, captura="O3_CicloEnCurso_programa_A.png"),
                             dict(PROGRAMA_B, captura="O3_CicloEnCurso_programa_B.png"),
                             {"entradas": [], "series": []}],
}


@pytest.fixture(scope="module", params=list(PASOS))
def resultado(request):
    return request.param, _correr(request.param, PASOS[request.param])


def test_carga_sin_avisos(resultado):
    _, r = resultado
    assert r["avisos"] == []


def test_muestra_las_entradas_del_programa_con_su_unidad(resultado):
    _, r = resultado
    a = r["pasos"][0]
    for texto in ("Temp. cámara", "Pres. chaqueta", "Temp. drenaje", "121.0", "250.0", "kPa"):
        assert texto in a, texto
    assert "—" in a


def test_al_cambiar_de_programa_cambian(resultado):
    _, r = resultado
    b = r["pasos"][1]
    for texto in ("Presión", "Temp. referencia", "2.05", "bar", "°F"):
        assert texto in b, texto
    assert "Pres. chaqueta" not in b and "250.0" not in b
    assert "Temp. drenaje" not in " ".join(b)


def test_lista_vacia_no_rompe(resultado):
    _, r = resultado
    assert isinstance(r["pasos"][2], list)


def test_grafica_leyenda_y_unidad():
    _, r = None, _correr("PantallaCicloEnCurso", PASOS["PantallaCicloEnCurso"][:2])
    a, b = r["pasos"]
    assert "Pres. chaqueta (sin registro)" in a
    assert "Temp. drenaje (sin registro)" in a
    # unidad de los ejes = la de las series
    assert b.count("bar") >= 2 and b.count("°F") >= 2
