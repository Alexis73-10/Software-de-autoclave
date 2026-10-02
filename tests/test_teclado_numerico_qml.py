# tests/test_teclado_numerico_qml.py
#
# Carga real de la pantalla de prueba del teclado numérico
# (qml/Pruebas/PruebaTecladoNumerico.qml) a 1200x1920 (Escala.factor = 1):
# medidas de tecla y separación (TEC-D11), distribución del diseñador,
# comportamiento por toques simulados, presionado visible >= 90 ms (TEC-D04)
# y cero avisos del motor QML. En subproceso para tener un QGuiApplication
# propio (otras pruebas crean QCoreApplication).

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.controllers.teclado_numerico_controller import TecladoNumericoController
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos

    app = QGuiApplication([])
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"textosJson": cargar_textos()})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaTecladoNumerico.qml"))
    w = engine.rootObjects()[0]
    w.setWidth(1200); w.setHeight(1920); w.show()
    QTest.qWait(200)

    def visuales(item):
        for h in item.childItems():
            yield h
            yield from visuales(h)

    # caracteres por su texto; acciones por objectName (Borrar no tiene texto: ícono)
    teclas = {{"teclaCancelar": "Cancelar", "teclaBorrar": "Borrar", "teclaConfirmar": "Confirmar"}
              .get(o.objectName(), o.property("texto")): o
              for o in visuales(w.contentItem())
              if o.metaObject().className().startswith("Tecla_QML")}
    r_icono_borrar = teclas["Borrar"].property("icono").toString()
    ctrl = w.findChild(QObject, "tecladoNumerico").findChildren(TecladoNumericoController)[0]
    resultado = w.findChild(QObject, "resultado")

    def geo(o):
        r = o.mapRectToScene(o.boundingRect())
        return [round(r.x(), 1), round(r.y(), 1), round(r.width(), 1), round(r.height(), 1)]

    def tocar(nombre, esperar=20):
        o = teclas[nombre]
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(esperar)

    r = {"geo": {k: geo(o) for k, o in teclas.items()}}

    # presionado visible al menos 90 ms aunque el toque sea instantáneo
    tocar("7", esperar=0)
    r["presionada_al_soltar"] = teclas["7"].property("verPresionada")
    QTest.qWait(40)
    r["presionada_a_40ms"] = teclas["7"].property("verPresionada")
    QTest.qWait(120)
    r["presionada_a_160ms"] = teclas["7"].property("verPresionada")
    tocar("Borrar")

    for t in "134.5":
        tocar(t)
    r["texto"] = ctrl.property("texto")
    tocar("."); tocar("5")
    r["sin_segundo_punto_ni_decimal"] = ctrl.property("texto")
    tocar("-")
    r["signo"] = ctrl.property("texto")
    tocar("-")
    tocar("Confirmar", esperar=50)
    r["entregado"] = resultado.property("text")
    for t in "500":
        tocar(t)
    tocar("Confirmar")
    r["fuera_de_rango"] = ctrl.property("fueraDeRango")
    r["entregado_tras_500"] = resultado.property("text")
    tocar("Cancelar", esperar=50)
    r["tras_cancelar"] = resultado.property("text")
    r["texto_tras_cancelar"] = ctrl.property("texto")
    r["icono_borrar"] = r_icono_borrar
    r["texto_borrar"] = teclas["Borrar"].property("texto")
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=False))
""")


@pytest.fixture(scope="module")
def salida():
    r = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"},
                       timeout=90)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_medidas_y_separacion_a_escala_1(salida):
    g = salida["geo"]
    for c in "0123456789-.":
        assert g[c][2:] == [206.0, 120.0], c
    assert g["8"][0] - (g["7"][0] + 206) == 14     # separación horizontal
    assert g["4"][1] - (g["7"][1] + 120) == 14     # separación vertical
    assert g["Cancelar"][2:] == [206.0, 120.0]
    assert g["Borrar"][2:] == [206.0, 120.0]
    assert g["Confirmar"][2:] == [206.0, 2 * 120.0 + 14]


def test_distribucion_del_disenador(salida):
    g = salida["geo"]
    filas = ["789", "456", "123", "-0."]
    for i, fila in enumerate(filas):
        ys = {g[c][1] for c in fila}
        assert len(ys) == 1, fila                   # misma fila
        assert [g[c][0] for c in fila] == sorted(g[c][0] for c in fila)
    assert g["Cancelar"][1] == g["7"][1]            # celda sobre Borrar
    assert g["Borrar"][1] == g["4"][1]
    assert g["Confirmar"][1] == g["1"][1]           # dos filas: 1-2-3 y - 0 .
    assert g["Cancelar"][0] > g["9"][0]


def test_presionado_visible_al_menos_90_ms(salida):
    assert salida["presionada_al_soltar"] is True
    assert salida["presionada_a_40ms"] is True
    assert salida["presionada_a_160ms"] is False


def test_comportamiento_por_toques(salida):
    assert salida["texto"] == "134.5"
    assert salida["sin_segundo_punto_ni_decimal"] == "134.5"
    assert salida["signo"] == "-134.5"
    assert salida["entregado"] == "134.5"
    assert salida["fuera_de_rango"] is True
    assert salida["entregado_tras_500"] == "134.5"   # 500 no se entrega
    assert salida["tras_cancelar"].startswith("Cancelado")
    assert salida["texto_tras_cancelar"] == ""


def test_borrar_lleva_el_icono_universal(salida):
    assert salida["icono_borrar"].endswith("/iconos/color/borrar.svg")
    assert salida["texto_borrar"] == ""
