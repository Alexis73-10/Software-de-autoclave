# tests/test_u10a_textos_caben_qml.py
#
# U10a (tanda 10, D10-1.3 y D10-1.5): en Preciclo y Ciclo en curso, en es y en,
# y en las resoluciones del equipo, ningún texto visible se sale de su cuadro
# ni cruza un divisor, y cada etiqueta de la tarjeta de parámetros y sensores
# (TextoAjustable) cabe en su columna: completa si cabe, abreviada si no.
# Las 9 entradas posibles (ciclo.entrada_corta_*) se recorren en 3 pasos de 3.
#
# La revisión es genérica (tests/helpers/textos_caben_qml.py): U10b agrega aquí, o en
# su propia prueba, los casos del resto de las pantallas.

import pytest

pytest.importorskip("PySide6")

from tests.helpers.textos_caben_qml import RESOLUCIONES, revisar  # noqa: E402

PANTALLAS = ("PantallaPreciclo", "PantallaCicloEnCurso")
IDIOMAS = ("es", "en")

# Valores de longitud real (los más anchos que se ven en el equipo)
PUENTE = {
    "connected": True,
    "programa": "INSTRUMENTAL 134",
    "cicloActivo": "02",
    "tempEsterilizacion": "134.0",
    "tiempoEsterilizacion": "3.5",
    "tiempoSecado": "15",
    "machineState": "PREPARADO",
    "entradasMostradas": [],
    "seriesGrafica": [],
}


def _entrada(clave):
    pres = clave.startswith("pres_")
    return {"clave": clave, "tipo": "pres" if pres else "temp",
            "valor": "-100.0" if pres else "134.2", "unidad": "kPa" if pres else "°C", "enUso": True}


GRUPOS = [
    ["temp_camara", "temp_2_camara", "temp_referencia"],
    ["temp_drenaje", "temp_drenaje_camara", "pres_camara"],
    ["pres_chaqueta", "pres_empaque_1", "pres_empaque_2"],
]
PASOS = [{"puente": {"entradasMostradas": [_entrada(c) for c in g]}} for g in GRUPOS]


@pytest.fixture(scope="module", params=[(p, i, r) for p in PANTALLAS for i in IDIOMAS for r in RESOLUCIONES],
                ids=lambda c: f"{c[0]}-{c[1]}-{c[2][0]}")
def resultado(request):
    pantalla, idioma, (ancho, alto) = request.param
    return revisar(pantalla, idioma, ancho, alto, puente=PUENTE, pasos=PASOS)


def test_carga_sin_avisos(resultado):
    assert resultado["avisos"] == []


def test_ningun_texto_se_sale_de_su_cuadro(resultado):
    problemas = [p for paso in resultado["pasos"] for p in paso["problemas"]]
    assert problemas == []


def test_la_tarjeta_usa_el_componente_en_todas_sus_etiquetas(resultado):
    # 3 parámetros de ciclo + 3 entradas por paso
    for paso in resultado["pasos"]:
        assert len(paso["ajustables"]) == 6, paso["ajustables"]


def test_se_muestra_el_completo_si_cabe_y_el_abreviado_si_no(resultado):
    for paso in resultado["pasos"]:
        for a in paso["ajustables"]:
            cabe = a["anchoCompleto"] <= a["anchoDisponible"]
            assert a["mostrado"] == (a["completo"] if cabe or not a["abreviado"] else a["abreviado"]), a


def test_las_nueve_entradas_se_recorren(resultado):
    vistos = {a["completo"] for paso in resultado["pasos"] for a in paso["ajustables"]}
    assert len(vistos) == 3 + 9


# ── D10-1.1: el componente solo ────────────────────────────────────────────

_SCRIPT_COMPONENTE = r'''
import json, os, sys
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from autoclave import i18n
from autoclave.ui_qml import app as _app  # noqa: F401
from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
from autoclave.ui_qml.bridge import i18n_qml
i18n.cargar(); i18n.fijar_idioma("es")
i18n_qml.instancia._consultar = lambda: None
QML = """
import QtQuick
import "Componentes"
Window {
    width: 400; height: 200; visible: true
    TextoAjustable { objectName: "ancho"; textoCompleto: "Temperatura de cámara"; textoAbreviado: "Temp. cámara"; anchoDisponible: 400 }
    TextoAjustable { objectName: "angosto"; textoCompleto: "Temperatura de cámara"; textoAbreviado: "Temp. cámara"; anchoDisponible: 100 }
    TextoAjustable { objectName: "nada"; textoCompleto: "Temperatura de cámara"; textoAbreviado: "Temp. cámara"; anchoDisponible: 20 }
    TextoAjustable { objectName: "sinAbrev"; textoCompleto: "Temperatura de cámara"; anchoDisponible: 20 }
    TextoAjustable { objectName: "clave"; clave: "ciclo.temp_ester"; anchoDisponible: 90 }
    TextoAjustable { objectName: "claveSinAbrev"; clave: "ciclo.entrada_corta_pres_camara"; anchoDisponible: 5 }
}
"""
ruta = f"{QML_DIR}/_prueba_u10a_componente_{os.getpid()}.qml"
open(ruta, "w", encoding="utf-8").write(QML)
try:
    qapp = QGuiApplication([]); _cargar_fuentes()
    engine = QQmlApplicationEngine(); avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR); engine.load(QUrl.fromLocalFile(ruta))
finally:
    os.remove(ruta)
w = engine.rootObjects()[0]; QTest.qWait(100)
r = {n: {k: w.findChild(QObject, n).property(k) for k in ("text", "usaAbreviado", "desborda")}
     for n in ("ancho", "angosto", "nada", "sinAbrev", "clave", "claveSinAbrev")}
print("RESULTADO=" + json.dumps({"r": r, "avisos": avisos}, ensure_ascii=False))
'''


def test_componente_completo_si_cabe_abreviado_si_no_y_desborda_detectable():
    import json
    import os
    import subprocess
    import sys
    from tests.helpers.textos_caben_qml import RAIZ
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_COMPONENTE], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout + p.stderr
    d = json.loads(linea[len("RESULTADO="):])
    r = d["r"]
    assert d["avisos"] == []
    assert r["ancho"] == {"text": "Temperatura de cámara", "usaAbreviado": False, "desborda": False}
    assert r["angosto"] == {"text": "Temp. cámara", "usaAbreviado": True, "desborda": False}
    assert r["nada"] == {"text": "Temp. cámara", "usaAbreviado": True, "desborda": True}
    assert r["sinAbrev"] == {"text": "Temperatura de cámara", "usaAbreviado": False, "desborda": True}
    assert r["clave"] == {"text": "Temp. ester.", "usaAbreviado": True, "desborda": False}
    # clave sin abrev.<clave>: siempre el completo (y se detecta que no cabe)
    assert r["claveSinAbrev"] == {"text": "Presión", "usaAbreviado": False, "desborda": True}
