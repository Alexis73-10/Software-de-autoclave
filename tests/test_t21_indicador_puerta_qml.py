"""FC-11 (tanda 21, P3): Componentes/IndicadorPuerta.qml, indicador de una
puerta sin actuador en preciclo (docs/mis_plans/planeacion_fin_de_ciclo.md).

Carga real del componente, offscreen y en subproceso, en es y en, a las escalas
de las dos resoluciones del equipo (1024 y 1200 px de ancho sobre el lienzo de
1196 del mockup de preciclo). Comprueba:
- los tres estados (texto, colores, ícono presente o ausente);
- falla cerrada: «PUERTA CERRADA» solo con datos vigentes y "CERRADO" exacto;
  cualquier otro estado con dato es ABIERTA y sin dato es gris;
- que no hay ningún manejador de toque en el árbol ni señales de comando;
- que el texto cabe en la caja (298 x 110 escalada) en dos líneas, sin elide.
Offscreen MultiEffect no se dibuja: el color del ícono no se mide, solo la
fuente de la imagen y su visibilidad."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

pytestmark = pytest.mark.req("FC-11")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
ARCHIVO = RAIZ_QML / "Componentes" / "IndicadorPuerta.qml"

ESCALAS = (1024 / 1196, 1200 / 1196)
IDIOMAS = ("es", "en")
TEXTOS = {
    "es": {"cerrada": "PUERTA CERRADA", "abierta": "PUERTA ABIERTA", "sin_datos": "PUERTA —"},
    "en": {"cerrada": "DOOR CLOSED", "abierta": "DOOR OPEN", "sin_datos": "DOOR —"},
}
# (estadoPuerta, datosVigentes, modo esperado)
CASOS = [
    ("CERRADO", True, "cerrada"),
    ("ABIERTO", True, "abierta"),
    ("ABRIENDO", True, "abierta"),
    ("CERRANDO", True, "abierta"),
    ("ATRAPADA", True, "abierta"),
    ("ERROR", True, "abierta"),
    ("DESCONOCIDO", True, "abierta"),
    ("XYZ", True, "abierta"),
    ("cerrado", True, "abierta"),
    (" CERRADO", True, "abierta"),
    ("", True, "sin_datos"),
    ("CERRADO", False, "sin_datos"),
    ("ABIERTO", False, "sin_datos"),
    ("DESCONOCIDO", False, "sin_datos"),
    ("", False, "sin_datos"),
]

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)

    qml_dir, qml, idioma, escalas, casos = sys.argv[1:6]
    from autoclave.ui_qml.app import _cargar_fuentes
    i18n.cargar()
    i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None
    app = QGuiApplication([])
    _cargar_fuentes()
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t21_puerta.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(50)

    def buscar(padre, nombre):
        for h in padre.childItems():
            if h.objectName() == nombre:
                return h
            r = buscar(h, nombre)
            if r is not None:
                return r
        return None

    ind = [o for o in ventana.findChildren(QQuickItem) if o.objectName() == "indicadorPrueba"][0]
    texto = buscar(ind, "textoIndicadorPuerta")
    icono = buscar(ind, "iconoPuerta")
    imagen = buscar(ind, "imagenPuerta")
    fondo = buscar(ind, "fondoIndicadorPuerta")

    # clases de todo el árbol (ítems visuales y objetos hijos, p. ej. handlers)
    clases = sorted({o.metaObject().className() for o in ind.findChildren(QObject)}
                    | {ind.metaObject().className()})
    # señales propias del componente (por encima de QQuickItem)
    mo = ind.metaObject()
    base = QQuickItem.staticMetaObject.methodCount()
    senales = [bytes(mo.method(i).name()).decode() for i in range(base, mo.methodCount())
               if mo.method(i).methodType().name == "Signal"]

    tokens = {k: ventana.property(k).name() for k in
              ("cBarra", "cAdvFondo", "cAdv", "cAdvTexto", "cSutil", "cBorde", "cGuia")}

    res = []
    for escala in json.loads(escalas):
        ind.setProperty("width", 298 * escala)
        ind.setProperty("height", 110 * escala)
        for n in (1, 2):
            ind.setProperty("numeroPuerta", n)
            for estado, vigentes, _ in json.loads(casos):
                ind.setProperty("estadoPuerta", estado)
                ind.setProperty("datosVigentes", vigentes)
                QTest.qWait(5)
                res.append({
                    "escala": escala, "puerta": n, "estado": estado, "vigentes": vigentes,
                    "modo": ind.property("modo"), "cerrada": ind.property("cerrada"),
                    "texto": texto.property("text"),
                    "fondo": fondo.property("color").name(),
                    "borde": fondo.property("colorBordeAplicado").name(),
                    "colorTexto": texto.property("color").name(),
                    "colorFondo": ind.property("colorFondo").name(),
                    "colorBorde": ind.property("colorBorde").name(),
                    "radio": fondo.property("radius"),
                    "icono_visible": icono.isVisible(),
                    "imagen": imagen.property("source").toString(),
                    "imagen_estado": imagen.property("progress"),
                    "lineas": texto.property("lineCount"),
                    "truncado": texto.property("truncated"),
                    "max_lineas": texto.property("maximumLineCount"),
                    "pixel": texto.property("fontInfo").property("pixelSize").toInt(),
                    "pedido": texto.property("font").pixelSize(),
                    "negrita": texto.property("font").bold(),
                    "caja_texto": [texto.x(), texto.y(), texto.width(), texto.height()],
                    "contenido": [texto.property("contentWidth"), texto.property("contentHeight")],
                    "ind": [ind.width(), ind.height()],
                })
    print("RESULTADO=" + json.dumps({"casos": res, "avisos": avisos[:20], "clases": clases,
                                     "senales": senales, "tokens": tokens}, ensure_ascii=False))
""")

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 400; height: 200; visible: true
    property color cBarra: Colores.fondoBarraSuperior
    property color cAdvFondo: Colores.advertenciaFondo
    property color cAdv: Colores.advertencia
    property color cAdvTexto: Colores.advertenciaTexto
    property color cSutil: Colores.fondoSutil
    property color cBorde: Colores.bordeCampo
    property color cGuia: Colores.textoGuia
    IndicadorPuerta { objectName: "indicadorPrueba"; x: 10; y: 10 }
}
"""


def _correr(idioma):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML, idioma, json.dumps(ESCALAS),
         json.dumps(CASOS)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        timeout=120, cwd=RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    out = json.loads(linea[0][len("RESULTADO="):])
    out["idioma"] = idioma
    return out


@pytest.fixture(scope="module", params=IDIOMAS)
def r(request):
    return _correr(request.param)


def _esperado(estado, vigentes):
    return next(m for e, v, m in CASOS if e == estado and v == vigentes)


def test_carga_sin_avisos(r):
    assert r["avisos"] == []


def test_modo_y_texto_de_cada_estado(r):
    textos = TEXTOS[r["idioma"]]
    for c in r["casos"]:
        modo = _esperado(c["estado"], c["vigentes"])
        assert c["modo"] == modo, c
        assert c["texto"] == textos[modo], c


def test_nunca_cerrada_sin_cerrado_confirmado(r):
    for c in r["casos"]:
        if c["modo"] == "cerrada" or c["cerrada"]:
            assert c["estado"] == "CERRADO" and c["vigentes"], c
            assert c["texto"] == TEXTOS[r["idioma"]]["cerrada"]
        else:
            assert c["texto"] != TEXTOS[r["idioma"]]["cerrada"], c


def test_colores_de_cada_estado(r):
    t = r["tokens"]
    esperados = {
        "cerrada": ("#eaf1f8", t["cBarra"], t["cBarra"]),
        "abierta": (t["cAdvFondo"], t["cAdv"], t["cAdvTexto"]),
        "sin_datos": (t["cSutil"], t["cBorde"], t["cGuia"]),
    }
    for c in r["casos"]:
        fondo, borde, texto = esperados[c["modo"]]
        assert c["fondo"] == fondo and c["colorFondo"] == fondo, c
        assert c["colorBorde"] == borde, c
        assert c["borde"] == borde, c
        assert c["colorTexto"] == texto, c


def test_rectangulo_radio_14(r):
    for c in r["casos"]:
        assert c["radio"] == pytest.approx(14 * c["escala"]), c


def test_icono_segun_estado_y_numero_de_puerta(r):
    for c in r["casos"]:
        if c["modo"] == "sin_datos":
            assert not c["icono_visible"] and c["imagen"] == "", c
            continue
        assert c["icono_visible"], c
        nombre = ("close_door_" if c["modo"] == "cerrada" else "open_door_") + str(c["puerta"]) + ".png"
        assert c["imagen"].endswith("/images/" + nombre), c
        assert c["imagen_estado"] == 1.0, c   # cargada: el archivo existe


def test_texto_bold_22_cabe_en_dos_lineas_sin_recorte(r):
    for c in r["casos"]:
        assert c["negrita"], c
        assert c["pedido"] == round(22 * c["escala"]), c
        assert not c["truncado"], c
        assert 1 <= c["lineas"] <= 2, c
        x, _, w, h = c["caja_texto"]
        cw, ch = c["contenido"]
        assert cw <= w + 0.5 and ch <= h + 0.5, c
        assert x >= 0 and x + w <= c["ind"][0] + 0.5, c
        # a la escala del equipo cabe sin que Fit tenga que reducir la letra
        assert c["pixel"] == c["pedido"], c


def test_sin_manejadores_de_toque_en_el_arbol(r):
    prohibidas = ("MouseArea", "TapHandler", "MultiPointTouchArea", "PointHandler",
                  "DragHandler", "Flickable", "PinchArea", "WheelHandler", "HoverHandler")
    for clase in r["clases"]:
        assert not any(p in clase for p in prohibidas), r["clases"]


def test_no_expone_senales_de_comando(r):
    # solo las de cambio de propiedad que genera QML
    assert all(s.endswith("Changed") for s in r["senales"]), r["senales"]


def test_fuente_sin_manejadores_ni_senales():
    fuente = ARCHIVO.read_text(encoding="utf-8")
    codigo = "\n".join(l.split("//", 1)[0] for l in fuente.splitlines())
    for palabra in ("MouseArea", "TapHandler", "MultiPointTouchArea", "PointHandler",
                    "DragHandler", "signal ", "onClicked", "onPressed", "onTapped", "UiBridge",
                    "puente", "comandos", "gradient", "shadow", "maximumLineCount", "ElideRight"):
        assert palabra not in codigo, palabra


def test_claves_i18n_en_ambos_idiomas():
    for idioma, textos in TEXTOS.items():
        d = json.loads((RAIZ / "src" / "autoclave" / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        assert d["ciclo"]["puerta_cerrada_estado"] == textos["cerrada"]
        assert d["ciclo"]["puerta_abierta_estado"] == textos["abierta"]
        assert d["ciclo"]["puerta_sin_datos_estado"] == textos["sin_datos"]


def test_preciclo_alimenta_el_indicador_con_el_estado_del_modulo_es():
    """Cierre 1.0: con el módulo E/S desconectado o sin tramas válidas,
    /status.estado_puertas queda congelado; el indicador no debe afirmar
    «PUERTA CERRADA». datosVigentes exige conexión Y estadoModuloEs "ok"."""
    import re

    fuente = (RAIZ_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    codigo = "\n".join(l.split("//", 1)[0] for l in fuente.splitlines())
    m = re.search(r"IndicadorPuerta\s*\{(.*?)\n    \}", codigo, re.S)
    assert m, "no se encontró la instancia de IndicadorPuerta"
    cuerpo = m.group(1)
    asignacion = re.search(r"datosVigentes:\s*(.+)", cuerpo)
    assert asignacion, cuerpo
    expr = asignacion.group(1)
    assert "raiz.datosVigentes" in expr
    assert 'raiz.estadoModuloEs === "ok"' in expr
    assert "&&" in expr
