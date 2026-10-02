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

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Escala.px(48)
            spacing: Escala.px(40)

            Rectangle {
                width: Escala.px(340); height: Escala.px(88)
                radius: Escala.px(6)
                color: Colores.fondoTarjeta
                border.width: Escala.px(2); border.color: Colores.bordeCampo
                Text {
                    anchors.centerIn: parent
                    text: raiz.textoCancelar
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz._descartar() }
            }
            Rectangle {
                width: Escala.px(340); height: Escala.px(88)
                radius: Escala.px(6)
                color: raiz.colorConfirmar
                Text {
                    anchors.centerIn: parent
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
