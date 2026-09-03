// ui_qml/components/TecladoAlfanumerico.qml
//
// Teclado alfanumérico en pantalla (§13.2 del plan de interfaz dual-
// pantalla). QWERTY español, sin tildes, con ñ. Capa de símbolos con @.
// Alternancia mayúsculas/minúsculas. Teclas de al menos 48x48 px.
//
// La grilla de teclas de cada capa (letras/símbolos) se reconstruye por
// código vía Component.createObject() en vez de Repeater: Repeater
// necesita una QQuickWindow con render loop activo para incubar sus
// delegates, algo que una prueba headless (QQmlComponent sin ventana) no
// puede garantizar — ver TecladoNumerico.qml para el mismo razonamiento,
// confirmado empíricamente antes de escribir este componente.
//
// Toda la lógica de acumulación/mayúsculas/capa vive en el controller
// (puente a domain/teclado_alfanumerico.py) — este componente solo dibuja
// y delega.

import QtQuick
import QtQuick.Controls
import Autoclave.Controllers 1.0

Rectangle {
    id: root

    property alias controller: controller

    signal confirmado(string texto)
    signal cancelado()

    color: "#FFFFFF"
    implicitWidth: 560
    implicitHeight: 320

    TecladoAlfanumericoController {
        id: controller
        objectName: "controller"
    }

    Component {
        id: teclaCaracterComp
        Button {
            objectName: "teclaCaracter"
            width: 48
            height: 48
            property string caracterBase: ""
            onClicked: controller.presionarCaracter(caracterBase)
        }
    }

    Component {
        id: filaComp
        Row {
            spacing: 4
        }
    }

    function reconstruirFilas() {
        // Item.destroy() difiere la eliminación al próximo ciclo del event
        // loop (como deleteLater()) — si no se desvincula del padre ahora
        // mismo, sigue contando en filasContainer.children mientras se
        // agregan las filas nuevas, duplicando temporalmente la grilla.
        while (filasContainer.children.length > 0) {
            var hijo = filasContainer.children[0]
            hijo.parent = null
            hijo.destroy()
        }

        var filas = controller.capaSimbolos ? controller.filasSimbolos : controller.filasLetras

        for (var f = 0; f < filas.length; f++) {
            var filaTexto = filas[f]
            var rowObj = filaComp.createObject(filasContainer)
            for (var c = 0; c < filaTexto.length; c++) {
                var base = filaTexto[c]
                var etiqueta = (!controller.capaSimbolos && controller.mayusculas) ? base.toUpperCase() : base
                teclaCaracterComp.createObject(rowObj, {"text": etiqueta, "caracterBase": base})
            }
        }
    }

    Component.onCompleted: reconstruirFilas()

    Connections {
        target: controller
        function onCapaSimbolosChanged() { reconstruirFilas() }
        function onMayusculasChanged() { reconstruirFilas() }
    }

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6

        Text {
            id: display
            text: controller.texto.length ? controller.texto : " "
            font.pixelSize: 20
        }

        Column {
            id: filasContainer
            spacing: 4
        }

        Row {
            spacing: 4

            Button {
                objectName: "teclaMayusculas"
                text: "⇧"
                checkable: true
                checked: controller.mayusculas
                width: 64
                height: 48
                visible: !controller.capaSimbolos
                onClicked: controller.alternarMayusculas()
            }

            Button {
                objectName: "teclaSimbolos"
                text: controller.capaSimbolos ? "ABC" : "123"
                width: 64
                height: 48
                onClicked: controller.alternarCapaSimbolos()
            }

            Button {
                objectName: "teclaEspacio"
                text: "espacio"
                width: 160
                height: 48
                onClicked: controller.presionarCaracter(" ")
            }

            Button {
                objectName: "teclaBorrar"
                text: "⌫"
                width: 64
                height: 48
                onClicked: controller.borrar()
            }
        }

        Button {
            objectName: "botonConfirmar"
            text: "Confirmar"
            width: 200
            height: 48
            enabled: controller.texto.length > 0
            onClicked: root.confirmado(controller.texto)
        }
    }
}
