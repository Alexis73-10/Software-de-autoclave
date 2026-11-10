# tests/test_hor_c_textos_contraste.py
#
# Tanda horizontal (9-nov), grupo C, ronda 2: en el lienzo horizontal 1920x1200
# ningún texto visible del Menú Principal (y sus ventanas flotantes) ni de
# Reportes (arriba, al medio, abajo, día elegido, año, ciclo abierto, fallo) se
# sale de su caja, en español e inglés; y los pares de color que se corrigieron
# solo en horizontal cumplen WCAG en oscuro sin cambiar el claro. Offscreen, en
# subproceso.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

from tests.test_tema_oscuro import _colores, _contraste  # noqa: E402

_SCRIPT = textwrap.dedent(r"""
    import json, sys, tempfile
    from pathlib import Path
    from PySide6.QtCore import QObject, QUrl, QPointF, Qt, QMetaObject, Q_ARG, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
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

    idioma = sys.argv[1]
    i18n.cargar(); i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()
    W, H = 1920, 1200

    def items(win):
        salida, pila = [], [win.contentItem()]
        while pila:
            it = pila.pop()
            if not it.isVisible() or it.opacity() == 0:
                continue
            salida.append(it)
            pila.extend(it.childItems())
        return salida

    def uno(win, nombre):
        for o in items(win):
            if o.objectName() == nombre:
                return o
        return None

    AYUDA = {}
    def info(t):
        # los enums de Text no se convierten a Python: se leen en JS como enteros
        v = QMetaObject.invokeMethod(AYUDA["obj"], "info", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", t))
        return json.loads(v if isinstance(v, str) else v.toString())

    def desbordes(win, estado):
        malos = []
        for t in items(win):
            if t.metaObject().className() not in ("QQuickText",) and not t.metaObject().className().startswith("QQuickText"):
                continue
            texto = t.property("text") or ""
            if not texto.strip() or t.width() <= 0:
                continue
            elide, wrap, cw, ch = info(t)
            if elide != 3:      # Text.ElideNone (= 3)
                malos.append({"estado": estado, "texto": texto[:40], "tipo": "elide"})
                continue
            if cw > t.width() + 1:
                malos.append({"estado": estado, "texto": texto[:40], "tipo": "ancho",
                              "contenido": round(cw), "caja": round(t.width())})
            if wrap != 0 and ch > t.height() + 2:
                malos.append({"estado": estado, "texto": texto[:40], "tipo": "alto",
                              "contenido": round(ch), "caja": round(t.height())})
        return malos

    def cargar(archivo, props):
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties(props)
        engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/{archivo}"))
        win = engine.rootObjects()[0]
        win.setProperty("width", W); win.setProperty("height", H)
        win.show()
        QTest.qWait(500)
        comp = QQmlComponent(engine)
        comp.setData(b"import QtQuick; QtObject { function info(t) { return JSON.stringify([t.elide, t.wrapMode, t.contentWidth, t.contentHeight]) } }",
                     QUrl.fromLocalFile(QML_DIR + "/_hor_c_ayuda.qml"))
        AYUDA["obj"] = comp.create()
        AYUDA["comp"] = comp
        return engine, win

    def tocar(win, o):
        c = o.mapToScene(QPointF(o.width() / 2, o.height() / 2)).toPoint()
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, c)
        QTest.qWait(700)

    r = {"desbordes": [], "iconos": {}}
    # ---------------- Menú Principal y ventanas
    backend = ejemplo.BackendEjemplo()
    props = {"historial": CiclosHistorial(backend),
             "acciones": AccionesCiclos(backend, cargar_config=ejemplo.config_correo_ejemplo,
                                        enviar=ejemplo.enviar_ejemplo)}
    eng, win = cargar("PruebaMenuPrincipal.qml", props)
    menu = uno(win, "menuPrincipal")
    r["desbordes"] += desbordes(win, "menu")
    for v, obj in (("ultimo_ciclo", "ventanaUltimoCiclo"), ("mantenimiento", "ventanaMantenimiento"),
                   ("ciclos_hoy", "ventanaCiclosHoy"), ("historial", "ventanaHistorial")):
        QMetaObject.invokeMethod(menu, "abrirVentana", Q_ARG("QVariant", v))
        QTest.qWait(900)
        r["desbordes"] += desbordes(win, v)
        if v in ("ciclos_hoy", "historial"):
            filas = [o for o in items(win) if o.objectName().startswith("resultado_")]
            if filas:
                tocar(win, filas[0])
                r["desbordes"] += desbordes(win, v + "_ciclo")
        win.findChild(QObject, obj).setProperty("visible", False)
        QTest.qWait(200)
    win.close(); eng.deleteLater(); QTest.qWait(50)

    # ---------------- Reportes
    cli = ClienteReportes(Path(tempfile.mkdtemp())).__enter__()
    rd = ReporteDashboard(cli, ejecutar=lambda t: t(), hoy=lambda: HOY)
    props = {"reporteDashboard": rd,
             "historial": CiclosHistorial(cli, ejecutar=lambda t: t(), hoy=lambda: HOY),
             "acciones": AccionesCiclos(cli, cargar_config=ejemplo.config_correo_ejemplo,
                                        enviar=ejemplo.enviar_ejemplo, ejecutar=lambda t: t())}
    eng, win = cargar("PruebaReportes.qml", props)
    flick = uno(win, "contenidoReportes")
    for n in ("iconoInicioReportesHz", "iconoSalirReportesHz"):
        o = uno(win, n)
        r["iconos"][n] = o is not None
    def recorrer(estado):
        tope = max(0, flick.property("contentHeight") - flick.height())
        y = 0
        while True:
            flick.setProperty("contentY", min(y, tope)); QTest.qWait(150)
            r["desbordes"].extend(desbordes(win, f"{estado}@{int(y)}"))
            if y >= tope:
                break
            y += flick.height() - 80
        flick.setProperty("contentY", 0)
    recorrer("mes")
    rd.elegirDia("2026-10-08"); QTest.qWait(400)
    recorrer("dia")
    filas = [o for o in items(win) if o.objectName().startswith("intento_")]
    if filas:
        tocar(win, filas[0])
        r["desbordes"] += desbordes(win, "ciclo")
        QMetaObject.invokeMethod(uno(win, "pantallaReportes"), "cerrarCiclo"); QTest.qWait(300)
    causas = (rd.property("datos") or {}).get("causas") or []
    if causas:
        rd.abrirFallo(causas[0]["causa"]); QTest.qWait(400)
        r["desbordes"] += desbordes(win, "fallo")
        rd.cerrarFallo(); QTest.qWait(300)
    rd.cambiarPeriodo("anio"); QTest.qWait(500)
    recorrer("anio")
    print("RESULTADO=" + json.dumps(r))
""")


def _correr(idioma):
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": os.path.join(raiz, "src") + os.pathsep + raiz}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, idioma], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=raiz, timeout=400)
    for linea in p.stdout.splitlines():
        if linea.startswith("RESULTADO="):
            return json.loads(linea[len("RESULTADO="):])
    raise AssertionError(p.stdout[-2000:] + p.stderr[-3000:])


@pytest.fixture(scope="module", params=["es", "en"])
def datos(request):
    return _correr(request.param)


def test_ningun_texto_horizontal_se_sale_de_su_caja(datos):
    assert datos["desbordes"] == [], datos["desbordes"][:10]


def test_iconos_de_la_barra_de_reportes_pintados_en_horizontal(datos):
    assert all(datos["iconos"].values()), datos["iconos"]


# --------------------------- contraste (oscuro) ---------------------------
# (color corregido en horizontal, fondo, mínimo WCAG, color que se usaba antes)
_PARES = [
    ("iconoBarraMenu", "fondoTarjeta", 3.0, None),   # casa de Reportes (antes trazo #231F20 del SVG)
    ("textoNegro", "fondoTarjeta", 3.0, None),       # salir de Reportes (antes trazo #000 del SVG)
    ("iconoCampo", "fondoTarjeta", 3.0, "bordeCampo"),     # borde punteado / no ejecutado del calendario
    ("iconoCampo", "fondoTarjeta", 3.0, "bordeDivisor"),   # casillas de marcar de Historial
]


@pytest.mark.parametrize("color,fondo,minimo,antes", _PARES)
def test_pares_corregidos_cumplen_wcag_en_oscuro(color, fondo, minimo, antes):
    props = _colores()
    assert _contraste(props[color][1], props[fondo][1]) >= minimo
    if antes is not None:
        assert _contraste(props[antes][1], props[fondo][1]) < minimo   # el de antes no cumplía


def test_el_claro_de_los_colores_usados_queda_igual():
    props = _colores()
    assert props["iconoBarraMenu"][0] == "#FF231F20"    # trazo del SVG de la casa
    assert props["textoNegro"][0] == "#FF000000"        # trazo del SVG de salir
    assert props["iconoCampo"][0] == props["bordeCampo"][0]
