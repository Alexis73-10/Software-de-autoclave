# tests/test_login_qml_autenticacion.py
#
# Validación provisional del Login QML (enmienda de planeacion_nuevo_usuario.md,
# 2026-10-01): tocar "INICIAR SESIÓN" valida contra la tabla usuarios
# (LoginController), muestra el error en la tarjeta, vacía la contraseña tras
# cada intento y, al acertar, emite sesionIniciada(usuario, rol). Carga real a
# 1200x1920 con una base temporal, en subproceso para tener un QGuiApplication propio.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, pathlib, tempfile
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  da a los Item su tipo (mapToScene)
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401  registra los controladores
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos
    from autoclave.ui_qml.controllers import login_controller
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.ui_pyside.services.session_manager import SessionManager
    from autoclave.backend.contrasenas import hash_password

    db = DbManager(db_path=pathlib.Path(tempfile.mkdtemp()) / "t.db")
    db.crear_usuario("Ana Ruiz", "anar", hash_password("clave1234", 1000), "tecnico")
    login_controller._db_por_defecto = lambda: db

    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        property var textosJson: ({})
        Binding { target: Escala; property: "factor"; value: 1 }
        Item {
            anchors.fill: parent
            Login { objectName: "login"; anchors.fill: parent; teclado: panel; textosJson: parent.parent.textosJson }
            PanelTeclado { id: panel; objectName: "panelTeclado"; textosJson: parent.parent.textosJson }
        }
    }
    '''
    ruta = f"{QML_DIR}/_prueba_login_autenticacion.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties({"textosJson": cargar_textos()})
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        import os; os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(200)

    login = w.findChild(QObject, "login")
    boton = w.findChild(QObject, "botonIniciarSesion")
    mensaje = w.findChild(QObject, "mensajeLogin")
    sesiones = []
    login.sesionIniciada.connect(lambda u, rol: sesiones.append([u, rol]))

    def tocar(o, esperar=50):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(esperar)

    r = {"avisos": avisos, "mensaje_inicial_visible": mensaje.property("visible")}

    tocar(boton)
    r["vacios"] = {"texto": mensaje.property("text"), "visible": mensaje.property("visible")}

    login.setProperty("usuario", "anar"); login.setProperty("clave", "mala12345")
    tocar(boton)
    r["mala"] = {"texto": mensaje.property("text"), "clave": login.property("clave"),
                 "usuario": login.property("usuario"), "sesion": SessionManager.is_authenticated(),
                 "senales": list(sesiones)}

    login.setProperty("clave", "clave1234")
    tocar(boton)
    r["buena"] = {"texto": mensaje.property("text"), "clave": login.property("clave"),
                  "sesion": SessionManager.current_user()["usuario"] if SessionManager.current_user() else None,
                  "senales": list(sesiones)}
    print(json.dumps(r))
""")


@pytest.fixture(scope="module")
def salida():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": "src"}
    r = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=90)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_sin_mensaje_al_inicio(salida):
    assert salida["mensaje_inicial_visible"] is False


def test_campos_vacios(salida):
    assert salida["vacios"] == {"texto": "Ingrese usuario y contraseña", "visible": True}


def test_credenciales_malas(salida):
    m = salida["mala"]
    assert m["texto"] == "Usuario o contraseña incorrectos"
    assert m["clave"] == ""            # la contraseña no se queda en el campo
    assert m["usuario"] == "anar"      # el usuario sí, para reintentar
    assert m["sesion"] is False
    assert m["senales"] == []


def test_credenciales_buenas(salida):
    b = salida["buena"]
    assert b["sesion"] == "anar"
    assert b["senales"] == [["anar", "tecnico"]]
    assert b["clave"] == ""
    assert "Ana Ruiz" in b["texto"]    # aviso provisional mientras no hay pantalla destino
