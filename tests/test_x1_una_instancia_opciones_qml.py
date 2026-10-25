# tests/test_x1_una_instancia_opciones_qml.py
#
# X1 (tanda 6): solapamiento en OPCIONES > Entradas/Salidas. Cristian vio la
# lista de Entradas dibujada bajo la de Salidas. Una de las vías es tener dos
# pantallas OPCIONES vivas en la pila de la misma ventana (OPCIONES -> Menú ->
# Iniciar sesión -> OPCIONES de nuevo). Esta prueba carga Main.qml real,
# offscreen, y exige una sola instancia de OPCIONES (y de Entradas/Salidas)
# por ventana tras ese recorrido, repetido.

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
        if ruta == "/auth/login":
            return 200, {"token": "tok-adm1", "usuario": "adm1", "nombre": "adm1",
                         "rol": "admin", "debe_cambiar_clave": False}
        if ruta == "/auth/sesion":
            return 200, {"usuario": "adm1", "rol": "admin"}
        return 200, {"ok": True}

    qapp = QGuiApplication([])
    sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                          cierre_s=30, intervalo_ms=50)
    sesion_backend.instalar(sesion)
    puente_nu = NuevoUsuarioBridge(sesion=sesion)
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARADO"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.return_value = []
    ui.get_estado_flag.side_effect = lambda f: f not in ("PARO_EMERGENCIA", "PARO_REAL")
    ui.get_cycle.return_value = {"name": "Bowe & Dick", "number": 1}
    ui.get_sensores_temp.return_value = {"temp_camara": 25.0}
    ui.get_sensores_pres.return_value = {"pres_camara": 101.3}
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "sesion": sesion, "puenteNuevoUsuario": puente_nu})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.show()

    def buscar(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]
    def visibles(tipo):
        return sum(1 for o in buscar(tipo) if o.property("visible"))
    def esperar(ms=600):
        QTest.qWait(ms)

    QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado"); esperar()
    QMetaObject.invokeMethod(buscar("PantallaPreciclo")[0], "avatarPulsado"); esperar()
    login = buscar("Login")[0]
    login.setProperty("usuario", "adm1"); login.setProperty("clave", "clave1234")
    QMetaObject.invokeMethod(login, "iniciarSesion"); esperar()
    buscar("Opciones")[0].setProperty("seccionActiva", "entradas_salidas"); esperar()
    r = {"inicio": [len(buscar("Opciones")), len(buscar("OpcionesEntradasSalidas"))]}
    for _ in range(3):
        QMetaObject.invokeMethod(buscar("Opciones")[0], "menuPulsado"); esperar()
        QMetaObject.invokeMethod(buscar("MenuPrincipal")[0], "iniciarSesionPulsado"); esperar()
    r["tras_menu"] = [len(buscar("Opciones")), len(buscar("OpcionesEntradasSalidas")),
                      visibles("Opciones"), visibles("OpcionesEntradasSalidas")]
    r["seccion"] = buscar("Opciones")[0].property("seccionActiva")
    print("RESULTADO " + json.dumps(r))
""")


@pytest.fixture(scope="module")
def resultado():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    p = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=_RAIZ, timeout=120, env=env)
    linea = [x for x in p.stdout.splitlines() if x.startswith("RESULTADO ")]
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[-1][len("RESULTADO "):])


def test_arranca_con_una_opciones_y_una_es(resultado):
    assert resultado["inicio"] == [1, 1]


def test_menu_e_iniciar_sesion_no_apilan_otra_opciones(resultado):
    # una sola OPCIONES y una sola Entradas/Salidas viva y visible en la ventana
    assert resultado["tras_menu"] == [1, 1, 1, 1]


def test_vuelve_a_la_misma_seccion(resultado):
    assert resultado["seccion"] == "entradas_salidas"


# --- Estructura de la pantalla: una pagina por segmento, modelo fijo ---------

_GUION_ES = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    import autoclave.ui_qml.bridge.i18n_qml  # noqa: F401
    import autoclave.ui_qml.controllers  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR
    from autoclave.core.runtime import io_names
    app = QGuiApplication([])
    v = QQuickView(); v.engine().addImportPath(QML_DIR)
    avisos = []
    v.engine().warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    v.setResizeMode(QQuickView.SizeRootObjectToView); v.resize(1100, 1400)
    v.setSource(QUrl.fromLocalFile(sys.argv[1]))
    v.show()
    r = v.rootObject()
    pant = r.findChild(QObject, "opcionesEntradasSalidas")
    c = pant.findChild(QObject, "entradasSalidasController")
    c._canales = {"DI": io_names.canales_digitales("DI"), "DO": io_names.canales_digitales("DO"),
                  "temperature": io_names.sensores("temperature"),
                  "pressure": io_names.sensores("pressure")}
    def items(it):
        for h in it.childItems():
            yield h
            yield from items(h)
    def vis(pref):
        return sum(1 for i in items(r) if i.objectName().startswith(pref) and i.isVisible())
    malos = []
    segs = ["entradas", "salidas", "temperatura", "presion"]
    for k in range(40):
        s = segs[k % 4] if k < 20 else segs[k % 2]   # al final: Entradas<->Salidas rapido
        pant.setProperty("segmento", s)
        c._reconstruir()                             # lectura que llega en medio
        if k % 3 == 0:
            app.processEvents()
        cuenta = {"entradas": vis("entrada_"), "salidas": vis("salida_"), "sensores": vis("sensor_")}
        esperado = {"entradas": s == "entradas", "salidas": s == "salidas",
                    "sensores": s in ("temperatura", "presion")}
        for clave, debe in esperado.items():
            if bool(cuenta[clave]) != debe:
                malos.append([k, s, cuenta])
    paginas = sorted(i.objectName() for i in items(r) if i.objectName().startswith("pagina"))
    fondo = pant.findChild(QObject, "fondoOpacoES")
    print("RESULTADO " + json.dumps({"malos": malos, "paginas": paginas,
          "fondo": bool(fondo and fondo.property("visible")),
          "avisos": [a for a in avisos if "sesion" not in a.lower()]}))
""")


@pytest.fixture(scope="module")
def estructura(tmp_path_factory):
    qml = _RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
    prueba = tmp_path_factory.mktemp("x1") / "x1_es.qml"
    prueba.write_text('import QtQuick\nimport "file:///' + str(qml / "Pantallas").replace("\\", "/")
                      + '"\nItem { OpcionesEntradasSalidas { anchors.fill: parent } }\n',
                      encoding="utf-8")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    p = subprocess.run([sys.executable, "-c", _GUION_ES, str(prueba)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=_RAIZ, timeout=120,
                       env=env)
    linea = [x for x in p.stdout.splitlines() if x.startswith("RESULTADO ")]
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[-1][len("RESULTADO "):])


def test_cambio_rapido_de_segmento_nunca_mezcla_listas(estructura):
    assert estructura["malos"] == []


def test_una_pagina_por_segmento_y_fondo_opaco(estructura):
    assert estructura["paginas"] == ["paginaEntradas", "paginaPresion", "paginaSalidas",
                                     "paginaTemperatura"]
    assert estructura["fondo"] is True


def test_sin_avisos_qml(estructura):
    assert estructura["avisos"] == []
