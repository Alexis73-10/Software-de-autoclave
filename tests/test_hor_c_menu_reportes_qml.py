# tests/test_hor_c_menu_reportes_qml.py
#
# Tanda horizontal (9-nov), grupo C: con el lienzo horizontal 1920x1200
# (Escala.horizontal true), las ventanas flotantes del Menú Principal caben en
# 1200 de alto, el detalle de un ciclo pone los datos a la izquierda y la
# gráfica a la derecha con la misma escala que en vertical (la letra no crece),
# y Reportes reparte sus secciones en dos columnas (indicadores a la izquierda,
# calendario a la derecha) con las tres columnas y las acciones debajo, a todo
# el ancho. En subproceso para tener un QGuiApplication propio. Offscreen.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, sys, tempfile
    from pathlib import Path
    from PySide6.QtCore import QObject, QUrl, QPointF
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml import historial_ejemplo as ejemplo
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    from autoclave.ui_qml.bridge.reporte_dashboard import ReporteDashboard
    from tests.helpers.reportes_ejemplo import ClienteReportes, HOY

    i18n.cargar(); i18n.fijar_idioma("es")
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()
    W, H = 1920, 1200

    def items(win):
        salida, pila = [], [win.contentItem()]
        while pila:
            it = pila.pop()
            salida.append(it)
            pila.extend(it.childItems())
        return salida

    def uno(win, nombre, solo_visible=False):
        for o in items(win):
            if o.objectName() == nombre and (not solo_visible or o.isVisible()):
                return o
        return None

    def rect(o, win):
        r = o.mapRectToItem(win.contentItem(), o.boundingRect())
        return [r.x(), r.y(), r.width(), r.height()]

    def cargar(archivo, props):
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties(props)
        engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/{archivo}"))
        win = engine.rootObjects()[0]
        win.setProperty("width", W); win.setProperty("height", H)
        win.show()
        QTest.qWait(500)
        return engine, win, avisos

    r = {}
    # ---------------- Menú Principal
    backend = ejemplo.BackendEjemplo()
    props = {"historial": CiclosHistorial(backend),
             "acciones": AccionesCiclos(backend, cargar_config=ejemplo.config_correo_ejemplo,
                                        enviar=ejemplo.enviar_ejemplo)}
    eng, win, avisos = cargar("PruebaMenuPrincipal.qml", props)
    menu = uno(win, "menuPrincipal")
    r["menu_escala"] = menu.property("escala")
    ventanas = {}
    for v, obj in (("ultimo_ciclo", "ventanaUltimoCiclo"), ("mantenimiento", "ventanaMantenimiento"),
                   ("ciclos_hoy", "ventanaCiclosHoy"), ("historial", "ventanaHistorial")):
        from PySide6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(menu, "abrirVentana", Q_ARG("QVariant", v))
        QTest.qWait(700)
        vent = uno(win, obj)
        tarjeta =[o for o in items(win) if o.objectName() == "tarjetaVentana" and o.parentItem() is vent]
        ventanas[v] = rect(tarjeta[0], win)
        if v == "ultimo_ciclo":
            g = uno(win, "graficaDetalleCiclo", solo_visible=True)
            d = uno(win, "detalleUltimoCiclo")
            r["grafica_ultimo"] = {"escala": g.property("escala"), "rect": rect(g, win),
                                   "detalle": rect(d, win)}
        if v == "historial":
            QTest.qWait(500)
            filas = [o for o in items(win) if o.objectName().startswith("resultado_") and o.isVisible()]
            c = filas[0].mapToScene(QPointF(filas[0].width() / 2, filas[0].height() / 2)).toPoint()
            from PySide6.QtCore import Qt
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, c)
            QTest.qWait(900)
            g = uno(win, "graficaDetalleCiclo", solo_visible=True)
            r["grafica_historial"] = {"escala": g.property("escala"), "rect": rect(g, win)}
            r["botones_historial"] = {n: rect(uno(win, n, True), win)
                                      for n in ("botonVolverHistorial", "botonEnviarCiclo", "botonImprimirCiclo")}
        vent.setProperty("visible", False)
        QTest.qWait(200)
    r["ventanas"] = ventanas
    r["avisos_menu"] = avisos
    win.close(); eng.deleteLater(); QTest.qWait(50)

    # ---------------- Reportes
    cli = ClienteReportes(Path(tempfile.mkdtemp())).__enter__()
    props = {"reporteDashboard": ReporteDashboard(cli, ejecutar=lambda t: t(), hoy=lambda: HOY),
             "historial": CiclosHistorial(cli, ejecutar=lambda t: t(), hoy=lambda: HOY),
             "acciones": AccionesCiclos(cli, cargar_config=ejemplo.config_correo_ejemplo,
                                        enviar=ejemplo.enviar_ejemplo, ejecutar=lambda t: t())}
    eng, win, avisos = cargar("PruebaReportes.qml", props)
    QTest.qWait(500)
    flick = uno(win, "contenidoReportes")
    contenido = flick.property("contentItem")
    def en_contenido(n):
        o = uno(win, n)
        p = o.mapToItem(contenido, QPointF(0, 0))
        return [p.x(), p.y(), o.width(), o.height()]
    r["reportes_escala"] = uno(win, "pantallaReportes").property("escala")
    r["flick"] = rect(flick, win)
    r["barra"] = rect(uno(win, "barraInferiorReportes"), win)
    r["secciones"] = {n: en_contenido(n) for n in (
        "seccionPeriodo", "seccionIndicadores", "seccionResultado", "seccionCiclosDia", "seccionProgramas",
        "seccionCalendario", "seccionCausas", "seccionMantenimiento", "seccionAlarmas",
        "seccionOperadores", "seccionAcciones")}
    r["avisos_reportes"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def datos():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": os.path.join(raiz, "src") + os.pathsep + raiz}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", env=env, cwd=raiz, timeout=300)
    for linea in p.stdout.splitlines():
        if linea.startswith("RESULTADO="):
            return json.loads(linea[len("RESULTADO="):])
    raise AssertionError(p.stdout[-2000:] + p.stderr[-3000:])


# escala de la pantalla en horizontal: la del lienzo vertical (1200 px / 1196 del mockup)
_ESCALA = 1200 / 1196


def test_escala_de_menu_y_reportes_es_la_del_lienzo_vertical(datos):
    assert datos["menu_escala"] == pytest.approx(_ESCALA)
    assert datos["reportes_escala"] == pytest.approx(_ESCALA)


def test_ventanas_flotantes_caben_en_1200_de_alto(datos):
    for v, (x, y, w, h) in datos["ventanas"].items():
        assert y >= 0 and y + h <= 1200, v
        assert x >= 0 and x + w <= 1920, v
    # Mantenimiento conserva el ancho vertical de la tarjeta (1128 px del mockup)
    assert datos["ventanas"]["mantenimiento"][2] == pytest.approx(1128 * _ESCALA, abs=1)


@pytest.mark.parametrize("clave", ["grafica_ultimo", "grafica_historial"])
def test_grafica_del_detalle_a_la_derecha_sin_crecer(datos, clave):
    g = datos[clave]
    # misma escala que en vertical (1032 de 1129 px del mockup), o menor si no cabe el alto
    assert g["escala"] <= _ESCALA * 1032 / 1129 + 1e-6
    assert g["escala"] >= _ESCALA * 1032 / 1129 * 0.95
    x, y, w, h = g["rect"]
    assert x > 700 and x + w <= 1920 and y + h <= 1200


def test_botones_del_ciclo_en_la_columna_de_datos(datos):
    gx = datos["grafica_historial"]["rect"][0]
    b = datos["botones_historial"]
    for n, (x, y, w, h) in b.items():
        assert x + w < gx, n
    assert b["botonEnviarCiclo"][1] > b["botonVolverHistorial"][1]


def test_reportes_en_dos_columnas_y_tres_columnas_a_todo_el_ancho(datos):
    s = datos["secciones"]
    izq, der = s["seccionIndicadores"], s["seccionCalendario"]
    assert izq[1] == pytest.approx(der[1])               # misma altura de arranque
    assert izq[0] + izq[2] < der[0]                       # lado a lado
    for n in ("seccionResultado", "seccionCiclosDia", "seccionProgramas"):
        assert s[n][0] == pytest.approx(izq[0]) and s[n][1] > izq[1], n
    assert s["seccionCausas"][0] == pytest.approx(der[0])
    fondo = max(s[n][1] + s[n][3] for n in ("seccionProgramas", "seccionCausas"))
    for n in ("seccionMantenimiento", "seccionAlarmas", "seccionOperadores"):
        assert s[n][1] > fondo, n
    ancho = s["seccionPeriodo"][2]
    assert s["seccionAcciones"][2] == pytest.approx(ancho)
    assert datos["flick"][0] + datos["flick"][2] <= 1920 - 50
    assert datos["barra"][2] == pytest.approx(datos["flick"][2])


def test_sin_errores_de_referencia(datos):
    for clave in ("avisos_menu", "avisos_reportes"):
        malos = [a for a in datos[clave] if "ReferenceError" in a or "TypeError" in a]
        assert malos == [], malos
