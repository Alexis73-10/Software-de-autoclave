"""AJ-03 (ajustes 28-oct): globo de valores de la gráfica del ciclo. El nombre
de cada fila (TextoAjustable) se abrevia si no cabe hasta su valor; si ni el
abreviado cabe, el globo crece lo justo (mín. 220 del mockup) y sigue dentro de
la tarjeta. Nunca se recorta (D8-5.4). En la línea de
tests/test_u10a_textos_caben_qml.py: las 3 entradas más largas, valores «—» y
«-123.4 kPa», en es y en, a las escalas de las dos resoluciones del equipo."""

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

# Escalas de la tarjeta: 1024 px (banco) y 1200 px (lienzo de diseño)
ESCALAS = (1024 / 1200, 1.0)
IDIOMAS = ("es", "en")
# Cursor en el centro y en los extremos (el globo se corre para no salirse)
CURSORES = (0.0, 5.0, 10.0)

# Las tres filas más largas: nombre largo + sufijos «(monitoreo)» / «(sin registro)»
SERIES = [
    {"clave": "a", "entrada": "temp_drenaje_camara", "color": "#6599FC", "eje": "izquierdo",
     "unidad": "°C", "monitoreo": True, "registrada": True},
    {"clave": "b", "entrada": "pres_empaque_2", "color": "#9732DA", "eje": "derecho",
     "unidad": "kPa", "registrada": False},
    {"clave": "c", "entrada": "temp_2_camara", "color": "#00CCB0", "eje": "derecho",
     "unidad": "kPa", "monitoreo": True, "registrada": False},
]

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n

    qml_dir, qml, idioma, escalas, cursores, series, claves = sys.argv[1:8]
    from autoclave.ui_qml.app import _cargar_fuentes
    i18n.cargar()
    i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None        # sin backend: no cambia el idioma
    app = QGuiApplication([])
    _cargar_fuentes()                                   # anchos con la fuente real
    engine = QQmlEngine()
    engine.addImportPath(qml_dir)
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(engine)
    comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_aj03.qml"))
    ventana = comp.createWithInitialProperties({})
    assert ventana is not None, comp.errorString()
    ventana.show()
    QTest.qWait(100)
    grafica = [o for o in ventana.findChildren(QQuickItem) if o.objectName() == "graficaPrueba"][0]
    series = json.loads(series)
    grafica.setProperty("seriesEntradas", series)   # [] = las tres por omisión

    def caja(it):
        p = it.mapToItem(grafica, 0, 0)
        return [p.x(), p.y(), it.width(), it.height()]

    def hijos(padre, nombre):
        # árbol visual (las filas del Repeater no son hijas QObject del globo)
        out = []
        for h in padre.childItems():
            if h.objectName() == nombre:
                out.append(h)
            out.extend(hijos(h, nombre))
        return out

    casos = []
    for escala in json.loads(escalas):
        grafica.setProperty("escala", escala)
        grafica.setProperty("width", 1129 * escala)
        grafica.setProperty("height", 794 * escala)
        for valores in ("vacios", "llenos"):
            v = None if valores == "vacios" else -123.4
            datos = {"t_min": [float(t) for t in range(11)]}
            for c in json.loads(claves):
                datos[c] = [v] * 11
            grafica.setProperty("datos", datos)
            for cursor in json.loads(cursores):
                grafica.setProperty("cursorMin", cursor)
                QTest.qWait(30)
                globo = hijos(grafica, "globoGrafica")[0]
                filas = []
                for f in hijos(globo, "filaGlobo"):
                    n = hijos(f, "nombreFilaGlobo")[0]
                    val = hijos(f, "valorFilaGlobo")[0]
                    filas.append({"nombre": n.property("text"),
                                  "completo": n.property("textoCompleto"),
                                  "abreviado": n.property("textoAbreviado"),
                                  "desborda": n.property("desborda"),
                                  "truncado": n.property("truncated"),
                                  "nombre_caja": caja(n), "nombre_ancho": n.property("implicitWidth"),
                                  "valor": val.property("text"), "valor_caja": caja(val),
                                  "valor_ancho": val.property("implicitWidth")})
                hora = hijos(globo, "horaGlobo")[0]
                casos.append({"escala": escala, "valores": valores, "cursor": cursor,
                              "globo": caja(globo), "tarjeta": [grafica.width(), grafica.height()],
                              "hora_caja": caja(hora), "hora_ancho": hora.property("implicitWidth"),
                              "visible": globo.isVisible(), "filas": filas})
    print("RESULTADO=" + json.dumps({"casos": casos, "avisos": avisos[:20]}, ensure_ascii=False))
""")

_QML = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    width: 1200; height: 900; visible: true
    GraficaCiclo { objectName: "graficaPrueba"; ocultarCursorMs: 600000 }
}
"""


def _correr(idioma, series, claves):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), _QML, idioma, json.dumps(ESCALAS),
         json.dumps(CURSORES), json.dumps(series), json.dumps(claves)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        timeout=120, cwd=RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    out = json.loads(linea[0][len("RESULTADO="):])
    out["idioma"] = idioma
    return out


@pytest.fixture(scope="module", params=IDIOMAS)
def r(request):
    return _correr(request.param, SERIES, [s["clave"] for s in SERIES])


@pytest.fixture(scope="module", params=IDIOMAS)
def r_omision(request):
    return _correr(request.param, [], ["temp_camara", "temp_ref", "pres_camara"])


def test_series_por_omision_sin_lectura_caben_sin_ensanchar(r_omision):
    """Sin lectura («—»), las tres de siempre caben en los 220 del mockup; con
    «-123.4» el globo puede crecer (ver test_el_globo_crece_solo_lo_justo).
    Nunca se solapan con el valor."""
    assert r_omision["avisos"] == []
    for c in r_omision["casos"]:
        if c["valores"] == "vacios":
            assert abs(c["globo"][2] - 220 * c["escala"]) <= 1, c["globo"]
        for f in c["filas"]:
            assert not f["desborda"]
            assert f["nombre_caja"][0] + f["nombre_ancho"] + 8 * c["escala"] <= f["valor_caja"][0] + 0.5


def test_carga_sin_avisos(r):
    assert r["avisos"] == []


def test_se_ven_las_tres_filas_con_sus_sufijos(r):
    for c in r["casos"]:
        assert c["visible"] and len(c["filas"]) == 3
        completos = [f["completo"] for f in c["filas"]]
        if r["idioma"] == "es":
            # 28-oct (6f06dd0): la gráfica ya no lleva el sufijo «(monitoreo)»
            assert completos == ["Temperatura de drenaje de cámara",
                                 "Presión de empaque 2 (sin registro)",
                                 "Temperatura de cámara 2 (sin registro)"]
        for f in c["filas"]:
            assert f["abreviado"] and f["abreviado"] != f["completo"]


def test_ninguna_fila_desborda_ni_se_recorta(r):
    for c in r["casos"]:
        for f in c["filas"]:
            assert not f["desborda"] and not f["truncado"], (c["escala"], f)
            assert f["nombre"] in (f["completo"], f["abreviado"])


def test_nombre_y_valor_no_se_solapan(r):
    for c in r["casos"]:
        margen = 8 * c["escala"]
        for f in c["filas"]:
            der_nombre = f["nombre_caja"][0] + f["nombre_ancho"]
            assert der_nombre + margen <= f["valor_caja"][0] + 0.5, (c["escala"], f)


def test_valor_y_hora_dentro_del_globo(r):
    for c in r["casos"]:
        gx, _, gw, _ = c["globo"]
        for f in c["filas"]:
            assert f["valor_caja"][0] + f["valor_ancho"] <= gx + gw + 0.5, f
            assert f["nombre_caja"][0] >= gx
        assert c["hora_caja"][0] + c["hora_ancho"] <= gx + gw + 0.5


def test_el_globo_queda_dentro_de_la_tarjeta(r):
    for c in r["casos"]:
        gx, gy, gw, gh = c["globo"]
        ancho, alto = c["tarjeta"]
        assert gx >= 0 and gx + gw <= ancho + 0.5, c["globo"]
        assert gy >= 0 and gy + gh <= alto + 0.5


def test_el_globo_mide_al_menos_el_del_mockup(r):
    for c in r["casos"]:
        assert c["globo"][2] >= 220 * c["escala"] - 0.5


def test_el_globo_crece_solo_lo_justo(r):
    """Si creció, la fila más ancha (con el abreviado) lo llena: margen
    derecho de 9 px del mockup."""
    for c in r["casos"]:
        gx, _, gw, _ = c["globo"]
        if gw <= 220 * c["escala"] + 1:
            continue
        der = max(f["valor_caja"][0] + f["valor_ancho"] for f in c["filas"])
        assert abs(gx + gw - der - 9 * c["escala"]) <= 1.5
        holgura = min(f["valor_caja"][0] - 8 * c["escala"] - f["nombre_caja"][0] - f["nombre_ancho"]
                      for f in c["filas"])
        assert holgura <= 1.5, holgura


def test_se_abrevia_solo_si_no_cabe_el_completo(r):
    for c in r["casos"]:
        for f in c["filas"]:
            disponible = f["valor_caja"][0] - 8 * c["escala"] - f["nombre_caja"][0]
            if f["nombre"] == f["abreviado"]:
                continue
            assert f["nombre_ancho"] <= disponible + 0.5
