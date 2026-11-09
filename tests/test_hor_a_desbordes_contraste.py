"""Tanda horizontal, ronda 2, grupo A: textos que no se salen de su cuadro (es y
en) y contraste en oscuro de los recuadros corregidos, en el lienzo 1920x1200.

Desbordes: Login (con la ayuda y el aviso sin base de datos abiertos),
CambioClave, NuevoUsuario y cada paso del asistente de instalación (arnés
PruebaInstalacion.qml, datos largos), en español e inglés. Para cada Text
visible: la tinta (contentWidth/contentHeight) no pasa su propia caja y la caja
no pasa la ventana.

Contraste: en oscuro y horizontal, los recuadros de los campos de NuevoUsuario
y CambioClave, la lista de roles y el botón Cancelar toman Colores.fondoCampo /
fondoTarjeta (en vertical siguen sin color, preexistente); se exige WCAG 4,5:1
para el texto y 3:1 para el texto guía grande sobre esos fondos."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from tests.test_tema_oscuro import _colores, _contraste  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QUrl, QPointF
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.bridge import i18n_qml

    idioma, tema = sys.argv[1], sys.argv[2]
    i18n.cargar(); i18n.fijar_idioma(idioma); i18n_qml.instancia._consultar = lambda: None

    class Sesion:
        sinConexion = False
        def enviar(self, *a, **k):
            return sesion_backend.Resultado("ok", {}, 200)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)
    sesion_backend.ventana = lambda: Sesion()
    qapp = QGuiApplication([])
    _cargar_fuentes()

    PUENTE_NU = ("QtObject { property var roles: [{valor: 'operador', etiqueta: 'Operador'},"
                 " {valor: 'administrador', etiqueta: 'Administrador'}];"
                 " property var longitudesMaximas: ({}); property bool operacionEnCurso: false;"
                 " property int altaActual: 0; signal guardadoResuelto(string e, var x, string m, int a);"
                 " function estadoDe(x) { return '' } function abandonarPreparacion() {}"
                 " function navegar(d) {} function guardar() { return { enviado: false, errores: {} } } }")

    def ventana(cuerpo):
        ruta = f"{QML_DIR}/_hor_a2_{os.getpid()}.qml"
        open(ruta, "w", encoding="utf-8").write("""
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        id: ventana
        width: 1920; height: 1200; visible: true
        Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(ventana.width, ventana.height) }
        Binding { target: Escala; property: "factor"; value: 1.0 }
        Item { width: 1920; height: 1200
            %s
        }
    }
    """ % cuerpo)
        eng = QQmlApplicationEngine(); eng.addImportPath(QML_DIR)
        eng.load(QUrl.fromLocalFile(ruta)); os.remove(ruta)
        return eng, eng.rootObjects()[0]

    def arnes(nombre):
        eng = QQmlApplicationEngine(); eng.addImportPath(QML_DIR)
        eng.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/{nombre}"))
        win = eng.rootObjects()[0]
        win.setProperty("width", 1920); win.setProperty("height", 1200)
        return eng, win

    def items(it):
        yield it
        for h in it.childItems():
            yield from items(h)

    def visible(it):
        while it is not None:
            if not it.isVisible() or it.property("opacity") == 0:
                return False
            it = it.parentItem()
        return True

    def desbordes(win, escena):
        malos = []
        for t in items(win.contentItem()):
            if t.property("contentWidth") is None or t.property("text") in (None, ""):
                continue
            if t.metaObject().className().find("Text") < 0 or t.metaObject().className().find("Field") >= 0:
                continue
            if not visible(t) or t.width() <= 0:
                continue
            cw, ch = t.property("contentWidth"), t.property("contentHeight")
            p = t.mapToScene(QPointF(0, 0))
            caja = (p.x(), p.y(), t.width(), t.height())
            texto = str(t.property("text"))[:40]
            if cw > t.width() + 2:
                malos.append([escena, texto, "tinta_ancho", round(cw), round(t.width())])
            if ch > t.height() + 2:
                malos.append([escena, texto, "tinta_alto", round(ch), round(t.height())])
            if p.x() < -2 or p.x() + t.width() > 1922 or p.y() + t.height() > 1202:
                malos.append([escena, texto, "fuera", [round(v) for v in caja]])
        return malos

    salida = {"desbordes": [], "colores": {}}
    motores = []

    def con_tema(eng):
        if tema == "oscuro":
            eng.singletonInstance("Tema", "Colores").setProperty("oscuro", True)

    for nombre, cuerpo, accion in [
        ("login", "Login { objectName: 'p'; anchors.fill: parent;"
                  " puente: QtObject { property bool sinBaseDatos: true } }", "ayuda"),
        ("cambio", "CambioClave { objectName: 'p'; anchors.fill: parent }", None),
        ("nuevo", "NuevoUsuario { objectName: 'p'; anchors.fill: parent; puente: " + PUENTE_NU + " }", None),
    ]:
        eng, win = ventana(cuerpo); motores.append(eng); con_tema(eng)
        QTest.qWait(150)
        p = [o for o in items(win.contentItem()) if o.objectName() == "p"][0]
        if accion == "ayuda":
            p.setProperty("ayudaOlvidoVisible", True)
        QTest.qWait(100)
        salida["desbordes"] += desbordes(win, nombre)
        if nombre in ("nuevo", "cambio"):
            todos = list(items(win.contentItem()))
            campo = [o for o in todos if o.objectName() in ("campoNombre", "campo_clave_actual")][0]
            salida["colores"][nombre + "_campo"] = campo.parentItem().property("color").name().upper()
            if nombre == "nuevo":
                rol = [o for o in todos if o.objectName() == "campoRol"][0]
                lista = [o for o in todos if o.objectName() == "listaRoles"][0]
                salida["colores"]["nuevo_rol"] = rol.property("color").name().upper()
                salida["colores"]["nuevo_lista"] = lista.property("color").name().upper()
                guardar = [o for o in todos if o.objectName() == "botonGuardarUsuario"][0]
                hermanos = guardar.parentItem().childItems()
                cancelar = hermanos[hermanos.index(guardar) - 1]
                salida["colores"]["nuevo_cancelar"] = cancelar.property("color").name().upper()

    eng, win = arnes("PruebaInstalacion.qml"); motores.append(eng); con_tema(eng)
    QTest.qWait(150)
    inst = [o for o in items(win.contentItem()) if o.objectName() == "instalacion"][0]
    largos = [("serie", "SN260001"), ("codigo", "ABCD-EFGH-IJKL-MNOP-QRST-UVWX-YZ23-4567-ABCD-EFGH-IJKL-MNOP"),
              ("automatizado", True), ("serie_original", "SERIE-ORIGINAL-DEL-FABRICANTE-1234567"),
              ("modelo_original", "MODELO ORIGINAL DEL FABRICANTE CON NOMBRE MUY LARGO 500"),
              ("clase", "piso_lab"), ("numPuertas", 2), ("tipoPuerta", "motorized_locking"), ("puertaPc", 2),
              ("nivelEnfriamiento", 4), ("capacidadLitros", 2000), ("tipoCarga", "H"), ("fuenteVapor", "mixed")]
    for k, v in largos:
        inst.setProperty(k, v)
    for i in range(9):
        inst.setProperty("indice", i); QTest.qWait(80)
        salida["desbordes"] += desbordes(win, "instalacion_%d" % i)
    inst.setProperty("terminado", True); QTest.qWait(80)
    salida["desbordes"] += desbordes(win, "instalacion_listo")
    salida["valores"] = {k: inst.property(k) for k, _ in largos}
    print("RESULTADO=" + json.dumps(salida, ensure_ascii=False))
''')


def _correr(idioma, tema):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, idioma, tema], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


@pytest.fixture(scope="module", params=["es", "en"])
def claro(request):
    return _correr(request.param, "claro")


@pytest.fixture(scope="module")
def oscuro():
    return _correr("es", "oscuro")


def test_sin_textos_que_se_salen_de_su_cuadro(claro):
    assert claro["desbordes"] == []


def test_oscuro_sin_desbordes(oscuro):
    assert oscuro["desbordes"] == []


def test_recuadros_en_oscuro_toman_los_fondos_del_tema(oscuro):
    c = {n: v[1][3:] for n, v in _colores().items()}   # oscuro, #RRGGBB
    col = {k: "#" + v.lstrip("#")[-6:] for k, v in oscuro["colores"].items()}
    assert col["nuevo_campo"] == "#" + c["fondoCampo"]
    assert col["cambio_campo"] == "#" + c["fondoCampo"]
    assert col["nuevo_rol"] == "#" + c["fondoCampo"]
    assert col["nuevo_lista"] == "#" + c["fondoCampo"]
    assert col["nuevo_cancelar"] == "#" + c["fondoTarjeta"]


def test_recuadros_en_claro_siguen_blancos(claro):
    for k, v in claro["colores"].items():
        assert v.upper().endswith("FFFFFF"), k


@pytest.mark.parametrize("texto,fondo,minimo", [
    ("textoPrimario", "fondoCampo", 4.5),     # lo escrito en el campo, roles
    ("textoGuia", "fondoCampo", 3.0),         # texto guía (≥ 19 px)
    ("textoPrimario", "fondoTarjeta", 4.5),   # «Cancelar»
    ("textoSecundario", "fondoCampo", 3.0),   # ojo de contraseña (gráfico)
])
def test_contraste_wcag_de_los_pares_corregidos(texto, fondo, minimo):
    col = _colores()
    assert _contraste(col[texto][1], col[fondo][1]) >= minimo
    # antes (sin color: blanco) el texto claro del oscuro quedaba ilegible
    if texto == "textoPrimario":
        assert _contraste(col[texto][1], "#FFFFFFFF") < 1.5
