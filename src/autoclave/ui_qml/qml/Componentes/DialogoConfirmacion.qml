import QtQuick
import Tema

// PROVISIONAL (sin diseño del diseñador): diálogo de confirmación sobre la
// pantalla que lo contiene, con el estilo de PanelModal. Mensaje y dos
// botones; tocar el fondo equivale a "no confirmar". Solo confirmación: sin
// credencial ni rol (planeacion_pantalla_ciclo_en_curso.md §10).
Item {
    id: raiz
    anchors.fill: parent
    visible: false
    z: 100

    property string mensaje: ""
    property string textoConfirmar: ""
    property string textoCancelar: ""
    property color colorConfirmar: Colores.accionPrimario

    signal confirmado()
    signal descartado()

    function abrir() { visible = true }
    function cerrar() { visible = false }
    function _descartar() { cerrar(); descartado() }

    Rectangle {
        anchors.fill: parent
        color: "#99000000"
        MouseArea { anchors.fill: parent; onClicked: raiz._descartar() }
    }

    Rectangle {
        id: tarjeta
        width: parent.width - Escala.px(160)
        height: textoMensaje.implicitHeight + Escala.px(96 + 88 + 64)
        anchors.centerIn: parent
        radius: Escala.px(28)
        color: Colores.fondoTarjeta
        MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo

        Text {
            id: textoMensaje
            x: Escala.px(56); y: Escala.px(56)
            width: tarjeta.width - Escala.px(112)
            text: raiz.mensaje
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(30)
        }

        // T21 (FC-10): ningún texto se recorta ni se sale (D8-5.4). Cada botón
        // mide 340 de diseño o lo que pida su texto (ensancha el contenedor);
        // los dos juntos no pasan del ancho útil de la tarjeta (Cancelar hasta
        // la mitad, Confirmar el resto). Solo si aun así no cabe, la letra
        // baja (HorizontalFit) hasta Escala.fuenteMinima.
        readonly property real _anchoUtil: tarjeta.width - Escala.px(112) - filaBotones.spacing
        readonly property real _anchoCancelar: Math.min(Math.max(Escala.px(340), medidaCancelar.advanceWidth + Escala.px(48)),
                                                        _anchoUtil / 2)
        readonly property real _anchoConfirmar: Math.min(Math.max(Escala.px(340), medidaConfirmar.advanceWidth + Escala.px(48)),
                                                         _anchoUtil - _anchoCancelar)
        TextMetrics {
            id: medidaCancelar
            font: textoCancelarBoton.font
            text: raiz.textoCancelar
        }
        TextMetrics {
            id: medidaConfirmar
            font: textoConfirmarBoton.font
            text: raiz.textoConfirmar
        }

        Row {
            id: filaBotones
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Escala.px(48)
            spacing: Escala.px(40)

            Rectangle {
                objectName: "botonCancelarDialogo"
                width: tarjeta._anchoCancelar; height: Escala.px(88)
                radius: Escala.px(6)
                color: Colores.fondoTarjeta
                border.width: Escala.px(2); border.color: Colores.bordeCampo
                Text {
                    id: textoCancelarBoton
                    anchors.centerIn: parent
                    width: parent.width - Escala.px(32)
                    horizontalAlignment: Text.AlignHCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    text: raiz.textoCancelar
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz._descartar() }
            }
            Rectangle {
                objectName: "botonConfirmarDialogo"
                width: tarjeta._anchoConfirmar; height: Escala.px(88)
                radius: Escala.px(6)
                color: raiz.colorConfirmar
                Text {
                    id: textoConfirmarBoton
                    anchors.centerIn: parent
                    width: parent.width - Escala.px(32)
                    horizontalAlignment: Text.AlignHCenter
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    text: raiz.textoConfirmar
                    color: "white"
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                // se cierra al confirmar: el estado del envío lo muestra la pantalla
                MouseArea { anchors.fill: parent; onClicked: { raiz.cerrar(); raiz.confirmado() } }
            }
        }
    }
}
