# tests/test_movimiento_ui_qml.py
#
# Movimiento de la interfaz (31-oct): crossfade de CargadorSeccion y elemento
# compartido de ElementoCompartido (VentanaFlotante), con las animaciones
# ACTIVAS (el arnés pone Movimiento.instantaneo = false; con la plataforma
# offscreen vale true por omisión y los demás tests ven los cambios al instante).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes

    app = QGuiApplication([])
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaMovimiento.qml"))
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(300)

    def obj(n):
        return w.findChild(QObject, n)

    r = {}
    A, B = obj("seccionA"), obj("seccionB")
    r["a_inicial"] = [A.property("active"), round(A.property("opacity"), 2)]
    r["b_inicial"] = [B.property("active"), round(B.property("opacity"), 2)]

    w.setProperty("primera", False)
    QTest.qWait(80)
    r["cruce"] = [A.property("active"), B.property("active"),
                  0 < A.property("opacity") < 1, 0 < B.property("opacity") < 1,
                  A.property("enabled"), B.property("enabled")]
    QTest.qWait(500)
    r["final"] = [A.property("active"), round(A.property("opacity"), 2),
                  B.property("active"), round(B.property("opacity"), 2)]

    tarjeta, ventana = obj("tarjetaPrueba"), obj("ventanaPrueba")
    comp = ventana.findChild(QObject, "elementoCompartidoVentana")
    centro = tarjeta.mapToScene(tarjeta.boundingRect().center()).toPoint()
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, centro)
    QTest.qWait(100)
    r["abriendo"] = [ventana.property("visible"), 0 < comp.property("progreso") < 1,
                     comp.property("origen") is not None]
    QTest.qWait(500)
    r["abierta"] = [ventana.property("visible"), round(comp.property("progreso"), 2)]
    ventana.metaObject().invokeMethod(ventana, "cerrar")
    QTest.qWait(100)
    r["cerrando"] = [ventana.property("visible"), 0 < comp.property("progreso") < 1]
    QTest.qWait(500)
    r["cerrada"] = [ventana.property("visible"), round(comp.property("progreso"), 2)]
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=90, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_seccion_seleccionada_se_carga_visible(r):
    assert r["a_inicial"] == [True, 1.0]
    assert r["b_inicial"] == [False, 0.0]


def test_crossfade_las_dos_conviven_y_la_saliente_no_recibe_toques(r):
    activa_a, activa_b, a_fade, b_fade, en_a, en_b = r["cruce"]
    assert activa_a and activa_b and a_fade and b_fade
    assert en_a is False and en_b is True


def test_crossfade_termina_descargando_la_saliente(r):
    assert r["final"] == [False, 0.0, True, 1.0]


def test_tarjeta_se_expande_a_la_ventana_y_vuelve(r):
    assert r["abriendo"] == [True, True, True]
    assert r["abierta"] == [True, 1.0]
    assert r["cerrando"] == [True, True]       # sigue visible mientras vuelve a la tarjeta
    assert r["cerrada"] == [False, 0.0]
