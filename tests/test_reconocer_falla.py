# Botón RECONOCER FALLA (T-16; planeacion_backend_autenticacion.md §5.9 y
# decisión 22): puente ComandoReconocerFalla y su presencia en la pantalla de
# preciclo de Main.qml (carga real en subproceso, offscreen): visible solo en
# FALLA y con datos vigentes, en el lugar de INICIAR CICLO; al tocarlo envía
# POST /fault/reset.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.bridge.comandos_falla import ComandoReconocerFalla

_RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


def _comando(estado="FALLA", conectado=True, ok=True):
    puente = MagicMock(connected=conectado, machineState=estado)
    ui = MagicMock()
    ui.reset_fault.return_value = ok
    return ComandoReconocerFalla(puente, ui, ejecutar=lambda t: t()), ui


def test_en_falla_envia_fault_reset():
    c, ui = _comando()
    c.reconocer()
    ui.reset_fault.assert_called_once_with()
    assert c.ocupado is False


@pytest.mark.parametrize("estado,conectado", [("PREPARADO", True), ("CICLO", True),
                                              ("FALLA", False)])
def test_fuera_de_falla_o_sin_conexion_no_envia(estado, conectado):
    c, ui = _comando(estado, conectado)
    c.reconocer()
    ui.reset_fault.assert_not_called()


def test_rechazo_del_backend_libera_el_boton():
    c, ui = _comando(ok=False)
    c.reconocer()
    assert c.ocupado is False


_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge.comandos_falla import ComandoReconocerFalla
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401

    qapp = QGuiApplication([])
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "FALLA"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.return_value = False
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 75.0}
    ui.reset_fault.return_value = True
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()
    comando = ComandoReconocerFalla(puente, ui, ejecutar=lambda t: t())

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "comandoFalla": comando})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.show()
    arranque = [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith("Reposo_QML")][0]
    QMetaObject.invokeMethod(arranque, "tocado")
    QTest.qWait(700)

    boton = ventana.findChild(QObject, "botonReconocerFalla")
    r = {"visible_en_falla": boton.property("visible")}
    pt = boton.mapToScene(boton.boundingRect().center()).toPoint()
    QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, pt)
    QTest.qWait(100)
    r["llamadas"] = ui.reset_fault.call_count
    ui.get_estado_global.return_value = "PREPARADO"
    puente.refrescar()
    QTest.qWait(100)
    r["visible_fuera"] = boton.property("visible")
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=120, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_boton_visible_en_falla_y_envia_el_reconocimiento(r):
    assert r["avisos"] == []
    assert r["visible_en_falla"] is True
    assert r["llamadas"] == 1


def test_boton_oculto_fuera_de_falla(r):
    assert r["visible_fuera"] is False
