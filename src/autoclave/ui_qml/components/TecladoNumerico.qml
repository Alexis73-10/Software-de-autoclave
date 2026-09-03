// ui_qml/components/TecladoNumerico.qml
//
// Teclado numérico en pantalla (§13.1 del plan de interfaz dual-pantalla).
// Sin punto decimal (D-18) — coma. Signo negativo solo si permiteNegativo.
// Teclas de al menos 64x64 px. Muestra rango y unidad del campo activo.
// Botón de confirmación deshabilitado fuera de rango (validación en vivo).
//
// Toda la lógica de acumulación/validación vive en el controller (puente a
// domain/teclado_numerico.py) — este componente solo dibuja y delega.

import QtQuick
import QtQuick.Controls
import Autoclave.Controllers 1.0

Rectangle {
    id: root

    property alias minimo: controller.minimo
    property alias maximo: controller.maximo
    property alias permiteNegativo: controller.permiteNegativo
    property alias controller: controller
    property string unidad: ""

    signal confirmado(real valor)
    signal cancelado()

    color: "#FFFFFF"
    implicitWidth: 296
    implicitHeight: 420

    TecladoNumericoController {
        id: controller
        objectName: "controller"
    }

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        Text {
            id: display
            text: (controller.texto.length ? controller.texto : "0") + (root.unidad ? " " + root.unidad : "")
            font.pixelSize: 28
        }

        Text {
            id: rangoLabel
            visible: isFinite(root.minimo) || isFinite(root.maximo)
            text: "Rango: " + (isFinite(root.minimo) ? root.minimo : "-") + " a " + (isFinite(root.maximo) ? root.maximo : "-")
            font.pixelSize: 12
            color: "#4D4D4D"
        }

        Grid {
            id: teclado
            columns: 3
            spacing: 4

            // Diez teclas de dígito, declaradas explícitamente en vez de un
            // Repeater: el layout es fijo (nunca cambia en tiempo de
            // ejecución), y evita la incubación asíncrona de Repeater, que
            // requiere una QQuickWindow con render loop activo para
            // completarse — frágil de instanciar en pruebas sin ventana.
            Button {
                objectName: "teclaNumerica"
                text: "7"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("7")
            }
            Button {
                objectName: "teclaNumerica"
                text: "8"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("8")
            }
            Button {
                objectName: "teclaNumerica"
                text: "9"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("9")
            }
            Button {
                objectName: "teclaNumerica"
                text: "4"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("4")
            }
            Button {
                objectName: "teclaNumerica"
                text: "5"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("5")
            }
            Button {
                objectName: "teclaNumerica"
                text: "6"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("6")
            }
            Button {
                objectName: "teclaNumerica"
                text: "1"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("1")
            }
            Button {
                objectName: "teclaNumerica"
                text: "2"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("2")
            }
            Button {
                objectName: "teclaNumerica"
                text: "3"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("3")
            }

            Button {
                objectName: "teclaSigno"
                text: "+/-"
                width: 64
                height: 64
                enabled: root.permiteNegativo
                onClicked: controller.presionarSigno()
            }

            Button {
                objectName: "teclaNumerica"
                text: "0"
                width: 64
                height: 64
                onClicked: controller.presionarDigito("0")
            }

            Button {
                objectName: "teclaComa"
                text: ","
                width: 64
                height: 64
                onClicked: controller.presionarComa()
            }
        }

        Row {
            spacing: 4

            Button {
                objectName: "teclaBorrar"
                text: "⌫"
                width: 140
                height: 64
                onClicked: controller.borrar()
            }

            Button {
                objectName: "botonConfirmar"
                text: "Confirmar"
                width: 140
                height: 64
                enabled: controller.valido
                onClicked: root.confirmado(controller.valor)
            }
        }
    }
}
