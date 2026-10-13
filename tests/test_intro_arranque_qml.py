# tests/test_intro_arranque_qml.py
#
# Intro de arranque (qml/Pantallas/IntroArranque.qml) cargada de verdad dentro de
# Main.qml, en subproceso con QT_QPA_PLATFORM=offscreen (planeacion_animacion_arranque.md §10):
#   - arranque normal: intro de 3,5 s + salida de 1 s y relevo a la pantalla de reposo
#   - fallo bloqueante en t = 0,3 / 1,5 / 3,0 s: alarma en < 200 ms, intro congelada, sin relevo
#   - sin progreso: fallo de arranque al vencer el plazo
#   - sin progresoArranque inyectado (pruebas): no hay intro

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml import app

RAIZ_QML = Path(app.__file__).resolve().parent / "qml"
ES_JSON = Path(app.__file__).resolve().parent / "assets" / "textos" / "es.json"

_SCRIPT = textwrap.dedent(r"""
    import json, sys, time
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.bridge.progreso_arranque import SimuladorProgresoArranque
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401

    qml_dir, es_json, escenario = sys.argv[1], sys.argv[2], sys.argv[3]
    qapp = QGuiApplication([])

    etapas = [("iniciando_servicios", 0.2), ("conectando_tarjeta", 0.2),
              ("verificando_sensores", 0.2), ("abriendo_base_datos", 0.2)]
    sim = None
    if escenario != "sin_intro":
        sim = SimuladorProgresoArranque(etapas=etapas, sin_progreso=escenario == "sin_progreso")

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    props = {"textosJson": json.load(open(es_json, encoding="utf-8")), "versionSoftware": "1.0"}
    if sim is not None:
        props["progresoArranque"] = sim
    engine.setInitialProperties(props)
    engine.load(QUrl.fromLocalFile(qml_dir + "/Main.qml"))
    t0 = time.monotonic()
    ventana = engine.rootObjects()[0]
    ventana.show()
    if sim is not None:
        sim.iniciar()

    loader = ventana.findChild(QObject, "introArranque")
    alarma = ventana.findChild(QObject, "alarmaArranque")

    def hay(nombre_tipo):
        return any(o.metaObject().className().startswith(nombre_tipo + "_QML")
                   for o in ventana.findChildren(QObject))

    def esperar(cond, max_s):
        fin = time.monotonic() + max_s
        while not cond() and time.monotonic() < fin:
            QTest.qWait(10)
        return cond()

    r = {"avisos": avisos, "intro_activa": bool(loader.property("active"))}
    if escenario == "normal":
        intro = loader.property("item")
        pie = intro.findChild(QObject, "pieArranque")
        r["pie"] = pie.property("text")
        r["fin_intro"] = esperar(lambda: intro.property("t") >= 3.5, 6)
        r["t_intro"] = round(time.monotonic() - t0, 2)
        r["termino"] = esperar(lambda: not loader.property("active"), 4)
        r["t_total"] = round(time.monotonic() - t0, 2)
        r["reposo"] = hay("Arranque")
        r["alarma"] = bool(alarma.property("visible"))
    elif escenario.startswith("fallo:"):
        intro = loader.property("item")
        en = float(escenario.split(":")[1])
        QTest.qWait(int(en * 1000))
        t_fallo = time.monotonic()
        sim.declarar_fallo()
        r["alarma"] = esperar(lambda: alarma.property("visible"), 1)
        r["ms_alarma"] = round((time.monotonic() - t_fallo) * 1000)
        t_congelado = intro.property("t")
        QTest.qWait(1500)
        r["congelada"] = intro.property("t") == t_congelado
        QTest.qWait(3500)
        r["intro_sigue"] = bool(loader.property("active"))
    elif escenario == "sin_progreso":
        intro = loader.property("item")
        intro.setProperty("plazoSinProgresoMs", 400)   # 20 s en producción
        QTest.qWait(150)
        r["antes_del_plazo"] = bool(alarma.property("visible"))
        r["alarma"] = esperar(lambda: alarma.property("visible"), 2)
        r["sin_progreso"] = bool(intro.property("sinProgreso"))
    print(json.dumps(r))
""")


def _correr(escenario):
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), str(ES_JSON), escenario],
        capture_output=True, text=True, encoding="utf-8", env=entorno, timeout=90,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_arranque_normal_dura_3_5_s_mas_1_s_de_salida_y_pasa_al_reposo():
    r = _correr("normal")
    assert r["avisos"] == []
    assert r["intro_activa"] is True
    assert r["pie"] == "Software v1.0"     # sin modelo: solo la versión (D-07)
    assert r["fin_intro"] is True
    assert 3.4 <= r["t_intro"] <= 4.0      # holgura del entorno de pruebas; §10.1 se mide en el PC industrial
    assert r["termino"] is True
    assert 4.4 <= r["t_total"] <= 5.2
    assert r["reposo"] is True
    assert r["alarma"] is False


@pytest.mark.parametrize("en", ["0.3", "1.5", "3.0"])
def test_fallo_bloqueante_muestra_la_alarma_y_congela_la_intro(en):
    r = _correr(f"fallo:{en}")
    assert r["avisos"] == []
    assert r["alarma"] is True
    assert r["ms_alarma"] < 200
    assert r["congelada"] is True
    assert r["intro_sigue"] is True        # no pasa a reposo


def test_sin_progreso_declara_fallo_al_vencer_el_plazo():
    r = _correr("sin_progreso")
    assert r["avisos"] == []
    assert r["antes_del_plazo"] is False
    assert r["alarma"] is True
    assert r["sin_progreso"] is True


def test_sin_progreso_arranque_inyectado_no_hay_intro():
    r = _correr("sin_intro")
    assert r["avisos"] == []
    assert r["intro_activa"] is False
