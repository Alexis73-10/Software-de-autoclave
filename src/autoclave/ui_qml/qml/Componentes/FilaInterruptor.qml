import QtQuick
import Tema

// Fila de ajuste sí/no con interruptor a la derecha (entradas de suministro,
// sondas de temperatura). Interruptor con las medidas del de NuevoUsuario.qml.
// `bloqueado`: el valor no se puede cambiar (muestra candado), p. ej. la sonda
// de cámara 1, que controla el ciclo.
Item {
    id: raiz

    property string etiqueta: ""
    property string detalle: ""
    property bool marcado: false
    property bool bloqueado: false
    property bool ultima: false        // sin línea divisoria inferior

    signal alternado()

    height: Escala.px(88)

    Text {
        anchors.left: parent.left
        anchors.leftMargin: Escala.px(8)
        anchors.right: interruptor.left
        anchors.rightMargin: Escala.px(24)
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: raiz.detalle !== "" ? -Escala.px(11) : 0
        text: raiz.etiqueta
        elide: Text.ElideRight
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
        font.weight: Tipografia.pesoMedium
    }
    Text {
        visible: raiz.detalle !== ""
        anchors.left: parent.left
        anchors.leftMargin: Escala.px(8)
        anchors.right: interruptor.left
        anchors.rightMargin: Escala.px(24)
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: Escala.px(22)
        text: raiz.detalle
        elide: Text.ElideRight
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(21)
    }

    Image {
        visible: raiz.bloqueado
        anchors.right: interruptor.left
        anchors.rightMargin: Escala.px(20)
        anchors.verticalCenter: parent.verticalCenter
        width: Escala.px(36); height: width
        source: "../../assets/iconos/color/candado.svg"
        sourceSize.width: width
        sourceSize.height: height
    }

    Rectangle {
        id: interruptor
        anchors.right: parent.right
        anchors.rightMargin: Escala.px(8)
        anchors.verticalCenter: parent.verticalCenter
        width: Escala.px(73); height: Escala.px(39); radius: height / 2
        color: raiz.marcado ? Colores.accionPrimario : Colores.bordeCampo
        opacity: raiz.bloqueado ? 0.5 : 1
        Rectangle {
            width: parent.height - Escala.px(6); height: width; radius: width / 2
            anchors.verticalCenter: parent.verticalCenter
            x: raiz.marcado ? parent.width - width - Escala.px(3) : Escala.px(3)
            color: "white"
            Behavior on x { NumberAnimation { duration: 150 } }
        }
    }
    MouseArea {
        anchors.fill: parent
        enabled: !raiz.bloqueado
        onClicked: raiz.alternado()
    }

    Rectangle {
        visible: !raiz.ultima
        anchors.bottom: parent.bottom
        width: parent.width; height: 1
        color: Colores.bordeDivisor
    }
}
