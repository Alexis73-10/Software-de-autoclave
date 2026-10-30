# tests/test_l9_login_qml_recordar_olvido.py
#
# D9-12 (H9, tanda 9): Login.qml real a 1200x1920 en subproceso, contra el
# backend real (TestClient, BD temporal). Comprueba:
#   - "Recordar usuario": con un nombre recordado, el campo usuario llega
#     prellenado y la casilla marcada; tocar la casilla cambia el controlador;
#     entrar con la casilla marcada guarda solo el nombre; desmarcada lo borra;
#   - "¿Olvidó su contraseña?": un toque muestra la ayuda (restablecimiento por
#     un administrador o ingeniero), otro la oculta;
#   - sin avisos del motor QML.
# El archivo de preferencias se redirige a una carpeta temporal.

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
    import json, pathlib, tempfile
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401  registra los controladores
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.domain import recordar_usuario as ru
    from autoclave.cliente.session_manager import SessionManager
    from tests.test_contrato_autenticacion import _backend_real

    tmp = pathlib.Path(tempfile.mkdtemp())
    ruta_pref = tmp / "login_recordado.json"
    ru.ruta_por_defecto = lambda: ruta_pref   # nunca el data/ real
    ru.guardar("tec1", ruta_pref)

    backend = _backend_real(tmp / "bd")
    def transporte(metodo, ruta, cuerpo, token, plazo):
        cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
        r = backend.request(metodo, ruta, json=cuerpo, headers=cabeceras)
        return r.status_code, r.json()
    sesion_backend.instalar(sesion_backend.SesionVentana(transporte=transporte))

    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        id: ventana
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        Item {
            anchors.fill: parent
            Loader { id: carga; objectName: "carga"; anchors.fill: parent
                     sourceComponent: Login { objectName: "login"; teclado: panel } }
            PanelTeclado { id: panel; objectName: "panelTeclado" }
        }
    }
    '''
    ruta = f"{QML_DIR}/_prueba_login_l9.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        import os; os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(200)
    carga = w.findChild(QObject, "carga")

    def partes():
        return (w.findChild(QObject, "login"), w.findChild(QObject, "loginController"),
                w.findChild(QObject, "casillaRecordarUsuario"), w.findChild(QObject, "enlaceOlvidoClave"),
                w.findChild(QObject, "ayudaOlvidoClave"), w.findChild(QObject, "botonIniciarSesion"))

    def tocar(o):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(30)

    def esperar(control):
        for _ in range(300):
            if not control.property("ocupado"):
                break
            QTest.qWait(10)

    def recargar():
        carga.setProperty("active", False); QTest.qWait(30)
        carga.setProperty("active", True); QTest.qWait(150)
        return partes()

    r = {}
    login, control, casilla, enlace, ayuda, boton = partes()
    r["inicio"] = {"usuario": login.property("usuario"), "marcada": casilla.property("marcado"),
                   "ctrl": control.property("recordarUsuario"), "ayuda_visible": ayuda.property("visible")}

    tocar(enlace)
    r["ayuda1"] = {"visible": ayuda.property("visible"), "texto": ayuda.property("text")}
    tocar(enlace)
    r["ayuda2"] = ayuda.property("visible")

    tocar(casilla)
    r["tras_tocar"] = {"marcada": casilla.property("marcado"), "ctrl": control.property("recordarUsuario"),
                       "archivo": ru.cargar(ruta_pref)}   # aún no se toca el archivo
    tocar(casilla)   # vuelve a marcada

    # otro usuario, marcada: al entrar se recuerda ese nombre
    login.setProperty("usuario", "tec1"); login.setProperty("clave", "clave1234")
    tocar(boton); esperar(control)
    r["entrar_marcada"] = {"sesion": SessionManager.current_user()["usuario"] if SessionManager.current_user() else None,
                           "archivo": json.loads(ruta_pref.read_text(encoding="utf-8"))}
    SessionManager.logout()

    # desmarcada: al entrar se olvida; al reabrir, campo vacío y casilla desmarcada
    login, control, casilla, enlace, ayuda, boton = recargar()
    tocar(casilla)
    login.setProperty("usuario", "tec1"); login.setProperty("clave", "clave1234")
    tocar(boton); esperar(control)
    r["entrar_desmarcada"] = {"existe": ruta_pref.exists()}
    SessionManager.logout()
    login, control, casilla, enlace, ayuda, boton = recargar()
    r["reabrir"] = {"usuario": login.property("usuario"), "marcada": casilla.property("marcado")}
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def salida():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.pathsep.join([str(_RAIZ / "src"), str(_RAIZ)])}
    r = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120, cwd=_RAIZ)
    linea = [l for l in r.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, r.stdout + r.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def _texto(ruta):
    from autoclave import i18n
    seccion, clave = ruta.split(".", 1)
    return i18n.catalogo("es")[seccion][clave]


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_usuario_recordado_prellenado_y_casilla_marcada(salida):
    assert salida["inicio"] == {"usuario": "tec1", "marcada": True, "ctrl": True,
                                "ayuda_visible": False}


def test_olvido_muestra_y_oculta_la_ayuda(salida):
    assert salida["ayuda1"] == {"visible": True, "texto": _texto("sesion.ayuda_olvido_clave")}
    assert salida["ayuda2"] is False


def test_tocar_la_casilla_cambia_el_controlador_sin_escribir(salida):
    assert salida["tras_tocar"] == {"marcada": False, "ctrl": False, "archivo": "tec1"}


def test_entrar_marcada_guarda_solo_el_nombre(salida):
    assert salida["entrar_marcada"] == {"sesion": "tec1", "archivo": {"usuario": "tec1"}}


def test_entrar_desmarcada_olvida(salida):
    assert salida["entrar_desmarcada"] == {"existe": False}
    assert salida["reabrir"] == {"usuario": "", "marcada": False}
