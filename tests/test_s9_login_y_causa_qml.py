# tests/test_s9_login_y_causa_qml.py
#
# S9 (tanda 9): Main.qml y la tarjeta de estado seguro, carga real en
# subproceso (offscreen), mismo andamiaje que test_navegacion_sesion_qml.py.
# - D9-1.5: el login se permite siempre: con el paro activo el avatar abre el
#   login, y si el paro (o la confirmación pendiente) llega con el login a la
#   vista, NO se vuelve a la principal.
# - D9-1.2: con el estado seguro del arranque (causa "arranque") la tarjeta
#   dice "Arranque con la cámara no segura" y nunca "paro liberado"; con la
#   confirmación pendiente (causa "paro_liberado") sí sale el aviso del paro.

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
    import json
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

    def transporte(metodo, ruta, cuerpo, token, plazo):
        return 200, {"ok": True}

    qapp = QGuiApplication([])
    sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                          cierre_s=0.8, intervalo_ms=50)
    sesion_backend.instalar(sesion)
    puente_nu = NuevoUsuarioBridge(sesion=sesion)

    flags = {"LISTO_PARA_CICLO": False, "PARO_EMERGENCIA": False, "PARO_REAL": False}
    campos = {"estado_modulo_es": "ok", "no_abrir": True, "estado_seguro": {}}
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARACION"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: flags.get(f, False)
    ui.get_campo.side_effect = lambda k, d=None: campos.get(k, d)
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": None}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "sesion": sesion, "puenteNuevoUsuario": puente_nu})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.show()

    def buscar(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]
    def visible(tipo):
        return any(o.property("visible") for o in buscar(tipo))
    def esperar(ms=700):
        QTest.qWait(ms)
    def pantalla():
        for t in ("CambioClave", "NuevoUsuario", "Opciones", "Login", "PantallaPreciclo"):
            if buscar(t) and visible(t):
                return t
        return "?"
    def refrescar():
        puente.refrescar()
        esperar(300)
    def abrir_config():
        QMetaObject.invokeMethod(buscar("PantallaPreciclo")[0], "avatarPulsado")
        esperar()
    def volver():
        QMetaObject.invokeMethod(buscar("Login")[0], "inicioPulsado")
        esperar()
    def notas(nombre):
        return [o for o in ventana.findChildren(QObject, nombre) if o.property("visible")]
    def textos(nombre):
        return [str(o.property("texto")) for o in notas(nombre)]

    r = {}
    QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
    esperar()

    # D9-1.2: estado seguro del arranque (sin confirmación)
    campos["estado_seguro"] = {"activo": True, "requiere_confirmacion": False, "causa": "arranque"}
    refrescar()
    r["causa_arranque"] = textos("avisoCausaEstadoSeguro")
    r["paro_liberado_sin_paro"] = len(notas("avisoParoLiberado"))
    r["confirmar_visible_sin_paro"] = puente.estadoSeguroRequiereConfirmacion

    # D9-1.5: avatar con el estado seguro activo -> login
    abrir_config()
    r["login_con_estado_seguro"] = pantalla()
    volver()

    # D9-1.5: con el paro real activo, el avatar abre el login
    flags["PARO_EMERGENCIA"] = flags["PARO_REAL"] = True
    refrescar()
    abrir_config()
    r["login_con_paro"] = pantalla()
    volver()

    # el paro llega con el login a la vista: no se vuelve a la principal
    flags["PARO_EMERGENCIA"] = flags["PARO_REAL"] = False
    refrescar()
    abrir_config()
    flags["PARO_EMERGENCIA"] = flags["PARO_REAL"] = True
    refrescar()
    r["login_sigue_al_llegar_el_paro"] = pantalla()

    # el paro se libera: confirmación pendiente, el login sigue
    flags["PARO_EMERGENCIA"] = flags["PARO_REAL"] = False
    campos["estado_seguro"] = {"activo": True, "requiere_confirmacion": True,
                               "causa": "paro_liberado"}
    refrescar()
    r["login_sigue_con_confirmacion"] = pantalla()
    volver()
    r["paro_liberado_con_confirmacion"] = len(notas("avisoParoLiberado"))
    r["causa_con_confirmacion"] = textos("avisoCausaEstadoSeguro")
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r, ensure_ascii=False))
""")


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=180, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_causa_del_arranque_sin_paro_liberado(r):
    assert r["causa_arranque"] and r["causa_arranque"][0].startswith("Arranque con la cámara no segura")
    assert r["paro_liberado_sin_paro"] == 0
    assert r["confirmar_visible_sin_paro"] is False


def test_login_permitido_con_estado_seguro_y_con_paro(r):
    assert r["login_con_estado_seguro"] == "Login"
    assert r["login_con_paro"] == "Login"


def test_sin_vuelta_forzada_del_login(r):
    assert r["login_sigue_al_llegar_el_paro"] == "Login"
    assert r["login_sigue_con_confirmacion"] == "Login"


def test_confirmacion_tras_paro_real_muestra_paro_liberado(r):
    assert r["paro_liberado_con_confirmacion"] >= 1
    assert r["causa_con_confirmacion"] == []


def test_sin_avisos_nuevos_del_motor_qml(r):
    assert [a for a in r["avisos"] if "Binding loop" not in a] == [], r["avisos"]
