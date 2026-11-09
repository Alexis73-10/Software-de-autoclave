# tests/test_cancelacion_ciclo_en_curso_qml.py
#
# Flujo de CANCELAR CICLO / CONFIRMAR en PantallaCicloEnCurso.
# Tanda 34 (CAN-02..CAN-04): mientras el ciclo corre, CANCELAR CICLO es el
# deslizador rojo `deslizadorCancelarCiclo` (DeslizadorInicio, variante
# "cancelar"), sin modal: solo el arrastre completo envía la cancelación (una
# por arrastre); soltar antes no envía nada; deshabilitado sin datos vigentes,
# con un comando en curso o con un modal abierto; un rechazo abre el aviso de
# siempre (ciclo.cancelar_error) y la manija vuelve al inicio. Al terminar el
# ciclo vuelve el botón CONFIRMAR con su modal (FC-09). Ya no existe
# `modalCancelarCiclo` (CAN-03).
# Además, la paleta: variante "cancelar" con los Colores.deslizadorCancelar* y
# "inicio" (por defecto, la de Preciclo) con los deslizador* de siempre (CAN-01).
# Los comandos se simulan con un QtObject en QML.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.req("T34-CAN")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"
ES_JSON = RAIZ_QML.parents[1] / "i18n" / "es.json"

_QML = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 600; height: 960; visible: true
    QtObject {
        id: comandos
        property int cancelaciones: 0
        property int confirmaciones: 0
        property bool ocupado: false
        property string error: ""
        function cancelar() { cancelaciones++ }
        function confirmar() { confirmaciones++ }
        function descartarError() { error = "" }
    }
    QtObject {
        id: progresoFalso
        property string resultado: ""
        property bool entregada: true   // ENT-09: CONFIRMAR exige la cámara entregada
        property bool activo: false
    }
    Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / 1200, ventana.height / 1920) }
    PantallaCicloEnCurso {
        id: pantalla
        anchors.fill: parent
        comandos: comandos
        progreso: progresoFalso
        datosVigentes: true
    }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, es_json, qml = sys.argv[1], sys.argv[2], sys.argv[3]
    textos = json.load(open(es_json, encoding="utf-8"))
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_cancelacion.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(300)
    hijos = ventana.findChildren(QObject)
    pantalla = [o for o in hijos if o.metaObject().className().startswith("PantallaCicloEnCurso_QML")][0]
    comandos = [o for o in hijos if o.metaObject().indexOfProperty("cancelaciones") >= 0][0]
    s = 600 / 1196   # px de la ventana por px del mockup
    senales = []
    pantalla.cancelarPulsado.connect(lambda: senales.append(1))

    def obj(nombre, raiz=None):
        hallados = [o for o in (raiz or ventana).findChildren(QObject) if o.objectName() == nombre]
        return hallados[0] if hallados else None

    desl = obj("deslizadorCancelarCiclo")
    manija = obj("manijaDeslizadorInicio", desl)
    boton = obj("botonCancelarCiclo")

    def tocar(x, y):  # px del mockup
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(x * s), int(y * s)))
        QTest.qWait(80)

    def arrastrar(fraccion):
        # de la manija hacia la derecha, `fraccion` del recorrido (>= 1: hasta el extremo y más)
        c = manija.mapToScene(QPointF(manija.width() / 2, manija.height() / 2))
        recorrido = desl.property("maxX") - desl.property("margen")
        dx = recorrido * fraccion + (30 if fraccion >= 1 else 0)
        p0 = QPoint(int(c.x()), int(c.y()))
        QTest.mousePress(ventana, Qt.LeftButton, Qt.NoModifier, p0)
        for i in range(1, 26):
            QTest.mouseMove(ventana, QPoint(int(c.x() + dx * i / 25), int(c.y())))
            QTest.qWait(10)
        QTest.qWait(30)
        QTest.mouseRelease(ventana, Qt.LeftButton, Qt.NoModifier,
                           QPoint(int(c.x() + dx), int(c.y())))
        QTest.qWait(450)

    def en_inicio():
        return abs(manija.property("x") - desl.property("margen")) < 0.5

    def aviso():
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith("PanelModal_QML") and o.property("titulo") == "AVISO"][0]

    def texto_aviso():
        return [o.property("text") for o in aviso().findChildren(QQuickItem)
                if o.metaObject().className() == "QQuickText" and o.property("text")]

    def accion(m):
        b = [o for o in m.findChildren(QQuickItem) if o.objectName() == "botonAccionModal"][0]
        c = b.mapToScene(b.boundingRect().center())
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
        QTest.qWait(80)

    r = {}
    r["sin_modal_cancelar"] = obj("modalCancelarCiclo") is None
    r["en_curso"] = {"deslizador": desl.isVisible(), "boton": boton.isVisible(),
                     "habilitado": desl.property("enabled"), "variante": desl.property("variante"),
                     "texto": obj("textoDeslizadorInicio", desl).property("text"),
                     "texto_completado": obj("textoCompletadoDeslizadorInicio", desl).property("text")}
    # pista cerca del extremo derecho: un toque no cancela
    tocar(1060, 1812)
    r["toque_no_cancela"] = comandos.property("cancelaciones")

    arrastrar(0.6)                                    # soltar antes del extremo
    r["parcial"] = [comandos.property("cancelaciones"), len(senales), en_inicio()]

    arrastrar(1.0)                                    # arrastre completo
    r["completo"] = [comandos.property("cancelaciones"), len(senales), en_inicio()]

    comandos.setProperty("ocupado", True)             # envío en curso
    QTest.qWait(50)
    r["ocupado_habilitado"] = desl.property("enabled")
    arrastrar(1.0)
    r["ocupado"] = comandos.property("cancelaciones")
    comandos.setProperty("ocupado", False)
    QTest.qWait(50)

    pantalla.setProperty("datosVigentes", False)      # sin datos vigentes
    QTest.qWait(50)
    r["sin_datos_habilitado"] = desl.property("enabled")
    arrastrar(1.0)
    r["sin_datos"] = comandos.property("cancelaciones")
    pantalla.setProperty("datosVigentes", True)
    QTest.qWait(50)

    arrastrar(1.0)                                    # segunda cancelación ...
    comandos.setProperty("error", "cancelar")         # ... que el backend rechaza
    QTest.qWait(450)
    r["rechazo"] = {"enviadas": comandos.property("cancelaciones"), "aviso": aviso().property("visible"),
                    "texto": texto_aviso(), "en_inicio": en_inicio(),
                    "habilitado": desl.property("enabled"), "modal_abierto": pantalla.property("modalAbierto")}
    arrastrar(1.0)                                    # con el aviso (modal) abierto
    r["con_modal"] = comandos.property("cancelaciones")
    aviso().setProperty("visible", False)
    QTest.qWait(80)
    r["tras_cerrar_aviso"] = [comandos.property("error"), desl.property("enabled")]

    pantalla.setProperty("resultado", "exitoso")      # ciclo terminado: CONFIRMAR
    QTest.qWait(80)
    r["terminado"] = {"deslizador": desl.isVisible(), "boton": boton.isVisible()}
    tocar(960, 1812)
    r["confirmar_sin_modal_no_envia"] = comandos.property("confirmaciones")
    r["modal_confirmar_abre"] = obj("modalConfirmarCiclo").property("visible")
    accion(obj("modalConfirmarCiclo"))
    r["confirmar_fin"] = comandos.property("confirmaciones")
    r["cancelaciones_fin"] = comandos.property("cancelaciones")
    r["cancelar_error"] = textos["ciclo"]["cancelar_error"]
    r["avisos"] = avisos
    print(json.dumps(r))
""")


@pytest.fixture(scope="module")
def r():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), str(ES_JSON), _QML],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_sin_avisos_qml(r):
    assert r["avisos"] == []


def test_ya_no_existe_el_modal_de_cancelar(r):
    assert r["sin_modal_cancelar"] is True


def test_en_curso_hay_deslizador_rojo_y_no_boton(r):
    e = r["en_curso"]
    assert e["deslizador"] is True and e["boton"] is False and e["habilitado"] is True
    assert e["variante"] == "cancelar"
    assert e["texto"] == "CANCELAR CICLO" and e["texto_completado"] == "Cancelando…"


def test_un_toque_no_cancela(r):
    assert r["toque_no_cancela"] == 0


def test_soltar_antes_del_extremo_no_envia_y_vuelve(r):
    assert r["parcial"] == [0, 0, True]


def test_arrastre_completo_una_sola_cancelacion(r):
    assert r["completo"] == [1, 1, True]


def test_deshabilitado_con_comando_en_curso(r):
    assert r["ocupado_habilitado"] is False
    assert r["ocupado"] == 1


def test_deshabilitado_sin_datos_vigentes(r):
    assert r["sin_datos_habilitado"] is False
    assert r["sin_datos"] == 1


def test_rechazo_muestra_el_aviso_y_vuelve_al_inicio(r):
    e = r["rechazo"]
    assert e["enviadas"] == 2
    assert e["aviso"] is True and r["cancelar_error"] in e["texto"]
    assert e["en_inicio"] is True
    assert e["habilitado"] is False and e["modal_abierto"] is True


def test_deshabilitado_con_un_modal_abierto(r):
    assert r["con_modal"] == 2
    assert r["tras_cerrar_aviso"] == ["", True]


def test_terminado_vuelve_confirmar_con_su_modal(r):
    assert r["terminado"] == {"deslizador": False, "boton": True}
    assert r["confirmar_sin_modal_no_envia"] == 0
    assert r["modal_confirmar_abre"] is True
    assert r["confirmar_fin"] == 1
    assert r["cancelaciones_fin"] == 2


# ── CAN-01: paleta de las variantes ──────────────────────────────────────

_QML_COLORES = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 400; height: 300; visible: true
    DeslizadorInicio { objectName: "inicio"; width: 332; height: 110 }
    DeslizadorInicio { objectName: "cancelar"; variante: "cancelar"; y: 150; width: 235; height: 88 }
}
"""

_PROPS = {  # propiedad del deslizador -> sufijo del color en Colores (deslizador<X> / deslizadorCancelar<X>)
    "colorPista": "Pista", "colorPistaListo": "PistaListo", "verdeReposo": "Acento",
    "verdeListo": "AcentoListo", "brilloReposo": "Brillo", "brilloListo": "BrilloListo",
    "colorTexto": "Texto", "colorSombraInterior": "SombraInterior", "colorNucleo": "Nucleo",
    "colorManija": "Manija", "colorManijaListo": "ManijaListo",
}

_SCRIPT_COLORES = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest

    qml_dir, qml, props = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_can_colores.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    QTest.qWait(100)
    colores = engine.singletonInstance("Tema", "Colores")
    d = {o.objectName(): o for o in ventana.findChildren(QObject) if o.objectName() in ("inicio", "cancelar")}
    r = {"avisos": avisos}
    for tema in (False, True):
        colores.setProperty("oscuro", tema)
        QTest.qWait(30)
        clave = "oscuro" if tema else "claro"
        r[clave] = {"variante_defecto": d["inicio"].property("variante")}
        for prop, suf in props.items():
            r[clave][prop] = {
                "inicio": d["inicio"].property(prop).name(),
                "inicio_alfa": d["inicio"].property(prop).alpha(),
                "cancelar": d["cancelar"].property(prop).name(),
                "cancelar_alfa": d["cancelar"].property(prop).alpha(),
                "esperado_inicio": colores.property("deslizador" + suf).name(),
                "esperado_inicio_alfa": colores.property("deslizador" + suf).alpha(),
                "esperado_cancelar": colores.property("deslizadorCancelar" + suf).name(),
                "esperado_cancelar_alfa": colores.property("deslizadorCancelar" + suf).alpha(),
            }
    print(json.dumps(r))
""")


@pytest.fixture(scope="module")
def colores():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT_COLORES, str(RAIZ_QML), _QML_COLORES, json.dumps(_PROPS)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_colores_sin_avisos(colores):
    assert colores["avisos"] == []


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_variante_inicio_por_defecto_sin_cambio(colores, tema):
    t = colores[tema]
    assert t["variante_defecto"] == "inicio"
    for prop in _PROPS:
        c = t[prop]
        assert (c["inicio"], c["inicio_alfa"]) == (c["esperado_inicio"], c["esperado_inicio_alfa"]), prop


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_variante_cancelar_en_rojo(colores, tema):
    t = colores[tema]
    for prop in _PROPS:
        c = t[prop]
        assert (c["cancelar"], c["cancelar_alfa"]) == (c["esperado_cancelar"], c["esperado_cancelar_alfa"]), prop
    # el acento de la variante es rojo: canal rojo dominante
    acento = t["verdeReposo"]["cancelar"]
    rr, gg, bb = int(acento[1:3], 16), int(acento[3:5], 16), int(acento[5:7], 16)
    assert rr > 2 * gg and rr > 2 * bb


def test_fuente_preciclo_no_fija_otra_variante():
    codigo = (RAIZ_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    i = codigo.index("deslizadorIniciarCiclo")
    bloque = codigo[i:codigo.index("onCompletado", i)]
    assert "variante" not in bloque
