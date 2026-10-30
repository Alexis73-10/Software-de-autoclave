import QtQuick
import Tema

// Opción de selección única en tarjeta (tipo de equipo, tipo de puerta, fuente
// de vapor): indicador circular, título, descripción opcional y chips de
// capacidades opcionales. La pantalla decide cuál está `seleccionada`; esta
// tarjeta solo avisa (`pulsado`). El alto crece con el contenido.
Item {
    id: raiz

    property string titulo: ""
    property string descripcion: ""
    property var chips: []             // lista de textos cortos
    property bool seleccionada: false
    property bool habilitada: true

    signal pulsado()

    implicitHeight: Escala.px(40) + columna.implicitHeight
    height: implicitHeight
    opacity: habilitada ? 1 : 0.4

    Rectangle {
        anchors.fill: parent
        radius: Escala.px(14)
        color: raiz.seleccionada ? Colores.accionFondoTenue : Colores.fondoTarjeta
        border.width: raiz.seleccionada ? Escala.px(3) : Escala.px(1)
        border.color: raiz.seleccionada ? Colores.accionPrimario : Colores.bordeCampo
    }

    // indicador de selección única
    Rectangle {
        id: aro
        x: Escala.px(28); y: Escala.px(26)
        width: Escala.px(40); height: width; radius: width / 2
        color: Colores.fondoTarjeta
        border.width: Escala.px(3)
        border.color: raiz.seleccionada ? Colores.accionPrimario : Colores.bordeCampo
        Rectangle {
            visible: raiz.seleccionada
            anchors.centerIn: parent
            width: parent.width * 0.5; height: width; radius: width / 2
            color: Colores.accionPrimario
        }
    }

    Column {
        id: columna
        x: Escala.px(96); y: Escala.px(20)
        width: parent.width - x - Escala.px(28)
        spacing: Escala.px(6)

        Text {
            width: parent.width
            text: raiz.titulo
            wrapMode: Text.Wrap
            color: raiz.seleccionada ? Colores.accionPrimarioTexto : Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(28)
            font.weight: Tipografia.pesoBold
        }
        Text {
            visible: raiz.descripcion !== ""
            width: parent.width
            text: raiz.descripcion
            wrapMode: Text.WordWrap
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(21)
        }
        Flow {
            visible: raiz.chips.length > 0
            width: parent.width
            spacing: Escala.px(10)
            topPadding: Escala.px(6)
            Repeater {
                model: raiz.chips
                delegate: Rectangle {
                    id: chip
                    required property string modelData
                    height: Escala.px(38)
                    width: etiquetaChip.implicitWidth + Escala.px(28)
                    radius: height / 2
                    color: raiz.seleccionada ? Colores.fondoTarjeta : Colores.fondoSutil
                    border.width: 1
                    border.color: Colores.bordeDivisor
                    Text {
                        id: etiquetaChip
                        anchors.centerIn: parent
                        text: chip.modelData
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(20)
                        font.weight: Tipografia.pesoMedium
                    }
                }
            }
        }
        // aire inferior
        Item { width: 1; height: Escala.px(2) }
    }

    MouseArea {
        anchors.fill: parent
        enabled: raiz.habilitada
        onClicked: raiz.pulsado()
    }
}
