# tests/test_u1_seguridad_navegacion_qml.py
#
# U1 (tanda 2): sin franja superior, el paro y la confirmación de estado seguro
# pendiente se ven en el panel de la campana. Main.qml real en subproceso:
# - en el login (sin campana), el paro vuelve a la pantalla principal, cuya
#   tarjeta de alarmas lo muestra (U4: el panel ya no se abre solo);
# - U4: la tarjeta desconectada (sin paro real) no saca del login ni abre nada;
# - con el paro activo, el avatar no deja una pantalla sin campana a la vista;
# - liberado el paro, la confirmación pendiente sigue a la vista en el panel;
# - ninguna pantalla monta la franja superior antigua (avisosSeguridad).

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
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401

    qapp = QGuiApplication([])
    estado = {"paro": False, "es": {}, "tarjeta": "ok", "sin_datos": False}
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: (
        estado["paro"] if f == "PARO_REAL"
        else (estado["paro"] or estado["sin_datos"]) if f == "PARO_EMERGENCIA" else True)
    ui.get_campo.side_effect = lambda c, d=None: (estado["es"] if c == "estado_seguro"
                                                  else estado["tarjeta"] if c == "estado_tarjeta"
                                                  else False if c == "no_abrir" else d)
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente})
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
        for t in ("Login", "PantallaPreciclo"):
            if buscar(t) and visible(t):
                return t
        return "?"
    def panel_abierto():
        return any(o.property("visible") for o in buscar("PanelNotificaciones"))
    def fijar(paro=None, es=None, tarjeta=None):
        if paro is not None:
            estado["paro"] = paro
        if es is not None:
            estado["es"] = es
        if tarjeta is not None:
            estado["tarjeta"] = tarjeta
            estado["sin_datos"] = tarjeta != "ok"
        puente.refrescar()
        esperar()
    def fila_preciclo(nombre):
        filas = [o for o in ventana.findChildren(QObject, nombre)
                 if any(p.objectName() == "seguridadPreciclo" for p in padres(o))]
        return any(o.property("visible") for o in filas)
    def padres(o):
        while o is not None:
            o = o.parent()
            if o is not None:
                yield o
    def avatar():
        QMetaObject.invokeMethod(buscar("PantallaPreciclo")[-1], "avatarPulsado")
        esperar()

    r = {}
    QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
    esperar()
    r["sin_franja"] = ventana.findChild(QObject, "avisosSeguridad") is None
    r["panel_cerrado_sin_paro"] = not panel_abierto()

    avatar()
    r["login"] = pantalla()
    fijar(tarjeta="desconectada")
    r["tarjeta_desconectada_no_mueve"] = [pantalla(), panel_abierto()]
    fijar(tarjeta="ok")
    fijar(paro=True)
    r["paro_vuelve"] = [pantalla(), panel_abierto(), fila_preciclo("filaParo")]

    avatar()
    r["avatar_con_paro"] = pantalla()

    fijar(paro=False, es={"activo": True, "requiere_confirmacion": True})
    r["confirmar_a_la_vista"] = [pantalla(), panel_abierto(),
                                 fila_preciclo("botonConfirmarEstadoSeguro")]
    fijar(es={"activo": False, "requiere_confirmacion": False})
    avatar()
    r["login_sin_aviso"] = pantalla()
    r["avisos"] = avisos
    print(json.dumps(r))
""")


def test_paro_y_confirmacion_quedan_a_la_vista_en_preciclo():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", cwd=_RAIZ, env=env, timeout=120)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("{")]
    assert linea, proc.stdout + proc.stderr
    r = json.loads(linea[-1])
    assert r.pop("avisos") == []
    assert r == {
        "sin_franja": True,
        "panel_cerrado_sin_paro": True,
        "login": "Login",
        "tarjeta_desconectada_no_mueve": ["Login", False],
        # S9 (tanda 9, D9-1.5): el login ya no se interrumpe con el paro ni
        # con la confirmación pendiente (antes volvía a Preciclo); la
        # confirmación sigue en la tarjeta de Preciclo y en la campana
        # (tests/test_s9_login_y_causa_qml.py)
        "paro_vuelve": ["Login", False, False],
        "avatar_con_paro": "Login",
        "confirmar_a_la_vista": ["Login", False, False],
        "login_sin_aviso": "Login",
    }
