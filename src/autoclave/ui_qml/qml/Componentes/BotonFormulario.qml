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
    // T21 (FC-10): sin ancho fijado por quien lo usa, el que pide su texto
    // (antes 0: el texto quedaba centrado en el borde, fuera del botón)
    implicitWidth: medidaTexto.advanceWidth + Escala.px(64)
                   + (raiz.icono != "" ? Escala.px(48 + 32) : 0)
    TextMetrics {
        id: medidaTexto
        font: textoBoton.font
        text: raiz.texto
    }
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
        id: fila
        anchors.centerIn: parent
        spacing: Escala.px(32)
        Image {
            id: iconoBoton
            visible: raiz.icono != ""
            anchors.verticalCenter: parent.verticalCenter
            width: Escala.px(48); height: width
            source: raiz.icono
            sourceSize.width: width
            sourceSize.height: height
        }
        // T21 (FC-10): el ancho lo fija quien lo usa; si el texto no cabe, la
        // letra baja (HorizontalFit) hasta Escala.fuenteMinima. Nunca se recorta.
        Text {
            id: textoBoton
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, raiz.width - Escala.px(32)
                            - (iconoBoton.visible ? iconoBoton.width + fila.spacing : 0))
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Escala.fuenteMinima
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
