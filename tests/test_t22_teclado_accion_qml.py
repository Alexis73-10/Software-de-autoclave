# tests/test_t22_teclado_accion_qml.py
#
# PanelTeclado, modo acción (tanda 22, PRB-T22-01, TEC-ACC-01..03):
# abrirAlfanumericoAccion entrega lo escrito una sola vez y solo al pulsar
# Confirmar con texto; escribir, Cancelar, Ocultar y abrir otro campo no
# llaman al callback; un Confirmar repetido o reentrante (desde el propio
# callback, como un POST síncrono en curso) no produce un segundo envío.
# El modo en vivo (abrirAlfanumerico/abrirNumerico) queda igual que antes.
# Carga real a 1200x1920 (Escala.factor = 1), en subproceso para tener un
# QGuiApplication propio; las teclas se tocan con el ratón como en
# test_panel_teclado_login.py.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

pytestmark = pytest.mark.req("TEC-ACC-01", "TEC-ACC-02", "TEC-ACC-03")

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401  registra los controladores
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes

    # Ventana mínima: PanelTeclado como lo arma Main.qml y un objeto de
    # prueba que abre el teclado y cuenta las llamadas a cada callback.
    QML = '''
    import QtQuick
    import Tema
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        Item {
            anchors.fill: parent
            PanelTeclado { id: panel; objectName: "panelTeclado" }
            Item {
                id: prueba
                objectName: "prueba"
                property var ctrlAlfa: null
                property bool reentrar: false
                property bool encadenar: false
                property var accion: []
                property var vivo: []
                property var otro: []
                property var numero: []
                function _json() {
                    return JSON.stringify({accion: accion, vivo: vivo, otro: otro, numero: numero})
                }
                function registro() { return _json() }
                function limpiar() { accion = []; vivo = []; otro = []; numero = [] }
                function _alAccion(t) {
                    accion = accion.concat([t])
                    if (reentrar) {
                        // doble toque mientras el POST síncrono está en curso
                        ctrlAlfa.confirmar()
                        ctrlAlfa.confirmar()
                    }
                    if (encadenar)
                        panel.abrirAlfanumericoAccion("Correo", "", 40, false, t2 => { otro = otro.concat([t2]) })
                }
                function abrirAccion() {
                    panel.abrirAlfanumericoAccion("Clave", "", 20, true, t => _alAccion(t))
                }
                function abrirVivo() {
                    panel.abrirAlfanumerico("Nombre", "", 20, false, t => { vivo = vivo.concat([t]) })
                }
                function abrirOtroVivo() {
                    panel.abrirAlfanumerico("Otro", "", 20, false, t => { otro = otro.concat([t]) })
                }
                function abrirOtroAccion() {
                    panel.abrirAlfanumericoAccion("Otro", "", 20, false, t => { otro = otro.concat([t]) })
                }
                function abrirNumero() {
                    panel.abrirNumerico("Tiempo", "min", 5, 0, 60, 0, v => { numero = numero.concat([v]) })
                }
                function cerrarPanel() { panel.cerrar() }
            }
        }
    }
    '''
    ruta = f"{QML_DIR}/_prueba_t22_teclado_accion.qml"
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
    from autoclave.ui_qml.controllers.teclado_numerico_controller import TecladoNumericoController
    ctrl = alfa.findChild(TecladoAlfanumericoController)
    prueba.setProperty("ctrlAlfa", ctrl)

    def llamar(nombre, esperar=600):
        QMetaObject.invokeMethod(prueba, nombre)
        QTest.qWait(esperar)

    def _leer():
        # las listas de QML se leen como JSON para no depender de la conversión
        from PySide6.QtCore import Q_RETURN_ARG
        res = QMetaObject.invokeMethod(prueba, "registro", Q_RETURN_ARG("QVariant"))
        return json.loads(res)

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

    def confirmar(esperar=600):
        tocar(tecla(nombre="teclaConfirmar"), esperar)

    def cancelar(esperar=600):
        tocar(tecla(nombre="teclaCancelar"), esperar)

    r = {}

    # 1. Escribir N caracteres en modo acción no llama; Confirmar llama una vez
    llamar("limpiar", 0); llamar("abrirAccion")
    escribir("abcde")
    r["acc_tras_escribir"] = _leer()["accion"]
    r["acc_texto_en_edicion"] = panel.property("textoEnEdicion")
    confirmar()
    r["acc_tras_confirmar"] = _leer()["accion"]
    r["acc_abierto_tras_confirmar"] = panel.property("abierto")

    # 2. Cancelar no llama (ni con "")
    llamar("limpiar", 0); llamar("abrirAccion")
    escribir("abc")
    cancelar()
    r["cancelar"] = _leer()["accion"]
    r["cancelar_abierto"] = panel.property("abierto")

    # 3. Ocultar (botón y cerrar()) no llama
    llamar("limpiar", 0); llamar("abrirAccion")
    escribir("abc")
    tocar(panel.findChild(QObject, "teclaOcultarTeclado"), 600)
    r["ocultar_boton"] = _leer()["accion"]
    r["ocultar_boton_abierto"] = panel.property("abierto")
    llamar("abrirAccion")
    escribir("abc")
    llamar("cerrarPanel")
    r["cerrar_funcion"] = _leer()["accion"]

    # 4. Abrir otro campo (vivo, acción, numérico) descarta lo escrito
    res_otro = {}
    for abrir_otro in ("abrirOtroVivo", "abrirOtroAccion", "abrirNumero"):
        llamar("limpiar", 0); llamar("abrirAccion")
        escribir("abc")
        llamar(abrir_otro)
        res_otro[abrir_otro] = _leer()["accion"]
        llamar("cerrarPanel")
    r["abrir_otro"] = res_otro

    # 5. Confirmar vacío: no llama y sigue abierto
    llamar("limpiar", 0); llamar("abrirAccion")
    confirmar()
    r["vacio"] = _leer()["accion"]
    r["vacio_abierto"] = panel.property("abierto")
    # escribir y borrar todo también es vacío
    escribir("a"); tocar(tecla(nombre="teclaBorrar"))
    confirmar()
    r["vacio_borrado"] = _leer()["accion"]
    r["vacio_borrado_abierto"] = panel.property("abierto")
    # solo espacios también es vacío
    tocar(tecla(nombre="teclaEspacio")); tocar(tecla(nombre="teclaEspacio"))
    confirmar()
    r["vacio_espacios"] = _leer()["accion"]
    r["vacio_espacios_abierto"] = panel.property("abierto")
    llamar("cerrarPanel")

    # 6. Doble Confirmar (toques seguidos y llamadas al controlador)
    llamar("limpiar", 0); llamar("abrirAccion")
    escribir("abc")
    confirmar(esperar=30)
    confirmar(esperar=600)
    r["doble_toque"] = _leer()["accion"]
    llamar("limpiar", 0); llamar("abrirAccion")
    escribir("abc")
    ctrl.confirmar(); ctrl.confirmar()
    QTest.qWait(100)
    r["doble_controlador"] = _leer()["accion"]
    r["doble_controlador_abierto"] = panel.property("abierto")

    # 7. Confirmar reentrante desde dentro del callback (POST síncrono)
    llamar("limpiar", 0); llamar("abrirAccion")
    prueba.setProperty("reentrar", True)
    escribir("abc")
    confirmar()
    prueba.setProperty("reentrar", False)
    r["reentrante"] = _leer()["accion"]
    r["reentrante_abierto"] = panel.property("abierto")

    # 8. El callback abre el siguiente teclado: el panel queda abierto en él
    llamar("limpiar", 0); llamar("abrirAccion")
    prueba.setProperty("encadenar", True)
    escribir("ana")
    confirmar()
    prueba.setProperty("encadenar", False)
    r["cadena_accion"] = _leer()["accion"]
    r["cadena_abierto"] = panel.property("abierto")
    r["cadena_otro_tras_abrir"] = _leer()["otro"]
    escribir("xy")
    r["cadena_otro_tras_escribir"] = _leer()["otro"]
    confirmar()
    r["cadena_otro_tras_confirmar"] = _leer()["otro"]
    r["cadena_accion_final"] = _leer()["accion"]

    # 9. Modo en vivo intacto: cada tecla llega, Cancelar entrega ""
    llamar("limpiar", 0); llamar("abrirVivo")
    escribir("abc")
    r["vivo_tras_escribir"] = _leer()["vivo"]
    cancelar()
    r["vivo_tras_cancelar"] = _leer()["vivo"]
    r["vivo_cancelar_abierto"] = panel.property("abierto")
    # abrir otro campo entrega lo pendiente al anterior
    llamar("limpiar", 0); llamar("abrirVivo")
    escribir("ab")
    llamar("abrirOtroVivo")
    r["vivo_abrir_otro"] = _leer()["vivo"]
    llamar("cerrarPanel")
    # Confirmar en vivo entrega el texto y cierra
    llamar("limpiar", 0); llamar("abrirVivo")
    escribir("ab")
    confirmar()
    r["vivo_confirmar"] = _leer()["vivo"]
    r["vivo_confirmar_abierto"] = panel.property("abierto")
    # tras un modo acción, el en vivo vuelve a entregar al escribir
    llamar("limpiar", 0); llamar("abrirAccion"); llamar("abrirVivo")
    escribir("a")
    r["vivo_tras_accion"] = _leer()["vivo"]
    r["accion_tras_vivo"] = _leer()["accion"]
    llamar("cerrarPanel")

    # 10. Numérico en vivo intacto: el valor llega al escribir y Cancelar
    # devuelve el inicial
    num = panel.findChild(QObject, "tecladoNumerico").findChild(TecladoNumericoController)
    llamar("limpiar", 0); llamar("abrirNumero")
    num.presionarDigito("4"); num.presionarDigito("2")
    QTest.qWait(50)
    r["num_tras_escribir"] = _leer()["numero"]
    num.cancelar()
    QTest.qWait(600)
    r["num_tras_cancelar"] = _leer()["numero"]
    r["num_cancelar_abierto"] = panel.property("abierto")

    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=False))
""")


@pytest.fixture(scope="module")
def salida():
    r = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"},
                       timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_accion_escribir_no_llama_y_confirmar_llama_una_vez(salida):
    assert salida["acc_tras_escribir"] == []
    assert salida["acc_texto_en_edicion"] == "Abcde"
    assert salida["acc_tras_confirmar"] == ["Abcde"]
    assert salida["acc_abierto_tras_confirmar"] is False


def test_accion_cancelar_no_llama(salida):
    assert salida["cancelar"] == []
    assert salida["cancelar_abierto"] is False


def test_accion_ocultar_no_llama(salida):
    assert salida["ocultar_boton"] == []
    assert salida["ocultar_boton_abierto"] is False
    assert salida["cerrar_funcion"] == []


@pytest.mark.parametrize("abrir_otro", ["abrirOtroVivo", "abrirOtroAccion", "abrirNumero"])
def test_accion_abrir_otro_campo_descarta_lo_escrito(salida, abrir_otro):
    assert salida["abrir_otro"][abrir_otro] == []


@pytest.mark.req("TEC-ACC-02")
def test_accion_confirmar_vacio_no_llama_y_sigue_abierto(salida):
    assert salida["vacio"] == []
    assert salida["vacio_abierto"] is True
    assert salida["vacio_borrado"] == []
    assert salida["vacio_borrado_abierto"] is True
    assert salida["vacio_espacios"] == []
    assert salida["vacio_espacios_abierto"] is True


@pytest.mark.req("TEC-ACC-03")
def test_accion_doble_confirmar_envia_una_vez(salida):
    assert salida["doble_toque"] == ["Abc"]
    assert salida["doble_controlador"] == ["Abc"]
    assert salida["doble_controlador_abierto"] is False


@pytest.mark.req("TEC-ACC-03")
def test_accion_confirmar_reentrante_desde_el_callback_envia_una_vez(salida):
    assert salida["reentrante"] == ["Abc"]
    assert salida["reentrante_abierto"] is False


def test_accion_callback_que_abre_otro_teclado_lo_deja_abierto(salida):
    assert salida["cadena_accion"] == ["Ana"]
    assert salida["cadena_abierto"] is True
    assert salida["cadena_otro_tras_abrir"] == []
    assert salida["cadena_otro_tras_escribir"] == []
    assert salida["cadena_otro_tras_confirmar"] == ["Xy"]
    assert salida["cadena_accion_final"] == ["Ana"]


def test_vivo_cada_tecla_llega_y_cancelar_entrega_vacio(salida):
    assert salida["vivo_tras_escribir"] == ["A", "Ab", "Abc"]
    assert salida["vivo_tras_cancelar"][:3] == ["A", "Ab", "Abc"]
    assert salida["vivo_tras_cancelar"][3:] and all(t == "" for t in salida["vivo_tras_cancelar"][3:])
    assert salida["vivo_cancelar_abierto"] is False


def test_vivo_abrir_otro_campo_entrega_lo_pendiente(salida):
    assert salida["vivo_abrir_otro"] == ["A", "Ab", "Ab"]


def test_vivo_confirmar_entrega_y_cierra(salida):
    assert salida["vivo_confirmar"] == ["A", "Ab", "Ab"]
    assert salida["vivo_confirmar_abierto"] is False


def test_vivo_tras_un_modo_accion_vuelve_a_entregar_al_escribir(salida):
    assert salida["vivo_tras_accion"] == ["A"]
    assert salida["accion_tras_vivo"] == []


def test_numerico_en_vivo_intacto(salida):
    assert salida["num_tras_escribir"] and salida["num_tras_escribir"][-1] == 42
    assert salida["num_tras_cancelar"][-1] == 5
    assert salida["num_cancelar_abierto"] is False
