import QtQuick
import Tema

// Campo de formulario de solo presentación: etiqueta arriba, recuadro y error
// en rojo debajo. No escribe: al tocarlo avisa (`tocado`) y la pantalla abre
// el teclado en pantalla. Mismas medidas que el Campo de NuevoUsuario.qml
// (recuadro de 82 px a 43 px de la etiqueta; alto total 125 px de diseño).
Item {
    id: raiz

    property string etiqueta: ""
    property string marcador: ""
    property string valor: ""          // lo confirmado, o lo que se escribe mientras se edita
    property bool activo: false        // campo con el teclado abierto
    property string mensajeError: ""
    property bool conOjo: false
    property bool oculto: false        // true = puntos en lugar del texto
    property alias nombreObjeto: texto.objectName
    property alias nombreError: textoError.objectName

    signal tocado()
    signal ojoTocado()

    height: Escala.px(125)

    Text {
        text: raiz.etiqueta
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
        font.weight: Tipografia.pesoMedium
    }
    Rectangle {
        id: recuadro
        y: Escala.px(43)
        width: parent.width; height: Escala.px(82)
        radius: Escala.px(6)
        border.color: raiz.mensajeError !== "" ? Colores.peligroTexto
                    : raiz.activo ? Colores.accionPrimario : Colores.bordeDivisor
        border.width: raiz.activo || raiz.mensajeError !== "" ? 2 : 1

        Text {
            id: texto
            anchors.left: parent.left
            anchors.leftMargin: Escala.px(24)
            anchors.right: raiz.conOjo ? ojo.left : parent.right
            anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: raiz.valor === "" ? raiz.marcador
                : raiz.oculto ? "●".repeat(raiz.valor.length) : raiz.valor
            color: raiz.valor === "" ? Colores.textoGuia : Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
        }
        MouseArea {
            anchors.fill: parent
            onClicked: raiz.tocado()
        }
        Image {
            id: ojo
            visible: raiz.conOjo
            anchors.right: parent.right
            anchors.rightMargin: Escala.px(24)
            anchors.verticalCenter: parent.verticalCenter
            width: Escala.px(44); height: Escala.px(44)
            source: "../../assets/iconos/color/" + (raiz.oculto ? "ojo_mostrar.svg" : "ojo_ocultar.svg")
            sourceSize.width: width
            sourceSize.height: height
            MouseArea {
                anchors.fill: parent
                anchors.margins: -Escala.px(16)
                onClicked: raiz.ojoTocado()
            }
        }
    }
    Text {
        id: textoError
        anchors.top: recuadro.bottom
        anchors.topMargin: Escala.px(4)
        x: Escala.px(4)
        text: raiz.mensajeError
        visible: text !== ""
        color: Colores.peligroTexto
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(20)
    }
}
