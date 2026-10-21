# tests/test_u2_navegacion_qml.py
#
# U2 (tanda 2): navegación inferior uniforme con Main.qml real en subproceso.
# - Atrás regresa a la pantalla anterior; Home, a la principal según el estado;
# - preciclo sin Home, con el avatar en su lugar;
# - ninguna barra tiene un Salir que cierre la sesión.

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
    estado = {"paro": False, "es": {}}
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: estado["paro"] if f in ("PARO_EMERGENCIA", "PARO_REAL") else True  # U4
    ui.get_campo.side_effect = lambda c, d=None: (estado["es"] if c == "estado_seguro"
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
        for t in ("Login", "MenuPrincipal", "PantallaPreciclo"):
            if buscar(t) and visible(t):
                return t
        return "?"
    def panel_abierto():
        return any(o.property("visible") for o in buscar("PanelNotificaciones"))
    def fijar(paro=None, es=None):
        if paro is not None:
            estado["paro"] = paro
        if es is not None:
            estado["es"] = es
        puente.refrescar()
        esperar()
    def pila_profundidad():
        pila = [o for o in ventana.findChildren(QObject) if "StackView" in o.metaObject().className() or "StackView" in (o.metaObject().superClass().className() if o.metaObject().superClass() else "")]
        return pila[0].property("depth")
    def avatar():
        QMetaObject.invokeMethod(buscar("PantallaPreciclo")[-1], "avatarPulsado")
        esperar()

    def invocar(tipo, metodo):
        QMetaObject.invokeMethod(buscar(tipo)[-1], metodo)
        esperar()

    r = {}
    invocar("Reposo", "tocado")
    invocar("PantallaPreciclo", "ajustesPulsado")
    r["menu"] = pantalla()
    invocar("MenuPrincipal", "atrasPulsado")
    r["menu_atras"] = pantalla()
    invocar("PantallaPreciclo", "ajustesPulsado")
    invocar("MenuPrincipal", "iniciarSesionPulsado")
    r["login_desde_menu"] = pantalla()
    invocar("Login", "atrasPulsado")
    r["login_atras"] = pantalla()
    invocar("MenuPrincipal", "iniciarSesionPulsado")
    invocar("Login", "inicioPulsado")
    r["login_inicio"] = [pantalla(), len(buscar("MenuPrincipal"))]
    invocar("PantallaPreciclo", "ajustesPulsado")
    invocar("MenuPrincipal", "inicioPulsado")
    r["menu_inicio"] = pantalla()
    avatar()
    invocar("Login", "atrasPulsado")
    r["login_atras_desde_preciclo"] = [pantalla(), pila_profundidad()]
    r["avisos"] = avisos
    print(json.dumps(r))
""")


def test_atras_y_home_uniformes():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", cwd=_RAIZ, env=env, timeout=120)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("{")]
    assert linea, proc.stdout + proc.stderr
    r = json.loads(linea[-1])
    assert r.pop("avisos") == []
    assert r == {
        "menu": "MenuPrincipal",
        "menu_atras": "PantallaPreciclo",
        "login_desde_menu": "Login",
        "login_atras": "MenuPrincipal",          # Atrás: pantalla anterior
        "login_inicio": ["PantallaPreciclo", 0],  # Home: principal, sin el menú debajo
        "menu_inicio": "PantallaPreciclo",
        "login_atras_desde_preciclo": ["PantallaPreciclo", 2],   # reposo + principal
    }


_QML = _RAIZ / "src" / "autoclave" / "ui_qml" / "qml"


def test_preciclo_sin_home_y_con_el_avatar_en_su_lugar():
    texto = (_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    assert "casa.svg" not in texto and "inicioPulsado" not in texto
    # B1 (tanda 6): el avatar ocupa la celda derecha de la barra flotante, donde
    # estaba la casa (x 800..1128 de BarraInferiorMenu), y la barra oculta Inicio
    assert 'x: raiz.m(800); y: 0; width: raiz.m(1128 - 800)' in texto
    assert "personalizada: true" in texto


@pytest.mark.parametrize("qml", [
    "Componentes/BarraInferiorMenu.qml", "Pantallas/CambioClave.qml",
    "Pantallas/NuevoUsuario.qml", "Pantallas/Opciones.qml", "Pantallas/Login.qml",
    "Pantallas/MenuPrincipal.qml",
])
def test_ninguna_barra_cierra_la_sesion(qml):
    texto = (_QML / qml).read_text(encoding="utf-8")
    # Pedido del 2026-10-20: OPCIONES tiene botón explícito de cerrar sesión
    # (logout_icon en la celda central de la barra), por eso "cerrarSesion()"
    # ya no se prohíbe; el antiguo Salir (salirPulsado, puente.salir()) sigue vetado.
    for prohibido in ("salir_sesion.svg", "salirPulsado", "salirHabilitado",
                      "puente.salir()"):
        assert prohibido not in texto, (qml, prohibido)
