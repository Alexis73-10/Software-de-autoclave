"""Tanda 21 (P2): componentes QML de fin de ciclo (planeacion_fin_de_ciclo.md).

PanelFinCiclo + FilaAcordeon (FC-01..FC-04, FC-07), RegresoPanel y
PildoraFinCiclo (FC-05, FC-07), ModalConfirmacion (FC-09) y los estados
`fallida`/`interrumpida` de BarraFases (FC-06). Componentes sueltos, offscreen,
en un subproceso con su propio QGuiApplication; nunca se esperan 30 s reales
(RegresoPanel.intervaloTickMs). Además, en es y en, ningún texto de estos
componentes se recorta ni se sale de su cuadro (D8-5.4, FC-10).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.req("FC-01")

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl, QMetaObject, QPoint, Qt, Q_ARG, Q_RETURN_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
import autoclave.ui_qml.bridge.i18n_qml  # registra I18n
from autoclave import i18n

cfg = json.loads(sys.argv[3])
i18n.cargar()
i18n.fijar_idioma(cfg["idioma"])
qml_dir, qml = sys.argv[1], sys.argv[2]
app = QGuiApplication([])
from autoclave.ui_qml.app import _cargar_fuentes
_cargar_fuentes()
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
comp = QQmlComponent(engine)
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t21_fin_ciclo.qml"))
ventana = comp.createWithInitialProperties({"datos": cfg["datos"]})
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(200)

def _visual(it, nombre):
    for h in it.childItems():
        if h.objectName() == nombre:
            return h
        e = _visual(h, nombre)
        if e is not None:
            return e
    return None

def buscar(nombre, en=None):
    base = en or ventana.contentItem()
    return (en.findChild(QObject, nombre) if en else ventana.findChild(QObject, nombre)) or _visual(base, nombre)

def tocar(item, dx=None, dy=None):
    r = item.mapRectToScene(item.boundingRect())
    x = r.x() + (dx if dx is not None else r.width() / 2)
    y = r.y() + (dy if dy is not None else r.height() / 2)
    QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(int(x), int(y)))
    QTest.qWait(40)

def jp(it, ruta):
    # propiedad leída en JS (enums, grupos como border.color y font.pixelSize)
    v = QMetaObject.invokeMethod(ventana, "prop", Q_RETURN_ARG("QVariant"),
                                 Q_ARG("QVariant", it), Q_ARG("QVariant", ruta))
    return v

def color(it, prop="color"):
    return it.property(prop).name().upper()

def llamar(obj, metodo):
    QMetaObject.invokeMethod(obj, metodo)
    QTest.qWait(30)

def esperar(cond, ms=3000):
    paso = 10
    for _ in range(ms // paso):
        if cond():
            return True
        QTest.qWait(paso)
    return cond()

def desbordes(raiz_item):
    # Textos visibles de un componente: ni recortados, ni anchos de más (sin
    # ajuste de línea ni de letra), ni con más líneas que su alto, ni fuera
    # del cuadro del componente.
    caja = raiz_item.mapRectToScene(raiz_item.boundingRect())
    out = []
    def rec(it):
        for h in it.childItems():
            if not h.isVisible() or h.property("opacity") == 0:
                continue
            if h.inherits("QQuickText") and (h.property("text") or "").strip():
                t = h.property("text")
                c = h.mapRectToScene(h.boundingRect())
                if h.property("truncated"):
                    out.append(["recortado", t])
                sin_ajuste = jp(h, "wrapMode") == 0 and jp(h, "fontSizeMode") == 0
                if sin_ajuste and h.property("implicitWidth") > h.width() + 0.5 and h.width() > 0:
                    out.append(["ancho", t, h.property("implicitWidth"), h.width()])
                if jp(h, "wrapMode") != 0 and h.property("contentHeight") > h.height() + 0.5:
                    out.append(["alto", t])
                if h.property("contentWidth") > h.width() + 0.5 and jp(h, "fontSizeMode") == 0:
                    out.append(["tinta", t, h.property("contentWidth"), h.width()])
                if c.x() < caja.x() - 0.5 or c.right() > caja.right() + 0.5:
                    out.append(["fuera", t])
            rec(h)
    rec(raiz_item)
    return out

r = {}
exec(cfg["pasos"])
r["avisos"] = avisos
print("RES=" + json.dumps(r, ensure_ascii=False))
"""

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 1200; height: 1920; visible: true
    required property var datos
    // lectura de propiedades para la prueba (enums y grupos no pasan a Python)
    function prop(it, ruta) {
        let v = it
        for (const p of ruta.split(".")) v = v[p]
        return (typeof v === "object" && v !== null && v.r !== undefined) ? ("" + v) : v
    }
    readonly property real esc: 1200 / 1196
    Binding { target: Escala; property: "factor"; value: 1 }

    PanelFinCiclo {
        objectName: "panel"
        x: 33 * ventana.esc; y: 804 * ventana.esc
        width: 1129 * ventana.esc; height: 794 * ventana.esc
        escala: ventana.esc
        modo: ventana.datos.modo
        subtitulo: ventana.datos.subtitulo
        causa: ventana.datos.causa
        alarmas: ventana.datos.alarmas
    }
    RegresoPanel { objectName: "regreso" }
    PildoraFinCiclo {
        objectName: "pildoraRoja"
        x: 300; y: 40; escala: ventana.esc
        tipo: "alarmas"; cantidad: 3; segundos: 24
    }
    PildoraFinCiclo {
        objectName: "pildoraAmbar"
        x: 300; y: 120; escala: ventana.esc
        tipo: "observaciones"; cantidad: 2; segundos: 24
    }
    BarraFases {
        objectName: "barraFases"
        width: 1200; height: 600
        escala: ventana.esc
        fases: [{fase: "precalentamiento", estado: "completada"},
                {fase: "vacio", estado: "completada"},
                {fase: "esterilizacion", estado: "fallida"},
                {fase: "secado", estado: "pendiente"}]
    }
    ModalConfirmacion {
        objectName: "modal"
        titulo: ventana.datos.modal.titulo
        cuerpo: ventana.datos.modal.cuerpo
        textoAccion: ventana.datos.modal.accion
    }
}
"""

_LARGO_ES = ("La presión de cámara corresponde a 136,4 °C de saturación, 2,3 K por encima del sensor "
             "Principal (134,1 °C). El ciclo se abortó y la carga debe reprocesarse por completo. ") * 3
_LARGO_EN = ("Chamber pressure corresponds to 136.4 °C saturation, 2.3 K above the Main sensor "
             "(134.1 °C). The cycle was aborted and the load must be fully reprocessed. ") * 3

_DATOS = {
    "es": {
        "modo": "fallo",
        "subtitulo": "Ciclo 03 terminó en FALLO a las 13:21",
        "causa": {"titulo": "Fallo en esterilización",
                  "subtitulo": "Aire o gases no condensables en la cámara (verificación de saturación)",
                  "hora": "13:21:07", "descripcion": _LARGO_ES,
                  "queHacer": "La carga NO está estéril. Revise la eliminación de aire (prevacío, "
                              "prueba de Bowie & Dick y fugas de la cámara) y repita el ciclo.",
                  "meta": "Fase: Esterilización · 28-oct-2026 13:21:07 · Código CIC-12"},
        "alarmas": [
            {"titulo": "Uniformidad térmica fuera de rango en la sonda de referencia de la carga",
             "hora": "13:19:40", "nivel": "media", "descripcion": _LARGO_ES,
             "queHacer": "Revise la carga y la ubicación de la sonda de referencia.",
             "meta": "Fase: Esterilización · 13:19:40 · Código CIC-09 · Se despejó a las 13:20:02"},
            {"titulo": "Presión de chaqueta baja", "hora": "13:02:15", "nivel": "baja",
             "descripcion": "La presión de chaqueta quedó bajo la banda.", "queHacer": "",
             "meta": "13:02:15 · Código CHQ-01 · Sigue activa"},
        ],
        "modal": {"titulo": "Confirmar y llevar a estado seguro",
                  "cuerpo": "El paro de emergencia se liberó. La carga NO está estéril. " * 3,
                  "accion": "Confirmar y llevar a estado seguro"},
    },
    "en": {
        "modo": "fallo",
        "subtitulo": "Cycle 03 ended in FAILURE at 13:21",
        "causa": {"titulo": "Failure in sterilization",
                  "subtitulo": "Air or non-condensable gases in the chamber (saturation check)",
                  "hora": "13:21:07", "descripcion": _LARGO_EN,
                  "queHacer": "The load is NOT sterile. Check air removal (pre-vacuum, Bowie & Dick "
                              "test and chamber leaks) and repeat the cycle.",
                  "meta": "Phase: Sterilization · 28-Oct-2026 13:21:07 · Code CIC-12"},
        "alarmas": [
            {"titulo": "Thermal uniformity out of range at the load reference probe",
             "hora": "13:19:40", "nivel": "media", "descripcion": _LARGO_EN,
             "queHacer": "Check the load and the reference probe placement.",
             "meta": "Phase: Sterilization · 13:19:40 · Code CIC-09 · Cleared at 13:20:02"},
            {"titulo": "Low jacket pressure", "hora": "13:02:15", "nivel": "baja",
             "descripcion": "Jacket pressure fell below the band.", "queHacer": "",
             "meta": "13:02:15 · Code CHQ-01 · Still active"},
        ],
        "modal": {"titulo": "Confirm and bring to a safe state",
                  "cuerpo": "The emergency stop was released. The load is NOT sterile. " * 3,
                  "accion": "Confirm and bring to a safe state"},
    },
}


def _correr(pasos, idioma="es", datos=None):
    cfg = {"idioma": idioma, "pasos": pasos, "datos": datos or _DATOS[idioma]}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, str(RAIZ_QML), _QML,
                        json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=120, env=env)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RES=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[4:])


def _t(clave, idioma, **params):
    from autoclave import i18n
    i18n.cargar()
    return i18n.t(clave, idioma, **params)


# ── acordeón (FC-04) y panel (FC-01, FC-02, FC-03, FC-07) ──────────────────

_PASOS_ACORDEON = r"""
panel = buscar("panel")
causa = buscar("filaCausa", panel)
a0 = buscar("filaAlarmaCiclo_0", panel)
a1 = buscar("filaAlarmaCiclo_1", panel)
def abiertas():
    return [causa.property("abierta"), a0.property("abierta"), a1.property("abierta")]
r["al_entrar"] = abiertas()
r["fila_abierta"] = panel.property("filaAbierta")
r["cuerpo_causa"] = buscar("cuerpoFila", causa).isVisible()
r["titulo"] = buscar("tituloPanelFinCiclo", panel).property("text")
r["color_titulo"] = color(buscar("tituloPanelFinCiclo", panel))
r["rotulo"] = buscar("rotuloAlarmasCiclo", panel).property("text")
r["sin_alarmas_visible"] = buscar("sinAlarmasCiclo", panel).isVisible()
r["cantidad"] = panel.property("cantidad")
r["barra_causa"] = color(buscar("barraNivel", causa))
r["barra_a0"] = color(buscar("barraNivel", a0))
r["barra_a1"] = color(buscar("barraNivel", a1))
r["fondo_causa_abierta"] = color(buscar("fondoFila", causa))
r["chevron_abierta"] = buscar("chevronFila", causa).property("rotation")
r["chevron_cerrada"] = buscar("chevronFila", a0).property("rotation")
r["sub_causa"] = buscar("subtituloFila", causa).isVisible()
r["sub_alarma"] = buscar("subtituloFila", a0).isVisible()
r["quehacer_a1"] = buscar("rotuloQueHacer", a1).property("visible")
# tocar una cerrada la abre y cierra la otra (en la cabecera: la fila cerrada es corta)
tocar(a0, dy=30)
r["tras_a0"] = abiertas()
r["cuerpo_causa_tras_a0"] = buscar("cuerpoFila", causa).isVisible()
# tocar la abierta la cierra
tocar(a0, dy=30)
r["tras_a0_otra_vez"] = abiertas()
tocar(a1, dy=30)
r["tras_a1"] = abiertas()
# volver al panel: la causa queda abierta otra vez, arriba del todo
flick = buscar("desplazablePanelFinCiclo", panel)
flick.setProperty("contentY", 50)
llamar(panel, "volverAlPanel")
r["tras_volver"] = abiertas()
r["contentY_tras_volver"] = flick.property("contentY")
# Ver gráfica: señal
cuenta = {"n": 0}
panel.verGraficaPulsado.connect(lambda: cuenta.__setitem__("n", cuenta["n"] + 1))
tocar(buscar("botonVerGrafica", panel))
r["ver_grafica"] = cuenta["n"]
# el contenido largo desplaza solo bajo el divisor (título, subtítulo y botón fijos)
r["flick_clip"] = flick.property("clip")
r["flick_bajo_divisor"] = flick.y() > buscar("divisorPanelFinCiclo", panel).y()
r["desbordes_fallo"] = desbordes(panel)
# cancelado sin alarmas: barra gris, sin (N), mensaje sin alarmas
panel.setProperty("modo", "cancelado")
panel.setProperty("alarmas", [])
QTest.qWait(50)
r["canc_barra"] = color(buscar("barraNivel", causa))
r["canc_rotulo"] = buscar("rotuloAlarmasCiclo", panel).property("text")
r["canc_sin_alarmas"] = buscar("sinAlarmasCiclo", panel).isVisible()
r["canc_causa_abierta"] = causa.property("abierta")
r["canc_cantidad"] = panel.property("cantidad")
r["desbordes_cancelado"] = desbordes(panel)
# causa sin título: nunca una fila vacía
panel.setProperty("causa", {})
QTest.qWait(30)
r["causa_vacia_titulo"] = buscar("tituloFila", causa).property("text")
# modo desconocido: falla cerrada como fallo
panel.setProperty("modo", "raro")
QTest.qWait(30)
r["raro_modo"] = panel.property("modoEfectivo")
r["raro_barra"] = color(buscar("barraNivel", causa))
# observaciones (ciclo exitoso): sin causa, título ámbar
panel.setProperty("modo", "observaciones")
panel.setProperty("alarmas", cfg["datos"]["alarmas"])
QTest.qWait(50)
r["obs_causa_visible"] = causa.isVisible()
r["obs_titulo"] = buscar("tituloPanelFinCiclo", panel).property("text")
r["obs_color"] = color(buscar("tituloPanelFinCiclo", panel))
r["obs_cantidad"] = panel.property("cantidad")
r["obs_fila_abierta"] = panel.property("filaAbierta")
r["desbordes_obs"] = desbordes(panel)
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_panel_y_acordeon(idioma):
    r = _correr(_PASOS_ACORDEON, idioma)
    assert r["avisos"] == []
    # al entrar, la causa abierta y solo ella
    assert r["al_entrar"] == [True, False, False] and r["fila_abierta"] == 0
    assert r["cuerpo_causa"] is True
    assert r["titulo"] == _t("ciclo.carga_no_esteril", idioma)
    assert r["color_titulo"] == "#D00000"
    assert r["rotulo"] == _t("ciclo.fin_alarmas_rotulo_n", idioma, n=2)
    assert r["sin_alarmas_visible"] is False
    assert r["cantidad"] == 3
    # barra roja de fallo; las alarmas con los colores de FilaAlarma
    assert (r["barra_causa"], r["barra_a0"], r["barra_a1"]) == ("#EE0000", "#FFCC00", "#00CCFF")
    assert r["fondo_causa_abierta"] == "#F6F6F6"
    assert r["chevron_abierta"] == 90 and r["chevron_cerrada"] == 0
    assert r["sub_causa"] is True and r["sub_alarma"] is False
    assert r["quehacer_a1"] is False   # sin acción: se omite «QUÉ HACER»
    # una sola abierta; tocar la abierta la cierra
    assert r["tras_a0"] == [False, True, False] and r["cuerpo_causa_tras_a0"] is False
    assert r["tras_a0_otra_vez"] == [False, False, False]
    assert r["tras_a1"] == [False, False, True]
    assert r["tras_volver"] == [True, False, False] and r["contentY_tras_volver"] == 0
    assert r["ver_grafica"] == 1
    assert r["flick_clip"] is True and r["flick_bajo_divisor"] is True
    assert r["desbordes_fallo"] == []
    # cancelado: barra gris, sin (N), mensaje sin alarmas
    assert r["canc_barra"] == "#808080"
    assert r["canc_rotulo"] == _t("ciclo.fin_alarmas_rotulo", idioma)
    assert r["canc_sin_alarmas"] is True and r["canc_causa_abierta"] is True
    assert r["canc_cantidad"] == 1
    assert r["desbordes_cancelado"] == []
    assert r["causa_vacia_titulo"] == _t("ciclo.fin_causa_generica", idioma)
    assert r["raro_modo"] == "fallo" and r["raro_barra"] == "#EE0000"
    # observaciones: sin causa, título ámbar, primera observación abierta
    assert r["obs_causa_visible"] is False
    assert r["obs_titulo"] == _t("ciclo.fin_titulo_observaciones", idioma)
    assert r["obs_color"] == "#B35A00"
    assert r["obs_cantidad"] == 2 and r["obs_fila_abierta"] == 1
    assert r["desbordes_obs"] == []


_PASOS_TITULO_LARGO = r"""
panel = buscar("panel")
causa = buscar("filaCausa", panel)
titulo = buscar("tituloFila", causa)
base = causa.property("tamTituloBase")
c = dict(cfg["datos"]["causa"])
c["titulo"] = cfg["extra"]["medio"]
panel.setProperty("causa", c)
QTest.qWait(50)
r["medio"] = [jp(titulo, "font.pixelSize"), base, jp(titulo, "wrapMode"), titulo.property("text")]
c["titulo"] = cfg["extra"]["enorme"]
panel.setProperty("causa", c)
QTest.qWait(50)
r["enorme"] = [jp(titulo, "font.pixelSize"), causa.property("fuenteMinima"),
               jp(titulo, "wrapMode"), causa.property("tituloEnVariasLineas")]
c["titulo"] = cfg["extra"]["enorme"]
c["tituloAbreviado"] = "Fallo"
panel.setProperty("causa", c)
QTest.qWait(50)
r["abreviado"] = [titulo.property("text"), jp(titulo, "font.pixelSize"), base]
r["desbordes"] = desbordes(panel)
"""


def test_titulo_largo_se_abrevia_reduce_o_parte_sin_recortar():
    datos = json.loads(json.dumps(_DATOS["es"]))
    datos_extra = {"medio": "Fallo en esterilización por aire o gases no condensables en la cámara",
                   "enorme": "Fallo en esterilización " * 12}
    cfg_datos = datos
    pasos = _PASOS_TITULO_LARGO.replace('cfg["extra"]', json.dumps(datos_extra))
    r = _correr(pasos, "es", cfg_datos)
    assert r["avisos"] == []
    tam, base, wrap, _ = r["medio"]
    assert tam < base and wrap == 0           # cabe reduciendo la letra, en una línea
    tam, minimo, wrap, varias = r["enorme"]
    assert tam == minimo and varias is True and wrap != 0   # ni al mínimo cabe: varias líneas
    texto, tam, base = r["abreviado"]
    assert texto == "Fallo" and tam == base   # el abreviado cabe con la letra base
    assert r["desbordes"] == []


# ── regreso automático (FC-05) ─────────────────────────────────────────────

_PASOS_REGRESO = r"""
reg = buscar("regreso")
r["constante"] = reg.property("regresoPanelS")
r["inicial"] = reg.property("restante")
r["quieto_inactivo"] = reg.property("corriendo")
vencidos = {"n": 0}
reg.vencido.connect(lambda: vencidos.__setitem__("n", vencidos["n"] + 1))
reg.setProperty("intervaloTickMs", 20)
reg.setProperty("activo", True)
r["baja"] = esperar(lambda: reg.property("restante") <= 25)
# un toque reinicia la cuenta
QMetaObject.invokeMethod(reg, "reiniciarCuenta")
r["tras_toque"] = reg.property("restante")
# con un modal abierto la cuenta se detiene
esperar(lambda: reg.property("restante") <= 27)
reg.setProperty("pausado", True)
QTest.qWait(30)
congelado = reg.property("restante")
QTest.qWait(200)
r["pausado_quieto"] = reg.property("restante") == congelado and not reg.property("corriendo")
r["vencidos_pausado"] = vencidos["n"]
reg.setProperty("pausado", False)
r["al_cerrar_modal"] = reg.property("restante")
# vence una sola vez y se detiene
r["vence"] = esperar(lambda: vencidos["n"] >= 1, 3000)
QTest.qWait(150)
r["vencidos"] = vencidos["n"]
r["restante_final"] = reg.property("restante")
r["corriendo_final"] = reg.property("corriendo")
reg.setProperty("activo", False)
r["al_desactivar"] = reg.property("restante")
"""


def test_regreso_automatico_con_tiempo_inyectable():
    r = _correr(_PASOS_REGRESO)
    assert r["avisos"] == []
    assert r["constante"] == 30 and r["inicial"] == 30 and r["quieto_inactivo"] is False
    assert r["baja"] is True
    assert r["tras_toque"] == 30
    assert r["pausado_quieto"] is True and r["vencidos_pausado"] == 0
    assert r["al_cerrar_modal"] == 30
    assert r["vence"] is True and r["vencidos"] == 1
    assert r["restante_final"] == 0 and r["corriendo_final"] is False
    assert r["al_desactivar"] == 30


# ── píldoras (FC-05, FC-07) ───────────────────────────────────────────────

_PASOS_PILDORAS = r"""
roja, ambar = buscar("pildoraRoja"), buscar("pildoraAmbar")
r["roja_texto"] = buscar("textoPildora", roja).property("text")
r["ambar_texto"] = buscar("textoPildora", ambar).property("text")
r["roja_colores"] = [color(roja), jp(roja, "border.color").upper(),
                     color(buscar("textoPildora", roja))]
r["ambar_colores"] = [color(ambar), color(buscar("textoPildora", ambar))]
roja.setProperty("segundos", 7)
QTest.qWait(20)
r["roja_7"] = buscar("textoPildora", roja).property("text")
n = {"n": 0}
roja.pulsada.connect(lambda: n.__setitem__("n", n["n"] + 1))
tocar(roja)
r["pulsada"] = n["n"]
r["desbordes"] = desbordes(roja) + desbordes(ambar)
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_pildora_roja_con_cuenta_y_ambar_sin_cuenta(idioma):
    r = _correr(_PASOS_PILDORAS, idioma)
    assert r["avisos"] == []
    assert r["roja_texto"] == _t("ciclo.pildora_alarmas", idioma, n=3, s="24")
    assert r["roja_7"] == _t("ciclo.pildora_alarmas", idioma, n=3, s="07")
    assert r["ambar_texto"] == _t("ciclo.pildora_observaciones", idioma, n=2)
    assert "24" not in r["ambar_texto"]
    assert r["roja_colores"] == ["#FFECEC", "#D00000", "#D00000"]
    assert r["ambar_colores"] == ["#FFF4E6", "#B35A00"]
    assert r["pulsada"] == 1
    assert r["desbordes"] == []


# ── modal de confirmación (FC-09) ─────────────────────────────────────────

_PASOS_MODAL = r"""
modal = buscar("modal")
cuentas = {"a": 0, "c": 0}
modal.aceptado.connect(lambda: cuentas.__setitem__("a", cuentas["a"] + 1))
modal.cancelado.connect(lambda: cuentas.__setitem__("c", cuentas["c"] + 1))
r["cerrado_al_inicio"] = not modal.isVisible()
llamar(modal, "abrir")
volver, accion = buscar("botonVolverModal", modal), buscar("botonAccionModal", modal)
r["tam_botones"] = [volver.width(), volver.height(), accion.width(), accion.height()]
r["volver_texto"] = buscar("botonVolverModal", modal).childItems()[0].property("text")
r["nota_sin_texto"] = buscar("notaModalConfirmacion", modal).isVisible()
r["accion_ajuste"] = jp(buscar("textoAccionModal", modal), "fontSizeMode")
r["desbordes"] = desbordes(buscar("tarjetaModalConfirmacion", modal))
# tocar el fondo = Volver, sin acción
tocar(buscar("fondoModalConfirmacion", modal), dx=20, dy=20)
r["fondo"] = [cuentas["a"], cuentas["c"], modal.isVisible()]
llamar(modal, "abrir")
tocar(buscar("botonVolverModal", modal))
r["volver"] = [cuentas["a"], cuentas["c"], modal.isVisible()]
llamar(modal, "abrir")
modal.setProperty("nota", cfg["datos"]["modal"]["cuerpo"])
modal.setProperty("colorAccion", "#009535")
QTest.qWait(30)
r["nota_visible"] = buscar("notaModalConfirmacion", modal).isVisible()
r["nota_colores"] = [color(buscar("notaModalConfirmacion", modal)),
                     jp(buscar("notaModalConfirmacion", modal), "border.color").upper()]
r["color_accion"] = color(buscar("botonAccionModal", modal))
r["desbordes_nota"] = desbordes(buscar("tarjetaModalConfirmacion", modal))
# tocar dentro de la tarjeta no cierra
tocar(buscar("tituloModalConfirmacion", modal))
r["tarjeta_no_cierra"] = modal.isVisible()
tocar(buscar("botonAccionModal", modal))
r["aceptar"] = [cuentas["a"], cuentas["c"], modal.isVisible()]
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_modal_confirmacion(idioma):
    r = _correr(_PASOS_MODAL, idioma)
    assert r["avisos"] == []
    assert r["cerrado_al_inicio"] is True
    assert r["tam_botones"] == [340, 88, 340, 88]
    assert r["volver_texto"] == _t("ciclo.modal_volver", idioma)
    assert r["nota_sin_texto"] is False
    assert r["accion_ajuste"] == 1   # Text.HorizontalFit
    assert r["desbordes"] == []
    assert r["fondo"] == [0, 1, False]
    assert r["volver"] == [0, 2, False]
    assert r["nota_visible"] is True
    assert r["nota_colores"] == ["#FFF4E6", "#FF9933"]
    assert r["color_accion"] == "#009535"
    assert r["desbordes_nota"] == []
    assert r["tarjeta_no_cierra"] is True
    assert r["aceptar"] == [1, 2, False]


# ── barra de fases (FC-06) ────────────────────────────────────────────────

_PASOS_BARRA = r"""
barra = buscar("barraFases")
def circulo(f):
    return buscar("circuloFase_" + f, barra)
r["fallida"] = color(circulo("esterilizacion"))
r["fallida_degradado"] = jp(circulo("esterilizacion"), "gradient") is not None
r["pendiente"] = color(circulo("secado"))
r["completada_degradado"] = jp(circulo("vacio"), "gradient") is not None
barra.setProperty("fases", [{"fase": "precalentamiento", "estado": "completada"},
                            {"fase": "vacio", "estado": "interrumpida"},
                            {"fase": "secado", "estado": "pendiente"}])
QTest.qWait(30)
r["interrumpida"] = color(circulo("vacio"))
r["icono"] = circulo("vacio").childItems()[0].property("source").toString().endswith("fase_vacio.svg")
"""


def test_barra_fases_fallida_e_interrumpida():
    r = _correr(_PASOS_BARRA)
    assert r["avisos"] == []
    assert r["fallida"] == "#EE0000" and r["fallida_degradado"] is False
    assert r["pendiente"] == "#CCCCCC"
    assert r["completada_degradado"] is True
    assert r["interrumpida"] == "#FF9933"
    assert r["icono"] is True
