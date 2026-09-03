// ui_qml/components/alarms/AlarmaToast.qml
//
// Alarma severidad 1 — Informativo (§ alarmSeverity de tokens.json):
// toast, no persistente, sin confirmación. Componente presentacional puro
// — no decide cuándo mostrarse ni por cuánto tiempo; eso lo gestiona el
// host (futuro AlarmManager, F4). autoDismissMs=0 (desactivado) por
// defecto: no hay una duración de toast especificada en el plan ni en
// tokens.json, así que no se inventa un valor — el host la fija si la
// necesita.

import QtQuick

Rectangle {
    id: root

    property string alarmId: ""
    property string descripcion: ""
    property color color: "black"
    property int autoDismissMs: 0

    signal dismissed()

    implicitWidth: 320
    implicitHeight: 48
    radius: 8

    Timer {
        interval: root.autoDismissMs
        running: root.autoDismissMs > 0
        onTriggered: root.dismissed()
    }

    Text {
        objectName: "toastTexto"
        text: root.descripcion
        color: "white"
        anchors.centerIn: parent
        anchors.margins: 12
        elide: Text.ElideRight
    }
}
