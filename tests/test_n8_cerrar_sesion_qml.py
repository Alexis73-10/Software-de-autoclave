# tests/test_n8_cerrar_sesion_qml.py
#
# N8 (tanda 8, D8-4.2): el botón Cerrar sesión de OPCIONES
# - invalida el token en el backend (POST /auth/logout con ese token);
# - lleva a la pantalla de LOGIN (no a Preciclo ni a Ciclo);
# - desde ese Login, Atrás y Home llevan a Preciclo o Ciclo según el estado;
# - un login correcto sigue el flujo normal (OPCIONES);
# - con cambios sin guardar, pide confirmación antes de cerrar.
# Main.qml real en subproceso offscreen, con un backend de sesión falso.
# Con TANDA8_CAPTURAS=1 guarda docs/informes/tanda8/capturas/n8/N8_1x_*.png.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]
_CAPTURAS = _RAIZ / "docs" / "informes" / "tanda8" / "capturas" / "n8"

_SCRIPT = textwrap.dedent(r"""
    import json, os, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import login_controller, teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
    from autoclave.ui.service_ui.session_manager import SessionManager
    from autoclave.ui_qml import sesion_backend

    estado, capturas = sys.argv[1], sys.argv[2]
    llamadas = []
    def transporte(metodo, ruta, cuerpo, token, plazo):
        llamadas.append([metodo, ruta, token])
        if ruta == "/auth/login":
            if cuerpo == {"usuario": "anar", "clave": "clave1234"}:
                n = sum(1 for l in llamadas if l[1] == "/auth/login")
                return 200, {"token": f"tok-{n}", "usuario": "anar", "nombre": "Ana Ruiz",
                             "rol": "tecnico", "debe_cambiar_clave": False}
            return 401, {"codigo": "credenciales_invalidas"}
        return 200, {"ok": True}
    sesion_ventana = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t())
    sesion_backend.instalar(sesion_ventana)

    qapp = QGuiApplication([])
    _cargar_fuentes()
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = estado
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: f not in ("PARO_EMERGENCIA", "PARO_REAL")
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
        for t in ("Login", "Opciones", "MenuPrincipal", "PantallaCicloEnCurso", "PantallaPreciclo"):
            if buscar(t) and visible(t):
                return t
        return "?"
    def capturar(nombre):
        if capturas:
            esperar(250)
            ventana.grabWindow().save(os.path.join(capturas, nombre))
    def profundidad():
        pila = [o for o in ventana.findChildren(QObject) if o.inherits("QQuickStackView")]
        return pila[0].property("depth") if pila else -1
    def entrar(acceso):
        QMetaObject.invokeMethod(buscar(origen)[-1], acceso); esperar()
    def iniciar_sesion():
        login = buscar("Login")[-1]
        login.setProperty("usuario", "anar"); login.setProperty("clave", "clave1234")
        QMetaObject.invokeMethod(login, "iniciarSesion"); esperar()
    def logouts():
        return [l[2] for l in llamadas if l[1] == "/auth/logout"]

    if estado != "CICLO":
        QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado"); esperar()
    origen = "PantallaCicloEnCurso" if estado == "CICLO" else "PantallaPreciclo"
    acceso = "ajustesPulsado" if estado == "CICLO" else "avatarPulsado"
    r = {}

    # 1) Cerrar sesión: token invalidado y pantalla de LOGIN
    entrar(acceso); iniciar_sesion()
    r["en_opciones"] = pantalla()
    capturar(f"N8_10_{estado}_opciones.png")
    QMetaObject.invokeMethod(buscar("Opciones")[-1], "cerrarSesion"); esperar()
    r["tras_cerrar"] = [pantalla(), SessionManager.is_authenticated(), logouts()]
    capturar(f"N8_11_{estado}_login_tras_cerrar_sesion.png")
    # Atrás del login -> principal según el estado (reposo + principal)
    QMetaObject.invokeMethod(buscar("Login")[-1], "atrasPulsado"); esperar()
    r["login_atras"] = [pantalla(), profundidad()]
    capturar(f"N8_12_{estado}_login_atras.png")

    # 2) Home del login -> principal
    entrar(acceso); iniciar_sesion()
    QMetaObject.invokeMethod(buscar("Opciones")[-1], "cerrarSesion"); esperar()
    QMetaObject.invokeMethod(buscar("Login")[-1], "inicioPulsado"); esperar()
    r["login_home"] = [pantalla(), profundidad(), logouts()]

    # 3) Login correcto desde ese Login -> flujo normal (OPCIONES)
    entrar(acceso); iniciar_sesion()
    QMetaObject.invokeMethod(buscar("Opciones")[-1], "cerrarSesion"); esperar()
    iniciar_sesion()
    r["login_de_nuevo"] = [pantalla(), SessionManager.is_authenticated(), len(buscar("Login"))]

    # 4) Con cambios sin guardar: confirma antes de cerrar
    op = buscar("Opciones")[-1]
    op.setProperty("cambiosPendientes", True)
    QMetaObject.invokeMethod(op, "cerrarSesion"); esperar()
    dialogo = op.findChild(QObject, "dialogoSalirOpciones")
    r["pide_confirmar"] = [dialogo.property("visible"), pantalla(), SessionManager.is_authenticated()]
    capturar(f"N8_13_{estado}_cerrar_sesion_con_cambios.png")
    QMetaObject.invokeMethod(dialogo, "descartado"); dialogo.setProperty("visible", False); esperar()
    r["cancelar"] = [pantalla(), SessionManager.is_authenticated()]
    QMetaObject.invokeMethod(op, "cerrarSesion"); esperar()
    QMetaObject.invokeMethod(dialogo, "confirmado"); esperar()
    r["confirmar"] = [pantalla(), SessionManager.is_authenticated(), len(logouts())]
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


def _correr(estado):
    capturas = ""
    if os.environ.get("TANDA8_CAPTURAS") == "1":
        _CAPTURAS.mkdir(parents=True, exist_ok=True)
        capturas = str(_CAPTURAS)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + str(_RAIZ)}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, estado, capturas], capture_output=True,
                          text=True, encoding="utf-8", env=env, timeout=180, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout[-3000:] + proc.stderr[-3000:]
    return json.loads(linea[0][len("RESULTADO="):])


@pytest.mark.parametrize("estado,origen", [("PREPARADO", "PantallaPreciclo"),
                                           ("CICLO", "PantallaCicloEnCurso")])
def test_cerrar_sesion_lleva_al_login(estado, origen):
    r = _correr(estado)
    assert r["avisos"] == []
    assert r["en_opciones"] == "Opciones"
    # token invalidado en el backend (logout con el token de esa sesión) y LOGIN
    assert r["tras_cerrar"] == ["Login", False, ["tok-1"]]
    assert r["login_atras"] == [origen, 2]
    assert r["login_home"] == [origen, 2, ["tok-1", "tok-2"]]
    assert r["login_de_nuevo"] == ["Opciones", True, 0]
    # cambios sin guardar: pregunta; cancelar conserva la sesión y OPCIONES
    assert r["pide_confirmar"] == [True, "Opciones", True]
    assert r["cancelar"] == ["Opciones", True]
    assert r["confirmar"] == ["Login", False, 4]
