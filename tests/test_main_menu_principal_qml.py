# tests/test_main_menu_principal_qml.py
#
# Navegación real de Main.qml hacia el Menú Principal (planeacion_menu_principal_ui_qml.md,
# conexión aprobada por Cristian el 2026-10-02): el engranaje de la pantalla de
# preciclo y el de la de ciclo en curso abren el menú; su casa regresa a la
# pantalla de la que se vino; Iniciar sesión abre el login QML y la casa del
# login regresa al menú; el menú no tiene engranaje. Carga real en
# subproceso, offscreen.
# Revisión del 2026-10-02: Iniciar sesión abre el login QML (no la configuración PySide).
# Revisión del 2026-10-07 (planeacion_opciones_parametros_ciclo.md, U-18): el engranaje
# de la pantalla de ciclo en curso ya no abre el menú sino el login
# (tests/test_opciones_qml.py); aquí queda solo el de preciclo.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge.resumen_sistema import ResumenSistema
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401

    estado = sys.argv[1]   # "PREPARADO" -> preciclo; "CICLO" -> ciclo en curso
    qapp = QGuiApplication([])

    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = estado
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    # LISTO_PARA_CICLO activo; sin paro (U1: el paro saca de las pantallas sin campana)
    ui.get_estado_flag.side_effect = lambda f: f not in ("PARO_EMERGENCIA", "PARO_REAL")  # U4
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    backend = MagicMock()
    backend.get.return_value = {"ciclos_totales": 7, "ciclos_hoy": 2, "ultimo_ciclo": None}
    resumen = ResumenSistema(backend, ejecutar=lambda t: t())

    class Ajustes(QObject):
        def __init__(self):
            super().__init__(); self.veces = 0
        @Slot()
        def abrir(self): self.veces += 1
    ajustes = Ajustes()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "resumen": resumen, "ajustes": ajustes})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.show()

    def buscar(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]

    def visible(tipo):
        return any(o.property("visible") for o in buscar(tipo))

    def esperar():
        QTest.qWait(700)   # transición del StackView

    if estado != "CICLO":
        QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
        esperar()
    origen = "PantallaCicloEnCurso" if estado == "CICLO" else "PantallaPreciclo"
    r = {"origen_visible": visible(origen)}

    QMetaObject.invokeMethod(buscar(origen)[0], "ajustesPulsado")   # engranaje
    esperar()
    menus = buscar("MenuPrincipal")
    r["menu_abre"] = len(menus) == 1 and bool(menus[0].property("visible"))
    r["ajustes_tras_engranaje"] = ajustes.veces
    r["menu_sin_engranaje"] = ventana.findChild(QObject, "zonaEngranaje") is None
    r["resumen_sondeando"] = resumen.property("sondeando")
    r["ciclos_totales"] = resumen.property("ciclosTotales")
    # B1: Preciclo también tiene una BarraInferiorMenu (personalizada); se busca en la del menú
    r["inicio_activo"] = ventana.findChild(QObject, "barraInferiorMenu").findChild(QObject, "botonInicio").property("enabled")

    QMetaObject.invokeMethod(menus[0], "iniciarSesionPulsado")      # Iniciar sesión -> login QML
    esperar()
    r["ajustes_tras_sesion"] = ajustes.veces
    r["login_abre"] = len(buscar("Login")) == 1 and visible("Login")
    QMetaObject.invokeMethod(buscar("Login")[0], "atrasPulsado")    # U2: Atrás del login -> menú
    esperar()
    r["login_regresa_al_menu"] = len(buscar("Login")) == 0 and visible("MenuPrincipal")

    QMetaObject.invokeMethod(buscar("MenuPrincipal")[0], "inicioPulsado")   # casa -> de vuelta
    esperar()
    r["menu_cierra"] = len(buscar("MenuPrincipal")) == 0
    r["origen_regresa"] = visible(origen)
    r["resumen_detenido"] = not resumen.property("sondeando")
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.mark.parametrize("estado", ["PREPARADO"])
def test_engranaje_abre_el_menu_y_la_casa_regresa(estado):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, estado], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=90, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    r = json.loads(linea[0][len("RESULTADO="):])
    assert r["avisos"] == []
    assert r["origen_visible"] is True
    assert r["menu_abre"] is True
    assert r["ajustes_tras_engranaje"] == 0        # el engranaje ya no lanza la configuración PySide
    assert r["menu_sin_engranaje"] is True
    assert r["resumen_sondeando"] is True and r["ciclos_totales"] == "7"
    assert r["inicio_activo"] is True              # la casa regresa a la pantalla de origen
    assert r["ajustes_tras_sesion"] == 0           # Iniciar sesión ya no lanza PySide
    assert r["login_abre"] is True                 # ... abre el login QML
    assert r["login_regresa_al_menu"] is True
    assert r["menu_cierra"] is True
    assert r["origen_regresa"] is True
    assert r["resumen_detenido"] is True
