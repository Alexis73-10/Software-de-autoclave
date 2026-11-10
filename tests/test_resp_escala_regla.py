"""Tanda responsive (10-nov): regla de proyección del lienzo (Tema/Escala.qml).

- Tabla de tamaños (px físicos) y escalas de Windows (100 a 200 %): factor,
  ancho y alto del lienzo, orientación y escala física según la regla del
  informe (factor único = el lado que primero se llena; el lienzo crece en el
  otro eje hasta medir lo mismo que la ventana: sin franjas, decisión de
  Cristian). La escala física (factor x dpr) no depende de la escala de
  Windows para una misma resolución física.
- 1200x1920 y 1920x1200 al 100 %: exactamente factor 1, alto de diseño y sin
  márgenes táctiles (nada cambia respecto a dev).
- Ventana de 0x0, negativa, NaN o infinita y ventanas muy chicas: sin NaN ni
  saltos (factor 1 y alto de diseño con medidas inválidas; continuo y
  positivo en las chicas).
- Zonas táctiles: margenTactil da el mínimo min(44 px físicos, tamaño de
  diseño), nunca negativo, 0 a escala física >= 1.
- Las 4 raíces (Main, InstalacionVentana, ReposoInstalacionVentana,
  NuevoUsuarioHost) solo enlazan la regla de Escala (una sola implementación)
  y la ventana real la sigue en caliente al cambiar de tamaño y de escala.
"""

import json
import math
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"

# Tamaños de la tabla (px físicos): los del prompt, sus giros y proporciones
# 4:3, 5:4, 21:9 y 9:16
TAMANOS = [(1024, 600), (1280, 720), (1366, 768), (1440, 900), (1600, 900), (1920, 1080),
           (1920, 1200), (2560, 1440), (1024, 768), (1280, 1024), (2560, 1080), (3840, 2160),
           (600, 1024), (720, 1280), (768, 1366), (900, 1440), (1080, 1920), (1200, 1920),
           (1440, 2560), (768, 1024)]
ESCALAS = (1.0, 1.25, 1.5, 1.75, 2.0)

_SCRIPT = textwrap.dedent(r'''
    import json, sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    cfg = json.loads(sys.argv[1])
    app = QGuiApplication([])
    eng = QQmlEngine()
    eng.addImportPath(cfg["qml"])
    c = QQmlComponent(eng)
    c.setData(b"""
    import QtQuick
    import Tema
    QtObject {
        function medir(w, h, d) {
            Escala.dpr = d
            const f = Escala.factorPara(w, h)
            Escala.factor = f
            const r = {horizontal: Escala.esHorizontal(w, h), factor: f,
                       altoLienzo: Escala.altoLienzoPara(w, h), anchoLienzo: Escala.anchoLienzoPara(w, h),
                       anchoDiseno: Escala.anchoDisenoPara(w, h), altoDiseno: Escala.altoDisenoPara(w, h),
                       escalaFisica: Escala.escalaFisica, soportado: Escala.soportado(w, h, d),
                       margenes: {}}
            for (const lado of [10, 24, 28, 40, 44, 56, 88, 120])
                r.margenes[lado] = Escala.margenTactil(lado * f)
            return JSON.stringify(r)
        }
    }
    """, QUrl.fromLocalFile(cfg["qml"] + "/_resp_regla.qml"))
    o = c.create()
    assert o is not None, c.errorString()
    salida = {}
    for clave, (w, h, d) in cfg["casos"].items():
        salida[clave] = json.loads(o.medir(w, h, d))
    print("RESULTADO=" + json.dumps(salida))
''')


def _correr(casos: dict) -> dict:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    cfg = {"qml": str(QML), "casos": casos}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


def _logico(w, h, d):
    return w / d, h / d


@pytest.fixture(scope="module")
def tabla():
    casos = {}
    for (w, h) in TAMANOS:
        for d in ESCALAS:
            lw, lh = _logico(w, h, d)
            casos[f"{w}x{h}@{d}"] = (lw, lh, d)
    raros = {"cero": (0, 0, 1), "ancho_cero": (0, 1200, 1), "alto_cero": (1920, 0, 1),
             "negativo": (-5, -5, 1), "nan": (float("nan"), 1200, 1), "inf": (float("inf"), 1200, 1),
             "uno": (1, 1, 1), "chica_h": (160, 100, 1), "chica_v": (100, 160, 1),
             "dpr_cero": (1920, 1200, 0), "dpr_nan": (1920, 1200, float("nan"))}
    casos.update(raros)
    # json no admite NaN/inf por defecto en el otro lado: se pasan como tales
    return _correr(casos)


def _esperado(w, h):
    hz = w >= h
    dw, dh = (1920, 1200) if hz else (1200, 1920)
    f = min(w / dw, h / dh)
    return hz, f, max(dh, h / f)


@pytest.mark.parametrize("w,h", TAMANOS)
def test_tabla_de_tamanos_y_escalas(tabla, w, h):
    fisicas = []
    for d in ESCALAS:
        r = tabla[f"{w}x{h}@{d}"]
        lw, lh = _logico(w, h, d)
        hz, f, alto = _esperado(lw, lh)
        assert r["horizontal"] is hz
        assert r["factor"] == pytest.approx(f, rel=1e-12)
        assert r["altoLienzo"] == pytest.approx(alto, rel=1e-12)
        # el lienzo cabe entero en la ventana y llena al menos un lado
        assert r["factor"] * r["anchoDiseno"] <= lw + 1e-6
        assert r["factor"] * r["altoDiseno"] <= lh + 1e-6
        assert (abs(r["factor"] * r["anchoDiseno"] - lw) < 1e-6
                or abs(r["factor"] * r["altoDiseno"] - lh) < 1e-6)
        # sin franjas (decisión de Cristian): el lienzo mide lo mismo que la ventana
        assert r["factor"] * r["altoLienzo"] == pytest.approx(lh)
        assert r["factor"] * r["anchoLienzo"] == pytest.approx(lw)
        assert r["anchoLienzo"] >= r["anchoDiseno"] - 1e-9 and r["altoLienzo"] >= r["altoDiseno"] - 1e-9
        fisicas.append(r["escalaFisica"])
        for v in [r["factor"], r["altoLienzo"], r["anchoLienzo"], r["escalaFisica"], *r["margenes"].values()]:
            assert math.isfinite(v)
    # misma resolución física -> misma escala física a cualquier escala de Windows
    assert max(fisicas) - min(fisicas) < 1e-9
    assert all(tabla[f"{w}x{h}@{d}"]["soportado"] for d in ESCALAS)


@pytest.mark.parametrize("clave,factor,alto", [("1920x1200@1.0", 1.0, 1200.0), ("1200x1920@1.0", 1.0, 1920.0)])
def test_tamanos_de_diseno_exactos(tabla, clave, factor, alto):
    r = tabla[clave]
    assert r["factor"] == factor
    assert r["altoLienzo"] == alto
    assert r["anchoLienzo"] == (1920.0 if alto == 1200.0 else 1200.0)
    assert r["escalaFisica"] == 1.0
    assert all(m == 0 for m in r["margenes"].values())


def test_medidas_invalidas_sin_nan(tabla):
    for clave in ("cero", "ancho_cero", "alto_cero", "negativo", "nan", "inf"):
        r = tabla[clave]
        assert r["factor"] == 1.0, clave
        assert r["altoLienzo"] in (1200.0, 1920.0), clave
        assert r["anchoLienzo"] in (1200.0, 1920.0), clave
        assert all(m == 0 for m in r["margenes"].values()), clave
    for clave in ("uno", "chica_h", "chica_v"):
        r = tabla[clave]
        assert 0 < r["factor"] < 0.2 and math.isfinite(r["altoLienzo"])
        assert not r["soportado"]
    # dpr inválido: se toma 1
    for clave in ("dpr_cero", "dpr_nan"):
        assert tabla[clave]["escalaFisica"] == 1.0


def test_continuidad_sin_saltos():
    """Al achicar la ventana de a 1 px el factor varía poco (sin saltos), salvo el
    cambio de orientación, que es el único punto donde el lienzo cambia."""
    casos = {f"h{w}": (w, 600, 1.0) for w in range(900, 1300, 7)}
    casos.update({f"v{h}": (600, h, 1.0) for h in range(900, 1300, 7)})
    r = _correr(casos)
    for pref in ("h", "v"):
        serie = [r[k]["factor"] for k in sorted((k for k in r if k[0] == pref), key=lambda k: int(k[1:]))]
        saltos = [abs(a - b) for a, b in zip(serie, serie[1:])]
        assert max(saltos) < 0.02


def test_margen_tactil(tabla):
    # 1024x600 al 100 %: escala física 0,5; un botón de 56 de diseño (28 px)
    # llega a 44 físicos; uno de 120 (60 px) no se toca; uno de 24 llega a 24
    r = tabla["1024x600@1.0"]
    assert r["escalaFisica"] == pytest.approx(0.5)
    assert r["margenes"]["56"] == pytest.approx((44 - 28) / 2)
    assert r["margenes"]["120"] == 0
    assert r["margenes"]["24"] == pytest.approx((24 - 12) / 2)
    # misma resolución a 200 %: mismo margen en px físicos
    r2 = tabla["1024x600@2.0"]
    assert r2["margenes"]["56"] * 2 == pytest.approx(r["margenes"]["56"])
    for clave, r in tabla.items():
        assert all(m >= 0 for m in r["margenes"].values()), clave


RAICES = ("Main.qml", "InstalacionVentana.qml", "ReposoInstalacionVentana.qml", "NuevoUsuarioHost.qml")


@pytest.mark.parametrize("raiz", RAICES)
def test_las_raices_solo_enlazan_la_regla(raiz):
    texto = (QML / raiz).read_text(encoding="utf-8")
    assert "Escala.factorPara(" in texto and "Escala.anchoLienzoPara(" in texto and "Escala.altoLienzoPara(" in texto
    assert 'property: "dpr"' in texto and "Screen.devicePixelRatio" in texto
    # sin fórmulas propias de factor o alto del lienzo
    assert not re.search(r"Math\.(min|max)\([^)]*Escala\.(anchoDiseno|altoDiseno)", texto)
    # el lienzo de la raíz mide lo que la ventana (sin franjas)
    assert "Escala.px(Escala.anchoLienzo)" in texto and "Escala.px(Escala.altoLienzo)" in texto


_SCRIPT_CALIENTE = textwrap.dedent(r'''
    import json, sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge import i18n_qml
    i18n.cargar(); i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    salida = {}
    for raiz in ("Main.qml", "ReposoInstalacionVentana.qml", "InstalacionVentana.qml"):
        eng = QQmlApplicationEngine()
        eng.addImportPath(QML_DIR)
        eng.load(QUrl.fromLocalFile(QML_DIR + "/" + raiz))
        v = eng.rootObjects()[0]
        esc = eng.singletonInstance("Tema", "Escala")
        pasos = []
        for w, h in ((1200, 1920), (1920, 1200), (1280, 720), (720, 1280), (1600, 1200), (1920, 1200)):
            v.setProperty("width", w); v.setProperty("height", h)
            QTest.qWait(60)
            pasos.append({k: esc.property(k) for k in ("horizontal", "factor", "altoLienzo", "anchoLienzo", "dpr")})
        salida[raiz] = pasos
        v.close(); eng.deleteLater(); QTest.qWait(30)
    print("RESULTADO=" + json.dumps(salida))
''')


def test_las_raices_siguen_el_tamano_en_caliente():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_CALIENTE], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    r = json.loads(linea[len("RESULTADO="):])
    for raiz, pasos in r.items():
        assert [s["horizontal"] for s in pasos] == [False, True, True, False, True, True], raiz
        assert pasos[0]["factor"] == 1.0 and pasos[1]["factor"] == 1.0 and pasos[5]["factor"] == 1.0
        assert pasos[2]["factor"] == pytest.approx(0.6)
        assert pasos[3]["factor"] == pytest.approx(0.6)
        assert pasos[4]["factor"] == pytest.approx(1600 / 1920)
        assert all(s["dpr"] > 0 for s in pasos)
    for raiz, pasos in r.items():
        assert pasos[0]["altoLienzo"] == 1920 and pasos[1]["altoLienzo"] == 1200, raiz
        assert pasos[2]["anchoLienzo"] == pytest.approx(1280 / 0.6), raiz           # 16:9: crece a lo ancho
        assert pasos[3]["altoLienzo"] == pytest.approx(1280 / 0.6), raiz            # 9:16: crece a lo alto
        assert pasos[4]["altoLienzo"] == pytest.approx(1200 / (1600 / 1920)), raiz  # 4:3 horizontal
