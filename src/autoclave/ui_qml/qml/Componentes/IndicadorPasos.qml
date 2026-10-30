import QtQuick
import Tema

// Indicador de avance de un asistente: círculos numerados unidos por una
// línea. Hechos = azul sólido; actual = aro azul; pendientes = gris.
// `total` puede cambiar a mitad del asistente (p. ej. se omite un paso).
Item {
    id: raiz

    property int total: 1
    property int actual: 0             // índice base 0

    height: Escala.px(52)

    readonly property real _diametro: Escala.px(52)

    Rectangle {   // línea de fondo
        anchors.verticalCenter: parent.verticalCenter
        x: raiz._diametro / 2
        width: parent.width - raiz._diametro; height: Escala.px(4)
        color: Colores.bordeDivisor
    }
    Rectangle {   // tramo recorrido
        anchors.verticalCenter: parent.verticalCenter
        x: raiz._diametro / 2
        width: raiz.total > 1 ? (parent.width - raiz._diametro) * raiz.actual / (raiz.total - 1) : 0
        height: Escala.px(4)
        color: Colores.accionPrimario
        Behavior on width { NumberAnimation { duration: 200 } }
    }

    Repeater {
        model: raiz.total
        delegate: Rectangle {
            id: punto
            required property int index
            readonly property bool hecho: index < raiz.actual
            readonly property bool actual: index === raiz.actual
            width: raiz._diametro; height: width; radius: width / 2
            x: raiz.total > 1 ? index * (raiz.width - width) / (raiz.total - 1) : 0
            color: hecho ? Colores.accionPrimario : Colores.fondoTarjeta
            border.width: Escala.px(3)
            border.color: (hecho || actual) ? Colores.accionPrimario : Colores.bordeCampo
            Text {
                anchors.centerIn: parent
                text: punto.index + 1
                color: punto.hecho ? "white" : punto.actual ? Colores.accionPrimarioTexto : Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
                font.weight: Tipografia.pesoBold
            }
        }
    }
}
