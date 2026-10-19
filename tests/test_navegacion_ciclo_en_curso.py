# tests/test_navegacion_ciclo_en_curso.py
#
# Navegación de la pantalla de ciclo en curso en Main.qml
# (planeacion_pantalla_ciclo_en_curso.md §9): entra cuando el backend reporta
# CICLO (no por el toque local de INICIAR CICLO), sale a la pantalla previa
# cuando la máquina deja CICLO, abre directamente si la UI arranca con la
# máquina ya en CICLO, y no navega con un estado desconocido.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"
ES_JSON = RAIZ_QML.parents[1] / "i18n" / "es.json"

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401  (singleton I18n)
    from PySide6.QtTest import QTest
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401

    qml_dir, es_json, inicial = sys.argv[1], sys.argv[2], sys.argv[3]
    app = QGuiApplication([])
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    estado = {"maquina": inicial}
    ui.get_estado_global.side_effect = lambda: estado["maquina"]
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    # LISTO_PARA_CICLO activo; sin paro (U1: el paro saca de las pantallas sin campana)
    ui.get_estado_flag.side_effect = lambda f: f != "PARO_EMERGENCIA"
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    engine.setInitialProperties({"puente": puente})
    engine.load(QUrl.fromLocalFile(qml_dir + "/Main.qml"))
    ventana = engine.rootObjects()[0]

    def visibles(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML") and o.property("visible")]

    def pantalla():
        QTest.qWait(700)   # transición del StackView
        if visibles("PantallaCicloEnCurso"): return "en_curso"
        if visibles("PantallaPreciclo"): return "preciclo"
        if visibles("Reposo"): return "arranque"
        return "?"

    def fijar(maquina):
        estado["maquina"] = maquina
        puente.refrescar()

    pasos = [("inicio", pantalla())]
    QMetaObject.invokeMethod([o for o in ventana.findChildren(QObject)
                              if o.metaObject().className().startswith("Reposo_QML")][0], "tocado")
    pasos.append(("toque", pantalla()))
    for maquina in sys.argv[4:]:
        fijar(maquina)
        pasos.append((maquina, pantalla()))
    print(json.dumps({"pasos": pasos, "avisos": avisos}))
""")


def _correr(inicial, *estados):
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(RAIZ_QML), str(ES_JSON), inicial, *estados],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=90,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_entra_al_iniciar_el_ciclo_y_sale_al_terminar():
    s = _correr("PREPARADO", "CICLO", "PREPARACION")
    assert s["avisos"] == []
    assert s["pasos"] == [
        ["inicio", "arranque"],
        ["toque", "preciclo"],
        ["CICLO", "en_curso"],
        ["PREPARACION", "preciclo"],
    ]


def test_arranca_con_la_maquina_ya_en_ciclo():
    # abre directamente la pantalla de ciclo en curso, sin pasar por el arranque
    s = _correr("CICLO")
    assert s["avisos"] == []
    assert s["pasos"] == [["inicio", "en_curso"], ["toque", "en_curso"]]


def test_estado_desconocido_no_saca_de_la_pantalla():
    s = _correr("CICLO", "DESCONOCIDO", "CICLO")
    assert s["pasos"][2:] == [["DESCONOCIDO", "en_curso"], ["CICLO", "en_curso"]]


def test_falla_tras_el_ciclo_vuelve_a_la_pantalla_previa():
    s = _correr("PREPARADO", "CICLO", "FALLA")
    assert s["pasos"][-1] == ["FALLA", "preciclo"]
