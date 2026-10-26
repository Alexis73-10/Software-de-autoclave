
import QtQuick
import Tema
import "Pantallas"
Window {
    width: 1200; height: 1920; visible: true
    Binding { target: Escala; property: "factor"; value: 1.000000 }
    QtObject { id: puenteFalso; objectName: "puente"; property string machineState: "PREPARADO"
               property bool connected: true }
    Opciones { objectName: "opciones"; anchors.fill: parent; puente: puenteFalso }
}
