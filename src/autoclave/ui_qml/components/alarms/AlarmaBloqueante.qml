// ui_qml/components/alarms/AlarmaBloqueante.qml
//
// Alarma severidad 4 — Fallo crítico (§ alarmSeverity de tokens.json):
// pantalla completa, bloqueante, siempre requiere confirmación. Hallazgo
// UI-05: "definida en tokens.json, sin maqueta" — sin mockup de
// referencia; diseño visual mínimo dentro de las restricciones del
// sistema de diseño (D-08: sin 3D en tiempo real). El host (futuro
// AlarmManager, F4) es responsable de dimensionar este componente a todo
// el lienzo y de que sea lo único interactivo mientras esté visible — el
// componente en sí no impone eso, solo se dibuja al tamaño que le den.

import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string alarmId: ""
    property string descripcion: ""
    property color color: "black"

    signal reconocida()

    Column {
        anchors.centerIn: parent
        spacing: 24
        width: parent.width * 0.8

        Text {
            objectName: "bloqueanteTexto"
            text: root.descripcion
            color: "white"
            font.pixelSize: 24
            font.bold: true
            wrapMode: Text.WordWrap
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
        }

        Button {
            objectName: "botonReconocer"
            text: "Reconocer"
            width: 200
            height: 64
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.reconocida()
        }
    }
}
