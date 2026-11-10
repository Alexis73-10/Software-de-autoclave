"""Tanda responsive (10-nov): escala de Windows (DPI) y dos pantallas.

DPI: con la escala de Windows simulada (QT_SCALE_FACTOR, solo en el entorno
del subproceso) la ventana raíz recibe su tamaño en px LÓGICOS y la escala de
la pantalla en Escala.dpr; el lienzo ocupa la misma fracción de la pantalla
física (escala física = factor x dpr constante) a 100, 125, 150, 175 y 200 %.

Dos pantallas: cada pantalla es un proceso propio (exe_unico/doble_pantalla
lanzan `--rol ui --door N --screen I` y app.main carga UNA raíz en UN motor),
y los singletons QML son por motor: aun dos motores en el mismo proceso
(p. ej. el QQuickWidget de NuevoUsuarioHost en AutoclaveSettings) tienen cada
uno su Escala. No hay ventanas que se pisen el singleton.
"""

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"

_SCRIPT_DPI = textwrap.dedent(r'''
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
    fw, fh = int(sys.argv[1]), int(sys.argv[2])
    qapp = QGuiApplication([])
    eng = QQmlApplicationEngine()
    eng.addImportPath(QML_DIR)
    eng.load(QUrl.fromLocalFile(QML_DIR + "/ReposoInstalacionVentana.qml"))
    v = eng.rootObjects()[0]
    pantalla = qapp.primaryScreen()
    dpr = pantalla.devicePixelRatio()
    # como app.py: la ventana toma el tamaño (lógico) de la pantalla física fw x fh
    v.setProperty("width", round(fw / dpr)); v.setProperty("height", round(fh / dpr))
    v.show(); QTest.qWait(150)
    esc = eng.singletonInstance("Tema", "Escala")
    print("RESULTADO=" + json.dumps({"dpr": dpr, "dpr_escala": esc.property("dpr"),
                                     "ancho": v.property("width"), "alto": v.property("height"),
                                     "factor": esc.property("factor"),
                                     "escalaFisica": esc.property("escalaFisica")}))
''')


def _dpi(escala: float, fw: int, fh: int) -> dict:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": f"{escala:g}",
           "QT_ENABLE_HIGHDPI_SCALING": "1", "QT_SCALE_FACTOR_ROUNDING_POLICY": "PassThrough",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    env.pop("QT_SCREEN_SCALE_FACTORS", None)
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_DPI, str(fw), str(fh)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


@pytest.mark.parametrize("fw,fh", [(1920, 1080), (1200, 1920)])
def test_la_escala_de_windows_se_compensa(fw, fh):
    medidas = {e: _dpi(e, fw, fh) for e in (1.0, 1.25, 1.5, 1.75, 2.0)}
    for e, m in medidas.items():
        assert m["dpr"] == pytest.approx(e)
        assert m["dpr_escala"] == pytest.approx(e)          # la raíz enlaza Escala.dpr
        assert m["ancho"] == round(fw / e)
    fisicas = [m["escalaFisica"] for m in medidas.values()]
    # la misma fracción de la pantalla física (redondeo del tamaño lógico a px enteros)
    assert max(fisicas) - min(fisicas) < 2e-3
    assert medidas[1.5]["factor"] == pytest.approx(medidas[1.0]["factor"] / 1.5, rel=2e-3)


def test_cada_pantalla_es_un_proceso_con_un_motor():
    exe = (SRC / "exe_unico.py").read_text(encoding="utf-8")
    assert '_cmd_propio("--rol", "ui", "--door", str(p), "--screen", str(m)) for p, m in pantallas' in exe
    assert "subprocess.Popen(cmd" in exe
    doble = (SRC / "ui_qml" / "doble_pantalla.py").read_text(encoding="utf-8")
    assert '"-m", "autoclave.ui_qml.app", "--door", str(puerta), "--screen", str(monitor)' in doble
    # app.main y los dos caminos sin perfil: un QQmlApplicationEngine y una raíz cada uno
    arbol = ast.parse((SRC / "ui_qml" / "app.py").read_text(encoding="utf-8"))
    for f in [n for n in arbol.body if isinstance(n, ast.FunctionDef)
              and n.name in ("main", "_abrir_instalacion", "_abrir_reposo_instalacion")]:
        fuente = ast.get_source_segment((SRC / "ui_qml" / "app.py").read_text(encoding="utf-8"), f)
        assert fuente.count("QQmlApplicationEngine()") == 1, f.name
        assert fuente.count("engine.load(") == 1, f.name
    # Ajustes (NuevoUsuarioHost) es otro proceso, con el motor de su QQuickWidget
    lanzador = (SRC / "ui_qml" / "bridge" / "lanzador_ajustes.py").read_text(encoding="utf-8")
    assert "self._popen(comando_ajustes()" in lanzador


_SCRIPT_MOTORES = textwrap.dedent(r'''
    import json
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
    motores = []
    for w, h in ((1200, 1920), (1280, 720)):
        eng = QQmlApplicationEngine()
        eng.addImportPath(QML_DIR)
        eng.load(QUrl.fromLocalFile(QML_DIR + "/ReposoInstalacionVentana.qml"))
        v = eng.rootObjects()[0]
        v.setProperty("width", w); v.setProperty("height", h)
        motores.append(eng)
    QTest.qWait(100)
    print("RESULTADO=" + json.dumps([{k: e.singletonInstance("Tema", "Escala").property(k)
                                      for k in ("horizontal", "factor")} for e in motores]))
''')


def test_dos_motores_no_comparten_escala():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_MOTORES], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    a, b = json.loads(linea[len("RESULTADO="):])
    assert a == {"horizontal": False, "factor": 1.0}
    assert b["horizontal"] is True and b["factor"] == pytest.approx(0.6)
