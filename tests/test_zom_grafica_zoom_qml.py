"""Tanda 34 (ZOM-02..ZOM-08): zoom de la gráfica del ciclo (GraficaCiclo.qml).

Ventana fija con datos nuevos, restablecimiento a los N ms (reloj de prueba:
restablecerZoomMs corto), reinicio de la cuenta con un toque, lupa que
restablece con transición, restablecimiento inmediato por unidades, por
cambio de ciclo y al ocultarse, cursor intacto con dos dedos, lupa visible
solo con zoom, rueda del mouse y vista sin zoom igual a la de antes.
Los toques son eventos táctiles reales (QTest.touchEvent) sobre la ventana.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_SCRIPT = textwrap.dedent(r"""
    import json, math, sys
    from PySide6.QtCore import QMetaObject, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    qml_dir, qml = sys.argv[1:3]
    i18n.cargar(); i18n.fijar_idioma("es")
    i18n_qml.instancia._consultar = lambda: None
    app = QGuiApplication([])
    avisos = []
    engine = QQmlEngine(); engine.addImportPath(qml_dir)
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode(), QUrl.fromLocalFile(qml_dir + "/prueba_zom.qml"))
    ventana = comp.createWithInitialProperties({}); assert ventana is not None, comp.errorString()
    ventana.show(); QTest.qWait(100)
    g = [o for o in ventana.findChildren(QQuickItem) if o.objectName() == "graficaPrueba"][0]
    lupa = [o for o in g.findChildren(QQuickItem) if o.objectName() == "lupaZoomGrafica"][0]
    dispositivo = QTest.createTouchDevice()

    def var(nombre):
        v = g.property(nombre)
        return v.toVariant() if hasattr(v, "toVariant") else v

    def datos(n, desfase=0.0):
        ts = [i * 0.5 + desfase for i in range(n)]
        return {"t_min": ts, "temp_camara": [20 + i * 0.3 for i in range(n)],
                "temp_ref": [18 + i * 0.3 for i in range(n)],
                "pres_camara": [90 + i * 0.7 for i in range(n)]}

    def reiniciar():
        g.setProperty("restablecerZoomMs", 600000)
        g.setProperty("seriesEntradas", None)
        g.setProperty("tiempoActualMin", 38.6)
        g.setProperty("datos", datos(78))
        g.setProperty("cursorMin", float("nan"))
        QTest.qWait(50)
        QMetaObject.invokeMethod(g, "restablecerAhora")
        QTest.qWait(30)

    def P(x, y):
        return QPoint(int(x), int(y))

    def gesto_dos_dedos(a0, b0, a1, b1, pasos=6, soltar=True):
        QTest.touchEvent(ventana, dispositivo).press(0, P(*a0), ventana).press(1, P(*b0), ventana).commit()
        QTest.qWait(20)
        for k in range(1, pasos + 1):
            f = k / pasos
            pa = (a0[0] + (a1[0] - a0[0]) * f, a0[1] + (a1[1] - a0[1]) * f)
            pb = (b0[0] + (b1[0] - b0[0]) * f, b0[1] + (b1[1] - b0[1]) * f)
            QTest.touchEvent(ventana, dispositivo).move(0, P(*pa), ventana).move(1, P(*pb), ventana).commit()
            QTest.qWait(20)
        if soltar:
            QTest.touchEvent(ventana, dispositivo).release(0, P(*a1), ventana).release(1, P(*b1), ventana).commit()
            QTest.qWait(20)

    def toque_un_dedo(x, y):
        QTest.touchEvent(ventana, dispositivo).press(0, P(x, y), ventana).commit(); QTest.qWait(20)
        QTest.touchEvent(ventana, dispositivo).release(0, P(x, y), ventana).commit(); QTest.qWait(20)

    r = {}
    g.setProperty("escala", 1.0); g.setProperty("width", 1129.0); g.setProperty("height", 794.0)
    g.setProperty("ocultarCursorMs", 600000)
    reiniciar()

    # vista sin zoom = la de antes
    r["sin_zoom"] = {"ventana": var("ventana"), "completa": var("vistaCompleta"),
                     "marcasX": var("marcasX"), "marcasIzq": var("marcasIzquierda"),
                     "ejeX": var("ejeX"), "lupa": lupa.isVisible(), "zoom": var("zoomActivo")}

    # gesto horizontal: amplía solo el tiempo; lupa visible
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    r["gesto_h"] = {"ventana": var("ventanaZoom"), "lupa": lupa.isVisible()}

    # ventana fija con datos nuevos y tiempo actual mayor
    antes = var("ventanaZoom")
    g.setProperty("tiempoActualMin", 60.0)
    g.setProperty("datos", datos(120))
    QTest.qWait(30)
    r["fija"] = {"antes": antes, "despues": var("ventanaZoom"), "completa": var("vistaCompleta")}

    # cambio de ciclo (datos que no continúan los anteriores): en el acto
    g.setProperty("datos", datos(120, desfase=0.1)); QTest.qWait(5)
    r["otro_ciclo"] = {"zoom": var("ventanaZoom"), "transicion": var("_desdeTransicion")}

    # unidades: en el acto
    reiniciar()
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    zoom_previo = var("zoomActivo")
    g.setProperty("seriesEntradas", [
        {"clave": "temp_camara", "entrada": "temp_camara", "eje": "izquierdo", "unidad": "°F"},
        {"clave": "pres_camara", "entrada": "pres_camara", "eje": "derecho", "unidad": "psi"}])
    QTest.qWait(5)
    r["unidades"] = {"previo": zoom_previo, "zoom": var("ventanaZoom"), "transicion": var("_desdeTransicion")}

    # sin datos: en el acto
    reiniciar()
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    zoom_previo = var("zoomActivo")
    g.setProperty("datos", {"t_min": [], "temp_camara": [], "temp_ref": [], "pres_camara": []})
    QTest.qWait(5)
    r["sin_datos"] = {"previo": zoom_previo, "zoom": var("ventanaZoom")}

    # oculta: en el acto
    reiniciar()
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    zoom_previo = var("zoomActivo")
    g.setProperty("visible", False); QTest.qWait(5)
    r["oculta"] = {"previo": zoom_previo, "zoom": var("ventanaZoom")}
    g.setProperty("visible", True); QTest.qWait(30)

    # restablecimiento a los N ms (reloj de prueba) con transición
    reiniciar()
    g.setProperty("restablecerZoomMs", 400)
    gesto_dos_dedos((464, 444), (664, 544), (364, 394), (764, 594))
    r["diagonal"] = var("ventanaZoom")
    QTest.qWait(250)
    r["antes_de_vencer"] = var("zoomActivo")
    QTest.qWait(250)   # vencido: transición en curso o terminada
    r["vencido"] = {"zoom": var("zoomActivo")}
    QTest.qWait(450)
    r["vencido"]["ventana"] = var("ventana"); r["vencido"]["completa"] = var("vistaCompleta")
    r["vencido"]["transicion"] = var("_desdeTransicion"); r["vencido"]["lupa"] = lupa.isVisible()

    # un toque de un dedo reinicia la cuenta
    reiniciar()
    g.setProperty("restablecerZoomMs", 400)
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    QTest.qWait(250)
    toque_un_dedo(564, 494)
    QTest.qWait(250)            # 500 ms desde el gesto, 250 desde el toque
    r["reinicio_cuenta"] = {"sigue": var("zoomActivo")}
    QTest.qWait(700)
    r["reinicio_cuenta"]["despues"] = var("zoomActivo")

    # lupa: restablece con la transición
    reiniciar()
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    p = lupa.mapToScene(QPointF(lupa.width() / 2, lupa.height() / 2))
    r["lupa_geom"] = [lupa.width(), lupa.height(), lupa.mapToItem(g, QPointF(0, 0)).x(),
                      lupa.mapToItem(g, QPointF(0, 0)).y(), g.property("yArriba")]
    toque_un_dedo(p.x(), p.y())
    r["lupa_toque"] = {"zoom": var("zoomActivo"), "en_transicion": var("_desdeTransicion") is not None}
    QTest.qWait(450)
    r["lupa_toque"]["ventana"] = var("ventana"); r["lupa_toque"]["completa"] = var("vistaCompleta")

    # un gesto nuevo durante la transición la interrumpe y parte de donde iba
    reiniciar()
    gesto_dos_dedos((464, 494), (664, 494), (364, 494), (764, 494))
    toque_un_dedo(p.x(), p.y())
    QTest.qWait(120)
    QTest.touchEvent(ventana, dispositivo).press(0, P(400, 494), ventana).press(1, P(600, 494), ventana).commit()
    QTest.qWait(30)
    r["interrumpe"] = {"zoom": var("zoomActivo"), "transicion": var("_desdeTransicion"),
                       "ventana": var("ventana"), "completa": var("vistaCompleta")}
    QTest.touchEvent(ventana, dispositivo).release(0, P(400, 494), ventana).release(1, P(600, 494), ventana).commit()
    QTest.qWait(30)

    # cursor: un dedo lo mueve; dos dedos no
    reiniciar()
    toque_un_dedo(93 + 0.5 * 942, 494)       # minuto 20 de 0..40
    c1 = var("cursorMin")
    gesto_dos_dedos((464, 494), (664, 494), (364, 520), (764, 470))
    c2 = var("cursorMin")
    # segundo dedo sobre un dedo que ya movía el cursor: el cursor queda quieto
    QTest.touchEvent(ventana, dispositivo).press(0, P(300, 494), ventana).commit(); QTest.qWait(20)
    c3 = var("cursorMin")
    QTest.touchEvent(ventana, dispositivo).stationary(0).press(1, P(700, 494), ventana).commit(); QTest.qWait(20)
    QTest.touchEvent(ventana, dispositivo).move(0, P(200, 494), ventana).move(1, P(900, 494), ventana).commit(); QTest.qWait(20)
    QTest.touchEvent(ventana, dispositivo).move(0, P(150, 494), ventana).release(1, P(900, 494), ventana).commit(); QTest.qWait(20)
    c4 = var("cursorMin")
    QTest.touchEvent(ventana, dispositivo).release(0, P(150, 494), ventana).commit(); QTest.qWait(20)
    r["cursor"] = [c1, c2, c3, c4]

    # rueda: zoom en X; Ctrl + rueda: zoom en Y
    reiniciar()
    def rueda(mods):
        pos = QPointF(564, 494)
        ev = QWheelEvent(pos, ventana.mapToGlobal(pos), QPoint(0, 0), QPoint(0, 120),
                         Qt.NoButton, mods, Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(ventana, ev); QTest.qWait(30)
    rueda(Qt.NoModifier)
    r["rueda_x"] = var("ventanaZoom")
    reiniciar()
    rueda(Qt.ControlModifier)
    r["rueda_y"] = var("ventanaZoom")

    # fijarVentana (arnés): 15-25 min, 110-135; marcas de la ventana
    reiniciar()
    d = datos(78); d["temp_camara"] = [40 + i * 1.17 for i in range(78)]   # hasta ≈ 130 °C
    g.setProperty("datos", d); QTest.qWait(30)
    from PySide6.QtCore import Q_ARG
    QMetaObject.invokeMethod(g, "fijarVentana", Q_ARG("QVariant", 15), Q_ARG("QVariant", 25),
                             Q_ARG("QVariant", 110), Q_ARG("QVariant", 135))
    QTest.qWait(30)
    r["fijar"] = {"ventana": var("ventanaZoom"), "marcasX": var("marcasX"),
                  "marcasIzq": var("marcasIzquierda"), "lupa": lupa.isVisible()}
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 1200; height: 900; visible: true
    color: Colores.fondoTarjeta
    GraficaCiclo { objectName: "graficaPrueba" }
}
"""


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env, timeout=180, cwd=RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def _igual(a, b, tol=1e-6):
    return all(abs(a[k] - b[k]) <= tol for k in b)


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_sin_zoom_vista_de_hoy_y_sin_lupa(r):
    s = r["sin_zoom"]
    assert s["ejeX"] == {"maximo": 40, "paso": 5}
    assert s["ventana"] == s["completa"]
    assert s["completa"]["t0"] == 0 and s["completa"]["t1"] == 40
    assert s["completa"]["yIzq0"] == 0 and s["completa"]["yDer0"] == 0
    assert s["marcasX"] == [0, 5, 10, 15, 20, 25, 30, 35, 40]
    assert len(s["marcasIzq"]) == 6 and s["marcasIzq"][0] == 0
    assert s["lupa"] is False and s["zoom"] is False


def test_gesto_horizontal_amplia_el_tiempo_y_muestra_la_lupa(r):
    v = r["gesto_h"]["ventana"]
    assert v is not None
    assert v["t1"] - v["t0"] == pytest.approx(20, abs=0.3)
    assert (v["yIzq0"], v["yIzq1"]) == pytest.approx((0, r["sin_zoom"]["completa"]["yIzq1"]))
    assert r["gesto_h"]["lupa"] is True


def test_gesto_diagonal_amplia_los_dos_ejes(r):
    v = r["diagonal"]
    c = r["sin_zoom"]["completa"]
    assert v["t1"] - v["t0"] == pytest.approx(20, abs=0.3)
    assert v["yIzq1"] - v["yIzq0"] == pytest.approx(c["yIzq1"] / 2, rel=0.03)
    assert v["yIzq0"] / c["yIzq1"] == pytest.approx(v["yDer0"] / c["yDer1"], abs=1e-6)


def test_ventana_fija_con_datos_nuevos(r):
    f = r["fija"]
    assert f["despues"] == f["antes"]
    assert f["completa"]["t1"] > 40          # la vista completa creció sin mover la ventana


def test_restablece_en_el_acto_por_otro_ciclo(r):
    assert r["otro_ciclo"] == {"zoom": None, "transicion": None}


def test_restablece_en_el_acto_por_unidades(r):
    assert r["unidades"]["previo"] is True
    assert r["unidades"]["zoom"] is None and r["unidades"]["transicion"] is None


def test_restablece_sin_datos_y_al_ocultarse(r):
    assert r["sin_datos"] == {"previo": True, "zoom": None}
    assert r["oculta"] == {"previo": True, "zoom": None}


def test_restablece_al_vencer_la_cuenta_con_transicion(r):
    assert r["antes_de_vencer"] is True
    v = r["vencido"]
    assert v["zoom"] is False
    assert _igual(v["ventana"], v["completa"])
    assert v["transicion"] is None and v["lupa"] is False


def test_un_toque_reinicia_la_cuenta(r):
    assert r["reinicio_cuenta"] == {"sigue": True, "despues": False}


def test_lupa_restablece_con_transicion(r):
    w, h, x, y, y_arriba = r["lupa_geom"]
    assert w >= 56 and h >= 56                       # zona táctil del mockup
    assert x + w <= 1059 and y >= y_arriba           # dentro de la cuadrícula
    assert r["lupa_toque"]["zoom"] is False and r["lupa_toque"]["en_transicion"] is True
    assert _igual(r["lupa_toque"]["ventana"], r["lupa_toque"]["completa"])


def test_cursor_intacto_con_dos_dedos(r):
    c1, c2, c3, c4 = r["cursor"]
    assert c1 == pytest.approx(20.0, abs=0.3)        # un dedo mueve el cursor
    assert c2 == c1                                  # un gesto de dos dedos no
    assert c3 != c1                                  # un dedo de nuevo lo mueve
    assert c4 == c3                                  # con el segundo dedo queda quieto


def test_rueda_zoom_x_y_ctrl_rueda_zoom_y(r):
    vx, vy = r["rueda_x"], r["rueda_y"]
    c = r["sin_zoom"]["completa"]
    assert vx["t1"] - vx["t0"] == pytest.approx(40 / 1.25)
    assert (vx["yIzq0"], vx["yIzq1"]) == pytest.approx((0, c["yIzq1"]))
    assert (vy["t0"], vy["t1"]) == pytest.approx((0, 40))
    assert vy["yIzq1"] - vy["yIzq0"] == pytest.approx(c["yIzq1"] / 1.25)


def test_fijar_ventana_y_marcas(r):
    f = r["fijar"]
    v = f["ventana"]
    assert (v["t0"], v["t1"], v["yIzq0"], v["yIzq1"]) == pytest.approx((15, 25, 110, 135))
    assert f["marcasX"] == pytest.approx([16, 18, 20, 22, 24])
    assert f["marcasIzq"] == pytest.approx([110, 115, 120, 125, 130, 135])
    assert f["lupa"] is True


def test_gesto_nuevo_interrumpe_la_transicion(r):
    i = r["interrumpe"]
    assert i["zoom"] is True and i["transicion"] is None
    ancho = i["ventana"]["t1"] - i["ventana"]["t0"]
    assert 20 < ancho < i["completa"]["t1"]            # a medio camino, sin saltar
