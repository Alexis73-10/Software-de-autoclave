"""Tanda 17 (ALM-01): listas de alarmas, alertas y fallos.

En el panel de la campana (PanelNotificaciones) y en la tarjeta de alarmas de
Preciclo cada fila muestra SOLO el nombre (título del catálogo en el idioma de
la interfaz) con el color de nivel. Al tocarla se abre la ventana emergente
VentanaDetalleAlarma con nombre, nivel, código, hora de activación,
descripción, causa o acción y estado, el botón DESPEJAR en COM-02/COM-03 (antes
en la fila) y Cerrar. «Confirmar y llevar a estado seguro» sigue fuera de la
ventana (SeccionEstadoSeguro, DECISIÓN SIN CONFIRMAR).

También SON-01 en la tarjeta de entradas de Preciclo: una entrada marcada
`monitoreo` lleva el rótulo «(monitoreo)».
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.req("ALM-01")

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
RAIZ_QML = RAIZ / "src" / "autoclave" / "ui_qml" / "qml"
FRAGMENTO_I18N = RAIZ / "docs" / "informes" / "tanda17" / "i18n" / "s4.json"

_COM02 = {"id": "COM-02|X", "codigo": "COM-02", "level": "FALLA", "nivel": "ALARMA",
          "description": "Enlace serie perdido (descripción larga)",
          "titulo": "Sin comunicación con la tarjeta",
          "textos": {"es": {"titulo": "Sin comunicación con la tarjeta",
                            "descripcion": "Enlace serie perdido (descripción larga)",
                            "accion": "Revise el cable de la tarjeta"},
                     "en": {"titulo": "No communication with the board",
                            "descripcion": "Serial link lost (long description)",
                            "accion": "Check the board cable"}},
          "accion": "Revise el cable de la tarjeta", "aparecida": "2026-10-26T10:15:30",
          "estado": "ACTIVA", "requiere_reconocimiento": True, "reconocida_por": None}
_SEN06 = {"id": "SEN-06", "codigo": "SEN-06", "level": "EMERGENCIA", "nivel": "FALLO_CRITICO",
          "description": "Sensor sin lectura",
          "titulo": "Sensor de presión sin lectura",
          "textos": {"es": {"titulo": "Sensor de presión sin lectura", "descripcion": "Sensor sin lectura",
                            "accion": "Llame a servicio"},
                     "en": {"titulo": "Pressure sensor without reading",
                            "descripcion": "Sensor without reading", "accion": "Call service"}},
          "accion": "Llame a servicio", "aparecida": "2026-10-26T09:00:00",
          "estado": "RESUELTA_SIN_RECONOCER", "requiere_reconocimiento": True, "reconocida_por": None}


# ── modelo (Python) ─────────────────────────────────────────────────────────

def test_modelo_expone_los_campos_del_detalle():
    from autoclave.ui_qml.bridge.ui_bridge import AlarmListModel
    m = AlarmListModel()
    m.establecer([_COM02, _SEN06, {"id": "X", "estado": "ACTIVA", "reconocida_por": "ana"}])
    f = m.filas()
    assert f[0]["codigo"] == "COM-02" and f[0]["aparecida"] == "2026-10-26T10:15:30"
    assert f[0]["titulos"] == {"es": "Sin comunicación con la tarjeta",
                               "en": "No communication with the board"}
    assert f[0]["acciones"]["en"] == "Check the board cable"
    assert f[0]["estado"] == "activa" and f[0]["requiere_reconocimiento"] is True
    assert f[1]["estado"] == "resuelta"
    assert f[2]["estado"] == "reconocida" and f[2]["codigo"] == "" and f[2]["titulos"] == {}
    roles = {bytes(n).decode() for n in m.roleNames().values()}
    assert {"codigo", "titulo", "titulos", "accion", "acciones", "aparecida", "estado"} <= roles
    assert m.detalle("SEN-06")["codigo"] == "SEN-06"
    assert m.detalle("NO-EXISTE") == {}


# ── QML ─────────────────────────────────────────────────────────────────────

_SCRIPT = r"""
import json, sys
from PySide6.QtCore import QObject, QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
import autoclave.ui_qml.bridge.i18n_qml  # registra I18n
from autoclave.ui_qml.bridge.ui_bridge import AlarmListModel
from autoclave import i18n

cfg = json.loads(sys.argv[3])
i18n.cargar()
# claves nuevas de s4 aún sin integrar en i18n/*.json (docs/informes/tanda17/i18n/s4.json)
for _idioma, _claves in cfg["fragmento"].items():
    for _clave, _texto in _claves.items():
        _nodo = i18n._catalogos[_idioma]
        _partes = _clave.split(".")
        for _p in _partes[:-1]:
            _nodo = _nodo.setdefault(_p, {})
        _nodo.setdefault(_partes[-1], _texto)
i18n.fijar_idioma(cfg["idioma"])
qml_dir, qml = sys.argv[1], sys.argv[2]
app = QGuiApplication([])
engine = QQmlEngine()
engine.addImportPath(qml_dir)
avisos = []
engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
modelo = AlarmListModel()
modelo.establecer(cfg["alarmas"])
comp = QQmlComponent(engine)
comp.setData(qml.encode("utf-8"), QUrl.fromLocalFile(qml_dir + "/prueba_t17_alarmas.qml"))
ventana = comp.createWithInitialProperties({"modelo": modelo})
assert ventana is not None, comp.errorString()
ventana.show()
QTest.qWait(200)

def _visual(it, nombre):
    for h in it.childItems():
        if h.objectName() == nombre:
            return h
        e = _visual(h, nombre)
        if e is not None:
            return e
    return None

def visibles_de(nombre, it=None):
    # ítems visibles con ese objectName en el árbol visual (desambigua)
    out = []
    for h in (it or ventana.contentItem()).childItems():
        if h.objectName() == nombre and h.isVisible():
            out.append(h)
        out.extend(visibles_de(nombre, h))
    return out

def es_descendiente(item, ancestro):
    while item is not None:
        if item == ancestro:
            return True
        item = item.parentItem()
    return False

def buscar_en(obj, nombre):
    return obj.findChild(QObject, nombre) or _visual(obj, nombre)

def tocar(item):
    from PySide6.QtCore import QPoint, Qt
    c = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(c.x(), c.y()))
    QTest.qWait(80)

def buscar(nombre):
    # árbol de objetos y, si no está (delegados de Repeater/ListView), el visual
    return ventana.findChild(QObject, nombre) or _visual(ventana.contentItem(), nombre)

def textos():
    # árbol visual (los delegados no son hijos QObject de la ventana)
    out = []
    def rec(it):
        for h in it.childItems():
            if not h.isVisible():
                continue
            if h.inherits("QQuickText"):
                out.append(h.property("text"))
            rec(h)
    rec(ventana.contentItem())
    return out

sistema = buscar("sistemaFalso")
r = {}
exec(cfg["pasos"])
r["avisos"] = avisos
print("RES=" + json.dumps(r, ensure_ascii=False))
"""

_QML_PANEL = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 1200; height: 1920; visible: true
    required property var modelo
    Binding { target: Escala; property: "factor"; value: 1 }
    QtObject {
        id: sistema
        objectName: "sistemaFalso"
        property bool ocupado: false
        property string mensaje: ""
        property string mensajeDespejar: ""
        property var despejadas: []
        function descartarMensajeDespejar() { mensajeDespejar = "" }
        function despejarAlarma(c) { despejadas = despejadas.concat([c]) }
    }
    QtObject {
        id: puenteFalso
        property bool noAbrir: false
        property bool paroActivo: false
        property bool estadoSeguroActivo: false
        property bool estadoSeguroRequiereConfirmacion: false
        property bool modoPrueba: false
        property bool connected: true
        property string estadoTarjeta: "ok"
    }
    PanelNotificaciones {
        objectName: "panelNotificaciones"
        alarmas: ventana.modelo
        puente: puenteFalso
        comandosSistema: sistema
    }
}
"""

_PASOS_PANEL = r"""
panel = buscar("panelNotificaciones")
QMetaObject.invokeMethod(panel, "abrir")
buscar("grupoAlarmas").setProperty("expandido", True)
QTest.qWait(100)
fila = buscar("filaAlarmaPanel_COM-02|X")
r["fila_texto"] = fila.property("descripcion")
r["fila_sin_despejar"] = not _visual(fila, "botonDespejar").property("visible")
r["vistos_antes"] = textos()
detalle = buscar("detalleAlarmaPanel")
r["cerrada_antes"] = not detalle.property("abierta")
fila.pulsada.emit()
QTest.qWait(100)
r["abierta"] = detalle.property("abierta")
capa = buscar("capaDetalleAlarma")
r["sobre_la_ventana"] = capa.parentItem() == ventana.contentItem()
r["vistos_detalle"] = textos()
# R4 (V17-s4-06): clic real sobre el único DESPEJAR visible
_vis = visibles_de("botonDespejarDetalle")
r["boton_despejar"] = len(_vis) == 1
tocar(_vis[0])
QTest.qWait(50)
r["despejadas"] = sistema.property("despejadas").toVariant()
# la alarma deja de estar activa con la ventana abierta: sin acciones
modelo.establecer([a for a in modelo.filas() if a["id"] != "COM-02|X"])
QTest.qWait(50)
r["vigente_tras_retiro"] = detalle.property("vigente")
r["boton_tras_retiro"] = buscar("botonDespejarDetalle").isVisible()
buscar("botonCerrarDetalle").pulsado.emit()
QTest.qWait(50)
r["cerrada"] = not detalle.property("abierta")
r["capa_vuelve"] = capa.parentItem() != ventana.contentItem()
# SEN-06 (emergencia, resuelta sin reconocer): sin DESPEJAR
buscar("filaAlarmaPanel_SEN-06").pulsada.emit()
QTest.qWait(50)
r["sen06_sin_despejar"] = not buscar("botonDespejarDetalle").isVisible()
r["sen06_vistos"] = textos()
QMetaObject.invokeMethod(panel, "cerrar")
QTest.qWait(50)
r["cierra_con_panel"] = not detalle.property("abierta")
"""


def _correr(qml, pasos, idioma="es", alarmas=None):
    cfg = {"idioma": idioma, "pasos": pasos, "alarmas": alarmas if alarmas is not None else [_COM02, _SEN06],
           "fragmento": json.loads(FRAGMENTO_I18N.read_text(encoding="utf-8"))}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, str(RAIZ_QML), qml,
                        json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=RAIZ, timeout=120, env=env)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RES=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[4:])


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_panel_fila_solo_nombre_y_detalle_al_tocar(idioma):
    r = _correr(_QML_PANEL, _PASOS_PANEL, idioma)
    t = _COM02["textos"][idioma]
    assert r["avisos"] == []
    # la fila: solo el nombre, sin la descripción ni el botón DESPEJAR
    assert r["fila_texto"] == t["titulo"]
    assert r["fila_sin_despejar"] is True
    assert t["descripcion"] not in r["vistos_antes"]
    # la ventana de detalle, sobre toda la ventana de la aplicación
    assert r["cerrada_antes"] and r["abierta"] and r["sobre_la_ventana"]
    vistos = r["vistos_detalle"]
    for esperado in (t["titulo"], t["descripcion"], t["accion"], "COM-02", "2026-10-26 10:15:30"):
        assert esperado in vistos, esperado
    from autoclave import i18n
    i18n.cargar()
    assert i18n.t("alarma_detalle.estado_activa", idioma) in vistos
    assert i18n.t("alarma_detalle.nivel_alarma", idioma) in vistos
    assert i18n.t("alarma_detalle.cerrar", idioma) in vistos
    # DESPEJAR (COM-02) desde la ventana
    assert r["boton_despejar"] is True and r["despejadas"] == ["COM-02|X"]
    # retirada con la ventana abierta: sin acciones; Cerrar la cierra
    assert r["vigente_tras_retiro"] is False and r["boton_tras_retiro"] is False
    assert r["cerrada"] and r["capa_vuelve"]
    # SEN-06: emergencia, sin DESPEJAR
    assert r["sen06_sin_despejar"] is True
    assert i18n.t("alarma_detalle.nivel_emergencia", idioma) in r["sen06_vistos"]
    assert r["cierra_con_panel"] is True


def test_preciclo_tarjeta_solo_nombre_detalle_y_monitoreo():
    qml = (RAIZ_QML / "Pantallas" / "PantallaPreciclo.qml").read_text(encoding="utf-8")
    # la fila abre el detalle; el texto de la fila es el título; la ventana existe
    assert "detalleAlarmaPreciclo.abrirDesde(fila.model)" in qml
    assert "(fila.model.titulos ?? {})[I18n.lang] || fila.model.titulo" in qml
    assert "VentanaDetalleAlarma {" in qml
    # «Confirmar y llevar a estado seguro» queda fuera de la ventana emergente
    ventana = (RAIZ_QML / "Componentes" / "VentanaDetalleAlarma.qml").read_text(encoding="utf-8")
    assert "confirmarEstadoSeguro" not in ventana and "SeccionEstadoSeguro {" not in ventana
    assert "SeccionEstadoSeguro {" in qml


_QML_PRECICLO = r"""
import QtQuick
import Tema
import "Pantallas"
Window {
    id: ventana
    width: 1200; height: 1920; visible: true
    required property var modelo
    Binding { target: Escala; property: "factor"; value: 1 }
    QtObject {
        id: sistema
        objectName: "sistemaFalso"
        property bool ocupado: false
        property string mensaje: ""
        property string mensajeDespejar: ""
        property var despejadas: []
        property int confirmaciones: 0
        function descartarMensajeDespejar() { mensajeDespejar = "" }
        function despejarAlarma(c) { despejadas = despejadas.concat([c]) }
        function confirmarEstadoSeguro() { confirmaciones += 1 }
    }
    QtObject {
        id: puenteFalso
        objectName: "puenteFalso"
        // R4 (V17-s4-06): estado seguro por confirmar, para ver el botón
        property bool estadoSeguroActivo: true
        property bool estadoSeguroRequiereConfirmacion: true
        property bool paroActivo: false
        property bool noAbrir: false
        property bool modoPrueba: false
        property var alarms: ventana.modelo
        property bool connected: true
        property string estadoTarjeta: "ok"
        property string machineState: "PREPARADO"
        property var entradasMostradas: [
            {clave: "temp_camara", tipo: "temp", valor: "134.0", unidad: "°C", monitoreo: false},
            {clave: "temp_2_camara", tipo: "temp", valor: "—", unidad: "°C", monitoreo: true}]
        property var seriesGrafica: []
    }
    PantallaPreciclo {
        anchors.fill: parent
        puente: puenteFalso
        comandosSistema: sistema
    }
}
"""

_PASOS_PRECICLO = r"""
QTest.qWait(200)
r["vistos"] = textos()
fila = buscar("filaAlarmaPreciclo_COM-02|X")
r["hay_fila"] = fila is not None
r["hay_area"] = _visual(fila, "areaFilaAlarmaPreciclo") is not None
# toque real en el centro de la fila
from PySide6.QtCore import QPoint, Qt
centro = fila.mapToScene(fila.boundingRect().center()).toPoint()
QTest.mouseClick(ventana, Qt.LeftButton, Qt.NoModifier, QPoint(centro.x(), centro.y()))
QTest.qWait(100)
detalle = buscar("detalleAlarmaPreciclo")
r["abierta"] = detalle.property("abierta")
r["vistos_detalle"] = textos()
# R4 (V17-s4-06): hay dos ventanas de detalle (Preciclo y campana) con los
# mismos objectName; se toca el DESPEJAR visible, con clic real
visibles = visibles_de("botonDespejarDetalle")
r["despejar_visibles"] = len(visibles)
r["despejar_en_detalle_preciclo"] = bool(visibles) and es_descendiente(visibles[0], buscar_en(detalle, "capaDetalleAlarma"))
tocar(visibles[0])
r["despejadas"] = sistema.property("despejadas").toVariant()
# «Confirmar y llevar a estado seguro»: visible y FUERA de la ventana emergente
capa = buscar_en(detalle, "capaDetalleAlarma")
confirmar = visibles_de("botonConfirmarEstadoSeguro")
r["confirmar_visible"] = len(confirmar) >= 1
r["confirmar_fuera"] = all(not es_descendiente(b, capa) for b in confirmar)
buscar_en(capa, "botonCerrarDetalle").pulsado.emit()
QTest.qWait(50)
tocar(confirmar[0])
r["confirmaciones"] = sistema.property("confirmaciones")
"""


def test_preciclo_en_pantalla():
    pasos = "from PySide6.QtCore import Q_ARG\n" + _PASOS_PRECICLO
    r = _correr(_QML_PRECICLO, pasos)
    assert [a for a in r["avisos"] if "Unidades" not in a and "sesion" not in a.lower()] == [], r["avisos"]
    t = _COM02["textos"]["es"]
    assert r["hay_fila"] is True and r["hay_area"] is True
    assert t["titulo"] in r["vistos"] and t["descripcion"] not in r["vistos"], r["vistos"]
    assert r["abierta"] is True
    assert t["descripcion"] in r["vistos_detalle"] and t["accion"] in r["vistos_detalle"]
    assert r["despejadas"] == ["COM-02|X"]
    # R4 (V17-s4-06): el DESPEJAR tocado es el único visible, el del detalle de Preciclo
    assert r["despejar_visibles"] == 1 and r["despejar_en_detalle_preciclo"] is True
    # «Confirmar y llevar a estado seguro» se ve fuera de la ventana y funciona con clic real
    assert r["confirmar_visible"] is True and r["confirmar_fuera"] is True
    assert r["confirmaciones"] == 1
    # SON-01: la entrada de la sonda No en uso se muestra; desde el 28-oct
    # (6f06dd0) sin el sufijo «(monitoreo)», que desbordaba la casilla
    assert not any(v.endswith("(monitoreo)") for v in r["vistos"]), r["vistos"]
