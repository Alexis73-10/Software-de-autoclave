# tests/test_menu_principal_componentes_qml.py
#
# Carga real de la galería de componentes del Menú Principal
# (qml/Pruebas/GaleriaMenuPrincipal.qml, Fase 1 de
# planeacion_menu_principal_ui_qml.md) a 1200x1920: medidas en px del mockup
# escaladas con m(), estados normal / presionado / deshabilitado / valor largo,
# toques simulados y cero avisos del motor QML. En subproceso para tener un
# QGuiApplication propio. Offscreen: MultiEffect (IconoColor) no se dibuja, así
# que aquí solo se comprueba geometría y comportamiento, no color.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from xml.etree import ElementTree

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]
_ICONOS = _RAIZ / "src" / "autoclave" / "ui_qml" / "assets" / "iconos"

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QSignalSpy, QTest
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos

    app = QGuiApplication([])
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"textosJson": cargar_textos()})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/GaleriaMenuPrincipal.qml"))
    w = engine.rootObjects()[0]
    w.setWidth(1200); w.setHeight(1920); w.show()
    QTest.qWait(300)

    def obj(nombre):
        return w.findChild(QObject, nombre)

    def geo(o):
        r = o.mapRectToScene(o.boundingRect())
        return [round(r.x(), 1), round(r.y(), 1), round(r.width(), 1), round(r.height(), 1)]

    def espia(o):
        mo = o.metaObject()
        return QSignalSpy(o, mo.method(mo.indexOfSignal("pulsada()")))

    def tocar(o):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier,
                         o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(20)

    def textos(o):
        for h in o.childItems():
            if h.metaObject().className().startswith("QQuickText"):
                yield h
            yield from textos(h)

    r = {"escala": 1200 / 1196}
    nombres = ["tarjetaNormal", "tarjetaDeshabilitada", "tarjetaPresionada", "tarjetaTextoLargo",
               "tarjetaSecadoSinValor", "tarjetaSecadoValorLargo", "resumenValorLargo",
               "resumenSinDato", "resumenNormal", "resumenUltimoCiclo",
               "resumenPresionado", "resumenDeshabilitado",
               "galeriaEncabezado", "galeriaBarraInferior"]
    tarjetas = nombres[:-2]
    r["geo"] = {n: geo(obj(n)) for n in nombres}
    r["opacidad"] = {n: obj(n).property("opacity")
                     for n in ("tarjetaNormal", "tarjetaDeshabilitada",
                               "resumenNormal", "resumenDeshabilitado")}
    r["presionada"] = {n: obj(n).property("presionada")
                       for n in ("tarjetaPresionada", "tarjetaNormal",
                                 "resumenPresionado", "resumenNormal")}

    # toques: las habilitadas emiten pulsada, las deshabilitadas no (menú y resumen, D-20)
    pares = ["tarjetaNormal", "tarjetaDeshabilitada", "resumenNormal", "resumenDeshabilitado"]
    espias = {n: espia(obj(n)) for n in pares}
    for n in pares:
        tocar(obj(n))
    r["pulsadas"] = {n: e.count() for n, e in espias.items()}

    # ningún texto se sale de su tarjeta (valor largo reducido, títulos elididos):
    # la caja del texto queda dentro de la tarjeta y su contenido cabe en la caja
    desbordes = []
    for n in tarjetas:
        t = obj(n)
        caja = t.mapRectToScene(t.boundingRect())
        for h in textos(t):
            if not h.isVisible() or not h.property("text"):
                continue
            c = h.mapRectToScene(h.boundingRect())
            fuera = (c.x() < caja.x() - 0.5 or c.right() > caja.right() + 0.5
                     or c.bottom() > caja.bottom() + 0.5)
            if fuera or h.property("contentWidth") > h.width() + 0.5:
                desbordes.append([n, h.property("text")])
    r["desbordes"] = desbordes

    r["insignia"] = obj("insigniaCampana").property("visible")
    r["salir_habilitado"] = obj("botonSalir").property("enabled")
    r["inicio_activo"] = obj("botonInicio").property("enabled")
    r["fecha"] = obj("fechaMenu").property("text")
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=60, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def _px(r, *valores):
    return [round(v * r["escala"], 1) for v in valores]


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_tarjetas_con_medidas_del_mockup(r):
    # x/y en la galería; ancho y alto de §5 (fila 1: 716/350 x 320; resumen: 230/293/206/308 x 330)
    assert r["geo"]["tarjetaNormal"] == _px(r, 63, 200, 716, 320)
    assert r["geo"]["tarjetaDeshabilitada"][2:] == _px(r, 350, 320)
    assert r["geo"]["tarjetaPresionada"][2:] == _px(r, 349, 320)
    assert [r["geo"][n][2] for n in ("resumenValorLargo", "resumenSinDato", "resumenNormal",
                                     "resumenUltimoCiclo")] == _px(r, 230, 293, 206, 308)
    assert r["geo"]["resumenNormal"][3] == _px(r, 330)[0]
    assert r["geo"]["resumenPresionado"][2:] == _px(r, 206, 330)
    assert r["geo"]["resumenDeshabilitado"][2:] == _px(r, 230, 330)


def test_encabezado_y_barra_inferior(r):
    assert r["geo"]["galeriaEncabezado"][2:] == _px(r, 1196, 177)
    assert r["geo"]["galeriaBarraInferior"][2:] == _px(r, 1128, 139)


def test_estados(r):
    assert r["opacidad"] == {"tarjetaNormal": 1.0, "tarjetaDeshabilitada": pytest.approx(0.4),
                             "resumenNormal": 1.0, "resumenDeshabilitado": pytest.approx(0.4)}
    assert r["presionada"] == {"tarjetaPresionada": True, "tarjetaNormal": False,
                               "resumenPresionado": True, "resumenNormal": False}


def test_tarjetas_de_menu_y_resumen_son_botones(r):
    assert r["pulsadas"] == {"tarjetaNormal": 1, "tarjetaDeshabilitada": 0,
                             "resumenNormal": 1, "resumenDeshabilitado": 0}


def test_ningun_texto_desborda_su_tarjeta(r):
    assert r["desbordes"] == []


def test_campana_salir_y_home(r):
    assert r["insignia"] is True             # galería con conteoAlarmas = 2
    assert r["salir_habilitado"] is False    # D-12
    assert r["inicio_activo"] is False       # Home inactivo en el propio menú


def test_fecha_con_mes_de_la_tabla_propia(r):
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    dia, mes, _, anio = r["fecha"].split()
    assert dia.isdigit() and mes in meses and len(anio) == 4


@pytest.mark.parametrize("carpeta", ["mono", "color"])
def test_icono_ciclos_totales_es_svg_tiny(carpeta):
    raiz = ElementTree.parse(_ICONOS / carpeta / "ciclos_totales.svg").getroot()
    assert raiz.get("baseProfile") == "tiny" and raiz.get("version") == "1.2"
    etiquetas = {e.tag.split("}")[-1] for e in raiz.iter()}
    assert etiquetas <= {"svg", "path"}   # sin style, text, filtros ni degradados
    for e in raiz.iter():
        d = e.get("d") or ""
        assert not any(c in d for c in "Aa"), "SVG Tiny 1.2 no admite arcos en path"
