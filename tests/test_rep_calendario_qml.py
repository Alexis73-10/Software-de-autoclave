"""Reportes (REP-07): componentes QML del calendario de ejecución.

CalendarioEjecucion, MesMiniatura y PanelDiaCalendario (solo dibujo). Se cargan
offscreen en un subproceso con su propio QGuiApplication, con datos armados por
el dominio (ui_qml/domain/reporte_dashboard.py), en es y en: mes, año, sin
programas, día elegido y panel con ciclos; tocar un día, un mes, «Ver año», un
programa o un intento emite su señal; nada se recorta (D8-5.4) ni dice
«conforme»/«apto» (DR-H01).
"""

import calendar
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
CLAVES = json.loads((RAIZ / "docs/informes/dashboard_reportes/claves_i18n_reportes.json").read_text(encoding="utf-8"))

from autoclave.ui_qml.domain import reporte_dashboard as d  # noqa: E402


def _t(clave, idioma=None, **params):
    texto = CLAVES.get(idioma or "es", CLAVES["es"]).get(clave)
    if texto is None:
        return clave
    for k, v in params.items():
        texto = texto.replace("{" + k + "}", str(v))
    return texto


def _dash(periodo="mes", desde="2026-10-01", hasta="2026-10-31"):
    return {"periodo": periodo, "desde": desde, "hasta": hasta, "indicadores": {}}


_PROGS = [{"numero": 1, "programa_id": "bd", "nombre": "Bowie & Dick"},
          {"numero": 3, "programa_id": "x", "nombre": "Textiles"}]


def _cal_mes(idioma):
    estados = {1: "exito", 2: "exito_fallo_previo", 3: "sin_exito", 4: "falto", 5: "no_ejecutado",
               6: "en_curso", 7: "futuro"}
    n = calendar.monthrange(2026, 10)[1]
    dias = [{"fecha": f"2026-10-{x:02d}", "estado": estados.get(x, "sin_operacion"), "intentos": 1, "exitos": 0}
            for x in range(1, n + 1)]
    return d.calendario(_dash(), {"periodo": "mes", "programas": _PROGS, "programa": 1, "dias": dias}, idioma, _t)


def _cal_anio(idioma):
    dias = []
    for m in range(1, 13):
        for x in range(1, calendar.monthrange(2026, m)[1] + 1):
            e = "futuro" if m >= 12 else "sin_operacion"
            if m == 10:
                e = {3: "exito_fallo_previo", 5: "falto", 6: "sin_exito"}.get(x, "exito")
            if m == 9:
                e = "exito"
            dias.append({"fecha": f"2026-{m:02d}-{x:02d}", "estado": e, "intentos": 0, "exitos": 0})
    return d.calendario(_dash("anio", "2026-01-01", "2026-12-31"),
                        {"periodo": "anio", "programas": _PROGS[:1], "programa": 1, "dias": dias}, idioma, _t)


def _cal_vacio(idioma):
    return d.calendario(_dash(), {"periodo": "mes", "programas": [], "programa": None, "dias": []}, idioma, _t)


_CICLOS = [
    {"id": 11, "numero": "012", "fecha": "05-oct-2026", "hora": "08:15", "programa": "01",
     "programa_nombre": "Bowie & Dick", "resultado": "FALLO", "resultado_detalle": "Aire en la cámara (CIC-12)",
     "operador": "Ana Maria Rodriguez Villamizar", "no_conforme": False},
    {"id": 12, "numero": "013", "fecha": "05-oct-2026", "hora": "09:40", "programa": "01",
     "programa_nombre": "Bowie & Dick", "resultado": "COMPLETADO", "resultado_detalle": "",
     "operador": "Ana", "no_conforme": False},
    {"id": 13, "numero": "014", "fecha": "05-oct-2026", "hora": "11:02", "programa": "01",
     "programa_nombre": "Bowie & Dick", "resultado": "COMPLETADO", "resultado_detalle": "",
     "operador": "Luis", "no_conforme": True},
]


def _panel(idioma, estado="exito_fallo_previo"):
    return d.panel_dia({"fecha": "2026-10-05", "estado": estado}, idioma, _t, 3)


_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl, QMetaObject, QPoint, Qt, Q_ARG, Q_RETURN_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
import autoclave.ui_qml.bridge.i18n_qml  # registra I18n
from autoclave import i18n

cfg = json.load(open(sys.argv[3], encoding="utf-8"))
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
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_rep_calendario.qml"))
ventana = comp.createWithInitialProperties({"datos": cfg["datos"]})
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(250)

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
    QTest.qWait(60)

def jp(it, ruta):
    return QMetaObject.invokeMethod(ventana, "prop", Q_RETURN_ARG("QVariant"),
                                    Q_ARG("QVariant", it), Q_ARG("QVariant", ruta))

def senales():
    v = ventana.property("senales")
    return list(v.toVariant() if hasattr(v, "toVariant") else v)

def poner(it, nombre, valor):
    it.setProperty(nombre, valor)
    QTest.qWait(80)

def textos(raiz_item):
    out = []
    def rec(it):
        for h in it.childItems():
            if not h.isVisible():
                continue
            if h.inherits("QQuickText") and (h.property("text") or "").strip():
                out.append(h.property("text"))
            rec(h)
    rec(raiz_item)
    return out

def desbordes(raiz_item):
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
    property var senales: []
    function prop(it, ruta) {
        let v = it
        for (const p of ruta.split(".")) v = v[p]
        return (typeof v === "object" && v !== null && v.r !== undefined) ? ("" + v) : v
    }
    function anota(x) { senales = senales.concat([x]) }
    readonly property real esc: 1200 / 1196
    Binding { target: Escala; property: "factor"; value: 1 }

    CalendarioEjecucion {
        objectName: "calendario"
        x: 33 * ventana.esc; y: 40 * ventana.esc
        width: 760 * ventana.esc
        escala: ventana.esc
        calendario: ventana.datos.calendario
        diaElegido: ventana.datos.diaElegido
        puedeVerAnio: ventana.datos.puedeVerAnio
        onDiaTocado: (f) => ventana.anota("dia:" + f)
        onMesElegido: (n) => ventana.anota("mes:" + n)
        onProgramaElegido: (n) => ventana.anota("programa:" + n)
        onVerAnioPedido: ventana.anota("verAnio")
    }
    PanelDiaCalendario {
        objectName: "panel"
        x: 810 * ventana.esc; y: 40 * ventana.esc
        width: 360 * ventana.esc; height: 900 * ventana.esc
        escala: ventana.esc
        panel: ventana.datos.panel
        ciclos: ventana.datos.ciclos
        cargando: ventana.datos.cargando
        error: ventana.datos.error
        textoToque: ventana.datos.calendario.texto_toque_dia
        onCicloElegido: (c) => ventana.anota("ciclo:" + c.id)
    }
}
"""


def _correr(pasos, idioma="es", **datos):
    base = {"calendario": _cal_mes(idioma), "diaElegido": "", "puedeVerAnio": False,
            "panel": {}, "ciclos": [], "cargando": False, "error": ""}
    base.update(datos)
    cfg = {"idioma": idioma, "pasos": pasos, "datos": base}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    # los datos van por archivo: el año completo no cabe en la línea de comandos
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "cfg.json"
        ruta.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, str(RAIZ_QML), _QML, str(ruta)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=RAIZ, timeout=120, env=env)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RES=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[4:])


def _catalogo(clave, idioma):
    from autoclave import i18n
    i18n.cargar()
    return i18n.t(clave, idioma)


_PROHIBIDAS = re.compile(r"conform|\bapto|\bapta|compliant|\bfit for", re.I)

_PASOS_MES = r"""
cal = buscar("calendario")
r["leyenda"] = buscar("leyendaCalendario", cal).property("text")
r["titulo"] = buscar("periodoCalendario", cal).property("text")
r["conteo"] = [buscar("conteo_" + e, cal) is not None for e in ("exito", "sin_exito", "en_curso")]
r["selector"] = buscar("selectorProgramaCalendario", cal).property("numero")
r["boton_anio"] = buscar("botonVerAnio", cal).isVisible()
r["textos_cal"] = textos(cal)
r["alto_celda"] = buscar("dia_2026-10-01", cal).property("height")
r["ancho_celda"] = buscar("dia_2026-10-01", cal).property("width")
tocar(buscar("dia_2026-10-03", cal))
tocar(buscar("dia_2026-10-07", cal))      # futuro: no emite
r["senales"] = senales()
r["desbordes"] = desbordes(cal)
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_vista_de_mes_y_toque_de_dia(idioma):
    r = _correr(_PASOS_MES, idioma, calendario=_cal_mes(idioma))
    assert r["avisos"] == []
    assert r["leyenda"] == _t("reportes.cal_leyenda", idioma)          # DR-H01: tal como llega
    assert r["titulo"] == _cal_mes(idioma)["titulo"]
    assert r["conteo"] == [True, True, True]
    assert r["selector"] == 1
    assert r["boton_anio"] is False
    assert r["alto_celda"] >= 64 and r["ancho_celda"] >= 64             # zona táctil >= 64 px
    assert r["senales"] == ["dia:2026-10-03"]
    assert r["desbordes"] == []
    for t in r["textos_cal"]:
        assert not _PROHIBIDAS.search(t), t


_PASOS_DIA_ELEGIDO = r"""
cal = buscar("calendario")
poner(cal, "puedeVerAnio", True)
r["boton_anio"] = buscar("botonVerAnio", cal).isVisible()
tocar(buscar("botonVerAnio", cal))
r["senales"] = senales()
r["elegido"] = cal.property("diaElegido")
"""


def test_dia_elegido_y_boton_ver_anio():
    r = _correr(_PASOS_DIA_ELEGIDO, "es", diaElegido="2026-10-02", puedeVerAnio=False)
    assert r["avisos"] == []
    assert r["elegido"] == "2026-10-02"
    assert r["boton_anio"] is True and r["senales"] == ["verAnio"]


_PASOS_ANIO = r"""
cal = buscar("calendario")
r["meses"] = [buscar("mes_%d" % n, cal) is not None for n in range(1, 13)]
r["boton_anio"] = buscar("botonVerAnio", cal).isVisible()
r["vista_mes_visible"] = buscar("vistaMes", cal).isVisible()
r["vista_anio_visible"] = buscar("vistaAnio", cal).isVisible()
tocar(buscar("mes_10", cal))
tocar(buscar("mes_1", cal))               # deshabilitado: sin datos
tocar(buscar("mes_12", cal))              # deshabilitado: futuro
r["senales"] = senales()
r["desbordes"] = desbordes(cal)
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_vista_de_anio_12_miniaturas(idioma):
    r = _correr(_PASOS_ANIO, idioma, calendario=_cal_anio(idioma), puedeVerAnio=True)
    assert r["avisos"] == []
    assert r["meses"] == [True] * 12
    assert r["boton_anio"] is False                      # en el año no hay «Ver año»
    assert r["vista_mes_visible"] is False and r["vista_anio_visible"] is True
    assert r["senales"] == ["mes:10"]                    # solo el habilitado emite
    assert r["desbordes"] == []


_PASOS_VACIO = r"""
cal = buscar("calendario")
r["sin_programas"] = buscar("textoSinProgramas", cal).isVisible()
r["texto"] = buscar("textoSinProgramas", cal).property("text")
r["conteo_visible"] = buscar("conteoEstados", cal).isVisible()
r["vista_mes_visible"] = buscar("vistaMes", cal).isVisible()
r["selector"] = buscar("selectorProgramaCalendario", cal).property("numero")
r["desbordes"] = desbordes(cal)
"""


def test_sin_programas():
    r = _correr(_PASOS_VACIO, "es", calendario=_cal_vacio("es"))
    assert r["avisos"] == []
    assert r["sin_programas"] is True and r["texto"] == _t("reportes.cal_sin_programas", "es")
    assert r["conteo_visible"] is False and r["vista_mes_visible"] is False
    assert r["selector"] == 0
    assert r["desbordes"] == []


_PASOS_SELECTOR = r"""
cal = buscar("calendario")
sel = buscar("selectorProgramaCalendario", cal)
QMetaObject.invokeMethod(sel, "abrir")
QTest.qWait(80)
tocar(buscar("programa_3"))
r["senales"] = senales()
"""


def test_selector_de_programa_emite():
    r = _correr(_PASOS_SELECTOR, "es")
    assert r["avisos"] == []
    assert r["senales"] == ["programa:3"]


_PASOS_PANEL = r"""
panel = buscar("panel")
r["toque_visible"] = buscar("textoToqueDia", panel).isVisible()
r["toque"] = buscar("textoToqueDia", panel).property("text")
r["flick_visible"] = buscar("desplazablePanelDia", panel).isVisible()
"""


def test_panel_sin_dia_elegido():
    cal = _cal_mes("es")
    r = _correr(_PASOS_PANEL, "es", calendario=cal)
    assert r["avisos"] == []
    assert r["toque_visible"] is True and r["flick_visible"] is False
    assert r["toque"] == cal["texto_toque_dia"] == _t("reportes.cal_toque_dia", "es")


_PASOS_PANEL_CICLOS = r"""
panel = buscar("panel")
r["toque_visible"] = buscar("textoToqueDia", panel).isVisible()
r["fecha"] = buscar("fechaPanelDia", panel).property("text")
r["estado"] = buscar("estadoPanelDia", panel).property("text")
r["expl"] = buscar("explicacionPanelDia", panel).property("text")
r["n_intentos"] = [buscar("intento_%d" % i, panel) is not None for i in range(4)]
r["res"] = [buscar("resultadoIntento_%d" % i, panel).property("text") for i in range(3)]
r["textos"] = textos(panel)
r["desbordes"] = desbordes(panel)
tocar(buscar("intento_1", panel))
tocar(buscar("intento_0", panel))
r["senales"] = senales()
poner(panel, "cargando", True)
r["cargando_visible"] = buscar("cargandoPanelDia", panel).isVisible()
r["intento_con_carga"] = buscar("intento_0", panel) is None
poner(panel, "cargando", False)
poner(panel, "error", "No se pudo leer")
r["error_visible"] = buscar("errorPanelDia", panel).isVisible()
"""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_panel_con_ciclos(idioma):
    r = _correr(_PASOS_PANEL_CICLOS, idioma, calendario=_cal_mes(idioma), diaElegido="2026-10-05",
                panel=_panel(idioma), ciclos=_CICLOS)
    assert r["avisos"] == []
    assert r["toque_visible"] is False
    assert r["fecha"] == _panel(idioma)["titulo"] and r["estado"] == _panel(idioma)["estado_rotulo"]
    assert r["expl"] == _panel(idioma)["explicacion"]
    assert r["n_intentos"] == [True, True, True, False]
    # el NO CONFORME guardado cuenta como «sin éxito» (DR-D13) y nunca se rotula «conforme»
    assert r["res"][2] == _catalogo("reportes.estado_sin_exito", idioma)
    assert r["senales"] == ["ciclo:12", "ciclo:11"]
    assert r["cargando_visible"] is True and r["intento_con_carga"] is True
    assert r["error_visible"] is True
    assert r["desbordes"] == []
    for t in r["textos"]:
        assert not _PROHIBIDAS.search(t), t


# Trazabilidad (matriz REQ-37..REQ-50, dashboard de Reportes)
import pytest as _pytest  # noqa: E402

pytestmark = [_pytest.mark.req("REQ-43")]
