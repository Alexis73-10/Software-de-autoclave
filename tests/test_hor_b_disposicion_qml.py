# tests/test_hor_b_disposicion_qml.py
#
# Tanda horizontal (9-nov), grupo B: Preciclo y Ciclo en curso en el lienzo
# horizontal 1920x1200. Comprueba la disposición en dos columnas (sin solapes
# entre columnas, todo dentro del lienzo), que la gráfica se adapta a su ancho
# (dw) con el zoom intacto (la lupa y la ventana absoluta), la pantalla
# completa a lo ancho y los controles de la barra inferior dentro de su celda;
# y que en vertical la gráfica sigue con dw = 0 (la geometría de siempre).
# Corre en un subproceso offscreen, como las demás pruebas QML.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]

_GUION = textwrap.dedent(r'''
    import json, os, sys
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject, QUrl, QPointF
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401 (los ítems se ven como QQuickItem)
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.domain import fin_de_ciclo

    i18n.cargar(); i18n.fijar_idioma("es")
    app = QGuiApplication([])
    ancho, alto = int(sys.argv[1]), int(sys.argv[2])

    FALLO = {"tipo": "fallo", "codigo": "CIC-12", "valores": {"tsat": 136.4, "dt": 2.3, "temp": 134.1},
             "motivo": "", "fase": "esterilizacion", "hora_fin": "2026-10-28T13:21:07",
             "cancelado_por": None, "observaciones": []}
    fin = fin_de_ciclo.armar(fin_de_ciclo.normalizar_terminacion(FALLO, "fallo"), [], "es")
    fases = [{"fase": f, "estado": "completada"} for f in ("precalentamiento", "vacio")] + \
            [{"fase": "calentamiento", "estado": "activa"}] + \
            [{"fase": f, "estado": "pendiente"} for f in ("esterilizacion", "descompresion", "secado")]

    def cargar(props):
        eng = QQmlApplicationEngine()
        eng.addImportPath(QML_DIR)
        eng.setInitialProperties(props)
        eng.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaFinDeCiclo.qml"))
        w = eng.rootObjects()[0]
        w.setProperty("width", ancho); w.setProperty("height", alto)
        QTest.qWait(250)
        return eng, w

    def items(w):
        # por el árbol visual: los delegados de un Repeater no son hijos QObject
        pila = [w.contentItem()]
        while pila:
            it = pila.pop()
            yield it
            pila.extend(it.childItems())

    def obj(w, n):
        r = [o for o in w.findChildren(QObject) if o.objectName() == n]
        r = r or [o for o in items(w) if o.objectName() == n]
        return r[0] if r else None

    def caja(o):
        p = o.mapToScene(QPointF(0, 0))
        return [p.x(), p.y(), o.width(), o.height()]

    salida = {}
    eng, w = cargar({"resultado": "", "fin": {}, "fases": fases})
    pc = obj(w, "pantallaCiclo")
    g = obj(w, "graficaCicloEnCurso")
    salida["ventana"] = [w.property("width"), w.property("height")]
    salida["pantalla"] = caja(pc)
    salida["escala"] = pc.property("_escalaHz")
    salida["hz"] = pc.property("hz")
    salida["grafica"] = caja(g)
    salida["dw"] = g.property("dw")
    salida["tarjeta"] = caja(obj(w, "tarjetaCicloEnCurso"))
    salida["barra"] = caja(obj(w, "barraInferiorCicloEnCurso"))
    salida["deslizador"] = caja(obj(w, "deslizadorCancelarCiclo"))
    salida["progresoFase"] = caja(obj(w, "textoProgresoFase"))
    salida["circuloSecado"] = caja(obj(w, "circuloFase_secado"))
    salida["equipo"] = caja(obj(w, "botonEquipoCiclo"))
    # zoom: ventana absoluta y lupa dentro de la tarjeta
    from PySide6.QtCore import QMetaObject, Q_ARG
    QMetaObject.invokeMethod(g, "fijarVentana", Q_ARG("QVariant", 15), Q_ARG("QVariant", 25),
                             Q_ARG("QVariant", 110), Q_ARG("QVariant", 135))
    QTest.qWait(50)
    salida["zoomActivo"] = g.property("zoomActivo")
    salida["lupa"] = caja(obj(w, "lupaZoomGrafica"))
    salida["lupaVisible"] = obj(w, "lupaZoomGrafica").property("visible")
    salida["toque"] = caja(obj(w, "toqueGraficaMultitactil"))
    # pantalla completa
    pc.setProperty("pantallaCompleta", True)
    QTest.qWait(100)
    completas = [o for o in items(w)
                 if o.metaObject().className().startswith("GraficaCiclo") and o.property("modoPantallaCompleta")]
    salida["completa"] = caja(completas[0]) if completas else None
    salida["completaDw"] = completas[0].property("dw") if completas else None
    w.close(); eng.deleteLater(); QTest.qWait(30)

    # fin de ciclo: panel en el lugar de la gráfica y píldora en la columna izquierda
    eng, w = cargar({"resultado": "fallo", "fin": fin, "fases": fases})
    salida["panelFin"] = caja(obj(w, "panelFinCiclo"))
    salida["confirmar"] = caja(obj(w, "botonCancelarCiclo"))
    obj(w, "pantallaCiclo").setProperty("vistaGrafica", True)
    QTest.qWait(100)
    salida["pildora"] = caja(obj(w, "pildoraFinCiclo"))
    salida["pildoraVisible"] = obj(w, "pildoraFinCiclo").property("visible")
    w.close(); eng.deleteLater(); QTest.qWait(30)

    # preciclo
    eng, w = cargar({"pantalla": "preciclo", "conActuador": True})
    salida["pre_tarjeta"] = caja(obj(w, "tarjetaPreciclo"))
    salida["pre_zona"] = caja([o for o in w.findChildren(QObject) if o.objectName() == "listaAlarmasPreciclo"][0])
    salida["pre_puerta"] = caja(obj(w, "botonPuertaPreciclo"))
    salida["pre_barra"] = caja(obj(w, "barraInferiorPreciclo"))
    salida["pre_avatar"] = caja(obj(w, "avatarPreciclo"))
    w.close(); eng.deleteLater(); QTest.qWait(30)
    print("SALIDA=" + json.dumps(salida))
''')


def _medir(ancho, alto):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _GUION, str(ancho), str(alto)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=300)
    for linea in p.stdout.splitlines():
        if linea.startswith("SALIDA="):
            return json.loads(linea[len("SALIDA="):])
    raise AssertionError(p.stderr[-3000:])


@pytest.fixture(scope="module")
def hz():
    return _medir(1920, 1200)


def _dentro(c, ancho=1920, alto=1200, tol=1.5):
    x, y, w, h = c
    return x >= -tol and y >= -tol and x + w <= ancho + tol and y + h <= alto + tol


def _derecha(c):
    return c[0] + c[2]


def test_horizontal_con_la_escala_del_vertical(hz):
    assert hz["hz"] is True
    # mismos px de diseño: 1200 px del lienzo vertical por cada 1196 del mockup
    assert hz["escala"] == pytest.approx(1200 / 1196, abs=1e-6)


def test_ciclo_dos_columnas_sin_solape(hz):
    g = hz["grafica"]
    assert _dentro(g)
    # la columna izquierda (fases, parámetros, relojes) termina antes de la gráfica
    assert _derecha(hz["circuloSecado"]) < g[0]
    assert _derecha(hz["progresoFase"]) <= g[0]
    # la gráfica queda dentro de la tarjeta principal, que va a lo ancho
    t = hz["tarjeta"]
    assert t[0] < 30 and _derecha(t) > 1880
    assert g[0] > t[0] and _derecha(g) < _derecha(t) and g[1] > t[1] and g[1] + g[3] < t[1] + t[3]
    # más alta que la del vertical (794 px del mockup)
    assert g[3] > 794 * hz["escala"]
    assert hz["dw"] < 0


def test_zoom_sigue_dentro_de_la_grafica(hz):
    g = hz["grafica"]
    assert hz["zoomActivo"] is True and hz["lupaVisible"] is True
    for c in (hz["lupa"], hz["toque"]):
        assert c[0] >= g[0] and _derecha(c) <= _derecha(g) + 0.5


def test_pantalla_completa_a_lo_ancho(hz):
    c = hz["completa"]
    assert c is not None and _dentro(c)
    assert c[2] > 1800 and hz["completaDw"] > 0


def test_barra_inferior_a_lo_ancho_y_controles_en_su_celda(hz):
    b = hz["barra"]
    assert _dentro(b) and b[2] > 1850
    # deslizador y CONFIRMAR centrados en la celda derecha (del separador de 800 al borde)
    x_celda = b[0] + b[2] * 800 / 1128
    for c in (hz["deslizador"], hz["confirmar"]):
        assert c[0] > x_celda and _derecha(c) < _derecha(b)
        assert (c[0] + c[2] / 2) == pytest.approx((x_celda + _derecha(b)) / 2, abs=1.5)
    assert _derecha(hz["equipo"]) <= x_celda


def test_fin_de_ciclo_en_el_lugar_de_la_grafica(hz):
    assert hz["panelFin"] == pytest.approx(hz["grafica"], abs=0.01)
    p = hz["pildora"]
    assert hz["pildoraVisible"] is True and _dentro(p)
    assert _derecha(p) < hz["grafica"][0]


def test_preciclo_alarmas_en_la_columna_derecha(hz):
    z, t, b = hz["pre_zona"], hz["pre_tarjeta"], hz["pre_barra"]
    assert _dentro(t) and _dentro(b) and _dentro(z)
    assert z[0] > 1180 and _derecha(z) < _derecha(t)
    puerta = hz["pre_puerta"]
    assert _derecha(puerta) < z[0]
    # los botones quedan sobre la barra, como en vertical
    assert puerta[1] + puerta[3] < b[1] and puerta[1] + puerta[3] > b[1] - 40
    assert b[2] > 1850 and _derecha(hz["pre_avatar"]) <= _derecha(b) + 0.5


def test_vertical_sin_cambios_en_la_grafica():
    v = _medir(1200, 1920)
    assert v["hz"] is False and v["dw"] == 0
    s = 1200 / 1196
    assert v["grafica"][0] == pytest.approx(33 * s, abs=0.01)
    assert v["grafica"][2] == pytest.approx(1129 * s, abs=0.01)
    assert v["completaDw"] == 0
