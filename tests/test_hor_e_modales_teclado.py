# tests/test_hor_e_modales_teclado.py
#
# Tanda horizontal (9-nov), grupo E: con el lienzo horizontal 1920x1200
# (Escala.horizontal true) el teclado en pantalla no pasa del 45 % del alto
# (TEC-D06) con las mismas teclas y tamaños, la rejilla queda centrada y todo
# dentro del panel; los modales y paneles caben en los 1200 de alto. En
# subproceso para tener un QGuiApplication propio.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, os
    from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml

    i18n.cargar(); i18n.fijar_idioma("es")
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()
    W, H = 1920, 1200
    QML = '''
    import QtQuick
    import Tema
    import "Componentes"
    Window {
        id: ventana
        width: %d; height: %d; visible: true
        Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(ventana.width, ventana.height) }
        Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }
        Item {
            id: lienzo; objectName: "lienzo"
            width: Escala.px(Escala.anchoDiseno); height: Escala.px(Escala.altoDiseno)
            PanelTeclado { id: tec; objectName: "tec" }
            ModalConfirmacion { objectName: "mc"; titulo: "T"; cuerpo: "Texto"; textoAccion: "Ok" }
            ModalOperador { objectName: "mo"; visible: false
                            operadores: [{id: 1, nombre: "Ana"}, {id: 2, nombre: "Carlos"}] }
            DialogoConfirmacion { objectName: "dc"; mensaje: "M"; textoConfirmar: "A"; textoCancelar: "B" }
            PanelEquipo { objectName: "pe"; titulo: "Equipo"; textoCerrar: "Cerrar"
                          filas: [{clave: "modelo", valor: "X", disponible: true},
                                  {clave: "serie", valor: "Y", disponible: true},
                                  {clave: "puertas", valor: "2", disponible: true}] }
            PanelNotificaciones { objectName: "pn"; titulo: "N"; textoCerrar: "Cerrar" }
        }
    }
    ''' % (W, H)
    ruta = f"{QML_DIR}/_hor_e_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(ruta))
    os.remove(ruta)
    w = engine.rootObjects()[0]
    w.setWidth(W); w.setHeight(H); w.show()
    QTest.qWait(200)
    lienzo = w.findChild(QObject, "lienzo")
    tec = w.findChild(QObject, "tec")

    def rect(o):
        r = o.mapRectToItem(lienzo, o.boundingRect())
        return [r.x(), r.y(), r.width(), r.height()]

    def visuales(item):
        for h in item.childItems():
            yield h
            yield from visuales(h)

    r = {"avisos": avisos}
    for tipo in ("alfa", "num"):
        if tipo == "alfa":
            QMetaObject.invokeMethod(tec, "abrirAlfanumerico", Q_ARG("QVariant", "Usuario"),
                Q_ARG("QVariant", ""), Q_ARG("QVariant", 30), Q_ARG("QVariant", False),
                Q_ARG("QVariant", None), Q_ARG("QVariant", None))
            nombre = "tecladoAlfanumerico"
        else:
            QMetaObject.invokeMethod(tec, "abrirNumerico", Q_ARG("QVariant", "Valor"),
                Q_ARG("QVariant", "°C"), Q_ARG("QVariant", 12), Q_ARG("QVariant", 0),
                Q_ARG("QVariant", 100), Q_ARG("QVariant", 1), Q_ARG("QVariant", None),
                Q_ARG("QVariant", None))
            nombre = "tecladoNumerico"
        QTest.qWait(700)
        teclado = w.findChild(QObject, nombre)
        teclas = [o for o in visuales(teclado) if o.metaObject().className().startswith("Tecla_QML")
                  and o.property("visible")]
        r[tipo] = {"panel": rect(tec), "teclado": rect(teclado),
                   "teclas": [rect(o) for o in teclas],
                   "anchoRejilla": teclado.property("anchoRejilla"),
                   "desplazamiento": teclado.property("desplazamientoRejilla")}
    QMetaObject.invokeMethod(tec, "cerrar")
    QTest.qWait(600)
    for n in ("mc", "dc", "pe", "pn"):
        o = w.findChild(QObject, n)
        o.setProperty("visible", True)
    mo = w.findChild(QObject, "mo"); mo.setProperty("visible", True)
    QTest.qWait(300)
    tarjetas = {}
    for n, interno in (("mc", "tarjetaModalConfirmacion"), ("mo", "panelModalOperador")):
        tarjetas[n] = rect(w.findChild(QObject, n).findChild(QObject, interno))
    for n in ("pe", "pn"):
        boton = w.findChild(QObject, n).findChild(QObject, "botonCerrarPanel")
        tarjetas[n] = rect(boton.parentItem())
    for n in ("dc",):
        boton = w.findChild(QObject, n).findChild(QObject, "botonConfirmarDialogo")
        tarjetas[n] = rect(boton.parentItem().parentItem())
    r["tarjetas"] = tarjetas
    r["columnasEquipo"] = bool(w.findChild(QObject, "pe").findChild(QObject, "columnasEquipo").property("visible"))
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


@pytest.mark.parametrize("tipo", ["alfa", "num"])
def test_teclado_horizontal_cabe_en_el_45_por_ciento(datos, tipo):
    x, y, w, h = datos[tipo]["panel"]
    assert h <= 1200 * 0.45 + 0.5
    assert abs(y + h - 1200) < 0.5 and w == 1920


@pytest.mark.parametrize("tipo", ["alfa", "num"])
def test_teclado_horizontal_teclas_dentro_del_panel_y_mismos_tamanos(datos, tipo):
    px, py, pw, ph = datos[tipo]["panel"]
    teclas = datos[tipo]["teclas"]
    assert teclas
    for x, y, w, h in teclas:
        assert y >= py - 0.5 and y + h <= py + ph + 0.5
        assert x >= -0.5 and x + w <= 1920.5
        assert h in (120, 2 * 120 + 14)      # TecladoProvisional.altoTeclaAlfanumerico (o CONFIRMAR doble)
    anchos = {w for _, _, w, _ in teclas}
    if tipo == "alfa":
        assert 96 in anchos and 206 in anchos      # Teclado.anchoTecla, BORRAR
    else:
        assert anchos == {206}


@pytest.mark.parametrize("tipo", ["alfa", "num"])
def test_teclado_horizontal_rejilla_centrada_y_encabezado_a_la_izquierda(datos, tipo):
    tx, ty, tw, th = datos[tipo]["teclado"]
    x_rejilla = tx + datos[tipo]["desplazamiento"]
    assert datos[tipo]["desplazamiento"] > 0
    assert abs(x_rejilla + datos[tipo]["anchoRejilla"] / 2 - 960) < 1
    assert tx >= 23.5


def test_modales_horizontales_caben_en_1200_de_alto(datos):
    for n, (x, y, w, h) in datos["tarjetas"].items():
        assert y >= 0 and y + h <= 1200, n
        assert x >= 0 and x + w <= 1920, n


def test_panel_equipo_en_dos_columnas(datos):
    assert datos["columnasEquipo"] is True


def test_sin_errores_de_referencia(datos):
    malos = [a for a in datos["avisos"] if "ReferenceError" in a or "TypeError" in a]
    assert malos == [], malos
