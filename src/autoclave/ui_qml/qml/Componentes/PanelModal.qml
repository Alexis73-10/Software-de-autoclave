import QtQuick
import Tema

// PROVISIONAL (sin diseño del diseñador): panel modal sobre la pantalla que lo
// contiene. Fondo oscurecido (tocarlo cierra), tarjeta centrada con título,
// contenido y botón de cierre. Lo usan PanelNotificaciones y PanelEquipo.
Item {
    id: raiz
    anchors.fill: parent
    visible: false
    z: 100

    property string titulo: ""
    property string textoCerrar: ""
    property real altoTarjeta: Escala.px(1300)
    default property alias contenido: zona.data

    function abrir() { visible = true }
    function cerrar() { visible = false }

    Rectangle {
        anchors.fill: parent
        color: "#99000000"
        MouseArea { anchors.fill: parent; onClicked: raiz.cerrar() }
    }

    Rectangle {
        id: tarjeta
        width: parent.width - Escala.px(96)
        height: Math.min(raiz.altoTarjeta, parent.height - Escala.px(192))
        anchors.centerIn: parent
        radius: Escala.px(28)
        color: Colores.fondoTarjeta
        MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo

        Text {
            id: titulo
            x: Escala.px(48); y: Escala.px(40)
            text: raiz.titulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
        }
        Rectangle {
            id: linea
            x: Escala.px(48); y: titulo.y + titulo.height + Escala.px(20)
            width: tarjeta.width - Escala.px(96); height: Escala.px(2)
            color: "#E6E6E6"
        }

        Item {
            id: zona
            x: Escala.px(48)
            anchors.top: linea.bottom
            anchors.topMargin: Escala.px(16)
            anchors.bottom: botonCerrar.top
            anchors.bottomMargin: Escala.px(24)
            width: tarjeta.width - Escala.px(96)
            clip: true
        }

        // T21 (FC-10): 360 de diseño o lo que pida el texto, sin pasar del ancho
        // útil de la tarjeta; solo si aun así no cabe, la letra baja
        // (HorizontalFit) hasta Escala.fuenteMinima. Nunca se recorta (D8-5.4).
        TextMetrics {
            id: medidaCerrar
            font: textoCerrarBoton.font
            text: raiz.textoCerrar
        }
        Rectangle {
            id: botonCerrar
            objectName: "botonCerrarPanel"
            width: Math.min(Math.max(Escala.px(360), medidaCerrar.advanceWidth + Escala.px(48)),
                            tarjeta.width - Escala.px(96))
            height: Escala.px(88)
            radius: Escala.px(6)
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Escala.px(40)
            color: Colores.accionPrimario
            Text {
                id: textoCerrarBoton
                anchors.centerIn: parent
                width: parent.width - Escala.px(32)
                horizontalAlignment: Text.AlignHCenter
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Escala.fuenteMinima
                text: raiz.textoCerrar
                color: "white"
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
            }
            MouseArea { anchors.fill: parent; onClicked: raiz.cerrar() }
        }
    }
}
