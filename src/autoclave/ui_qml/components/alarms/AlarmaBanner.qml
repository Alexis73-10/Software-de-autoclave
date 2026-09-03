// ui_qml/components/alarms/AlarmaBanner.qml
//
// Alarma severidad 2 — Aviso (banner, sin ack) y severidad 3 — Alarma
// (banner parpadeante, con ack) — mismo componente, `parpadea`/
// `requiereAck` como propiedades (§ alarmSeverity de tokens.json).
// Parpadeo a 1 Hz por defecto (tokens.json → motion.alarmBlinkHz).
// Componente presentacional puro: emite `reconocida()`, no llama al
// backend — eso lo hace el host (futuro AlarmManager, F4).

import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string alarmId: ""
    property string descripcion: ""
    property color color: "black"
    property bool requiereAck: false
    property bool parpadea: false
    property real blinkHz: 1.0

    signal reconocida()

    implicitWidth: 736
    implicitHeight: 56

    SequentialAnimation on opacity {
        objectName: "blinkAnimation"
        running: root.parpadea
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.4; duration: 500 / root.blinkHz }
        NumberAnimation { from: 0.4; to: 1.0; duration: 500 / root.blinkHz }
    }

    Row {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        Text {
            objectName: "bannerTexto"
            text: root.descripcion
            color: "white"
            width: parent.width - (requiereAck ? 120 : 0) - 12
            elide: Text.ElideRight
            anchors.verticalCenter: parent.verticalCenter
        }

        Button {
            objectName: "botonReconocer"
            text: "Reconocer"
            visible: root.requiereAck
            width: 108
            height: 48
            anchors.verticalCenter: parent.verticalCenter
            onClicked: root.reconocida()
        }
    }
}
