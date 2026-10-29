# tests/test_t22_pantallas_accion_qml.py
#
# TEC-ACC-04 (tanda 22, PRB-T22-01): las pantallas cuyo teclado ejecuta una
# acción usan el modo acción del PanelTeclado. Se cargan las pantallas reales
# con un PanelTeclado real y una sesión doble (`sesion_backend.ventana`) que
# cuenta cada envío; se escribe letra a letra tocando las teclas.
# - Reasignación: la contraseña no se envía al escribir; Confirmar → 1 POST
#   (aplicar, restaurar fábrica, verificar). El nombre reforzado no abre el
#   siguiente diálogo hasta Confirmar; Cancelar aborta la cadena.
# - Conectividad: el teclado del correo no se abre hasta Confirmar el nombre;
#   1 PUT al Confirmar el correo; Cancelar en el correo no envía.
# - Manejo de ciclos: crear / duplicar 1 POST al Confirmar; Cancelar no envía.
# La primera letra sale en mayúscula (mayúscula automática del teclado).
# Subproceso con QGuiApplication propio, 1200x1920 (Escala.factor = 1).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

pytestmark = pytest.mark.req("TEC-ACC-04")

RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl, Q_ARG, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401  registra los controladores
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.sesion_backend import Resultado

    FILAS = [
        {"funcion": "bomba_vacio", "tipo": "DO", "i18n": "io.do.bomba_vacio",
         "puerto_actual": 19, "id_actual": "DO 19", "puerto_guardado": 19, "puerto_fabrica": 19,
         "id_fabrica": "DO 19", "critica": False, "reforzada": False, "temperatura": False},
        {"funcion": "paro_emergencia", "tipo": "DI", "i18n": "io.di.paro_emergencia",
         "puerto_actual": 11, "id_actual": "DI 11", "puerto_guardado": 11, "puerto_fabrica": 11,
         "id_fabrica": "DI 11", "critica": True, "reforzada": True, "temperatura": False},
    ]
    DATOS = {
        "filas": FILAS,
        "puertos": {"DI": list(range(1, 17)), "DO": list(range(1, 33)),
                    "AI_TEMP": list(range(1, 7)), "AI_PRES": list(range(9, 17))},
        "ocupados": {"DI": {"11": "paro_emergencia"}, "DO": {"19": "bomba_vacio"}, "AI": {}},
        "cambios_guardados": {}, "reinicio_pendiente": False, "error_archivo": "", "bloqueo": "",
        "verificacion": {"estado": "sin_cambios", "funciones": {}},
        "editable": True, "motivo": "", "reinicio_disponible": True,
    }

    class Sesion:
        # Doble de la sesión de la ventana: cuenta cada envío que no es GET.
        # Las acciones responden con un error para que la pantalla siga igual.
        def __init__(self):
            self.envios = []
        def enviar(self, metodo, ruta, cuerpo=None):
            if metodo == "GET":
                if ruta == "/io/assignment":
                    return Resultado("ok", json.loads(json.dumps(DATOS)), 200)
                if ruta == "/email/config":
                    return Resultado("ok", {"envio_activo": True, "destinatarios": []}, 200)
                return Resultado("ok", {}, 200)
            self.envios.append([metodo, ruta, cuerpo])
            return Resultado("error_generico")
        def __getattr__(self, nombre):
            return lambda *a, **k: None

    sesion = Sesion()
    sesion_backend.ventana = lambda: sesion

    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        Item {
            anchors.fill: parent
            Loader { id: carga; objectName: "carga"; anchors.fill: parent }
            PanelTeclado { id: panel; objectName: "panelTeclado" }
            Item {
                objectName: "prueba"
                function cargar(nombre) {
                    carga.setSource("Pantallas/" + nombre + ".qml",
                                    { teclado: panel, rol: "ingeniero", estadoMaquina: "PREPARADO" })
                }
                function pantalla() { return carga.item }
                function verificar() {
                    carga.item.iniciarVerificacion({ funcion: "paro_emergencia", i18n: "io.di.paro_emergencia",
                                                     tipo: "DI", puerto: "DI 11", reforzada: true })
                }
            }
        }
    }
    '''
    ruta = f"{QML_DIR}/_prueba_t22_pantallas_accion.qml"
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
    panel = w.findChild(QObject, "panelTeclado")
    prueba = w.findChild(QObject, "prueba")
    alfa = panel.findChild(QObject, "tecladoAlfanumerico")
    from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import TecladoAlfanumericoController
    ctrl_alfa = alfa.findChild(TecladoAlfanumericoController)

    def titulo():
        return ctrl_alfa.titulo

    def invocar(obj, nombre, *args, esperar=400):
        QMetaObject.invokeMethod(obj, nombre, *args)
        QTest.qWait(esperar)

    def cargar(nombre):
        invocar(prueba, "cargar", Q_ARG("QVariant", nombre), esperar=600)
        return QMetaObject.invokeMethod(prueba, "pantalla", Q_RETURN_ARG("QVariant"))

    def visuales(item):
        for h in item.childItems():
            yield h
            yield from visuales(h)

    def tecla(texto=None, nombre=None):
        for o in visuales(alfa):
            if not o.metaObject().className().startswith("Tecla_QML"):
                continue
            if (nombre and o.objectName() == nombre) or (texto and o.objectName() == "" and o.property("texto").lower() == texto):
                return o
        raise KeyError(texto or nombre)

    def tocar(o, esperar=30):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(esperar)

    def escribir(texto):
        for c in texto:
            tocar(tecla(c))

    def confirmar():
        tocar(tecla(nombre="teclaConfirmar"), 600)

    def cancelar():
        tocar(tecla(nombre="teclaCancelar"), 600)

    def envios():
        return [e[:2] for e in sesion.envios]

    def limpiar():
        sesion.envios.clear()

    def hijo(nombre):
        return w.findChild(QObject, nombre)

    r = {}

    # ---- Reasignación ----
    p = cargar("OpcionesReasignacion")
    ctrl = hijo("reasignacionController")
    QMetaObject.invokeMethod(ctrl, "elegirPuerto", Q_ARG(str, "bomba_vacio"), Q_ARG(int, 20))
    QTest.qWait(200)
    for dialogo, clave in (("dialogoReinicioReasignacion", "aplicar"),
                           ("dialogoFabricaReasignacion", "fabrica")):
        limpiar()
        invocar(hijo(dialogo), "confirmado")
        r[clave + "_abierto"] = panel.property("abierto")
        escribir("secreta")
        r[clave + "_al_escribir"] = envios()
        confirmar()
        r[clave + "_al_confirmar"] = [[e[0], e[1], e[2].get("clave")] for e in sesion.envios]
        # Cancelar la contraseña no envía nada
        limpiar()
        invocar(hijo(dialogo), "confirmado")
        escribir("sec")
        cancelar()
        r[clave + "_cancelar"] = envios()

    # Verificar una función reforzada: nombre y luego contraseña
    limpiar()
    invocar(prueba, "verificar")
    invocar(hijo("dialogoVerificarReasignacion"), "confirmado")
    escribir("paro")
    r["verif_titulo_al_escribir"] = titulo()
    r["verif_al_escribir_nombre"] = envios()
    confirmar()
    r["verif_tras_nombre_abierto"] = panel.property("abierto")
    r["verif_titulo_tras_nombre"] = titulo()
    escribir("secreta")
    r["verif_al_escribir_clave"] = envios()
    confirmar()
    r["verif_al_confirmar"] = [[e[0], e[1], e[2].get("clave"), e[2].get("nombre")] for e in sesion.envios]
    # Cancelar el nombre aborta la cadena
    limpiar()
    invocar(prueba, "verificar")
    invocar(hijo("dialogoVerificarReasignacion"), "confirmado")
    escribir("pa")
    cancelar()
    r["verif_cancelar_nombre"] = [envios(), panel.property("abierto")]

    # Nombre reforzado: el diálogo de reinicio no se abre hasta Confirmar
    QMetaObject.invokeMethod(ctrl, "elegirPuerto", Q_ARG(str, "paro_emergencia"), Q_ARG(int, 12))
    QTest.qWait(200)
    reinicio = hijo("dialogoReinicioReasignacion")
    limpiar()
    invocar(hijo("dialogoReforzadaReasignacion"), "confirmado")
    escribir("p")
    r["reforzada_reinicio_tras_1_letra"] = reinicio.property("visible")
    escribir("aro")
    r["reforzada_reinicio_al_escribir"] = reinicio.property("visible")
    confirmar()
    r["reforzada_reinicio_tras_confirmar"] = reinicio.property("visible")
    r["reforzada_envios"] = envios()
    invocar(reinicio, "cerrar")
    # Cancelar el nombre reforzado no avanza
    invocar(hijo("dialogoReforzadaReasignacion"), "confirmado")
    escribir("pa")
    cancelar()
    r["reforzada_cancelar"] = [reinicio.property("visible"), envios()]

    # ---- Conectividad ----
    p = cargar("OpcionesConectividad")
    r["conect_editable"] = p.property("editable")
    limpiar()
    invocar(p, "agregarDestinatario")
    titulo_nombre = titulo()
    escribir("ana")
    r["conect_mismo_teclado_al_escribir"] = titulo() == titulo_nombre
    r["conect_al_escribir_nombre"] = envios()
    confirmar()
    r["conect_correo_abierto"] = [panel.property("abierto"), titulo() != titulo_nombre]
    escribir("ana")
    r["conect_al_escribir_correo"] = envios()
    confirmar()
    r["conect_al_confirmar"] = [[e[0], e[1], e[2]["destinatarios"][-1]] for e in sesion.envios]
    limpiar()
    invocar(p, "agregarDestinatario")
    escribir("ana"); confirmar(); escribir("an"); cancelar()
    r["conect_cancelar_correo"] = envios()

    # ---- Manejo de ciclos ----
    p = cargar("OpcionesManejoCiclos")
    for funcion, arg in (("elegirBase", 3), ("pedirDuplicar", 4)):
        limpiar()
        invocar(p, funcion, Q_ARG("QVariant", arg))
        escribir("nuevo")
        r[funcion + "_al_escribir"] = envios()
        confirmar()
        r[funcion + "_al_confirmar"] = [[e[0], e[1], e[2]] for e in sesion.envios]
        limpiar()
        invocar(p, funcion, Q_ARG("QVariant", arg))
        escribir("nu")
        cancelar()
        r[funcion + "_cancelar"] = envios()

    r["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
    print(json.dumps(r))
""")


@pytest.fixture(scope="module")
def r():
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(RAIZ / "src")}
    p = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=RAIZ, timeout=240, env=env)
    assert p.returncode == 0, p.stderr[-3000:]
    return json.loads(p.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("clave, ruta", [("aplicar", "/io/assignment"),
                                         ("fabrica", "/io/assignment/factory")])
def test_reasignacion_la_clave_se_envia_una_vez_al_confirmar(r, clave, ruta):
    assert r[clave + "_abierto"] is True
    assert r[clave + "_al_escribir"] == []
    assert r[clave + "_al_confirmar"] == [["POST", ruta, "Secreta"]]
    assert r[clave + "_cancelar"] == []


def test_reasignacion_verificar_reforzada(r):
    assert r["verif_al_escribir_nombre"] == []
    assert r["verif_tras_nombre_abierto"] is True
    assert r["verif_titulo_tras_nombre"] != r["verif_titulo_al_escribir"]   # ahora pide la clave
    assert r["verif_al_escribir_clave"] == []
    assert r["verif_al_confirmar"] == [["POST", "/io/assignment/verify", "Secreta", "Paro"]]
    assert r["verif_cancelar_nombre"] == [[], False]


def test_reasignacion_nombre_reforzado_avanza_solo_al_confirmar(r):
    assert r["reforzada_reinicio_tras_1_letra"] is False
    assert r["reforzada_reinicio_al_escribir"] is False
    assert r["reforzada_reinicio_tras_confirmar"] is True
    assert r["reforzada_envios"] == []
    assert r["reforzada_cancelar"] == [False, []]


def test_conectividad_correo_tras_confirmar_el_nombre(r):
    assert r["conect_editable"] is True
    assert r["conect_mismo_teclado_al_escribir"] is True
    assert r["conect_al_escribir_nombre"] == []
    assert r["conect_correo_abierto"] == [True, True]
    assert r["conect_al_escribir_correo"] == []
    assert r["conect_al_confirmar"] == [["PUT", "/email/config", {"nombre": "Ana", "correo": "Ana"}]]
    assert r["conect_cancelar_correo"] == []


@pytest.mark.parametrize("funcion, numero, cuerpo", [
    ("elegirBase", 3, {"nombre": "Nuevo", "crear": True}),
    ("pedirDuplicar", 4, {"nombre": "Nuevo"}),
])
def test_manejo_ciclos_una_vez_al_confirmar(r, funcion, numero, cuerpo):
    assert r[funcion + "_al_escribir"] == []
    assert r[funcion + "_al_confirmar"] == [["POST", f"/programas/{numero}/duplicar", cuerpo]]
    assert r[funcion + "_cancelar"] == []


def test_sin_avisos_qml(r):
    assert r["avisos"] == []
