# tests/test_navegacion_sesion_qml.py
#
# Navegación de Main.qml con la sesión de la ventana (T-8; plan_t8_login_qml.md
# §3.3-§3.7, §4): carga real en subproceso, offscreen, con un backend de sesión
# falso que registra las peticiones. Cubre:
# - login con cambio obligatorio -> CAMBIAR CONTRASEÑA -> OPCIONES;
# - abandonar el cambio -> logout y pantalla principal;
# - 429 en el cambio -> Login con el bloqueo y su cuenta regresiva;
# - OPCIONES › Usuarios -> Nuevo usuario a pantalla completa; "<" vuelve a Usuarios;
# - sin conexión con token en uso: aviso con cuenta regresiva; reconexión antes
#   del plazo con GET /auth/sesion 200 (sigue) o 401 (Login); plazo vencido ->
#   principal y logout al volver; en el cambio obligatorio -> Login sin enviar nada;
# - HIBERNACION -> logout y pantalla principal;
# - inactividad de la sesión (SAF-01) -> logout y pantalla principal.

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
    from autoclave.ui_qml.app import QML_DIR, cargar_textos
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_pyside.services.session_manager import SessionManager
    from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

    USUARIOS = {"admin": ("admin1234", True), "adm1": ("clave1234", False)}
    llamadas = []
    respuestas = {"cambio": (200, {"ok": True}), "sesion": (200, {"usuario": "adm1", "rol": "admin"})}

    def transporte(metodo, ruta, cuerpo, token, plazo):
        llamadas.append([metodo, ruta, token])
        if ruta == "/auth/login":
            u = cuerpo["usuario"]
            if u in USUARIOS and USUARIOS[u][0] == cuerpo["clave"]:
                return 200, {"token": f"tok-{u}-{len(llamadas)}", "usuario": u, "nombre": u,
                             "rol": "admin", "debe_cambiar_clave": USUARIOS[u][1]}
            return 401, {"codigo": "credenciales_invalidas"}
        if ruta == "/auth/change_password":
            return respuestas["cambio"]
        if ruta == "/auth/sesion":
            return respuestas["sesion"]
        return 200, {"ok": True}

    qapp = QGuiApplication([])
    sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                          cierre_s=0.8, intervalo_ms=50)
    sesion_backend.instalar(sesion)
    puente_nu = NuevoUsuarioBridge(sesion=sesion)

    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.return_value = True
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "textosJson": cargar_textos(),
                                 "sesion": sesion, "puenteNuevoUsuario": puente_nu})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.show()

    def buscar(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]
    def visible(tipo):
        return any(o.property("visible") for o in buscar(tipo))
    def hijo(nombre):
        return ventana.findChild(QObject, nombre)
    def esperar(ms=700):
        QTest.qWait(ms)
    def pantalla():
        for t in ("CambioClave", "NuevoUsuario", "Opciones", "Login", "PantallaPreciclo"):
            if buscar(t) and visible(t):
                return t
        return "?"
    def rutas():
        return [r for _, r, _ in llamadas]
    def conexion(valor):
        ui.connected = valor
        puente.refrescar()
        QTest.qWait(80)
    def abrir_config():
        QMetaObject.invokeMethod(buscar("PantallaPreciclo")[0], "avatarPulsado")
        esperar()
    def entrar(usuario, clave):
        abrir_config()
        login = buscar("Login")[0]
        login.setProperty("usuario", usuario)
        login.setProperty("clave", clave)
        QMetaObject.invokeMethod(login, "iniciarSesion")
        esperar()
    def cambiar_clave():
        c = buscar("CambioClave")[0]
        for k, v in (("clave_actual", "admin1234"), ("clave_nueva", "nueva12345"),
                     ("confirmacion", "nueva12345")):
            c.setProperty(k, v)
        QMetaObject.invokeMethod(c, "cambiar")
        esperar()

    r = {}
    QMetaObject.invokeMethod(buscar("Arranque")[0], "tocado")
    esperar()

    # cambio obligatorio -> OPCIONES -> Nuevo usuario
    entrar("admin", "admin1234")
    r["cambio_abre"] = pantalla()
    r["titulo_cambio"] = hijo("tituloCambioClave").property("text")
    cambiar_clave()
    r["tras_cambio"] = pantalla()
    r["pendiente_tras_cambio"] = SessionManager.debe_cambiar_clave()
    QMetaObject.invokeMethod(buscar("Opciones")[0], "nuevoUsuarioPulsado")
    esperar()
    r["nuevo_usuario"] = pantalla()
    QMetaObject.invokeMethod(buscar("NuevoUsuario")[0], "pulsarAtras")
    esperar()
    r["atras"] = [pantalla(), buscar("Opciones")[0].property("seccionActiva")]

    # sin conexión con OPCIONES a la vista: aviso; reconexión con 200
    conexion(False)
    r["aviso"] = [hijo("avisoSinConexionSesion").property("visible"),
                  hijo("cuentaRegresivaSesion").property("text")]
    conexion(True)
    r["reconecta_200"] = [hijo("avisoSinConexionSesion").property("visible"), pantalla(),
                          SessionManager.is_authenticated(), rutas().count("/auth/sesion")]

    # plazo vencido: principal; al volver, logout
    conexion(False)
    esperar(2000)
    r["cierre"] = [pantalla(), SessionManager.is_authenticated()]
    antes = rutas().count("/auth/logout")
    conexion(True)
    r["logout_al_volver"] = rutas().count("/auth/logout") - antes

    # reconexión con 401 -> Login
    entrar("adm1", "clave1234")
    respuestas["sesion"] = (401, {"codigo": "sesion_invalida"})
    conexion(False)
    conexion(True)
    esperar()
    r["reconecta_401"] = [pantalla(), SessionManager.is_authenticated(),
                          buscar("Login")[0].findChild(QObject, "loginController").property("mensajeClave")]
    respuestas["sesion"] = (200, {"usuario": "adm1", "rol": "admin"})
    QMetaObject.invokeMethod(buscar("Login")[0], "inicioPulsado")
    esperar()

    # HIBERNACION -> logout y principal
    entrar("adm1", "clave1234")
    antes = rutas().count("/auth/logout")
    ui.get_estado_global.return_value = "HIBERNACION"
    puente.refrescar()
    esperar()
    r["hibernacion"] = [pantalla(), SessionManager.is_authenticated(),
                        rutas().count("/auth/logout") - antes]
    ui.get_estado_global.return_value = "PREPARADO"
    puente.refrescar()
    esperar()

    # cambio obligatorio sin conexión -> Login, token descartado sin enviar nada
    entrar("admin", "admin1234")
    n = len(llamadas)
    conexion(False)
    esperar(2000)
    r["cambio_sin_conexion"] = [pantalla(), SessionManager.is_authenticated()]
    conexion(True)
    r["cambio_sin_conexion_llamadas"] = len(llamadas) - n
    QMetaObject.invokeMethod(buscar("Login")[0], "inicioPulsado")
    esperar()

    # 429 en el cambio -> Login con el bloqueo
    entrar("admin", "admin1234")
    respuestas["cambio"] = (429, {"codigo": "usuario_bloqueado", "segundos_restantes": 120})
    cambiar_clave()
    control = buscar("Login")[0].findChild(QObject, "loginController") if buscar("Login") else None
    r["bloqueo_cambio"] = [pantalla(), SessionManager.is_authenticated(),
                           control.property("mensajeClave") if control else "",
                           control.property("tiempoBloqueo") if control else ""]
    QMetaObject.invokeMethod(buscar("Login")[0], "inicioPulsado")
    esperar()

    # abandonar el cambio -> logout y principal
    respuestas["cambio"] = (200, {"ok": True})
    entrar("admin", "admin1234")
    antes = rutas().count("/auth/logout")
    QMetaObject.invokeMethod(buscar("CambioClave")[0], "abandonar")
    esperar()
    r["abandonar"] = [pantalla(), SessionManager.is_authenticated(),
                      rutas().count("/auth/logout") - antes]

    # inactividad (SAF-01; plazo reducido): OPCIONES -> principal con logout
    entrar("adm1", "clave1234")
    antes = rutas().count("/auth/logout")
    sesion._inactividad_s = 0.3
    esperar(1500)
    r["inactividad"] = [pantalla(), SessionManager.is_authenticated(),
                        rutas().count("/auth/logout") - antes]
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=180, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def test_sin_avisos_del_motor_qml(r):
    assert r["avisos"] == []


def test_cambio_obligatorio_lleva_a_opciones(r):
    assert r["cambio_abre"] == "CambioClave"
    assert r["titulo_cambio"] == "CAMBIAR CONTRASEÑA"
    assert r["tras_cambio"] == "Opciones"
    assert r["pendiente_tras_cambio"] is False


def test_nuevo_usuario_a_pantalla_completa_y_atras_vuelve_a_usuarios(r):
    assert r["nuevo_usuario"] == "NuevoUsuario"
    assert r["atras"] == ["Opciones", "usuarios"]


def test_sin_conexion_aviso_con_cuenta_regresiva(r):
    visible, texto = r["aviso"]
    assert visible is True
    assert texto.startswith("La sesión se cerrará en 0:0")


def test_reconexion_antes_del_plazo_valida_una_vez(r):
    assert r["reconecta_200"] == [False, "Opciones", True, 1]


def test_plazo_vencido_cierra_y_hace_logout_al_volver(r):
    assert r["cierre"] == ["PantallaPreciclo", False]
    assert r["logout_al_volver"] == 1


def test_reconexion_con_401_vuelve_al_login(r):
    assert r["reconecta_401"] == ["Login", False, "sesion.sesion_invalida"]


def test_hibernacion_cierra_la_sesion_con_logout(r):
    assert r["hibernacion"] == ["PantallaPreciclo", False, 1]


def test_cambio_obligatorio_sin_conexion_descarta_sin_enviar(r):
    assert r["cambio_sin_conexion"] == ["Login", False]
    assert r["cambio_sin_conexion_llamadas"] == 0


def test_bloqueo_en_el_cambio_lleva_al_login_con_cuenta_regresiva(r):
    assert r["bloqueo_cambio"] == ["Login", False, "sesion.usuario_bloqueado", "2:00"]


def test_abandonar_el_cambio_cierra_con_logout(r):
    assert r["abandonar"] == ["PantallaPreciclo", False, 1]


def test_inactividad_cierra_la_sesion_y_vuelve_a_la_principal(r):
    assert r["inactividad"] == ["PantallaPreciclo", False, 1]
