# Revisión visual (RV, etapa A): el detector de solapes de
# tests/helpers/solapes_qml.py en un QML mínimo offscreen.

from tests.helpers.solapes_qml import revisar_qml

_CAB = "import QtQuick\nWindow { width: 400; height: 400; visible: true\n"


def _solapes(cuerpo, tmp_path):
    return revisar_qml(_CAB + cuerpo + "\n}\n", str(tmp_path))


def test_dos_textos_encimados_dan_un_solape(tmp_path):
    r = _solapes("""
        Text { x: 10; y: 10; text: "Temperatura"; font.pixelSize: 30 }
        Text { x: 20; y: 15; text: "Presión"; font.pixelSize: 30 }
    """, tmp_path)
    assert len(r) == 1
    assert r[0]["tipo"] == "solape"
    assert {r[0]["a"]["texto"], r[0]["b"]["texto"]} == {"Temperatura", "Presión"}
    assert r[0]["area"] > 0


def test_texto_sobre_su_rectangulo_no_es_solape(tmp_path):
    r = _solapes("""
        Rectangle { x: 10; y: 10; width: 200; height: 60; color: "red"
            Text { anchors.centerIn: parent; text: "Iniciar"; font.pixelSize: 24 } }
    """, tmp_path)
    assert r == []


def test_texto_bajo_un_modal_visible_no_cuenta(tmp_path):
    r = _solapes("""
        Text { x: 10; y: 10; text: "Fondo uno"; font.pixelSize: 30 }
        Text { x: 20; y: 15; text: "Fondo dos"; font.pixelSize: 30 }
        Rectangle { anchors.fill: parent; color: "#80000000"
            Text { x: 200; y: 300; text: "Modal"; font.pixelSize: 20 } }
    """, tmp_path)
    assert r == []


def test_textos_separados_por_un_clip_no_son_solape(tmp_path):
    r = _solapes("""
        Item { x: 0; y: 0; width: 100; height: 50; clip: true
            Text { x: 0; y: 0; text: "Visible"; font.pixelSize: 20 }
            Text { x: 0; y: 60; text: "Recortado"; font.pixelSize: 20 } }
        Text { x: 0; y: 60; text: "Afuera"; font.pixelSize: 20 }
    """, tmp_path)
    assert r == []


def test_texto_debajo_de_un_boton_si_es_solape(tmp_path):
    r = _solapes("""
        Text { x: 10; y: 10; text: "Valor del ciclo"; font.pixelSize: 24 }
        Rectangle { x: 20; y: 5; width: 120; height: 40; color: "blue"
            Text { anchors.centerIn: parent; text: "Botón"; font.pixelSize: 20 }
            MouseArea { anchors.fill: parent } }
    """, tmp_path)
    assert len(r) >= 1


def test_hora_grande_sobre_la_fecha_no_cuenta_el_interlineado(tmp_path):
    # la caja de línea de un texto grande pasa sobre el de abajo, la tinta no
    r = _solapes("""
        Text { id: hora; x: 10; y: 0; text: "18:46"; font.pixelSize: 96; lineHeight: 1.3 }
        Text { x: 40; y: hora.y + hora.height - 12; text: "19 nov"; font.pixelSize: 24 }
    """, tmp_path)
    assert r == []
