# tests/test_ui_qml_app.py
#
# Punto de entrada QML (ui_qml/app.py): argumentos, elección de monitor, textos
# de es.json que usan las pantallas, y carga real de Main.qml -> Ciclo.qml con
# un UIServiceBackend simulado (en subproceso, para tener un QGuiApplication
# propio sin depender del QCoreApplication que crean otras pruebas).

import json
import logging
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml import app

RAIZ_QML = Path(app.__file__).resolve().parent / "qml"
ES_JSON = Path(app.__file__).resolve().parent / "assets" / "textos" / "es.json"


# ── argumentos y monitor ──────────────────────────────────────────────────

def test_argumentos_por_defecto():
    args = app.parse_args([])
    assert (args.door, args.screen) == (1, 0)


def test_argumentos_explicitos():
    args = app.parse_args(["--door", "2", "--screen", "1"])
    assert (args.door, args.screen) == (2, 1)


def test_sin_door_avisa_que_la_ventana_es_la_puerta_1(caplog):
    # --screen elige solo el monitor; la puerta no se deduce de él
    with caplog.at_level(logging.WARNING, logger=app.__name__):
        args = app.parse_args(["--screen", "1"])
    assert args.door == 1
    assert "Sin --door" in caplog.text


def test_door_invalida_se_rechaza():
    with pytest.raises(SystemExit):
        app.parse_args(["--door", "3"])


def test_elegir_pantalla_por_indice():
    assert app.elegir_pantalla(["A", "B"], 1, "A") == "B"


@pytest.mark.parametrize("indice", [2, -1])
def test_pantalla_inexistente_usa_la_primaria_y_avisa(indice, caplog):
    with caplog.at_level(logging.WARNING, logger=app.__name__):
        assert app.elegir_pantalla(["A", "B"], indice, "A") == "A"
    assert "no existe" in caplog.text


# ── textos ────────────────────────────────────────────────────────────────

def test_es_json_trae_todas_las_claves_que_usa_ciclo_qml():
    textos = json.loads(ES_JSON.read_text(encoding="utf-8"))
    qml = (RAIZ_QML / "Pantallas" / "Ciclo.qml").read_text(encoding="utf-8")
    usadas = re.findall(r'tx\("(\w+)",\s*"(\w+)"\)', qml)
    assert usadas, "Ciclo.qml debería leer sus textos con tx()"
    faltantes = [f"{s}.{c}" for s, c in usadas if not isinstance(textos.get(s, {}).get(c), str)]
    assert faltantes == []


def test_es_json_trae_los_doce_meses():
    textos = json.loads(ES_JSON.read_text(encoding="utf-8"))
    assert len(textos["fecha"]["meses"]) == 12


def test_cargar_textos_lee_es_json():
    assert app.cargar_textos(str(ES_JSON))["sistema"]["sin_conexion"]


# ── carga real de los .qml ────────────────────────────────────────────────

_SCRIPT_CARGA = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QUrl, QMetaObject
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401  (PanelTeclado)

    qml_dir, es_json, conectado, door = sys.argv[1], sys.argv[2], sys.argv[3] == "1", int(sys.argv[4])
    qapp = QGuiApplication([])

    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = conectado
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.side_effect = lambda n: {"Puerta 1": "CERRADO", "Puerta 2": "ABIERTO"}.get(n)
    ui.get_alarmas.return_value = [
        {"id": "PARO_EMERGENCIA", "level": "EMERGENCIA", "description": "Paro", "source_state": "PREPARADO"},
        {"id": "CHAQUETA_FRIA", "level": "FALLA", "description": "", "source_state": "PREPARADO"}]
    ui.get_estado_flag.return_value = True
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=door, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(qml_dir)
    engine.setInitialProperties({"puente": puente, "textosJson": json.load(open(es_json, encoding="utf-8"))})
    engine.load(QUrl.fromLocalFile(qml_dir + "/Main.qml"))
    ventana = engine.rootObjects()[0]

    def buscar(nombre_tipo):   # tipos QML: className() = "<Nombre>_QMLTYPE_<n>"
        from PySide6.QtCore import QObject
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(nombre_tipo + "_QML")]

    arranque = buscar("Arranque")[0]
    QMetaObject.invokeMethod(arranque, "tocado")
    for _ in range(5):
        qapp.processEvents()
    ciclo = buscar("Ciclo")[0]

    from PySide6.QtTest import QTest
    QMetaObject.invokeMethod(ciclo, "avatarPulsado")      # avatar -> login QML
    QTest.qWait(600)
    login_abre = len(buscar("Login")) == 1
    QMetaObject.invokeMethod(buscar("Login")[0], "inicioPulsado")   # casa -> principal
    QTest.qWait(600)
    login_regresa = len(buscar("Login")) == 0 and bool(ciclo.property("visible"))

    print(json.dumps({
        "login_abre": login_abre,
        "login_regresa": login_regresa,
        "avisos": avisos,
        "datosVigentes": ciclo.property("datosVigentes"),
        "puertaAbierta": ciclo.property("puertaAbierta"),
        "puerta": ciclo.property("puerta"),
        "conteoAlarmas": ciclo.property("conteoAlarmas"),
        "version": ciclo.property("version"),
        "cicloActivo": ciclo.property("cicloActivo"),
        "estadoTexto": ciclo.property("estadoTexto"),
    }))
""")


_SCRIPT_DOS_PANTALLAS = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.backend.actividad_ui import ActividadUI
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.bridge.standby import Standby
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401  (PanelTeclado)

    qml_dir, es_json = sys.argv[1], sys.argv[2]
    qapp = QGuiApplication([])

    class Reloj:
        t = 1000.0
        def __call__(self): return self.t
    reloj = Reloj()
    actividad = ActividadUI(reloj=reloj)          # "backend" común a las dos pantallas

    class Backend:
        def post(self, ruta, body=None):
            assert ruta == "/ui/activity"
            actividad.registrar()

    def pantalla():
        ui = MagicMock(spec=UIServiceBackend)
        ui.connected = True
        ui.get_estado_global.return_value = "PREPARADO"
        ui.get_alarmas.return_value = []
        ui.get_inactividad_ui.side_effect = actividad.inactividad_s
        ui.get_config_param.side_effect = lambda n: 5 if n == "tiempo_standby" else None
        standby = Standby(ui, Backend(), reloj=reloj, ejecutar=lambda t: t(), iniciar=False)
        engine = QQmlApplicationEngine()
        engine.addImportPath(qml_dir)
        engine.setInitialProperties({"standby": standby,
                                     "textosJson": json.load(open(es_json, encoding="utf-8"))})
        engine.load(QUrl.fromLocalFile(qml_dir + "/Main.qml"))
        ventana = engine.rootObjects()[0]
        ventana.installEventFilter(standby)
        ventana.show()
        return engine, standby, ventana

    a, b = pantalla(), pantalla()

    def evaluar_ambas():
        a[1].evaluar(); b[1].evaluar()
        QTest.qWait(700)                          # transición del StackView

    def en_ciclo(p):
        return any(o.metaObject().className().startswith("Ciclo_QML")
                   for o in p[2].findChildren(QObject))

    estados = []
    evaluar_ambas()
    estados.append(("inicio", en_ciclo(a), en_ciclo(b)))

    QTest.mouseClick(a[2], Qt.LeftButton, Qt.NoModifier, QPoint(300, 480))   # toque en la pantalla A
    evaluar_ambas()
    estados.append(("toque_en_A", en_ciclo(a), en_ciclo(b)))

    reloj.t += 299
    evaluar_ambas()
    estados.append(("4m59s", en_ciclo(a), en_ciclo(b)))

    reloj.t += 1
    evaluar_ambas()
    estados.append(("5min", en_ciclo(a), en_ciclo(b)))

    QTest.mouseClick(b[2], Qt.LeftButton, Qt.NoModifier, QPoint(300, 480))   # toque en la pantalla B
    evaluar_ambas()
    estados.append(("toque_en_B", en_ciclo(a), en_ciclo(b)))
    print(json.dumps(estados))
""")


def test_standby_simultaneo_en_dos_pantallas():
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT_DOS_PANTALLAS, str(RAIZ_QML), str(ES_JSON)],
        capture_output=True, text=True, encoding="utf-8", env=entorno, timeout=90,
    )
    assert r.returncode == 0, r.stderr
    estados = json.loads(r.stdout.strip().splitlines()[-1])
    assert estados == [
        ["inicio", False, False],        # ambas en arranque
        ["toque_en_A", True, True],      # un toque en A despierta A y B
        ["4m59s", True, True],
        ["5min", False, False],          # 5 min sin actividad: ambas al arranque
        ["toque_en_B", True, True],      # un toque en B despierta ambas
    ]


@pytest.mark.parametrize("conectado, door, puerta_abierta", [(True, 1, False), (False, 2, True)])
def test_main_qml_navega_a_ciclo_sin_avisos(conectado, door, puerta_abierta):
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    r = subprocess.run(
        [sys.executable, "-c", _SCRIPT_CARGA, str(RAIZ_QML), str(ES_JSON), "1" if conectado else "0", str(door)],
        capture_output=True, text=True, encoding="utf-8", env=entorno, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    salida = json.loads(r.stdout.strip().splitlines()[-1])
    assert salida["avisos"] == []
    assert salida["datosVigentes"] is conectado
    assert salida["puerta"] == door
    assert salida["puertaAbierta"] is puerta_abierta
    assert salida["conteoAlarmas"] == 2
    assert salida["version"] == "V: 1.0"
    assert salida["cicloActivo"] == "01"
    assert salida["login_abre"] is True
    assert salida["login_regresa"] is True
    assert salida["estadoTexto"] == "Listo"   # PREPARADO + LISTO_PARA_CICLO



def test_forzar_tema_claro_aunque_windows_este_en_oscuro():
    # Con Windows en modo oscuro, los controles estándar de Qt pintaban el
    # texto de los campos en blanco sobre blanco (Login). La plataforma
    # offscreen de las pruebas ignora el esquema de color, así que se
    # verifica la petición; el efecto se comprobó en Windows real.
    from unittest.mock import MagicMock
    from PySide6.QtCore import Qt
    qapp = MagicMock()
    app.forzar_tema_claro(qapp)
    qapp.styleHints.return_value.setColorScheme.assert_called_once_with(Qt.ColorScheme.Light)
