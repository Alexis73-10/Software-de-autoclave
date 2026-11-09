# tests/test_hor_e_desbordes.py
#
# Tanda horizontal, ronda 2, grupo E: en el lienzo horizontal 1920x1200, en
# español y en inglés y con los textos reales más largos, ningún texto de los
# modales, paneles y teclados se sale de su caja (contentWidth/contentHeight
# mayores que la caja sin reducción ni ajuste) ni del recuadro visible que lo
# contiene, y en el encabezado del numérico con el valor vacío la unidad no se
# monta sobre el rango. En subproceso, un QGuiApplication por idioma.

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml

    idioma = sys.argv[1]
    i18n.cargar(); i18n.fijar_idioma(idioma)
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()
    W, H = 1920, 1200
    claves = ["modelo", "serie", "serial_especifika", "id_maquina", "puertas", "puerta_pantalla",
              "enfriamiento", "fecha_instalacion", "ciclos_realizados", "ultimo_ciclo",
              "ultimo_mantenimiento", "ciclos_restantes", "version_software", "enlace_io",
              "emparejamiento_modulo_es", "version_modulo_es", "id_modulo_es"]
    filas = ",".join('{clave: "%s", valor: "2026-11-09 08:14", disponible: %s}'
                     % (c, "false" if c == "emparejamiento_modulo_es" else "true") for c in claves)
    QML = '''
    import QtQuick
    import Tema
    import Autoclave.I18n
    import "Componentes"
    Window {
        id: ventana
        width: %d; height: %d; visible: true
        Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(ventana.width, ventana.height) }
        Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }
        QtObject { id: comandos; property bool ventanaPrincipal: true; property bool fueraDeCiclo: true
                   property bool camaraNoSegura: true; property bool apagadoRechazado: true
                   property bool ocupado: false; property string mensaje: "ciclo en curso" }
        Item {
            id: lienzo; objectName: "lienzo"
            width: Escala.px(Escala.anchoDiseno); height: Escala.px(Escala.altoDiseno)
            Item { objectName: "c_tec"; anchors.fill: parent; visible: false
                PanelTeclado { id: tec; objectName: "tec" } }
            Item { objectName: "c_mc"; anchors.fill: parent; visible: false
                ModalConfirmacion { visible: true
                    titulo: I18n.t("ciclo.modal_forzar_titulo", I18n.lang)
                    cuerpo: I18n.t("ciclo.modal_forzar_cuerpo", I18n.lang)
                    nota: I18n.t("ciclo.modal_estado_seguro_nota", I18n.lang)
                    textoAccion: I18n.t("ciclo.confirmar_forzado", I18n.lang) } }
            Item { objectName: "c_mo"; anchors.fill: parent; visible: false
                ModalOperador { mensajeClave: "operador_ciclo.err_no_verificable"; elegido: 2
                    operadores: [{id: 1, nombre: "Ana"},
                                 {id: 2, nombre: "Operadora con un nombre muy largo que no cabe en una sola linea de la lista tactil"}] } }
            Item { objectName: "c_dc"; anchors.fill: parent; visible: false
                DialogoConfirmacion { visible: true
                    mensaje: I18n.t("equipo.apagar_pregunta", I18n.lang) + "\\n\\n" + I18n.t("equipo.apagar_camara_no_segura", I18n.lang)
                    textoConfirmar: I18n.t("equipo.apagar", I18n.lang)
                    textoCancelar: I18n.t("acciones.cancelar", I18n.lang) } }
            Item { objectName: "c_pe"; anchors.fill: parent; visible: false
                PanelEquipo { visible: true; comandosSistema: comandos
                    titulo: I18n.t("equipo.titulo", I18n.lang); textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
                    filas: [%s] } }
            Item { objectName: "c_pn"; anchors.fill: parent; visible: false
                PanelNotificaciones { visible: true
                    titulo: I18n.t("notificaciones.titulo", I18n.lang); textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
                    alarmas: ListModel { Component.onCompleted: {
                        append({ id: "SEN-04", level: "FALLA", priority: "media",
                                 description: "Sensor de presion de camara sin lectura; revise el transmisor, su alimentacion y el cableado hasta el modulo E/S" })
                        append({ id: "SUM-03", level: "ALERTA", priority: "baja", description: "Suministro de agua bajo" }) } } } }
            Item { objectName: "c_va"; anchors.fill: parent; visible: false
                VentanaDetalleAlarma { objectName: "va" } }
        }
    }
    ''' % (W, H, filas)
    ruta = f"{QML_DIR}/_hor_e_desb_{os.getpid()}.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.load(QUrl.fromLocalFile(ruta))
    os.remove(ruta)
    w = engine.rootObjects()[0]
    w.setWidth(W); w.setHeight(H); w.show()
    QTest.qWait(200)
    lienzo = w.findChild(QObject, "lienzo")
    from PySide6.QtCore import Q_RETURN_ARG
    from PySide6.QtQml import QQmlComponent
    comp = QQmlComponent(engine)
    comp.setData(b"import QtQuick\nQtObject { function info(t) { return JSON.stringify("
                 b"[t.fontSizeMode, t.elide, t.horizontalAlignment]) } }",
                 QUrl.fromLocalFile(QML_DIR + "/_info_hor_e.qml"))
    ayudante = comp.create()

    def info(t):
        return json.loads(QMetaObject.invokeMethod(ayudante, "info", Q_RETURN_ARG("QVariant"),
                                                   Q_ARG("QVariant", t)))

    def visuales(item):
        for h in item.childItems():
            yield h
            yield from visuales(h)

    def visible_de_verdad(it):
        while it is not None:
            if not it.isVisible() or it.opacity() == 0:
                return False
            it = it.parentItem()
        return True

    def rect(o, ref):
        r = o.mapRectToItem(ref, o.boundingRect())
        return (r.x(), r.y(), r.width(), r.height())

    def revisar(raiz, nombre):
        malos = []
        for t in visuales(raiz):
            if t.metaObject().className() != "QQuickText" or not visible_de_verdad(t):
                continue
            texto = t.property("text") or ""
            if not texto.strip():
                continue
            ancho, alto = t.width(), t.height()
            cw, ch = t.property("contentWidth"), t.property("contentHeight")
            fsm, elide, alinea = info(t)
            # fontSizeMode distinto de FixedSize reduce la letra: lo mide la revisión de capturas
            if fsm == 0 and elide == 0:
                if cw > ancho + 1.5:
                    malos.append([nombre, "tinta_ancho", texto[:40], round(cw), round(ancho)])
                if ch > alto + 1.5:
                    malos.append([nombre, "tinta_alto", texto[:40], round(ch), round(alto)])
            # recuadro visible que lo contiene (sin un recorte entre medio)
            p = t.parentItem(); recorte = False
            while p is not None and p is not raiz.parentItem():
                if p.clip():
                    recorte = True; break
                if p.metaObject().className() == "QQuickRectangle" and p.property("color").alpha() > 0:
                    break
                p = p.parentItem()
            if p is None or recorte or p is raiz.parentItem():
                continue
            x, y, a, h = rect(t, p)
            x0 = x if alinea == 1 else (x + a - cw if alinea == 2 else x + (a - cw) / 2)
            if x0 < -1.5 or x0 + min(cw, a if fsm else cw) > p.width() + 1.5 \
                    or y < -1.5 or y + min(ch, h) > p.height() + 1.5:
                malos.append([nombre, "sale_del_padre", texto[:40], round(x0), round(y), round(p.width()), round(p.height())])
        return malos

    r = {"malos": [], "solapes": [], "avisos": avisos}
    for n in ("c_mc", "c_mo", "c_dc", "c_pe", "c_pn"):
        c = w.findChild(QObject, n); c.setProperty("visible", True); QTest.qWait(250)
        r["malos"] += revisar(c, n)
        c.setProperty("visible", False)
    c = w.findChild(QObject, "c_va"); c.setProperty("visible", True)
    va = w.findChild(QObject, "va")
    QMetaObject.invokeMethod(va, "abrir", Q_ARG("QVariant", {
        "id": "SEN-04", "codigo": "SEN-04", "level": "FALLA", "priority": "media",
        "titulo": "Sensor de presion de camara sin lectura durante la esterilizacion del ciclo en curso",
        "description": "x " * 300, "accion": "y " * 200, "aparecida": "2026-11-09T10:21:07", "estado": "activa"}))
    QTest.qWait(300)
    r["malos"] += revisar(w.contentItem(), "c_va")
    QMetaObject.invokeMethod(va, "cerrar"); QTest.qWait(300)
    c.setProperty("visible", False)
    c = w.findChild(QObject, "c_tec"); c.setProperty("visible", True)
    tec = w.findChild(QObject, "tec")
    for tipo in ("alfa", "num"):
        if tipo == "alfa":
            QMetaObject.invokeMethod(tec, "abrirAlfanumerico",
                Q_ARG("QVariant", i18n.t("nuevo_usuario.confirmar_contrasena") if i18n.existe("nuevo_usuario.confirmar_contrasena") else "Confirmar contrasena nueva del usuario"),
                Q_ARG("QVariant", ""), Q_ARG("QVariant", 30), Q_ARG("QVariant", False),
                Q_ARG("QVariant", None), Q_ARG("QVariant", None))
            teclado = w.findChild(QObject, "tecladoAlfanumerico")
        else:
            QMetaObject.invokeMethod(tec, "abrirNumerico", Q_ARG("QVariant", "Presion de despresurizacion de la chaqueta"),
                Q_ARG("QVariant", "kPa"), Q_ARG("QVariant", None), Q_ARG("QVariant", 5),
                Q_ARG("QVariant", 50), Q_ARG("QVariant", 1), Q_ARG("QVariant", None),
                Q_ARG("QVariant", None))
            teclado = w.findChild(QObject, "tecladoNumerico")
        QTest.qWait(700)
        r["malos"] += revisar(teclado, "teclado_" + tipo)
        # encabezado: textos fuera de las teclas, sin solaparse entre sí
        textos = []
        for t in visuales(teclado):
            if t.metaObject().className() != "QQuickText" or not visible_de_verdad(t) or not (t.property("text") or "").strip():
                continue
            padre = t.parentItem()
            if padre is not None and padre.metaObject().className().startswith("Tecla_QML"):
                continue
            x, y, a, h = rect(t, lienzo)
            textos.append((t.property("text")[:20], x, y, t.property("contentWidth"), min(h, t.property("contentHeight"))))
        for i in range(len(textos)):
            for j in range(i + 1, len(textos)):
                a, b = textos[i], textos[j]
                if a[1] < b[1] + b[3] - 1 and b[1] < a[1] + a[3] - 1 and a[2] < b[2] + b[4] - 1 and b[2] < a[2] + a[4] - 1:
                    r["solapes"].append([tipo, a[0], b[0]])
    print("RESULTADO=" + json.dumps(r))
""")


@pytest.fixture(scope="module", params=["es", "en"])
def datos(request):
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": os.path.join(raiz, "src") + os.pathsep + raiz}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, request.param], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=raiz, timeout=300)
    for linea in p.stdout.splitlines():
        if linea.startswith("RESULTADO="):
            return json.loads(linea[len("RESULTADO="):])
    raise AssertionError(p.stdout[-2000:] + p.stderr[-3000:])


def test_ningun_texto_se_sale_de_su_caja_ni_de_su_recuadro(datos):
    assert datos["malos"] == [], datos["malos"]


def test_encabezado_del_teclado_sin_solapes_con_valor_vacio(datos):
    assert datos["solapes"] == [], datos["solapes"]


def test_sin_errores_de_referencia(datos):
    malos = [a for a in datos["avisos"] if "ReferenceError" in a or "TypeError" in a]
    assert malos == [], malos
