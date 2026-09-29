import QtQuick

Window {
    width: 480; height: 800
    visible: true

    Rectangle {
        id: barra
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 60
        color: "#303030"

        Text {
            text: "EN CICLO"
            color: "white"
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: centro.right
            anchors.rightMargin: 16
        }
    }

    Rectangle {
        id: centro
        anchors.top: barra.bottom
        anchors.bottom: botonera.top
        anchors.left: parent.left
        anchors.right: parent.right
        color: "#1060a0"
    }

    Rectangle {
        id: botonera
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        width: 200
        height: 90
        color: "#505050"
    }
}