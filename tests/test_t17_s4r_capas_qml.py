"""Tanda 17, revisión R4 (s4).

- V17-s4-01/03: el motivo del rechazo de DESPEJAR (ComandosSistema.mensajeDespejar)
  se ve DENTRO de la ventana de detalle (antes solo en el panel, tapado por
  ella), se descarta al cerrarla, y una alarma ya reconocida no ofrece DESPEJAR.
- V17-s4-02: las capas emergentes sobre toda la ventana (Desplegable,
  Calendario, VentanaDetalleAlarma) se cierran con Capas.cerrarTodas(), que
  Main.qml llama en irAPanelSeguridad() (paro o estado seguro por confirmar),
  y la ventana de detalle y el calendario se cierran si su pantalla se oculta.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from tests.test_t17_s4_alarmas_qml import _COM02, _QML_PANEL, _SEN06, _correr  # noqa: E402

pytestmark = pytest.mark.req("ALM-01")

RAIZ_QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml"


_PASOS_MENSAJE = r"""
panel = buscar("panelNotificaciones")
QMetaObject.invokeMethod(panel, "abrir")
buscar("grupoAlarmas").setProperty("expandido", True)
QTest.qWait(80)
detalle = buscar("detalleAlarmaPanel")
buscar("filaAlarmaPanel_COM-02|X").pulsada.emit()
QTest.qWait(50)
r["sin_mensaje"] = not buscar("mensajeDespejarDetalle").isVisible()
sistema.setProperty("mensajeDespejar", "notificaciones.despejar_sin_enlace")
QTest.qWait(50)
m = buscar("mensajeDespejarDetalle")
r["mensaje_visible"] = m.isVisible()
r["mensaje_texto"] = m.property("text")
r["mensaje_en_detalle"] = es_descendiente(m, buscar_en(detalle, "capaDetalleAlarma"))
buscar("botonCerrarDetalle").pulsado.emit()
QTest.qWait(50)
r["descartado"] = sistema.property("mensajeDespejar")
# ya reconocida: sin DESPEJAR
modelo.establecer([dict(a, reconocida_por="ana") if a["id"] == "COM-02|X" else a for a in RECONOCIDA])
QTest.qWait(50)
buscar("filaAlarmaPanel_COM-02|X").pulsada.emit()
QTest.qWait(50)
datos = detalle.property("datos")
datos = datos.toVariant() if hasattr(datos, "toVariant") else datos
r["estado_reconocida"] = datos["estado"]
r["despejar_reconocida"] = len(visibles_de("botonDespejarDetalle"))
"""


def test_mensaje_de_despejar_en_la_ventana_y_reconocida_sin_despejar():
    from autoclave import i18n
    i18n.cargar()
    pasos = "RECONOCIDA = " + repr([_COM02, _SEN06]) + "\n" + _PASOS_MENSAJE
    r = _correr(_QML_PANEL, pasos)
    assert r["avisos"] == [], r["avisos"]
    assert r["sin_mensaje"] is True
    assert r["mensaje_visible"] is True and r["mensaje_en_detalle"] is True
    assert r["mensaje_texto"] == i18n.t("notificaciones.despejar_sin_enlace", "es")
    assert r["descartado"] == ""                       # se descarta al cerrar la ventana
    assert r["estado_reconocida"] == "reconocida"
    assert r["despejar_reconocida"] == 0


_QML_CAPAS = r"""
import QtQuick
import Tema
import "Componentes"
Window {
    id: ventana
    width: 1200; height: 1920; visible: true
    required property var modelo
    Binding { target: Escala; property: "factor"; value: 1 }
    QtObject { id: sistema; objectName: "sistemaFalso" }
    function cerrarCapas() { Capas.cerrarTodas() }
    Item {
        id: pantalla
        objectName: "pantalla"
        anchors.fill: parent
        Desplegable {
            objectName: "desplegable"
            width: 400
            opciones: [{ valor: 1, texto: "uno" }, { valor: 2, texto: "dos" }]
            valor: 1
        }
        Calendario { objectName: "calendario" }
        VentanaDetalleAlarma { objectName: "detalle"; alarmas: ventana.modelo }
    }
}
"""

_PASOS_CAPAS = r"""
d, c, v = buscar("desplegable"), buscar("calendario"), buscar("detalle")
def abrir_todas():
    QMetaObject.invokeMethod(d, "abrir")
    c.abrir("2026-10-26", "Fecha")
    v.abrirDesde({"id": "COM-02|X"})
    QTest.qWait(50)
    return [d.property("abierto"), c.property("abierta"), v.property("abierta")]
r["abiertas"] = abrir_todas()
r["sobre_ventana"] = all(x.parentItem() == ventana.contentItem()
                         for x in (buscar("capaDesplegable"), buscar("capaCalendario"), buscar("capaDetalleAlarma")))
QMetaObject.invokeMethod(ventana, "cerrarCapas")
QTest.qWait(50)
r["tras_cerrar"] = [d.property("abierto"), c.property("abierta"), v.property("abierta")]
r["capas_visibles"] = [buscar(n).isVisible() for n in ("capaDesplegable", "capaCalendario", "capaDetalleAlarma")]
# la pantalla que las contiene se oculta: también se cierran
r["abiertas_2"] = abrir_todas()
buscar("pantalla").setProperty("visible", False)
QTest.qWait(50)
r["tras_ocultar"] = [d.property("abierto"), c.property("abierta"), v.property("abierta")]
"""


def test_capas_se_cierran_con_la_seguridad_urgente_y_al_ocultarse():
    r = _correr(_QML_CAPAS, _PASOS_CAPAS)
    assert r["avisos"] == [], r["avisos"]
    assert r["abiertas"] == [True, True, True] and r["sobre_ventana"] is True
    assert r["tras_cerrar"] == [False, False, False]
    assert r["capas_visibles"] == [False, False, False]
    assert r["abiertas_2"] == [True, True, True]
    assert r["tras_ocultar"] == [False, False, False]


def test_main_cierra_las_capas_en_ir_a_panel_seguridad():
    """Main.qml irAPanelSeguridad(): con la seguridad urgente cierra las capas
    (Capas.cerrarTodas) antes de cualquier salida anticipada, junto al teclado
    (SAF-02)."""
    main = (RAIZ_QML / "Main.qml").read_text(encoding="utf-8")
    cuerpo = re.search(r"function irAPanelSeguridad\(\) \{(.*?)\n    \}", main, re.S).group(1)
    i_capas = cuerpo.index("Capas.cerrarTodas()")
    assert cuerpo.index("if (!seguridadUrgente)") < i_capas < cuerpo.index('actual === "areaLogin"')
    assert "onSeguridadUrgenteChanged: irAPanelSeguridad()" in main
    qmldir = (RAIZ_QML / "Tema" / "qmldir").read_text(encoding="utf-8")
    assert "singleton Capas 1.0 Capas.qml" in qmldir
    for comp in ("Desplegable.qml", "Calendario.qml", "VentanaDetalleAlarma.qml"):
        assert "function onCierreSolicitado()" in (RAIZ_QML / "Componentes" / comp).read_text(encoding="utf-8")
