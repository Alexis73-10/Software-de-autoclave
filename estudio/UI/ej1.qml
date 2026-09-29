import QtQuick

Window {
    id: raiz
    width: 400; height: 200
    visible: true

    property real presion: 0.0
    property string estado: presion > 1.0 ? "PRESURIZADO" : "VENTEADO"

    Text {
        id: etiqueta
        anchors.centerIn: parent
        text: raiz.estado + " — " + raiz.presion.toFixed(2) + " bar"
    }

    Component.onCompleted: raiz.presion = 1.5

    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: {
            raiz.presion += 0.5
            etiqueta.text = "midiendo…"
        }
    }
}