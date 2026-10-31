# tests/test_login_qml_autenticacion.py
#
# Login QML contra el backend REAL (T-8; plan_t8_login_qml.md §6.3): carga real
# de Login.qml a 1200x1920 en subproceso (QGuiApplication propio), con la sesión
# de la ventana apuntando a un TestClient de autoclave.backend.server sobre una
# BD SQLite temporal, y POST /auth/login en un hilo de trabajo real.
# Comprueba: mensajes por clave de es.json (campos vacíos, credenciales,
# bloqueo con cuenta regresiva m:ss), "Validando…" y botón deshabilitado
# mientras la petición está en vuelo, contraseña vaciada tras cada intento,
# sesión con token válido en el backend, cambio obligatorio de la semilla admin
# y registro en audit_log (login_ok, login_fallido).

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
    import json, pathlib, tempfile, threading
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  da a los Item su tipo (mapToScene)
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401  registra los controladores
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.cliente.session_manager import SessionManager
    from tests.test_contrato_autenticacion import _backend_real

    backend = _backend_real(pathlib.Path(tempfile.mkdtemp()))
    retener = threading.Event(); retener.set()   # limpiar() bloquea el siguiente login
    def transporte(metodo, ruta, cuerpo, token, plazo):
        retener.wait(5)
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
            Login { objectName: "login"; anchors.fill: parent; teclado: panel }
            PanelTeclado { id: panel; objectName: "panelTeclado" }
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
        engine.setInitialProperties({})
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        import os; os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(200)

    login = w.findChild(QObject, "login")
    control = w.findChild(QObject, "loginController")
    boton = w.findChild(QObject, "botonIniciarSesion")
    mensaje = w.findChild(QObject, "mensajeLogin")
    senales = []
    login.sesionIniciada.connect(lambda u, rol: senales.append(["sesion", u, rol]))
    login.cambioClaveRequerido.connect(lambda: senales.append(["cambio"]))

    def tocar(o):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(30)
        for _ in range(200):          # respuesta del hilo de trabajo
            if not control.property("ocupado"):
                break
            QTest.qWait(10)

    def intentar(usuario, clave):
        login.setProperty("usuario", usuario); login.setProperty("clave", clave)
        tocar(boton)
        return {"clave_msg": control.property("mensajeClave"), "texto": mensaje.property("text"),
                "campo_clave": login.property("clave"), "usuario": login.property("usuario"),
                "sesion": SessionManager.current_user()["usuario"] if SessionManager.current_user() else None}

    def eventos(nombre):
        from autoclave.backend import server
        return len(server.context.db.get_auditoria(evento=nombre, limite=100))

    r = {"avisos": avisos, "mensaje_inicial_visible": mensaje.property("visible")}
    tocar(boton)
    r["vacios"] = {"clave_msg": control.property("mensajeClave"), "texto": mensaje.property("text")}

    # en vuelo: Validando… y botón deshabilitado
    retener.clear()
    login.setProperty("usuario", "tec1"); login.setProperty("clave", "clave1234")
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, boton.mapToScene(boton.boundingRect().center()).toPoint())
    QTest.qWait(50)
    r["en_vuelo"] = {"texto": mensaje.property("text"), "puede": login.property("puedeIntentar"),
                     "opacidad": boton.property("opacity"), "ocupado": control.property("ocupado")}
    retener.set()
    for _ in range(200):
        if not control.property("ocupado"):
            break
        QTest.qWait(10)
    r["buena"] = {"sesion": SessionManager.current_user()["usuario"] if SessionManager.current_user() else None,
                  "clave": login.property("clave"), "senales": list(senales),
                  "token_valido": backend.get("/auth/sesion", headers={
                      "Authorization": f"Bearer {SessionManager.token()}"}).status_code == 200,
                  "login_ok": eventos("login_ok")}

    r["mala"] = intentar("tec1", "mala12345")
    r["mala"]["login_fallido"] = eventos("login_fallido")
    r["mala"]["senales"] = len(senales)

    for _ in range(4):
        intentar("bloq1", "mala")
    b = intentar("bloq1", "mala")
    b["bloqueado"] = control.property("bloqueado")
    b["tiempo"] = control.property("tiempoBloqueo")
    login.setProperty("usuario", "BLOQ1")
    b["puede_mismo"] = login.property("puedeIntentar")
    login.setProperty("usuario", "tec1")
    b["puede_otro"] = login.property("puedeIntentar")
    r["bloqueo"] = b

    senales.clear()
    r["admin"] = intentar("admin", "admin1234")
    r["admin"]["senales"] = list(senales)
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


def _texto(ruta, **valores):
    from autoclave import i18n
    seccion, clave = ruta.split(".", 1)
    texto = i18n.catalogo("es")[seccion][clave]
    for k, v in valores.items():
        texto = texto.replace("{" + k + "}", v)
    return texto


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_sin_mensaje_al_inicio(salida):
    assert salida["mensaje_inicial_visible"] is False


def test_campos_vacios(salida):
    assert salida["vacios"] == {"clave_msg": "sesion.campos_vacios",
                                "texto": _texto("sesion.campos_vacios")}


def test_validando_y_boton_deshabilitado_en_vuelo(salida):
    assert salida["en_vuelo"] == {"texto": _texto("sesion.validando"), "puede": False,
                                  "opacidad": 0.5, "ocupado": True}


def test_credenciales_buenas_contra_el_backend(salida):
    b = salida["buena"]
    assert b["sesion"] == "tec1"
    assert b["senales"] == [["sesion", "tec1", "tecnico"]]
    assert b["clave"] == ""
    assert b["token_valido"] is True
    assert b["login_ok"] == 1


def test_credenciales_malas(salida):
    m = salida["mala"]
    assert m["clave_msg"] == "sesion.credenciales_invalidas"
    assert m["texto"] == _texto("sesion.credenciales_invalidas")
    assert m["campo_clave"] == ""      # la contraseña no se queda en el campo
    assert m["usuario"] == "tec1"      # el usuario sí, para reintentar
    assert m["sesion"] is None
    # Tanda 17 (BIT-03, decisión de Cristian): login_fallido ya no va a audit_log
    assert m["login_fallido"] == 0
    assert m["senales"] == 1           # solo la del login bueno


def test_bloqueo_con_cuenta_regresiva(salida):
    b = salida["bloqueo"]
    assert b["clave_msg"] == "sesion.usuario_bloqueado"
    assert b["texto"] == _texto("sesion.usuario_bloqueado", tiempo="5:00")
    assert b["bloqueado"] is True and b["tiempo"] == "5:00"
    assert b["puede_mismo"] is False   # botón deshabilitado para el usuario bloqueado
    assert b["puede_otro"] is True     # el bloqueo es por usuario, como en el backend


def test_semilla_admin_pide_cambio_de_clave(salida):
    a = salida["admin"]
    assert a["senales"] == [["cambio"]]
    assert a["sesion"] == "Admin"   # U11: se escribe "admin", la cuenta es Admin
