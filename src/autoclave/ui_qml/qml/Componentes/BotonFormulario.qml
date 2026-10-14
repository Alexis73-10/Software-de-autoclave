import QtQuick
import Tema

// Botón rectangular de formulario (97 px de alto de diseño, como Cancelar y
// Guardar de NuevoUsuario.qml): primario azul con texto blanco, o secundario
// con borde. El ancho lo fija quien lo usa.
Item {
    id: raiz

    property string texto: ""
    property bool primario: false
    property bool habilitado: true
    property url icono: ""

    signal pulsado()

    height: Escala.px(97)
    opacity: habilitado ? 1 : 0.4

    Rectangle {
        anchors.fill: parent
        radius: Escala.px(8)
        color: raiz.primario ? Colores.accionPrimario : Colores.fondoTarjeta
        border.width: raiz.primario ? 0 : 1
        border.color: Colores.bordeDivisor
        opacity: zona.pressed ? 0.8 : 1
    }
    Row {
        anchors.centerIn: parent
        spacing: Escala.px(32)
        Image {
            visible: raiz.icono != ""
            anchors.verticalCenter: parent.verticalCenter
            width: Escala.px(48); height: width
            source: raiz.icono
            sourceSize.width: width
            sourceSize.height: height
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: raiz.texto
            color: raiz.primario ? "white" : Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
            font.weight: raiz.primario ? Tipografia.pesoSemiBold : Tipografia.pesoMedium
        }
    }
    MouseArea {
        id: zona
        anchors.fill: parent
        enabled: raiz.habilitado
        onClicked: raiz.pulsado()
    }
}
