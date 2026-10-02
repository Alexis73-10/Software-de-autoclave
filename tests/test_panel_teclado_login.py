# tests/test_panel_teclado_login.py
#
# PanelTeclado (Paso 5 de planeacion_teclados_qml.md) con su primer
# consumidor, la pantalla de Login: tocar un campo abre el alfanumérico al
# pie, el campo muestra lo que se escribe, Confirmar guarda y pasa al
# siguiente campo (en el último cierra), tocar otro campo guarda lo escrito,
# Cancelar vacía el campo y cierra, el texto no sale blanco con Windows
# en modo oscuro, la
# contraseña sale oculta en el encabezado y el panel no pasa del 45 % del
# alto (TEC-D06). Carga real a 1200x1920 (Escala.factor = 1), en subproceso
# para tener un QGuiApplication propio.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401  registra los controladores
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos

    # Ventana mínima: Login + PanelTeclado como los arma Main.qml
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
    ruta = f"{QML_DIR}/_prueba_panel_teclado_login.qml"
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

    panel = w.findChild(QObject, "panelTeclado")
    login = w.findChild(QObject, "login")
    usuario = w.findChild(QObject, "campoUsuario")
    clave = w.findChild(QObject, "campoClave")
    alfa = panel.findChild(QObject, "tecladoAlfanumerico")

    def visuales(item):
        for h in item.childItems():
            yield h
            yield from visuales(h)

    def teclas():
        return [o for o in visuales(alfa) if o.metaObject().className().startswith("Tecla_QML")]

    def tecla(texto=None, nombre=None):
        for o in teclas():
            if (nombre and o.objectName() == nombre) or (texto and o.objectName() == "" and o.property("texto").lower() == texto):
                return o
        raise KeyError(texto or nombre)

    def tocar(o, esperar=30):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(esperar)

    def valor_encabezado():
        return alfa.findChild(QObject, "valorAlfanumerico").property("text")

    r = {"cerrado_al_inicio": panel.property("abierto"), "visible_al_inicio": panel.property("visible")}

    tocar(usuario, esperar=600)          # 400 ms de animación
    r["abre_con_usuario"] = panel.property("abierto")
    r["campo_activo"] = login.property("campoActivo")
    r["panel_y"] = panel.property("y"); r["panel_alto"] = panel.property("height")
    r["altura_ocupada"] = panel.property("alturaOcupada")
    r["alfa_visible"] = alfa.property("visible")
    for c in "ana":
        tocar(tecla(c))
    r["campo_mientras_escribe"] = usuario.property("text")
    r["valor_sin_confirmar"] = login.property("usuario")
    r["color_texto"] = usuario.property("color").name()
    # Confirmar en usuario guarda y pasa a la contraseña sin cerrar
    tocar(tecla(nombre="teclaConfirmar"), esperar=600)
    r["usuario"] = usuario.property("text")
    r["abierto_tras_confirmar_usuario"] = panel.property("abierto")
    r["campo_activo_tras_confirmar_usuario"] = login.property("campoActivo")

    for c in "xy1":
        if c == "1":
            tocar(tecla(nombre="teclaCapa")); tocar(tecla("1")); tocar(tecla(nombre="teclaCapa"))
        else:
            tocar(tecla(c))
    r["encabezado_clave"] = valor_encabezado()
    # último campo: Confirmar guarda y cierra
    tocar(tecla(nombre="teclaConfirmar"), esperar=600)
    r["clave"] = clave.property("text")
    r["valor_clave"] = login.property("clave")
    r["cerrado_tras_ultimo"] = panel.property("abierto")
    r["campo_activo_tras_ultimo"] = login.property("campoActivo")

    # tocar otro campo sin Confirmar conserva lo escrito
    tocar(usuario, esperar=600)
    r["reabre_con_texto"] = valor_encabezado()
    tocar(tecla("b"))
    tocar(clave, esperar=100)
    r["usuario_tras_cambiar_de_campo"] = login.property("usuario")
    r["campo_activo_tras_cambiar"] = login.property("campoActivo")

    # Cancelar vacía el campo y cierra
    tocar(tecla(nombre="teclaCancelar"), esperar=600)
    r["clave_tras_cancelar"] = login.property("clave")
    r["usuario_tras_cancelar"] = login.property("usuario")
    r["cerrado_tras_cancelar"] = panel.property("abierto")
    r["visible_tras_cancelar"] = panel.property("visible")
    r["icono_borrar"] = tecla(nombre="teclaBorrar").property("icono").toString()
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=False))
""")


@pytest.fixture(scope="module")
def salida():
    r = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"},
                       timeout=90)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_panel_cerrado_al_inicio(salida):
    assert salida["cerrado_al_inicio"] is False
    assert salida["visible_al_inicio"] is False


def test_tocar_un_campo_abre_el_alfanumerico_al_pie(salida):
    assert salida["abre_con_usuario"] is True
    assert salida["campo_activo"] == "usuario"
    assert salida["alfa_visible"] is True
    assert salida["panel_y"] + salida["panel_alto"] == 1920        # anclado al pie
    assert salida["panel_alto"] <= 0.45 * 1920                      # TEC-D06
    assert salida["altura_ocupada"] == salida["panel_alto"]


def test_el_campo_muestra_lo_que_se_escribe(salida):
    assert salida["campo_mientras_escribe"] == "Ana"
    assert salida["valor_sin_confirmar"] == ""                      # el valor solo cambia al Confirmar


def test_texto_del_campo_en_color_del_tema(salida):
    # con Windows en modo oscuro el estilo Basic lo pintaría blanco sobre blanco
    assert salida["color_texto"].lower() == "#031225"               # Colores.textoPrimario


def test_confirmar_pasa_al_siguiente_campo(salida):
    assert salida["usuario"] == "Ana"
    assert salida["abierto_tras_confirmar_usuario"] is True
    assert salida["campo_activo_tras_confirmar_usuario"] == "clave"


def test_contrasena_oculta_y_confirmar_en_el_ultimo_cierra(salida):
    assert salida["encabezado_clave"] == "•" * 3
    assert salida["valor_clave"] == "Xy1"
    assert salida["clave"] == "Xy1"
    assert salida["cerrado_tras_ultimo"] is False
    assert salida["campo_activo_tras_ultimo"] == ""


def test_tocar_otro_campo_conserva_lo_escrito(salida):
    assert salida["reabre_con_texto"] == "Ana"
    assert salida["usuario_tras_cambiar_de_campo"] == "Anab"
    assert salida["campo_activo_tras_cambiar"] == "clave"


def test_cancelar_vacia_el_campo_y_cierra(salida):
    assert salida["clave_tras_cancelar"] == ""
    assert salida["usuario_tras_cancelar"] == "Anab"
    assert salida["cerrado_tras_cancelar"] is False
    assert salida["visible_tras_cancelar"] is False


def test_borrar_lleva_el_icono_universal(salida):
    assert salida["icono_borrar"].endswith("/iconos/color/borrar.svg")
