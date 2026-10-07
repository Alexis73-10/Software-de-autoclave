# tests/test_opciones_qml.py
#
# Navegación real de Main.qml hacia OPCIONES (planeacion_opciones_parametros_ciclo.md,
# Fase 1, rev. 3, 2026-10-07):
# - el engranaje de la pantalla de ciclo en curso abre el login (U-18); el de
#   preciclo sigue abriendo el Menú Principal (test_main_menu_principal_qml.py);
# - el login validado se reemplaza por OPCIONES con las secciones del rol;
# - con ciclo en curso, aviso de edición bloqueada; en PREPARADO, no;
# - Inicio regresa a preciclo o ciclo en curso (aunque se llegue por el menú),
#   conservando la sesión (el siguiente acceso va directo a
#   OPCIONES); Salir la cierra (el siguiente acceso pide login);
# - cajón lateral (rev. 3, U-19): la hamburguesa abre, tocar fuera o elegir
#   una entrada cierra, el fondo atenuado no deja tocar el contenido, con
#   cambios sin guardar cambiar de sección pide confirmación; el título muestra
#   la sección activa y el admin aterriza en Usuarios;
# - ningún acceso lanza PySide.
# Carga real en subproceso, offscreen, con base de usuarios temporal.

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
    import json, pathlib, sys, tempfile
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QPoint, Qt, QUrl, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml.app import QML_DIR, cargar_textos
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import login_controller, teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.ui_pyside.services.session_manager import SessionManager, hash_password

    estado, rol = sys.argv[1], sys.argv[2]
    db = DbManager(db_path=pathlib.Path(tempfile.mkdtemp()) / "t.db")
    db.crear_usuario("Ana Ruiz", "anar", hash_password("clave1234"), rol)
    login_controller._db_por_defecto = lambda: db

    qapp = QGuiApplication([])
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = estado
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.return_value = True
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

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
    engine.setInitialProperties({"puente": puente, "ajustes": ajustes, "textosJson": cargar_textos()})
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

    def esperar():
        QTest.qWait(700)   # transición del StackView

    if estado != "CICLO":
        QMetaObject.invokeMethod(buscar("Arranque")[0], "tocado")
        esperar()
    origen = "PantallaCicloEnCurso" if estado == "CICLO" else "PantallaPreciclo"
    # ciclo en curso: engranaje (U-18); preciclo: avatar (su engranaje abre el menú)
    acceso = "ajustesPulsado" if estado == "CICLO" else "avatarPulsado"
    r = {"origen_visible": visible(origen)}

    QMetaObject.invokeMethod(buscar(origen)[0], acceso)
    esperar()
    r["login_abre"] = visible("Login") and not buscar("MenuPrincipal")

    login = buscar("Login")[0]
    login.setProperty("usuario", "anar")
    login.setProperty("clave", "clave1234")
    QMetaObject.invokeMethod(login, "iniciarSesion")
    esperar()
    r["login_reemplazado"] = len(buscar("Login")) == 0
    r["opciones_abre"] = visible("Opciones")
    r["sesion"] = SessionManager.is_authenticated()
    op = buscar("Opciones")[0]

    def tocar(item, esperar_ms=300):
        pt = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.qWait(esperar_ms)

    def tocar_punto(fx, fy, esperar_ms=300):
        QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier,
                         QPoint(int(ventana.width() * fx), int(ventana.height() * fy)))
        QTest.qWait(esperar_ms)

    def entradas():
        # delegados del Repeater del cajón
        return [i for i in hijo("navegacionOpciones").childItems()
                if i.objectName().startswith("entrada_")]

    r["entradas"] = [i.objectName()[len("entrada_"):] for i in entradas()]
    r["seccion_activa"] = op.property("seccionActiva")
    r["titulo"] = hijo("tituloOpciones").property("text")
    r["proximamente"] = hijo("textoProximamente").property("visible")
    r["sin_secciones"] = hijo("textoSinSecciones").property("visible")
    r["aviso_bloqueo"] = hijo("avisoEdicionBloqueada").property("visible")
    r["engranaje_visible"] = hijo("engranajeEncabezado").property("visible")
    r["cajon_inicial"] = op.property("cajonAbierto")

    # hamburguesa abre; tocar fuera (lado derecho atenuado) cierra
    tocar(hijo("botonHamburguesa"))
    # las entradas (y su recuadro azul) quedan dentro del borde del cajón
    cajon = hijo("cajonOpciones")
    borde = cajon.mapToScene(cajon.boundingRect().topRight()).x()
    r["entradas_dentro"] = all(
        i.mapToScene(i.boundingRect().topRight()).x() <= borde + 0.5 for i in entradas())
    r["hamburguesa_abre"] = op.property("cajonAbierto") and hijo("fondoCajon").property("visible")
    tocar_punto(0.85, 0.5)
    r["fuera_cierra"] = not op.property("cajonAbierto")
    # alternar (el botón otra vez) abre y cierra
    QMetaObject.invokeMethod(op, "alternarCajon")
    abierto = op.property("cajonAbierto")
    QMetaObject.invokeMethod(op, "alternarCajon")
    r["alternar"] = abierto and not op.property("cajonAbierto")
    # con el cajón abierto, el fondo no deja tocar la casa de la barra (solo cierra)
    tocar(hijo("botonHamburguesa"))
    tocar(op.findChild(QObject, "botonInicio"))
    r["fondo_bloquea"] = visible("Opciones") and not op.property("cajonAbierto")

    if len(r["entradas"]) > 1:
        # elegir una entrada cierra el cajón y muestra su sección en el título
        tocar(hijo("botonHamburguesa"))
        tocar(entradas()[1])
        r["elegir_cierra"] = not op.property("cajonAbierto")
        r["titulo_segunda"] = hijo("tituloOpciones").property("text")
        r["aviso_bloqueo_segunda"] = hijo("avisoEdicionBloqueada").property("visible")
        # con cambios sin guardar, cambiar de sección pide confirmación
        op.setProperty("cambiosPendientes", True)
        tocar(hijo("botonHamburguesa"))
        tocar(entradas()[0])
        dialogo = hijo("dialogoCambiarSeccion")
        r["pide_confirmar"] = (dialogo.property("visible")
                               and op.property("seccionActiva") == r["entradas"][1])
        QMetaObject.invokeMethod(dialogo, "confirmado")
        dialogo.setProperty("visible", False)
        r["confirmar_cambia"] = op.property("seccionActiva") == r["entradas"][0]
        op.setProperty("cambiosPendientes", False)

    QMetaObject.invokeMethod(op, "inicioPulsado")             # Inicio: conserva sesión
    esperar()
    r["inicio_regresa"] = len(buscar("Opciones")) == 0 and visible(origen)
    r["sesion_tras_inicio"] = SessionManager.is_authenticated()

    QMetaObject.invokeMethod(buscar(origen)[0], acceso)       # con sesión: directo a OPCIONES
    esperar()
    r["directo_a_opciones"] = visible("Opciones") and not buscar("Login")

    QMetaObject.invokeMethod(buscar("Opciones")[0], "salir")  # Salir: cierra sesión
    esperar()
    r["salir_regresa"] = len(buscar("Opciones")) == 0 and visible(origen)
    r["sesion_tras_salir"] = SessionManager.is_authenticated()

    QMetaObject.invokeMethod(buscar(origen)[0], acceso)       # sin sesión: login de nuevo
    esperar()
    r["login_de_nuevo"] = visible("Login")

    # Llegando por el Menú Principal (engranaje de preciclo), Inicio vuelve a
    # preciclo y no al menú (decisión de Cristian, 2026-10-07)
    if estado != "CICLO":
        QMetaObject.invokeMethod(buscar("Login")[0], "inicioPulsado")
        esperar()
        QMetaObject.invokeMethod(buscar(origen)[0], "ajustesPulsado")    # -> menú
        esperar()
        QMetaObject.invokeMethod(buscar("MenuPrincipal")[0], "iniciarSesionPulsado")
        esperar()
        login = buscar("Login")[0]
        login.setProperty("usuario", "anar")
        login.setProperty("clave", "clave1234")
        QMetaObject.invokeMethod(login, "iniciarSesion")
        esperar()
        QMetaObject.invokeMethod(buscar("Opciones")[0], "inicioPulsado")
        esperar()
        r["inicio_desde_menu"] = (not buscar("Opciones") and not buscar("MenuPrincipal")
                                  and visible(origen))
    r["ajustes"] = ajustes.veces
    r["avisos"] = avisos
    print("RESULTADO=" + json.dumps(r))
""")

_TECNICAS = ["parametros_ciclo", "parametros_sistema", "entradas_salidas",
             "mantenimiento", "opciones_avanzadas"]


def _correr(estado, rol):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-c", _SCRIPT, estado, rol], capture_output=True,
                          text=True, encoding="utf-8", env=env, timeout=90, cwd=_RAIZ)
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULTADO=")]
    assert linea, proc.stdout + proc.stderr
    return json.loads(linea[0][len("RESULTADO="):])


def _navegacion_comun(r):
    assert r["avisos"] == []
    assert r["origen_visible"] is True
    assert r["login_abre"] is True
    assert r["login_reemplazado"] is True
    assert r["opciones_abre"] is True
    assert r["sesion"] is True
    assert r["engranaje_visible"] is True
    assert r["inicio_regresa"] is True
    assert r["sesion_tras_inicio"] is True
    assert r["directo_a_opciones"] is True
    assert r["cajon_inicial"] is False
    assert r["hamburguesa_abre"] is True
    assert r["fuera_cierra"] is True
    assert r["entradas_dentro"] is True
    assert r["alternar"] is True
    assert r["fondo_bloquea"] is True
    assert r["salir_regresa"] is True
    assert r["sesion_tras_salir"] is False
    assert r["login_de_nuevo"] is True
    assert r["ajustes"] == 0          # QML ya no lanza la configuración PySide (U-4)


@pytest.mark.parametrize("estado,bloqueado", [("CICLO", True), ("PREPARADO", False)])
def test_tecnico_entra_a_opciones(estado, bloqueado):
    r = _correr(estado, "tecnico")
    _navegacion_comun(r)
    assert r["entradas"] == _TECNICAS
    assert r["seccion_activa"] == "parametros_ciclo"
    assert r["titulo"] == "PARÁMETROS DEL CICLO"
    assert r["elegir_cierra"] is True
    assert r["titulo_segunda"] == "PARÁMETROS DEL SISTEMA"
    assert r["pide_confirmar"] is True
    assert r["confirmar_cambia"] is True
    assert r["proximamente"] is True
    assert r["sin_secciones"] is False
    assert r["aviso_bloqueo"] is bloqueado
    assert r["aviso_bloqueo_segunda"] is bloqueado
    if estado != "CICLO":
        assert r["inicio_desde_menu"] is True


def test_ingeniero_edita_con_ciclo_en_curso():
    # Excepción de Cristian (2026-10-07): el ingeniero modifica lo que sea en cualquier momento
    r = _correr("CICLO", "ingeniero")
    _navegacion_comun(r)
    assert r["entradas"] == _TECNICAS
    assert r["aviso_bloqueo"] is False            # Parámetros del ciclo
    assert r["aviso_bloqueo_segunda"] is False    # Parámetros del sistema


def test_admin_ve_solo_usuarios_y_conectividad():
    r = _correr("PREPARADO", "admin")
    _navegacion_comun(r)
    assert r["entradas"] == ["usuarios", "conectividad"]
    assert r["seccion_activa"] == "usuarios"     # el admin aterriza en Usuarios
    assert r["titulo"] == "USUARIOS"


def test_rol_sin_secciones():
    r = _correr("PREPARADO", "operador")
    _navegacion_comun(r)
    assert r["entradas"] == []
    assert r["seccion_activa"] == ""
    assert r["sin_secciones"] is True
    assert r["proximamente"] is False
    assert r["aviso_bloqueo"] is False
    assert r["titulo"] == "OPCIONES"
